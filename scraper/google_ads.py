"""Google Search Ads tracker, via Google's own Ads Transparency Center
(Apify's solidcode/ads-transparency-scraper). For each competitor we run two
searches:
  1. By brand name - Google resolves this to the company's own advertiser
     profile, surfacing their own search/display/video ad creatives.
  2. By website domain, treated as a keyword search - this surfaces ANY
     advertiser (including a competitor) running ads that show up for that
     term, which is how brand-conquesting gets caught (e.g. Mavis running
     ads against "brakesplus.com").
Both are cheap (~$0.001 per 20 results).
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse

from apify_client import ApifyClient

from categorize.classify import classify_funnel_stage
from categorize.vision import classify_image_funnel_stage
from db.connection import get_conn
from scraper.media import fetch_thumbnail

ACTOR_ID = "solidcode/ads-transparency-scraper"


def _domain_from_url(url: str) -> str:
    netloc = urllib.parse.urlparse(url).netloc or url
    return re.sub(r"^www\.", "", netloc).rstrip("/")


def _run_search(query: str, max_results: int) -> list:
    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run = client.actor(ACTOR_ID).call(run_input={
        "searchQuery": query,
        "maxResults": max_results,
        "region": "US",
    })
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def _is_own_ad(advertiser_name: str, competitor_name: str) -> bool:
    if not advertiser_name:
        return False
    a = re.sub(r"[^a-z0-9]", "", advertiser_name.lower())
    b = re.sub(r"[^a-z0-9]", "", competitor_name.lower())
    return b in a or a in b


def capture_google_ads(run_type: str = "weekly", max_results: int = 20,
                        only_own_brand: bool = False) -> dict:
    conn = get_conn()
    stats = {"competitors_scraped": 0, "ads_added": 0, "ads_updated": 0, "errors": []}

    query = "SELECT id, name, website_url FROM competitors WHERE is_active = TRUE AND website_url IS NOT NULL"
    if only_own_brand:
        query += " AND is_own_brand = TRUE"
    with conn.cursor() as cur:
        cur.execute(query)
        competitors = cur.fetchall()
    conn.commit()
    stats["competitors_scraped"] = len(competitors)

    for competitor_id, name, website_url in competitors:
        domain = _domain_from_url(website_url)
        searches = [(name, name), (domain, domain)]

        for search_term, query_used in searches:
            try:
                items = _run_search(search_term, max_results)
            except Exception as exc:  # noqa: BLE001
                stats["errors"].append({"scope": "actor_run", "competitor_id": competitor_id,
                                         "search_term": search_term, "error": str(exc)})
                continue

            for item in items:
                creative_id = item.get("creativeId")
                if not creative_id:
                    continue

                with conn.cursor() as cur:
                    cur.execute("SELECT id, funnel_stage FROM google_ads WHERE creative_id = %s", (creative_id,))
                    existing = cur.fetchone()

                advertiser_name = item.get("advertiserName")
                is_own = _is_own_ad(advertiser_name, name)
                last_shown = item.get("lastShown")
                is_active_now = bool(last_shown)  # actor only returns currently/recently-served creatives

                if existing:
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE google_ads SET last_shown = %s, approx_days_shown = %s,
                                                      is_active = %s, last_seen_at = now()
                               WHERE creative_id = %s""",
                            (last_shown, item.get("approxDaysShown"), is_active_now, creative_id),
                        )
                    stats["ads_updated"] += 1
                else:
                    image_url = item.get("imageUrl")
                    creative_bytes = fetch_thumbnail(image_url) if image_url else None
                    ad_format = item.get("adFormat") or "text"
                    caption_context = f"Google {ad_format} ad. Advertiser: {advertiser_name}. Search term: {search_term}."
                    if creative_bytes:
                        stage, confidence = classify_image_funnel_stage(creative_bytes, extra_context=caption_context)
                    else:
                        stage, confidence = classify_funnel_stage(caption_context, "", "Google search ad")

                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO google_ads (competitor_id, creative_id, advertiser_name, is_own_ad,
                                                        search_term, ad_format, ad_url, image_url, creative,
                                                        first_shown, last_shown, approx_days_shown, is_active,
                                                        funnel_stage, funnel_stage_confidence)
                               VALUES (%(competitor_id)s, %(creative_id)s, %(advertiser_name)s, %(is_own)s,
                                       %(search_term)s, %(ad_format)s, %(ad_url)s, %(image_url)s, %(creative)s,
                                       %(first_shown)s, %(last_shown)s, %(approx_days_shown)s, %(is_active)s,
                                       %(stage)s, %(confidence)s)
                               ON CONFLICT (creative_id) DO NOTHING""",
                            {
                                "competitor_id": competitor_id, "creative_id": creative_id,
                                "advertiser_name": advertiser_name, "is_own": is_own,
                                "search_term": query_used, "ad_format": ad_format,
                                "ad_url": item.get("adUrl"), "image_url": image_url,
                                "creative": creative_bytes, "first_shown": item.get("firstShown"),
                                "last_shown": last_shown, "approx_days_shown": item.get("approxDaysShown"),
                                "is_active": is_active_now, "stage": stage, "confidence": confidence,
                            },
                        )
                    stats["ads_added"] += 1
                conn.commit()

    status = "failed" if stats["errors"] and stats["ads_added"] + stats["ads_updated"] == 0 else (
        "partial" if stats["errors"] else "success"
    )
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO scrape_runs (source, run_type, competitors_scraped, posts_added,
                                         posts_skipped_duplicate, errors, status)
               VALUES ('google_ads', %s, %s, %s, %s, %s, %s)""",
            (run_type, stats["competitors_scraped"], stats["ads_added"], stats["ads_updated"],
             json.dumps(stats["errors"]), status),
        )
    conn.commit()

    stats["status"] = status
    return stats
