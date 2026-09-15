"""X (Twitter) tracker. Pulls each competitor's recent posts via Apify's
Tweet Scraper (apidojo/tweet-scraper), stores text/engagement metrics, and
classifies content type via the shared taxonomy.
"""
from __future__ import annotations

import json
import os

from apify_client import ApifyClient

from categorize.classify import classify_caption, classify_funnel_stage, classify_message_attribute
from db.connection import get_conn
from scraper.apify_client import dataset_id

ACTOR_ID = "apidojo/tweet-scraper"


def _run_actor(handles: list, max_items_per_handle: int) -> list:
    if not handles:
        return []
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR_ID).call(run_input={
        "twitterHandles": handles,
        "maxItems": max_items_per_handle * len(handles),
        "sort": "Latest",
    })
    return list(client.dataset(dataset_id(run)).iterate_items())


def capture_x(run_type: str = "weekly", max_items_per_handle: int = 20, only_own_brand: bool = False) -> dict:
    conn = get_conn()
    stats = {"competitors_scraped": 0, "posts_added": 0, "posts_skipped_duplicate": 0, "errors": []}

    query = "SELECT id, x_handle FROM competitors WHERE is_active = TRUE AND x_handle IS NOT NULL"
    if only_own_brand:
        query += " AND is_own_brand = TRUE"
    with conn.cursor() as cur:
        cur.execute(query)
        competitors = cur.fetchall()
    conn.commit()
    stats["competitors_scraped"] = len(competitors)
    by_handle = {handle.lower(): cid for cid, handle in competitors}

    try:
        raw_items = _run_actor([h for _, h in competitors], max_items_per_handle)
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append({"scope": "actor_run", "error": str(exc)})
        raw_items = []

    for item in raw_items:
        username = ((item.get("author") or {}).get("userName") or "").lower()
        competitor_id = by_handle.get(username)
        tweet_id = item.get("id")
        if not competitor_id or not tweet_id:
            continue

        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM x_posts WHERE tweet_id = %s", (str(tweet_id),))
            if cur.fetchone():
                stats["posts_skipped_duplicate"] += 1
                conn.commit()
                continue

        text = item.get("fullText") or item.get("text")
        category, confidence = classify_caption(text, "X post")
        funnel_stage, funnel_confidence = classify_funnel_stage(text, category, "X post")
        message_attribute, attribute_confidence = classify_message_attribute(text, category, "X post")

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO x_posts (competitor_id, tweet_id, post_url, text, posted_at,
                                         like_count, retweet_count, reply_count, quote_count,
                                         view_count, is_retweet, category, category_confidence,
                                         funnel_stage, funnel_stage_confidence,
                                         message_attribute, message_attribute_confidence)
                   VALUES (%(competitor_id)s, %(tweet_id)s, %(post_url)s, %(text)s, %(posted_at)s,
                           %(like_count)s, %(retweet_count)s, %(reply_count)s, %(quote_count)s,
                           %(view_count)s, %(is_retweet)s, %(category)s, %(confidence)s,
                           %(funnel_stage)s, %(funnel_confidence)s, %(message_attribute)s, %(attribute_confidence)s)
                   ON CONFLICT (tweet_id) DO NOTHING""",
                {
                    "competitor_id": competitor_id,
                    "tweet_id": str(tweet_id),
                    "post_url": item.get("url") or item.get("twitterUrl"),
                    "text": text,
                    "posted_at": item.get("createdAt"),
                    "like_count": item.get("likeCount"),
                    "retweet_count": item.get("retweetCount"),
                    "reply_count": item.get("replyCount"),
                    "quote_count": item.get("quoteCount"),
                    "view_count": item.get("viewCount"),
                    "is_retweet": bool(item.get("isRetweet")),
                    "category": category,
                    "confidence": confidence,
                    "funnel_stage": funnel_stage,
                    "funnel_confidence": funnel_confidence,
                    "message_attribute": message_attribute,
                    "attribute_confidence": attribute_confidence,
                },
            )
        stats["posts_added"] += 1
        conn.commit()

    status = "failed" if stats["errors"] and stats["posts_added"] == 0 else (
        "partial" if stats["errors"] else "success"
    )
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scrape_runs (source, run_type, competitors_scraped, posts_added,
                                         posts_skipped_duplicate, errors, status)
               VALUES ('x', %s, %s, %s, %s, %s, %s)""",
            (run_type, stats["competitors_scraped"], stats["posts_added"],
             stats["posts_skipped_duplicate"], json.dumps(stats["errors"]), status),
        )
    conn.commit()

    stats["status"] = status
    return stats
