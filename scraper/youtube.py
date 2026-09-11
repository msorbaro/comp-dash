"""YouTube video tracker. Pulls each competitor's recent YouTube videos (and
Shorts) via Apify's YouTube Scraper (streamers/youtube-scraper, the detailed
per-video variant with likes/comments/full description), stores metrics/
thumbnail permanently, and classifies content type via the shared taxonomy.
"""
from __future__ import annotations

import json
import os

from apify_client import ApifyClient

from categorize.classify import classify_caption
from db.connection import get_conn
from scraper.media import fetch_thumbnail

ACTOR_ID = "streamers/youtube-scraper"


def _run_actor(channel_urls: list, max_results: int, max_shorts: int) -> list:
    if not channel_urls:
        return []
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    start_urls = []
    for url in channel_urls:
        base = url.rstrip("/")
        start_urls.append({"url": f"{base}/videos"})
        if max_shorts:
            start_urls.append({"url": f"{base}/shorts"})
    run = client.actor(ACTOR_ID).call(run_input={
        "startUrls": start_urls,
        "maxResults": max_results,
        "maxResultsShorts": max_shorts,
        "maxResultStreams": 0,
    })
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def capture_youtube(run_type: str = "weekly", max_results: int = 15, max_shorts: int = 15,
                     only_own_brand: bool = False) -> dict:
    conn = get_conn()
    stats = {"competitors_scraped": 0, "videos_added": 0, "videos_skipped_duplicate": 0, "errors": []}

    query = "SELECT id, youtube_url FROM competitors WHERE is_active = TRUE AND youtube_url IS NOT NULL"
    if only_own_brand:
        query += " AND is_own_brand = TRUE"
    with conn.cursor() as cur:
        cur.execute(query)
        competitors = cur.fetchall()
    conn.commit()
    stats["competitors_scraped"] = len(competitors)
    # Successful items don't echo back the input URL - only `channelUsername`
    # (the @handle, no @) - so match on that instead of the channel URL.
    by_handle = {url.rstrip("/").split("@")[-1].lower(): cid for cid, url in competitors}

    try:
        raw_items = _run_actor([url for _, url in competitors], max_results, max_shorts)
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append({"scope": "actor_run", "error": str(exc)})
        raw_items = []

    for item in raw_items:
        username = (item.get("channelUsername") or "").lower()
        competitor_id = by_handle.get(username)
        video_id = item.get("id")
        if not competitor_id or not video_id:
            continue

        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM youtube_videos WHERE youtube_video_id = %s", (str(video_id),))
            if cur.fetchone():
                stats["videos_skipped_duplicate"] += 1
                conn.commit()
                continue

        caption = item.get("text")
        category, confidence = classify_caption(caption or item.get("title"), "YouTube video")
        thumbnail = fetch_thumbnail(item.get("thumbnailUrl"))

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO youtube_videos (competitor_id, youtube_video_id, video_url, title,
                                                caption, posted_at, duration, video_type, thumbnail,
                                                view_count, like_count, comment_count, category,
                                                category_confidence)
                   VALUES (%(competitor_id)s, %(video_id)s, %(video_url)s, %(title)s, %(caption)s,
                           %(posted_at)s, %(duration)s, %(video_type)s, %(thumbnail)s, %(view_count)s,
                           %(like_count)s, %(comment_count)s, %(category)s, %(confidence)s)
                   ON CONFLICT (youtube_video_id) DO NOTHING""",
                {
                    "competitor_id": competitor_id,
                    "video_id": str(video_id),
                    "video_url": item.get("url"),
                    "title": item.get("title"),
                    "caption": caption,
                    "posted_at": item.get("date"),
                    "duration": item.get("duration"),
                    "video_type": item.get("type") if item.get("type") in ("video", "shorts") else "video",
                    "thumbnail": thumbnail,
                    "view_count": item.get("viewCount"),
                    "like_count": item.get("likes"),
                    "comment_count": item.get("commentsCount"),
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
               VALUES ('youtube', %s, %s, %s, %s, %s, %s)""",
            (run_type, stats["competitors_scraped"], stats["videos_added"],
             stats["videos_skipped_duplicate"], json.dumps(stats["errors"]), status),
        )
    conn.commit()

    stats["status"] = status
    return stats
