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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from apify_client import ApifyClient

from db.connection import get_conn
from scraper.apify_client import dataset_id

ACTOR_ID = "karamelo/apple-maps-scraper"
MAX_WORKERS = 5
MAX_RESULTS_PER_QUERY = 20

MAX_SEARCH_ATTEMPTS = 3
# This actor exits with Status: SUCCEEDED even when its proxy session never
# initialized and it therefore scraped nothing - confirmed live, 828 of 1902
# runs in a single batch failed this way ("Failed to initialize session:
# Client network socket disconnected", "Proxy responded with 590
# UPSTREAM502") while every one of them still reported success. An empty
# dataset on its own cannot distinguish "Apple has no such listing" from
# "the scrape never ran", and treating the second as the first is what put
# ~840 (brand, city) groups into voice.apple_maps_rating_runs as completed
# when they had never actually been searched - permanently, since a
# completed group is skipped on every later run.
_FAILURE_MARKERS = ("Failed to initialize session", "Fatal scraper error")


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


def _scrape_failed(client: ApifyClient, run: dict) -> bool:
    """Whether an empty result came from the actor failing rather than from
    Apple genuinely having no match - read off the run's own log, since the
    run status is SUCCEEDED either way (see _FAILURE_MARKERS above)."""
    try:
        log_text = client.run(run["id"]).log().get() or ""
    except Exception:  # noqa: BLE001 - best-effort; never fail a group over the log fetch
        return False
    return any(marker in log_text for marker in _FAILURE_MARKERS)


def _search_apple_maps(client: ApifyClient, brand_name: str, city: str, state: str) -> tuple:
    """Returns (items, failed). `failed` is True only when every attempt hit
    an actor-level failure, and it must keep the caller from recording this
    group as completed - a group marked done is never retried, so swallowing
    a transient proxy failure here loses that group's ratings permanently."""
    for attempt in range(MAX_SEARCH_ATTEMPTS):
        run = client.actor(ACTOR_ID).call(run_input={
            "searchQueries": [{"query": brand_name, "location": f"{city}, {state}", "maxResults": MAX_RESULTS_PER_QUERY}],
            "proxyConfiguration": {"useApifyProxy": True},
        })
        items = list(client.dataset(dataset_id(run)).iterate_items())
        if items:
            return items, False
        if not _scrape_failed(client, run):
            return [], False  # a real "Apple Maps has nothing here"
        if attempt < MAX_SEARCH_ATTEMPTS - 1:
            time.sleep(2 * (attempt + 1))
    return [], True


def _process_group(client: ApifyClient, key: tuple, candidates: list, state: str) -> dict:
    brand_id, brand_name, aliases, city = key
    items, scrape_failed = _search_apple_maps(client, brand_name, city, state)
    if scrape_failed:
        # Deliberately NOT writing the apple_maps_rating_runs marker, so this
        # group stays eligible for a retry on the next run instead of being
        # recorded as a confirmed no-match it never actually was.
        return {
            "brand_name": brand_name, "city": city, "n_candidates": len(candidates),
            "n_written": 0, "n_apple_maps_results": 0, "unmatched_location_ids": [],
            "scrape_failed": True,
        }
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
        "scrape_failed": False,
    }


def run(state: str, limit: int | None = None) -> dict:
    groups = _locations_by_brand_city(state)
    if limit:
        groups = dict(list(groups.items())[:limit])
    if not groups:
        return {"n_groups": 0, "n_written": 0, "groups_skipped": 0,
                "unmatched_location_ids": [], "n_scrape_failed": 0}

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
    n_scrape_failed = 0
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
            if result.get("scrape_failed"):
                n_scrape_failed += 1
                print(
                    f"[{done}/{len(tasks)}] {result['brand_name']} / {result['city']}: "
                    f"SCRAPE FAILED after {MAX_SEARCH_ATTEMPTS} attempts - left unrecorded for retry",
                    flush=True,
                )
                continue
            print(
                f"[{done}/{len(tasks)}] {result['brand_name']} / {result['city']}: "
                f"{result['n_written']}/{result['n_candidates']} matched "
                f"({result['n_apple_maps_results']} Apple Maps results)",
                flush=True,
            )

    if n_scrape_failed:
        print(
            f"\n{state}: {n_scrape_failed} group(s) could not be scraped (actor/proxy failures). "
            f"They were NOT recorded as done - re-run this state to retry them.",
            flush=True,
        )

    return {
        "n_groups": len(groups), "n_written": n_written,
        "groups_skipped": skipped, "unmatched_location_ids": unmatched_location_ids,
        "n_scrape_failed": n_scrape_failed,
    }
