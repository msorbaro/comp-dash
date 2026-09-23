"""Phase 3 - individual review text + date, per location. Given the place
IDs already on file from Phase 1's location census, fetches recent reviews
via Apify's compass/google-maps-reviews-scraper actor (same publisher as
compass/crawler-google-places, already integrated in voice/places.py).

Cost is bounded two ways: `reviewsStartDate` (below) stops the actor as soon
as it hits a review older than the cutoff, so cost tracks the ACTUAL review
volume in that window, not a flat cap; `MAX_REVIEWS_PER_PLACE` is a per-place
safety ceiling against one unusually high-volume location blowing the budget.

Sentiment is NOT computed here - see categorize/sentiment.py. Keeping the
(paid) scrape and the (separately paid) LLM classification pass as two
independent steps means a bug in one never forces a re-pay of the other.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from apify_client import ApifyClient

from db.connection import get_conn
from scraper.apify_client import dataset_id

ACTOR_ID = "compass/google-maps-reviews-scraper"
BATCH_SIZE = 25
# Lowered from 5 after a live run got OOM-killed - each concurrent batch
# materializes its whole review set (up to MAX_REVIEWS_PER_PLACE x 25
# places) in memory before writing, and some real batches came back with
# 5000+ reviews. Keep BATCH_SIZE unchanged, though - it's baked into
# _batch_key(), so changing it would make already-completed batches
# unrecognizable on resume and cause redundant (paid) re-scraping.
MAX_WORKERS = 3
MAX_REVIEWS_PER_PLACE = 1000


def _batch_key(place_ids: list[str]) -> str:
    """Stable across re-runs regardless of ordering - lets a killed run
    resume without re-paying for batches already fetched, same purpose as
    voice.places.location_census_runs."""
    return hashlib.sha256("|".join(sorted(place_ids)).encode()).hexdigest()


def _locations_for_state(state: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT location_id, source_place_id FROM voice.locations
                   WHERE state = %s AND source_place_id IS NOT NULL""",
                (state,),
            )
            rows = cur.fetchall()
    return [{"location_id": loc_id, "place_id": pid} for loc_id, pid in rows]


def _chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _fetch_reviews(client: ApifyClient, place_ids: list[str], start_date: str) -> list[dict]:
    run = client.actor(ACTOR_ID).call(run_input={
        "placeIds": place_ids,
        "reviewsSort": "newest",
        "reviewsStartDate": start_date,
        "maxReviews": MAX_REVIEWS_PER_PLACE,
        "language": "en",
        "reviewsOrigin": "google",
        "personalData": False,
    })
    return list(client.dataset(dataset_id(run)).iterate_items())


def _process_batch(client: ApifyClient, batch: list[dict], start_date: str) -> dict:
    """Runs entirely for one batch of ~BATCH_SIZE places: fetch -> write,
    opening its own DB connection only for the write block (the Apify call
    itself, which can run minutes, never holds a connection open)."""
    place_ids = [loc["place_id"] for loc in batch]
    by_place_id = {loc["place_id"]: loc["location_id"] for loc in batch}
    items = _fetch_reviews(client, place_ids, start_date)

    n_written, n_unmatched = 0, 0
    with get_conn() as conn:
        with conn:
            with conn.cursor() as cur:
                for item in items:
                    place_id = item.get("placeId")
                    location_id = by_place_id.get(place_id)
                    review_id = item.get("reviewId")
                    if not location_id or not review_id:
                        n_unmatched += 1
                        continue
                    cur.execute(
                        """INSERT INTO voice.reviews
                               (location_id, source, source_review_id, rating, review_date, text, language)
                           VALUES (%(location_id)s, 'google_maps', %(review_id)s, %(rating)s,
                                   %(review_date)s, %(text)s, %(language)s)
                           ON CONFLICT (source, source_review_id) DO UPDATE
                               SET rating = EXCLUDED.rating, review_date = EXCLUDED.review_date,
                                   text = EXCLUDED.text""",
                        {
                            "location_id": location_id, "review_id": review_id,
                            "rating": item.get("stars"), "review_date": item.get("publishedAtDate"),
                            "text": item.get("text"), "language": item.get("originalLanguage"),
                        },
                    )
                    n_written += 1
                cur.execute(
                    """INSERT INTO voice.review_scrape_runs (batch_key, n_places, n_reviews)
                       VALUES (%s, %s, %s) ON CONFLICT (batch_key) DO NOTHING""",
                    (_batch_key(place_ids), len(batch), n_written),
                )

    return {"n_places": len(batch), "n_written": n_written, "n_unmatched": n_unmatched}


def run(state: str, years_back: int = 2, limit: int | None = None) -> dict:
    """Returns a summary dict: locations processed, reviews written, batches
    skipped (already done in a prior run), and any batch-level failures.
    Skips any batch already recorded in voice.review_scrape_runs. `limit`
    caps how many locations are processed - for a cheap validation run
    before releasing this on a whole state."""
    locations = _locations_for_state(state)
    if limit:
        locations = locations[:limit]
    if not locations:
        return {"n_locations": 0, "n_reviews_written": 0, "batches_skipped": 0, "failed_batches": []}

    start_date = (dt.date.today() - dt.timedelta(days=365 * years_back)).isoformat()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT batch_key FROM voice.review_scrape_runs")
            already_done = {row[0] for row in cur.fetchall()}

    all_batches = _chunk(locations, BATCH_SIZE)
    tasks = [b for b in all_batches if _batch_key([loc["place_id"] for loc in b]) not in already_done]
    skipped = len(all_batches) - len(tasks)
    if skipped:
        print(f"Skipping {skipped} already-completed batch(es) from a prior run.", flush=True)

    client = ApifyClient(os.environ["APIFY_TOKEN"])
    n_reviews_written = 0
    failed_batches = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_process_batch, client, batch, start_date): batch for batch in tasks}
        for future in as_completed(futures):
            batch = futures[future]
            done += 1
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - one bad batch shouldn't abort the whole run
                print(f"[{done}/{len(tasks)}] batch of {len(batch)} places FAILED: {exc}", flush=True)
                failed_batches.append([loc["place_id"] for loc in batch])
                continue
            n_reviews_written += result["n_written"]
            print(
                f"[{done}/{len(tasks)}] batch of {result['n_places']} places: "
                f"{result['n_written']} reviews written"
                + (f", {result['n_unmatched']} unmatched" if result["n_unmatched"] else ""),
                flush=True,
            )

    return {
        "n_locations": len(locations), "n_reviews_written": n_reviews_written,
        "batches_skipped": skipped, "failed_batches": failed_batches,
    }
