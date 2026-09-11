"""Orchestrates one full run: scrape new posts -> categorize them -> write a
human-readable markdown log. This is what both GitHub Actions (weekly) and
you (manually) invoke.

Run with:  python -m scripts.run_weekly [--backfill]
"""
import argparse
import datetime as dt
import pathlib

from categorize.classify import classify_pending_posts
from scraper.ingest import ingest_new_posts

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true", help="Initial historical pull instead of a normal weekly run")
    args = parser.parse_args()

    run_type = "backfill" if args.backfill else "weekly"
    today = dt.date.today().isoformat()

    ingest_stats = ingest_new_posts(run_type=run_type)
    classify_stats = classify_pending_posts()

    log_lines = [
        f"# Run log — {today} ({run_type})",
        "",
        f"- Competitors scraped: {ingest_stats['competitors_scraped']}",
        f"- New posts added: {ingest_stats['posts_added']}",
        f"- Duplicate posts skipped: {ingest_stats['posts_skipped_duplicate']}",
        f"- Posts categorized this run: {classify_stats['classified']} (classification errors: {classify_stats['errors']})",
        f"- Status: {ingest_stats['status']}",
    ]
    if ingest_stats["errors"]:
        log_lines.append("")
        log_lines.append("## Errors")
        for err in ingest_stats["errors"]:
            log_lines.append(f"- {err}")

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / f"{today}.md").write_text("\n".join(log_lines) + "\n")

    print("\n".join(log_lines))


if __name__ == "__main__":
    main()
