"""Facebook/Instagram Ads Library tracker.

For each competitor's Facebook Page, pulls currently-running (and recently
run) ads via Apify's Facebook Ads Library Scraper, stores the creative +
caption + platforms + run dates, and classifies each ad's messaging theme
via Claude vision (only once per ad - the creative doesn't change).

Ads are living records (an ad keeps running week to week), so this uses
upsert-by-ad_archive_id and updates is_active/last_seen_at/end_date on every
run rather than insert-once like Instagram posts.
"""
from __future__ import annotations

import io
import os
import urllib.request

from apify_client import ApifyClient
from PIL import Image

from categorize.classify import classify_funnel_stage
from categorize.vision import classify_image_funnel_stage, classify_image_theme
from db.connection import get_conn

ACTOR_ID = "apify/facebook-ads-scraper"
STORE_WIDTH = 600
JPEG_QUALITY = 80


def _run_actor(page_urls: list, results_limit: int) -> list:
    if not page_urls:
        return []
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR_ID).call(run_input={
        "startUrls": [{"url": u} for u in page_urls],
        "resultsLimit": results_limit,
        "activeStatus": "active",
    })
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def _first_non_template(*candidates):
    for c in candidates:
        if c and "{{" not in c:
            return c
    return None


def _extract_media_url(snapshot: dict) -> tuple:
    """Returns (creative_type, thumbnail_url_for_download, playable_video_url)."""
    videos = snapshot.get("videos") or []
    images = snapshot.get("images") or []
    cards = snapshot.get("cards") or []

    if videos:
        v = videos[0]
        return "Video", v.get("videoPreviewImageUrl"), v.get("videoHdUrl") or v.get("videoSdUrl")
    if images:
        return "Image", images[0].get("originalImageUrl") or images[0].get("resizedImageUrl"), None
    if cards:
        card = cards[0]
        video_url = card.get("videoHdUrl") or card.get("video_hd_url") or card.get("videoSdUrl")
        if video_url:
            return ("Carousel" if len(cards) > 1 else "Video"), card.get("videoPreviewImageUrl") or card.get("video_preview_image_url"), video_url
        img = card.get("originalImageUrl") or card.get("resizedImageUrl") or card.get("image_url")
        if img:
            return ("Carousel" if len(cards) > 1 else "Image"), img, None
    return "Image", None, None


def _download_and_resize(url: str):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        if img.width > STORE_WIDTH:
            ratio = STORE_WIDTH / img.width
            img = img.resize((STORE_WIDTH, int(img.height * ratio)))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY)
        return out.getvalue()
    except Exception:  # noqa: BLE001
        return None


def _normalize(item: dict) -> dict:
    snapshot = item.get("snapshot") or {}
    cards = snapshot.get("cards") or []
    first_card = cards[0] if cards else {}

    creative_type, media_url, video_url = _extract_media_url(snapshot)
    caption = _first_non_template(
        (snapshot.get("body") or {}).get("text"),
        first_card.get("body"),
    )
    headline = _first_non_template(
        snapshot.get("title") if isinstance(snapshot.get("title"), str) else None,
        first_card.get("title"),
    )

    return {
        "ad_archive_id": str(item.get("adArchiveID") or item.get("adArchiveId")),
        "ad_url": f"https://www.facebook.com/ads/library/?id={item.get('adArchiveID') or item.get('adArchiveId')}",
        "creative_type": creative_type,
        "caption": caption,
        "headline": headline,
        "platforms": item.get("publisherPlatform") or [],
        "start_date": (item.get("startDateFormatted") or "")[:10] or None,
        "end_date": (item.get("endDateFormatted") or "")[:10] or None,
        "is_active": bool(item.get("isActive")),
        "media_url": media_url,
        "video_url": video_url,
    }


