"""Orchestrates one full run: scrape new Instagram/TikTok/YouTube/X posts,
capture homepage screenshots, capture Facebook/Instagram ads, categorize/
classify everything, and write a human-readable markdown log. This is what
both GitHub Actions (weekly) and you (manually) invoke.

Run with:  python -m scripts.run_weekly [--backfill]
"""
import argparse
import datetime as dt
import pathlib

from categorize.classify import classify_pending_funnel_stage, classify_pending_posts
from scraper.ads import capture_ads
from scraper.google_ads import capture_google_ads
from scraper.homepage import capture_homepages
from scraper.ingest import ingest_new_posts
from scraper.tiktok import capture_tiktok
from scraper.x import capture_x
from scraper.youtube import capture_youtube

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _safe(label, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - one pipeline failing shouldn't kill the others
        return {"status": "failed", "error": str(exc), "_label": label}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="Initial historical pull instead of a normal weekly run")
    args = parser.parse_args()

    run_type = "backfill" if args.backfill else "weekly"
    today = dt.date.today().isoformat()

    ingest_stats = _safe("instagram ingest", ingest_new_posts, run_type=run_type)
    classify_stats = _safe("categorization", classify_pending_posts, batch_size=2000)
    funnel_stats = _safe("funnel stage classification", classify_pending_funnel_stage, batch_size=2000)
    homepage_stats = _safe("homepage capture", capture_homepages, run_type=run_type)
    ads_stats = _safe("ads capture", capture_ads, run_type=run_type)
    tiktok_stats = _safe("tiktok capture", capture_tiktok, run_type=run_type)
    youtube_stats = _safe("youtube capture", capture_youtube, run_type=run_type)
    x_stats = _safe("x capture", capture_x, run_type=run_type)
    google_ads_stats = _safe("google ads capture", capture_google_ads, run_type=run_type)

    log_lines = [f"# Run log — {today} ({run_type})", ""]

    log_lines += [
        "## Instagram",
        f"- Competitors scraped: {ingest_stats.get('competitors_scraped', '—')}",
        f"- New posts added: {ingest_stats.get('posts_added', '—')}",
        f"- Duplicate posts skipped: {ingest_stats.get('posts_skipped_duplicate', '—')}",
        f"- Status: {ingest_stats.get('status')}",
        "",
        "## Categorization (Instagram)",
        f"- Posts categorized this run: {classify_stats.get('classified', '—')} "
        f"(errors: {classify_stats.get('errors', '—')})",
        f"- Posts assigned a funnel stage: {funnel_stats.get('classified', '—')}",
        "",
        "## Website homepage tracker",
        f"- Competitors checked: {homepage_stats.get('competitors_scraped', '—')}",
        f"- Homepages changed: {homepage_stats.get('changed', '—')}",
        f"- Homepages unchanged: {homepage_stats.get('unchanged', '—')}",
        f"- Status: {homepage_stats.get('status')}",
        "",
        "## Ads library",
        f"- Competitors checked: {ads_stats.get('competitors_scraped', '—')}",
        f"- New ads found: {ads_stats.get('ads_added', '—')}",
        f"- Existing ads updated: {ads_stats.get('ads_updated', '—')}",
        f"- Status: {ads_stats.get('status')}",
        "",
        "## TikTok",
        f"- Competitors checked: {tiktok_stats.get('competitors_scraped', '—')}",
        f"- New videos added: {tiktok_stats.get('videos_added', '—')}",
        f"- Status: {tiktok_stats.get('status')}",
        "",
        "## YouTube",
        f"- Competitors checked: {youtube_stats.get('competitors_scraped', '—')}",
        f"- New videos added: {youtube_stats.get('videos_added', '—')}",
        f"- Status: {youtube_stats.get('status')}",
        "",
        "## X (Twitter)",
        f"- Competitors checked: {x_stats.get('competitors_scraped', '—')}",
        f"- New posts added: {x_stats.get('posts_added', '—')}",
        f"- Status: {x_stats.get('status')}",
        "",
        "## Google Search Ads",
        f"- Competitors checked: {google_ads_stats.get('competitors_scraped', '—')}",
        f"- New ads found: {google_ads_stats.get('ads_added', '—')}",
        f"- Existing ads updated: {google_ads_stats.get('ads_updated', '—')}",
        f"- Status: {google_ads_stats.get('status')}",
    ]

    all_stats = [
        ("Instagram", ingest_stats), ("Homepage", homepage_stats), ("Ads", ads_stats),
        ("TikTok", tiktok_stats), ("YouTube", youtube_stats), ("X", x_stats),
        ("Google Ads", google_ads_stats),
    ]
    for label, stats in all_stats:
        if stats.get("errors"):
            log_lines.append("")
            log_lines.append(f"### {label} errors")
            for err in stats["errors"]:
                log_lines.append(f"- {err}")
        if stats.get("_label"):
            log_lines.append(f"\n**{stats['_label']} crashed:** {stats.get('error')}")

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / f"{today}.md").write_text("\n".join(log_lines) + "\n")

    print("\n".join(log_lines))


if __name__ == "__main__":
    main()
