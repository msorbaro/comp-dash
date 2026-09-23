"""Yelp aggregate rating per location (Mavis banners + competitors) - writes
into the SAME voice.rating_snapshots table the Google census already uses
(that table's `source` column exists for exactly this - up to now it's only
ever been 'google_maps'), so no new rating storage is needed, just a new
source value.

Yelp has no place ID we can seed from the way voice/places.py seeds off
Google's compass/crawler-google-places - so this searches by brand name +
city instead of crawling by ID. Matching is conservative, same spirit as
voice/places.py's alias/dedupe hazards: a Yelp result only gets attached to
one of our known locations if its name confidently matches a brand alias,
and - when more than one of our locations share that brand + city - its
street address also lines up. Anything that doesn't clear that bar is left
unmatched and reported, never guessed.
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from apify_client import ApifyClient

from db.connection import get_conn
from scraper.apify_client import dataset_id

ACTOR_ID = "rigelbytes/yelp-scraper"
MAX_WORKERS = 5


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def _normalize_street(s: str) -> str:
    """Loose compare, not exact - drops suite/unit noise ("123 Main St Ste
    4" vs "123 Main St") since that's where a Yelp listing and our own
    address text most often diverge even for the same real store."""
    n = _normalize(s)
    for sep in (" ste", " suite", " unit", " #"):
        n = n.split(sep)[0]
    return n.strip()


def _match_alias(title: str, aliases: list) -> bool:
    norm_title = _normalize(title)
    return any(_normalize(a) and norm_title.startswith(_normalize(a)) for a in aliases)


def _locations_by_brand_city(state: str) -> dict:
    """{(brand_id, brand_name, aliases, city): [{location_id, street}, ...]}"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT vl.location_id, vl.city, vl.street, vb.brand_id, vb.name, vb.aliases
                   FROM voice.locations vl JOIN voice.brands vb ON vb.brand_id = vl.brand_id
                   WHERE vl.state = %s AND vl.city IS NOT NULL""",
                (state,),
            )
            rows = cur.fetchall()
    groups = {}
    for location_id, city, street, brand_id, name, aliases in rows:
        key = (brand_id, name, tuple(aliases), city)
        groups.setdefault(key, []).append({"location_id": location_id, "street": street})
    return groups


def _search_yelp(client: ApifyClient, brand_name: str, city: str, state: str) -> list:
    run = client.actor(ACTOR_ID).call(run_input={
        "searchQueries": [f"{brand_name} in {city}, {state}"],
        "countryCode": "US",
        # Required in practice, not just "recommended" - every call failed
        # with a bare "request failed" until this was added. Yelp runs
        # DataDome bot protection; residential proxies are what the
        # actor's own docs say get past it.
        "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
    })
    return list(client.dataset(dataset_id(run)).iterate_items())


def _process_group(client: ApifyClient, key: tuple, candidates: list, state: str) -> dict:
    brand_id, brand_name, aliases, city = key
    items = _search_yelp(client, brand_name, city, state)
    matched_items = [i for i in items if _match_alias(i.get("name") or "", list(aliases))]

    n_written = 0
    unmatched_location_ids = []
    with get_conn() as conn:
        with conn:
            with conn.cursor() as cur:
                if len(candidates) == 1 and matched_items:
                    item = matched_items[0]
                    cur.execute(
                        """INSERT INTO voice.rating_snapshots (location_id, source, avg_rating, review_count)
                           VALUES (%s, 'yelp', %s, %s)""",
                        (candidates[0]["location_id"], item.get("rating"), item.get("reviewCount")),
                    )
                    n_written += 1
                elif len(candidates) == 1:
                    unmatched_location_ids.append(candidates[0]["location_id"])
                else:
                    used = set()
                    for cand in candidates:
                        cand_street = _normalize_street(cand["street"])
                        best_idx = None
                        for idx, item in enumerate(matched_items):
                            if idx in used or not cand_street:
                                continue
                            item_street = _normalize_street(item.get("address") or "")
                            if item_street and (cand_street in item_street or item_street in cand_street):
                                best_idx = idx
                                break
                        if best_idx is not None:
                            used.add(best_idx)
                            item = matched_items[best_idx]
                            cur.execute(
                                """INSERT INTO voice.rating_snapshots (location_id, source, avg_rating, review_count)
                                   VALUES (%s, 'yelp', %s, %s)""",
                                (cand["location_id"], item.get("rating"), item.get("reviewCount")),
                            )
                            n_written += 1
                        else:
                            unmatched_location_ids.append(cand["location_id"])
                cur.execute(
                    """INSERT INTO voice.yelp_rating_runs (brand_id, city, state)
                       VALUES (%s, %s, %s) ON CONFLICT (brand_id, city, state) DO NOTHING""",
                    (brand_id, city, state),
                )

    return {
        "brand_name": brand_name, "city": city, "n_candidates": len(candidates),
        "n_written": n_written, "n_yelp_results": len(items),
        "unmatched_location_ids": unmatched_location_ids,
    }


def run(state: str, limit: int | None = None) -> dict:
    """Returns a summary: groups processed, snapshots written, groups
    skipped (already done in a prior run), and every location that couldn't
    be confidently matched (for manual review, per the same "report
    unmatched, never guess" rule voice/places.py already follows). `limit`
    caps how many (brand, city) groups are processed - for a cheap
    validation run before releasing this on a whole state."""
    groups = _locations_by_brand_city(state)
    if limit:
        groups = dict(list(groups.items())[:limit])
    if not groups:
        return {"n_groups": 0, "n_written": 0, "groups_skipped": 0, "unmatched_location_ids": []}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT brand_id, city, state FROM voice.yelp_rating_runs WHERE state = %s", (state,))
            already_done = {(bid, city) for bid, city, _st in cur.fetchall()}

    tasks = {k: v for k, v in groups.items() if (k[0], k[3]) not in already_done}
    skipped = len(groups) - len(tasks)
    if skipped:
        print(f"Skipping {skipped} already-completed (brand, city) group(s) from a prior run.", flush=True)

    client = ApifyClient(os.environ["APIFY_TOKEN"])
    n_written = 0
    unmatched_location_ids = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_process_group, client, key, candidates, state): key for key, candidates in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            done += 1
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - one bad group shouldn't abort the whole run
                print(f"[{done}/{len(tasks)}] {key[1]} / {key[3]} FAILED: {exc}", flush=True)
                continue
            n_written += result["n_written"]
            unmatched_location_ids.extend(result["unmatched_location_ids"])
            print(
                f"[{done}/{len(tasks)}] {result['brand_name']} / {result['city']}: "
                f"{result['n_written']}/{result['n_candidates']} matched "
                f"({result['n_yelp_results']} Yelp results)",
                flush=True,
            )

    return {
        "n_groups": len(groups), "n_written": n_written,
        "groups_skipped": skipped, "unmatched_location_ids": unmatched_location_ids,
    }
