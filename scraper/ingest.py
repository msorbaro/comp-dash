"""Fetches new posts for every active competitor and upserts them into the
database. Dedupes on `instagram_post_id`, so re-running is always safe.
"""
import json
import os

from db.connection import get_conn
from scraper.apify_client import fetch_posts, normalize_post
from scraper.media import fetch_thumbnail


def _insert_posts(conn, raw_items: list, run_type: str, by_handle: dict,
                   commit_every: int = 25) -> dict:
    """Normalizes + inserts raw Apify items already in hand, downloading each
    post's thumbnail while its signed Instagram URL is still fresh. Split out
    from ingest_new_posts so a completed Apify run's dataset can be re-applied
    to the DB without paying for another scrape (see recover_run below).

    Commits every `commit_every` posts so a crash partway through a large
    batch (each thumbnail download + API call already has real cost/time
    sunk into it) doesn't lose everything already processed.
    """
    stats = {"posts_added": 0, "posts_skipped_duplicate": 0}

    for raw in raw_items:
        post = normalize_post(raw)
        if not post:
            continue

        match = by_handle.get(post["owner_username"])
        if not match:
            continue  # post from an account not in our competitor list (shouldn't happen)
        competitor_id, _ = match

        # No age cutoff here: `results_limit` (backfill_max_posts) already bounds
        # how many posts we fetch and pay for per profile, so an additional age
        # filter only throws away already-fetched data - and for a low-frequency
        # or previously-dormant account, that meant its real recent history
        # (e.g. a burst of activity 4-5 months ago) was silently discarded and
        # never recovered by later weekly runs, which only look at each
        # profile's *newest* posts rather than digging back through time.

        thumbnail = fetch_thumbnail(post["media_url"])

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO posts (competitor_id, instagram_post_id, post_url, post_type,
                                    posted_at, caption, media_url, thumbnail, like_count,
                                    comment_count, view_count)
                VALUES (%(competitor_id)s, %(instagram_post_id)s, %(post_url)s, %(post_type)s,
                        %(posted_at)s, %(caption)s, %(media_url)s, %(thumbnail)s, %(like_count)s,
                        %(comment_count)s, %(view_count)s)
                ON CONFLICT (instagram_post_id) DO NOTHING
                """,
                {**post, "competitor_id": competitor_id, "thumbnail": thumbnail},
            )
            added = cur.rowcount > 0

        if added:
            stats["posts_added"] += 1
        else:
            stats["posts_skipped_duplicate"] += 1

        if (stats["posts_added"] + stats["posts_skipped_duplicate"]) % commit_every == 0:
            conn.commit()

    conn.commit()
    return stats


def _get_active_competitors(conn, only_own_brand: bool = False):
    query = "SELECT id, instagram_handle, instagram_url FROM competitors WHERE is_active = TRUE"
    if only_own_brand:
        query += " AND is_own_brand = TRUE"
    with conn.cursor() as cur:
        cur.execute(query)
        competitors = cur.fetchall()
    by_handle = {handle.lower(): (comp_id, url) for comp_id, handle, url in competitors}
    return competitors, by_handle


def _log_run(conn, run_type: str, competitors_scraped: int, stats: dict, errors: list) -> str:
    status = "failed" if errors and stats["posts_added"] == 0 else ("partial" if errors else "success")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scrape_runs (run_type, competitors_scraped, posts_added,
                                      posts_skipped_duplicate, errors, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (run_type, competitors_scraped, stats["posts_added"], stats["posts_skipped_duplicate"],
             json.dumps(errors), status),
        )
    return status


def ingest_new_posts(run_type: str = "weekly", only_own_brand: bool = False) -> dict:
    max_per_run = int(os.environ.get("MAX_POSTS_PER_RUN", "20"))
    backfill_max_posts = int(os.environ.get("BACKFILL_MAX_POSTS", "40"))
    results_limit = max_per_run if run_type == "weekly" else backfill_max_posts

    conn = get_conn()
    errors = []

    with conn:
        competitors, by_handle = _get_active_competitors(conn, only_own_brand)
        profile_urls = [url for _, _, url in competitors]
        conn.commit()  # release the read lock before the (potentially long) external actor call

        try:
            raw_items = fetch_posts(profile_urls, results_limit)
        except Exception as exc:  # noqa: BLE001 - surface any scrape failure, don't crash the run
            errors.append({"scope": "actor_run", "error": str(exc)})
            raw_items = []

        stats = _insert_posts(conn, raw_items, run_type, by_handle)
        status = _log_run(conn, run_type, len(competitors), stats, errors)

    stats["competitors_scraped"] = len(competitors)
    stats["errors"] = errors
    stats["status"] = status
    return stats


def backfill_thumbnails(commit_every: int = 25) -> dict:
    """One-off/rerunnable: fetches thumbnails for existing posts that don't
    have one yet (e.g. posts inserted before the `thumbnail` column existed).
    Uses each post's already-stored `media_url` - only works while that
    signed URL is still valid, so run this soon after the posts were scraped.
    """
    conn = get_conn()
    stats = {"fetched": 0, "failed": 0}

    with conn.cursor() as cur:
        cur.execute("SELECT id, media_url FROM posts WHERE thumbnail IS NULL AND media_url IS NOT NULL")
        pending = cur.fetchall()

    for post_id, media_url in pending:
        thumbnail = fetch_thumbnail(media_url)
        with conn.cursor() as cur:
            cur.execute("UPDATE posts SET thumbnail = %s WHERE id = %s", (thumbnail, post_id))
        if thumbnail:
            stats["fetched"] += 1
        else:
            stats["failed"] += 1
        if (stats["fetched"] + stats["failed"]) % commit_every == 0:
            conn.commit()

    conn.commit()
    return stats


def recover_run(apify_run_id: str, run_type: str = "backfill") -> dict:
    """Re-applies an already-completed Apify run's dataset to the DB, without
    triggering a new (paid) scrape. Useful if the DB insert step failed after
    a successful scrape.
    """
    from scraper.apify_client import ApifyClient, dataset_id  # local import, optional dep path

    conn = get_conn()

    with conn:
        competitors, by_handle = _get_active_competitors(conn)

        client = ApifyClient(os.environ["APIFY_TOKEN"])
        run = client.run(apify_run_id).get()
        raw_items = list(client.dataset(dataset_id(run)).iterate_items())

        stats = _insert_posts(conn, raw_items, run_type, by_handle)
        status = _log_run(conn, run_type, len(competitors), stats, [])

    stats["competitors_scraped"] = len(competitors)
    stats["errors"] = []
    stats["status"] = status
    return stats
