"""Apple Maps aggregate rating per location (Mavis banners + competitors) -
writes into the SAME voice.rating_snapshots table the Google census and
voice/yelp_ratings.py already use (source='apple_maps'), no new schema.

Same search-by-name+city approach and matching hazards as
voice/yelp_ratings.py (Apple Maps has no place ID we can seed from either)
- see that module's docstring for the matching rationale. Confirmed live
that this actor's region search can also surface neighboring-town results
(e.g. a "San Antonio, TX" query returning a Live Oak, TX location) - that's
fine here since matching is still gated on our own per-location city
grouping, not on the search query's nominal city.
"""
from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from apify_client import ApifyClient

from db.connection import get_conn
from scraper.apify_client import dataset_id

ACTOR_ID = "karamelo/apple-maps-scraper"
MAX_WORKERS = 5
MAX_RESULTS_PER_QUERY = 20


def _clean_rating(value) -> float | None:
    """A live run hit "numeric field overflow" against rating_snapshots'
    NUMERIC(3,2) avg_rating column (max 9.99) across 116 groups spanning 8
    different brands - not one bad listing, some real fraction of Apple
    Maps results return a rating value that isn't on the normal 0-5 scale.
    Never trust it blindly; drop anything outside a plausible star rating
    range rather than let one bad value fail the whole group's insert."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f < 0 or f > 5:
        return None
    return round(f, 2)


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def _normalize_street(s: str) -> str:
    n = _normalize(s)
    for sep in (" ste", " suite", " unit", " #"):
        n = n.split(sep)[0]
    return n.strip()


def _match_alias(title: str, aliases: list) -> bool:
    norm_title = _normalize(title)
    return any(_normalize(a) and norm_title.startswith(_normalize(a)) for a in aliases)


def _locations_by_brand_city(state: str) -> dict:
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


def _search_apple_maps(client: ApifyClient, brand_name: str, city: str, state: str) -> list:
    run = client.actor(ACTOR_ID).call(run_input={
        "searchQueries": [{"query": brand_name, "location": f"{city}, {state}", "maxResults": MAX_RESULTS_PER_QUERY}],
        "proxyConfiguration": {"useApifyProxy": True},
    })
    return list(client.dataset(dataset_id(run)).iterate_items())


def _process_group(client: ApifyClient, key: tuple, candidates: list, state: str) -> dict:
    brand_id, brand_name, aliases, city = key
    items = _search_apple_maps(client, brand_name, city, state)
    matched_items = [i for i in items if _match_alias(i.get("name") or "", list(aliases))]

    n_written = 0
    unmatched_location_ids = []
    with get_conn() as conn:
        with conn:
            with conn.cursor() as cur:
                if len(candidates) == 1 and matched_items:
                    # Prefer a same-city match if several came back (the
                    # region search can surface neighboring towns too);
                    # fall back to the first confident name match.
                    same_city = [i for i in matched_items if _normalize(city) in _normalize(i.get("address") or "")]
                    item = (same_city or matched_items)[0]
                    cur.execute(
                        """INSERT INTO voice.rating_snapshots (location_id, source, avg_rating, review_count)
                           VALUES (%s, 'apple_maps', %s, %s)""",
                        (candidates[0]["location_id"], _clean_rating(item.get("rating")), item.get("reviewCount")),
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
                                   VALUES (%s, 'apple_maps', %s, %s)""",
                                (cand["location_id"], _clean_rating(item.get("rating")), item.get("reviewCount")),
                            )
                            n_written += 1
                        else:
                            unmatched_location_ids.append(cand["location_id"])
                cur.execute(
                    """INSERT INTO voice.apple_maps_rating_runs (brand_id, city, state)
                       VALUES (%s, %s, %s) ON CONFLICT (brand_id, city, state) DO NOTHING""",
                    (brand_id, city, state),
                )

    return {
        "brand_name": brand_name, "city": city, "n_candidates": len(candidates),
        "n_written": n_written, "n_apple_maps_results": len(items),
        "unmatched_location_ids": unmatched_location_ids,
    }


def run(state: str, limit: int | None = None) -> dict:
    groups = _locations_by_brand_city(state)
    if limit:
        groups = dict(list(groups.items())[:limit])
    if not groups:
        return {"n_groups": 0, "n_written": 0, "groups_skipped": 0, "unmatched_location_ids": []}

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT brand_id, city, state FROM voice.apple_maps_rating_runs WHERE state = %s", (state,))
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
                f"({result['n_apple_maps_results']} Apple Maps results)",
                flush=True,
            )

    return {
        "n_groups": len(groups), "n_written": n_written,
        "groups_skipped": skipped, "unmatched_location_ids": unmatched_location_ids,
    }
