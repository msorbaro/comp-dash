"""One-off (safe to re-run) backfill: assigns a See/Think/Do funnel stage to
every existing piece of content across all six content tables. Future
ingestion should classify funnel stage inline (see each scraper module) - this
script exists to catch up content that predates that, and can be re-run
harmlessly since it only touches rows where funnel_stage IS NULL.

Run with: python -m scripts.backfill_funnel_stage
"""
from categorize.classify import classify_funnel_stage
from categorize.vision import classify_image_funnel_stage
from db.connection import get_conn


def backfill_text_table(table: str, text_col: str, category_col: str, context: str,
                         commit_every: int = 20) -> int:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, {text_col}, {category_col} FROM {table} WHERE funnel_stage IS NULL")
        pending = cur.fetchall()
    conn.commit()

    count = 0
    for row_id, text, category in pending:
        stage, confidence = classify_funnel_stage(text, category or "", context)
        with conn.cursor() as cur:
            cur.execute(f"UPDATE {table} SET funnel_stage = %s, funnel_stage_confidence = %s WHERE id = %s",
                        (stage, confidence, row_id))
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
        cur.execute("SELECT id, creative, caption, category FROM ads WHERE funnel_stage IS NULL")
        pending = cur.fetchall()
    conn.commit()

    count = 0
    for row_id, creative, caption, category in pending:
        if creative:
            stage, confidence = classify_image_funnel_stage(
                creative, extra_context=f"This is an ad creative. Ad caption: {caption or '(none)'}"
            )
        elif caption:
            stage, confidence = classify_funnel_stage(caption, category or "", "Ad caption")
        else:
            stage, confidence = "Think", "low"
        with conn.cursor() as cur:
            cur.execute("UPDATE ads SET funnel_stage = %s, funnel_stage_confidence = %s WHERE id = %s",
                        (stage, confidence, row_id))
        count += 1
        if count % commit_every == 0:
            conn.commit()
            print(f"  ads: {count}/{len(pending)}", flush=True)
    conn.commit()
    print(f"ads: done, {count} classified")
    return count


def backfill_homepage_snapshots(commit_every: int = 10) -> int:
    """Homepage: an unchanged snapshot (changed=False, screenshot=NULL) should
    inherit the funnel stage of the most recent snapshot that actually has an
    image, same logic as how `theme` is inherited at capture time - not a
    fresh classification of nothing.
    """
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, competitor_id, captured_at, changed, screenshot, theme
               FROM homepage_snapshots ORDER BY competitor_id, captured_at"""
        )
        rows = cur.fetchall()
    conn.commit()

    last_stage_by_competitor = {}
    count = 0
    for row_id, competitor_id, captured_at, changed, screenshot, theme in rows:
        if screenshot:
            stage, confidence = classify_image_funnel_stage(
                screenshot, extra_context=f"This is a screenshot of a company's website homepage. Messaging theme: {theme or 'unknown'}."
            )
            last_stage_by_competitor[competitor_id] = (stage, confidence)
        else:
            stage, confidence = last_stage_by_competitor.get(competitor_id, ("Think", "low"))
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE homepage_snapshots SET funnel_stage = %s, funnel_stage_confidence = %s "
                "WHERE id = %s AND funnel_stage IS NULL",
                (stage, confidence, row_id),
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
    total += backfill_homepage_snapshots()
    print(f"\nTOTAL classified: {total}")


if __name__ == "__main__":
    run()
