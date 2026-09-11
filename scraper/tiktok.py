"""TikTok video tracker. Pulls each competitor's recent TikTok videos via
Apify's TikTok Scraper (clockworks/tiktok-scraper), stores caption/metrics/
thumbnail permanently, and classifies content type via the shared taxonomy.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from apify_client import ApifyClient

from categorize.classify import classify_caption
from db.connection import get_conn
from scraper.media import fetch_thumbnail

ACTOR_ID = "clockworks/tiktok-scraper"


def _run_actor(usernames: list, results_per_page: int) -> list:
    if not usernames:
        return []
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR_ID).call(run_input={
        "profiles": usernames,
        "resultsPerPage": results_per_page,
        "profileScrapeSections": ["videos"],
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
    })
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def capture_tiktok(run_type: str = "weekly", results_per_page: int = 20) -> dict:
    conn = get_conn()
    stats = {"competitors_scraped": 0, "videos_added": 0, "videos_skipped_duplicate": 0, "errors": []}

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, tiktok_handle FROM competitors WHERE is_active = TRUE AND tiktok_handle IS NOT NULL"
        )
        competitors = cur.fetchall()
    conn.commit()
    stats["competitors_scraped"] = len(competitors)
    by_handle = {handle.lower(): cid for cid, handle in competitors}

    try:
        raw_items = _run_actor([h for _, h in competitors], results_per_page)
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append({"scope": "actor_run", "error": str(exc)})
        raw_items = []

    for item in raw_items:
        username = ((item.get("authorMeta") or {}).get("name") or "").lower()
        competitor_id = by_handle.get(username)
        video_id = item.get("id")
        if not competitor_id or not video_id:
            continue

        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM tiktok_videos WHERE tiktok_video_id = %s", (str(video_id),))
            if cur.fetchone():
                stats["videos_skipped_duplicate"] += 1
                conn.commit()
                continue

        caption = item.get("text")
        category, confidence = classify_caption(caption, "TikTok video")
        video_meta = item.get("videoMeta") or {}
        thumbnail = fetch_thumbnail(video_meta.get("coverUrl"))

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO tiktok_videos (competitor_id, tiktok_video_id, video_url, caption,
                                               posted_at, duration_seconds, thumbnail, view_count,
                                               like_count, comment_count, share_count, category,
                                               category_confidence)
                   VALUES (%(competitor_id)s, %(video_id)s, %(video_url)s, %(caption)s, %(posted_at)s,
                           %(duration)s, %(thumbnail)s, %(view_count)s, %(like_count)s,
                           %(comment_count)s, %(share_count)s, %(category)s, %(confidence)s)
                   ON CONFLICT (tiktok_video_id) DO NOTHING""",
                {
                    "competitor_id": competitor_id,
                    "video_id": str(video_id),
                    "video_url": item.get("webVideoUrl"),
                    "caption": caption,
                    "posted_at": item.get("createTimeISO"),
                    "duration": video_meta.get("duration"),
                    "thumbnail": thumbnail,
                    "view_count": item.get("playCount"),
                    "like_count": item.get("diggCount"),
                    "comment_count": item.get("commentCount"),
                    "share_count": item.get("shareCount"),
                    "category": category,
                    "confidence": confidence,
                },
            )
        stats["videos_added"] += 1
        conn.commit()

    status = "failed" if stats["errors"] and stats["videos_added"] == 0 else (
        "partial" if stats["errors"] else "success"
    )
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scrape_runs (source, run_type, competitors_scraped, posts_added,
                                         posts_skipped_duplicate, errors, status)
               VALUES ('tiktok', %s, %s, %s, %s, %s, %s)""",
            (run_type, stats["competitors_scraped"], stats["videos_added"],
             stats["videos_skipped_duplicate"], json.dumps(stats["errors"]), status),
        )
    conn.commit()

    stats["status"] = status
    return stats
