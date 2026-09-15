"""Phase 2 - ratings census. Writes voice.rating_snapshots from the
rating_rows voice.places.run() already collected off the SAME
compass/crawler-google-places response used for Phase 1 - confirmed live
(2026-09-15) that the actor returns totalScore/reviewsCount directly on
every place, so this makes no Apify call of its own.

Append-only: never updates an existing snapshot, always inserts a new row,
so rating movement over time is trendable rather than only ever showing
"now". A None avg_rating/review_count (a location with literally no reviews
yet) is written as NULL, not skipped or estimated - never fabricate.
"""
from db.connection import get_conn


def write_snapshots(rating_rows: list) -> dict:
    """rating_rows: [(location_id, avg_rating, review_count), ...] as
    collected by voice/places.py. Returns {"written": n, "null_rating": n}."""
    conn = get_conn()
    written, null_rating = 0, 0
    with conn:
        with conn.cursor() as cur:
            for location_id, avg_rating, review_count in rating_rows:
                if avg_rating is None:
                    null_rating += 1
                cur.execute(
                    """INSERT INTO voice.rating_snapshots (location_id, source, avg_rating, review_count)
                       VALUES (%s, 'google_maps', %s, %s)""",
                    (location_id, avg_rating, review_count),
                )
                written += 1
    return {"written": written, "null_rating": null_rating}
