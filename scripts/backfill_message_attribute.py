"""One-off (safe to re-run) backfill: assigns a message attribute (Safety,
Trust, Price, etc - see categorize/attribute_taxonomy.py) to every existing
piece of content across all seven content tables. Future ingestion classifies
this inline (see each scraper module) - this script exists to catch up
content that predates that, and can be re-run harmlessly since it only
touches rows where message_attribute IS NULL.

Run with: python -m scripts.backfill_message_attribute
"""
from categorize.classify import classify_message_attribute
from categorize.vision import classify_image_message_attribute
from db.connection import get_conn


def backfill_text_table(table: str, text_col: str, category_col: str, context: str,
                         commit_every: int = 20) -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, {text_col}, {category_col} FROM {table} WHERE message_attribute IS NULL")
        pending = cur.fetchall()
    conn.commit()

    count = 0
    for row_id, text, category in pending:
        attribute, confidence = classify_message_attribute(text, category or "", context)
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {table} SET message_attribute = %s, message_attribute_confidence = %s WHERE id = %s",
                        (attribute, confidence, row_id))
        count += 1
        if count % commit_every == 0:
            conn.commit()
            print(f"  {table}: {count}/{len(pending)}", flush=True)
    conn.commit()
    print(f"{table}: done, {count} classified")
    return count


def backfill_ads(commit_every: int = 20) -> int:
    """Ads: use the creative image when we have one (most informative); fall
    back to caption text; if neither, default without spending an API call.
    """
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, creative, caption, category FROM ads WHERE message_attribute IS NULL")
        pending = cur.fetchall()
    conn.commit()

    count = 0
    for row_id, creative, caption, category in pending:
        if creative:
            attribute, confidence = classify_image_message_attribute(
                bytes(creative), extra_context=f"This is an ad creative. Ad caption: {caption or '(none)'}"
            )
        elif caption:
            attribute, confidence = classify_message_attribute(caption, category or "", "Ad caption")
        else:
            attribute, confidence = "None Clear / Other", "low"
        with conn.cursor() as cur:
            cur.execute("UPDATE ads SET message_attribute = %s, message_attribute_confidence = %s WHERE id = %s",
                        (attribute, confidence, row_id))
        count += 1
        if count % commit_every == 0:
            conn.commit()
            print(f"  ads: {count}/{len(pending)}", flush=True)
    conn.commit()
    print(f"ads: done, {count} classified")
    return count


def backfill_google_ads(commit_every: int = 20) -> int:
    """Google Search ads: use the creative image when we have one, else the
    same coarse advertiser/search-term context used for funnel_stage."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, creative, advertiser_name, search_term, ad_format
               FROM google_ads WHERE message_attribute IS NULL"""
        )
        pending = cur.fetchall()
    conn.commit()

    count = 0
    for row_id, creative, advertiser_name, search_term, ad_format in pending:
        if creative:
            caption_context = f"Google {ad_format or 'text'} ad. Advertiser: {advertiser_name}. Search term: {search_term}."
            attribute, confidence = classify_image_message_attribute(bytes(creative), extra_context=caption_context)
        else:
            caption_context = f"Google {ad_format or 'text'} ad. Advertiser: {advertiser_name}. Search term: {search_term}."
            attribute, confidence = classify_message_attribute(caption_context, "", "Google search ad")
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE google_ads SET message_attribute = %s, message_attribute_confidence = %s WHERE id = %s",
                (attribute, confidence, row_id),
            )
        count += 1
        if count % commit_every == 0:
            conn.commit()
            print(f"  google_ads: {count}/{len(pending)}", flush=True)
    conn.commit()
    print(f"google_ads: done, {count} classified")
    return count


def backfill_homepage_snapshots(commit_every: int = 10) -> int:
    """Homepage: an unchanged snapshot (changed=False, screenshot=NULL) should
    inherit the attribute of the most recent snapshot that actually has an
    image, same logic as how funnel_stage/theme are inherited at capture time
    - not a fresh classification of nothing."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, competitor_id, captured_at, changed, screenshot, theme
               FROM homepage_snapshots WHERE message_attribute IS NULL ORDER BY competitor_id, captured_at"""
        )
        rows = cur.fetchall()
    conn.commit()

    last_attr_by_competitor = {}
    count = 0
    for row_id, competitor_id, captured_at, changed, screenshot, theme in rows:
        if screenshot:
            attribute, confidence = classify_image_message_attribute(
                bytes(screenshot), extra_context=f"This is a screenshot of a company's website homepage. Messaging theme: {theme or 'unknown'}."
            )
            last_attr_by_competitor[competitor_id] = (attribute, confidence)
        else:
            attribute, confidence = last_attr_by_competitor.get(competitor_id, ("None Clear / Other", "low"))
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE homepage_snapshots SET message_attribute = %s, message_attribute_confidence = %s "
                "WHERE id = %s AND message_attribute IS NULL",
                (attribute, confidence, row_id),
            )
        count += 1
        if count % commit_every == 0:
            conn.commit()
            print(f"  homepage_snapshots: {count}/{len(rows)}", flush=True)
    conn.commit()
    print(f"homepage_snapshots: done, {count} processed")
    return count


def run():
    total = 0
    total += backfill_text_table("posts", "caption", "category", "Instagram post")
    total += backfill_text_table("tiktok_videos", "caption", "category", "TikTok video")
    total += backfill_text_table("youtube_videos", "caption", "category", "YouTube video")
    total += backfill_text_table("x_posts", "text", "category", "X post")
    total += backfill_ads()
    total += backfill_google_ads()
    total += backfill_homepage_snapshots()
    print(f"\nTOTAL classified: {total}", flush=True)


if __name__ == "__main__":
    run()
