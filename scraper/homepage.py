"""Weekly homepage screenshot tracker.

For each competitor's website, takes a screenshot via Apify's Website
Screenshot Generator actor (all homepages batched into one actor run),
compares it to the last stored screenshot using a perceptual hash, and:
  - if visually unchanged: logs a row with changed=False, no new image bytes
    (avoids re-storing a duplicate image every week)
  - if changed (or first time seen): stores the new screenshot and classifies
    its messaging theme via Claude vision

Apify's own storage only retains run results for a few days, so screenshots
are downloaded and stored in Postgres immediately, not linked by URL.
"""
from __future__ import annotations

import io
import os
import urllib.request

import imagehash
from apify_client import ApifyClient
from PIL import Image

from categorize.vision import classify_image_funnel_stage, classify_image_theme
from db.connection import get_conn

ACTOR_ID = "apify/screenshot-url"
STORE_WIDTH = 800
JPEG_QUALITY = 80
HASH_MATCH_THRESHOLD = 4  # hamming distance <= this counts as "unchanged"


def _capture_screenshots(website_urls: list) -> dict:
    """Runs the screenshot actor once for all URLs, returns {url: screenshot_bytes}."""
    if not website_urls:
        return {}

    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR_ID).call(run_input={
        "urls": [{"url": u} for u in website_urls],
        "format": "png",
        "waitUntil": "load",
        "viewportWidth": 1280,
    })
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    results = {}
    for item in items:
        screenshot_url = item.get("screenshotUrl")
        start_url = item.get("startUrl")
        if not screenshot_url or not start_url:
            continue
        try:
            req = urllib.request.Request(screenshot_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
            results[start_url] = raw
        except Exception:  # noqa: BLE001
            continue
    return results


def _resize_and_encode(raw_png: bytes) -> bytes:
    img = Image.open(io.BytesIO(raw_png)).convert("RGB")
    if img.width > STORE_WIDTH:
        ratio = STORE_WIDTH / img.width
        img = img.resize((STORE_WIDTH, int(img.height * ratio)))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=JPEG_QUALITY)
    return out.getvalue()


def _process_screenshots(conn, competitors: list, raw_screenshots: dict, stats: dict) -> None:
    for competitor_id, website_url in competitors:
        # Apify may normalize the URL slightly (e.g. add a trailing slash) - match loosely.
        raw = raw_screenshots.get(website_url) or next(
            (v for k, v in raw_screenshots.items() if k.rstrip("/") == website_url.rstrip("/")), None
        )
        if raw is None:
            stats["errors"].append({"scope": "competitor", "competitor_id": competitor_id,
                                     "error": "no screenshot returned"})
            continue

        try:
            jpeg_bytes = _resize_and_encode(raw)
            new_hash = str(imagehash.average_hash(Image.open(io.BytesIO(jpeg_bytes))))
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append({"scope": "competitor", "competitor_id": competitor_id, "error": str(exc)})
            continue

        with conn.cursor() as cur:
            cur.execute(
                """SELECT image_hash, theme, theme_confidence, funnel_stage, funnel_stage_confidence
                   FROM homepage_snapshots WHERE competitor_id = %s ORDER BY captured_at DESC LIMIT 1""",
                (competitor_id,),
            )
            prev = cur.fetchone()

        changed = True
        theme, confidence = None, None
        funnel_stage, funnel_confidence = None, None
        if prev:
            prev_hash, prev_theme, prev_confidence, prev_funnel_stage, prev_funnel_confidence = prev
            distance = imagehash.hex_to_hash(new_hash) - imagehash.hex_to_hash(prev_hash)
            if distance <= HASH_MATCH_THRESHOLD:
                changed = False
                theme, confidence = prev_theme, prev_confidence
                funnel_stage, funnel_confidence = prev_funnel_stage, prev_funnel_confidence

        if changed:
            homepage_context = "This is a screenshot of a company's website homepage."
            theme, confidence = classify_image_theme(jpeg_bytes, extra_context=homepage_context)
            funnel_stage, funnel_confidence = classify_image_funnel_stage(jpeg_bytes, extra_context=homepage_context)

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO homepage_snapshots
                       (competitor_id, screenshot, image_hash, changed, theme, theme_confidence,
                        funnel_stage, funnel_stage_confidence)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (competitor_id, jpeg_bytes if changed else None, new_hash, changed, theme, confidence,
                 funnel_stage, funnel_confidence),
            )
        conn.commit()

        if changed:
            stats["changed"] += 1
        else:
            stats["unchanged"] += 1


def _log_run(conn, run_type: str, stats: dict) -> str:
    status = "failed" if stats["errors"] and stats["changed"] + stats["unchanged"] == 0 else (
        "partial" if stats["errors"] else "success"
    )
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scrape_runs (source, run_type, competitors_scraped, posts_added,
                                         posts_skipped_duplicate, errors, status)
               VALUES ('homepage', %s, %s, %s, %s, %s, %s)""",
            (run_type, stats["competitors_scraped"], stats["changed"], stats["unchanged"],
             __import__("json").dumps(stats["errors"]), status),
        )
    conn.commit()
    return status


def capture_homepages(run_type: str = "weekly", only_own_brand: bool = False) -> dict:
    conn = get_conn()
    stats = {"competitors_scraped": 0, "changed": 0, "unchanged": 0, "errors": []}

    query = "SELECT id, website_url FROM competitors WHERE is_active = TRUE AND website_url IS NOT NULL"
    if only_own_brand:
        query += " AND is_own_brand = TRUE"
    with conn.cursor() as cur:
        cur.execute(query)
        competitors = cur.fetchall()
    conn.commit()  # release the read lock before the (multi-minute) external actor call
    stats["competitors_scraped"] = len(competitors)

    try:
        raw_screenshots = _capture_screenshots([url for _, url in competitors])
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append({"scope": "actor_run", "error": str(exc)})
        raw_screenshots = {}

    _process_screenshots(conn, competitors, raw_screenshots, stats)
    stats["status"] = _log_run(conn, run_type, stats)
    return stats


def recover_homepage_run(apify_run_id: str, run_type: str = "backfill") -> dict:
    """Re-applies an already-completed (or still-running-until-you-wait) Apify
    screenshot run's dataset to the DB, without triggering a new scrape.
    """
    conn = get_conn()
    stats = {"competitors_scraped": 0, "changed": 0, "unchanged": 0, "errors": []}

    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, website_url FROM competitors WHERE is_active = TRUE AND website_url IS NOT NULL"
        )
        competitors = cur.fetchall()
    conn.commit()
    stats["competitors_scraped"] = len(competitors)

    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run_client = client.run(apify_run_id)
    run_client.wait_for_finish()
    run = run_client.get()
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    raw_screenshots = {}
    for item in items:
        screenshot_url, start_url = item.get("screenshotUrl"), item.get("startUrl")
        if not screenshot_url or not start_url:
            continue
        try:
            req = urllib.request.Request(screenshot_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw_screenshots[start_url] = resp.read()
        except Exception:  # noqa: BLE001
            continue

    _process_screenshots(conn, competitors, raw_screenshots, stats)
    stats["status"] = _log_run(conn, run_type, stats)
    return stats