def capture_ads(run_type: str = "weekly", results_limit: int = 30, only_own_brand: bool = False) -> dict:
    conn = get_conn()
    stats = {"competitors_scraped": 0, "ads_added": 0, "ads_updated": 0, "errors": []}

    query = "SELECT id, facebook_url FROM competitors WHERE is_active = TRUE AND facebook_url IS NOT NULL"
    if only_own_brand:
        query += " AND is_own_brand = TRUE"
    with conn.cursor() as cur:
        cur.execute(query)
        competitors = cur.fetchall()
    conn.commit()  # release the read lock before the (potentially long) external actor call
    stats["competitors_scraped"] = len(competitors)
    by_url = {url: cid for cid, url in competitors}

    try:
        raw_items = _run_actor([url for _, url in competitors], results_limit)
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append({"scope": "actor_run", "error": str(exc)})
        raw_items = []

    for item in raw_items:
        input_url = item.get("inputUrl")
        competitor_id = by_url.get(input_url) or by_url.get((input_url or "").rstrip("/"))
        if not competitor_id:
            continue

        ad = _normalize(item)
        if not ad["ad_archive_id"] or ad["ad_archive_id"] == "None":
            continue

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ads WHERE ad_archive_id = %s", (ad["ad_archive_id"],))
            existing = cur.fetchone()

        if existing:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE ads SET is_active = %s, end_date = %s, last_seen_at = now()
                       WHERE ad_archive_id = %s""",
                    (ad["is_active"], ad["end_date"], ad["ad_archive_id"]),
                )
            stats["ads_updated"] += 1
        else:
            creative_bytes = _download_and_resize(ad["media_url"])
            ad_context = f"This is an ad creative. Ad caption: {ad['caption'] or '(none)'}"
            if creative_bytes:
                theme, confidence = classify_image_theme(creative_bytes, extra_context=ad_context)
                funnel_stage, funnel_confidence = classify_image_funnel_stage(creative_bytes, extra_context=ad_context)
            else:
                theme, confidence = "Mixed / Other", "low"
                funnel_stage, funnel_confidence = classify_funnel_stage(ad["caption"] or "", "", "Ad caption")

            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ads (competitor_id, ad_archive_id, ad_url, creative_type, creative,
                                         video_url, caption, headline, platforms, start_date, end_date,
                                         is_active, category, category_confidence, funnel_stage,
                                         funnel_stage_confidence)
                       VALUES (%(competitor_id)s, %(ad_archive_id)s, %(ad_url)s, %(creative_type)s,
                               %(creative)s, %(video_url)s, %(caption)s, %(headline)s, %(platforms)s,
                               %(start_date)s, %(end_date)s, %(is_active)s, %(category)s,
                               %(category_confidence)s, %(funnel_stage)s, %(funnel_stage_confidence)s)
                       ON CONFLICT (ad_archive_id) DO NOTHING""",
                    {**ad, "competitor_id": competitor_id, "creative": creative_bytes,
                     "category": theme, "category_confidence": confidence,
                     "funnel_stage": funnel_stage, "funnel_stage_confidence": funnel_confidence},
                )
            stats["ads_added"] += 1

        conn.commit()

    # Ads no longer returned by this run (for a competitor we did check) are inferred inactive.
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE ads SET is_active = FALSE
               WHERE is_active = TRUE AND competitor_id = ANY(%s)
                 AND last_seen_at < now() - interval '1 day'""",
            (list(by_url.values()),),
        )
    conn.commit()

    status = "failed" if stats["errors"] and stats["ads_added"] + stats["ads_updated"] == 0 else (
        "partial" if stats["errors"] else "success"
    )
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scrape_runs (source, run_type, competitors_scraped, posts_added,
                                         posts_skipped_duplicate, errors, status)
               VALUES ('ads', %s, %s, %s, %s, %s, %s)""",
            (run_type, stats["competitors_scraped"], stats["ads_added"], stats["ads_updated"],
             __import__("json").dumps(stats["errors"]), status),
        )
    conn.commit()

    stats["status"] = status
    return stats
