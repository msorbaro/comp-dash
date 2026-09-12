"""Google Search Ads tracker, via Google's own Ads Transparency Center
(Apify's solidcode/ads-transparency-scraper). For each competitor we run two
searches - neither reliably resolves to a single verified advertiser account,
so both just return whichever advertisers show up for that query, and
`_is_own_ad` is what actually decides "is this really the company's own ad":
  1. By brand name - usually turns up the company's own ads, but Google
     resolving an exact brand-name search to a single advertiser is NOT
     proof that advertiser is the company itself: "Brakes Plus" resolves to
     exactly one advertiser, "Brakes Plus Automotive", which looked like it
     could be a legal-name variant (the same pattern as Walmart's "Wal-Mart
     Stores, Inc"), but the user confirmed it is a different company, not
     Brakes Plus's ad. Confirmed false positives are excluded per-brand via
     KNOWN_NON_OWN_ADVERTISERS below; when that leaves a brand with zero
     name-search "own" ads, that's a legitimate result (not every brand buys
     Google Search ads) - never paper over it by loosening the match.
  2. By website domain, treated as a keyword search - this surfaces ANY
     advertiser running ads that show up for that term. This is usually a
     competitor conquesting the brand's domain as a keyword, BUT for a
     brand that's actually owned by a larger operator, the parent's
     corporate entity buying its own portfolio brand's search ads under the
     PARENT's advertiser name is a real, common pattern too - confirmed here
     for Brakes Plus, Express Oil, and Mavis Discount Tire, all of which run
     under "Mavis Tire Supply LLC" rather than their storefront brand name.
     KNOWN_OWN_ADVERTISERS below is the (user-confirmed only) allowlist for
     this - a name showing up there for one Mavis-owned brand does NOT mean
     it applies to every "Our Brands" entry; several of those are separate
     companies in reality (Pep Boys, Midas, etc.) and must be confirmed
     individually, not assumed from the portfolio grouping.
Both are cheap (~$0.001 per 20 results).
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse

from apify_client import ApifyClient

from categorize.classify import classify_funnel_stage, classify_message_attribute
from categorize.vision import classify_image_funnel_stage, classify_image_message_attribute, extract_ad_headline
from db.connection import get_conn
from scraper.media import fetch_thumbnail, to_jpeg

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


def _screenshot_ad_creative(ad_url: str) -> bytes | None:
    """Fallback for when the actor's own `imageUrl` field is empty for a
    creative - which happens even for genuinely live, currently-running ads
    (confirmed: an ad last shown yesterday still had no imageUrl). Google
    renders the actual creative inside an iframe on the ad's own Ads
    Transparency Center page, so screenshotting just that iframe gets the
    real ad with none of the surrounding page chrome."""
    if not ad_url:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 900})
                page.goto(ad_url, wait_until="load", timeout=20000)
                page.wait_for_timeout(2500)
                for frame_el in page.locator("iframe").all():
                    box = frame_el.bounding_box()
                    if box and box["width"] > 50 and box["height"] > 50:
                        # Playwright screenshots are PNG - normalize to JPEG
                        # since every vision call in this codebase assumes it.
                        return to_jpeg(frame_el.screenshot())
                return None
            finally:
                browser.close()
    except Exception:  # noqa: BLE001
        return None


# Confirmed-wrong advertiser-name matches, keyed by our competitor name -
# each entry here is a user-confirmed false positive, not a guess.
KNOWN_NON_OWN_ADVERTISERS = {
    "Brakes Plus": {"Brakes Plus Automotive"},  # confirmed by the user: not the same company
}

# The reverse case: an advertiser name that does NOT match the brand name at
# all (so the substring check below would miss it) but IS confirmed to be
# that brand's real ads, usually because a parent/corporate entity buys the
# ads rather than the storefront brand itself. User-confirmed only.
KNOWN_OWN_ADVERTISERS = {
    "Brakes Plus": {"Mavis Tire Supply LLC"},
    "Express Oil": {"Mavis Tire Supply LLC"},
    "Mavis Discount Tire / Mavis Tires and Brakes": {"Mavis Tire Supply LLC"},
}


def _is_own_ad(advertiser_name: str, competitor_name: str) -> bool:
    if not advertiser_name:
        return False
    if advertiser_name in KNOWN_OWN_ADVERTISERS.get(competitor_name, set()):
        return True
    if advertiser_name in KNOWN_NON_OWN_ADVERTISERS.get(competitor_name, set()):
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
                    cur.execute(
                        "SELECT id, funnel_stage, image_url, headline FROM google_ads WHERE creative_id = %s",
                        (creative_id,),
                    )
                    existing = cur.fetchone()

                advertiser_name = item.get("advertiserName")
                is_own = _is_own_ad(advertiser_name, name)
                last_shown = item.get("lastShown")
                is_active_now = bool(last_shown)  # actor only returns currently/recently-served creatives

                if existing:
                    # The actor doesn't always return an imageUrl for a given
                    # creative on every run (transient gap, not a permanent
                    # property of the ad) - a row inserted without one should
                    # still get backfilled once a later run does have it,
                    # instead of staying imageless forever.
                    _, _existing_stage, existing_image_url, existing_headline = existing
                    update_fields = {"last_shown": last_shown, "approx_days_shown": item.get("approxDaysShown"),
                                      "is_active": is_active_now}
                    if not existing_image_url:
                        creative_bytes = fetch_thumbnail(item["imageUrl"]) if item.get("imageUrl") else None
                        source_url = item.get("imageUrl")
                        if not creative_bytes:
                            creative_bytes = _screenshot_ad_creative(item.get("adUrl"))
                            source_url = item.get("adUrl") if creative_bytes else None
                        if creative_bytes:
                            update_fields["image_url"] = source_url
                            update_fields["creative"] = creative_bytes
                    if not existing_headline:
                        img_for_headline = update_fields.get("creative")
                        if img_for_headline is None and existing_image_url:
                            with conn.cursor() as cur:
                                cur.execute("SELECT creative FROM google_ads WHERE creative_id = %s", (creative_id,))
                                row = cur.fetchone()
                                img_for_headline = row[0] if row else None
                        if img_for_headline:
                            update_fields["headline"] = extract_ad_headline(img_for_headline)
                    set_clause = ", ".join(f"{k} = %({k})s" for k in update_fields)
                    with conn.cursor() as cur:
                        cur.execute(
                            f"UPDATE google_ads SET {set_clause}, last_seen_at = now() WHERE creative_id = %(creative_id)s",
                            {**update_fields, "creative_id": creative_id},
                        )
                    stats["ads_updated"] += 1
                else:
                    image_url = item.get("imageUrl")
                    creative_bytes = fetch_thumbnail(image_url) if image_url else None
                    if not creative_bytes:
                        creative_bytes = _screenshot_ad_creative(item.get("adUrl"))
                        image_url = item.get("adUrl") if creative_bytes else None
                    ad_format = item.get("adFormat") or "text"
                    caption_context = f"Google {ad_format} ad. Advertiser: {advertiser_name}. Search term: {search_term}."
                    if creative_bytes:
                        stage, confidence = classify_image_funnel_stage(creative_bytes, extra_context=caption_context)
                        message_attribute, attribute_confidence = classify_image_message_attribute(creative_bytes, extra_context=caption_context)
                        headline = extract_ad_headline(creative_bytes)
                    else:
                        stage, confidence = classify_funnel_stage(caption_context, "", "Google search ad")
                        message_attribute, attribute_confidence = classify_message_attribute(caption_context, "", "Google search ad")
                        headline = None

                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO google_ads (competitor_id, creative_id, advertiser_name, is_own_ad,
                                                        search_term, headline, ad_format, ad_url, image_url, creative,
                                                        first_shown, last_shown, approx_days_shown, is_active,
                                                        funnel_stage, funnel_stage_confidence,
                                                        message_attribute, message_attribute_confidence)
                               VALUES (%(competitor_id)s, %(creative_id)s, %(advertiser_name)s, %(is_own)s,
                                       %(search_term)s, %(headline)s, %(ad_format)s, %(ad_url)s, %(image_url)s, %(creative)s,
                                       %(first_shown)s, %(last_shown)s, %(approx_days_shown)s, %(is_active)s,
                                       %(stage)s, %(confidence)s, %(message_attribute)s, %(attribute_confidence)s)
                               ON CONFLICT (creative_id) DO NOTHING""",
                            {
                                "competitor_id": competitor_id, "creative_id": creative_id,
                                "advertiser_name": advertiser_name, "is_own": is_own,
                                "search_term": query_used, "headline": headline, "ad_format": ad_format,
                                "ad_url": item.get("adUrl"), "image_url": image_url,
                                "creative": creative_bytes, "first_shown": item.get("firstShown"),
                                "last_shown": last_shown, "approx_days_shown": item.get("approxDaysShown"),
                                "is_active": is_active_now, "stage": stage, "confidence": confidence,
                                "message_attribute": message_attribute, "attribute_confidence": attribute_confidence,
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
