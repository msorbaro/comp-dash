"""Customer Voice - Phase 3 (review scrape + sentiment classification),
scoped to one state (Texas for the pilot). Mirrors
scripts/run_voice_phase1and2.py's report-to-logs/ pattern.

Run with:
    python -m scripts.run_voice_reviews --state TX --limit 20   # cheap validation pull
    python -m scripts.run_voice_reviews --state TX              # full run
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib

from categorize import sentiment
from voice import reviews

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(state: str, limit: int | None, years_back: int):
    print(f"Scraping reviews for state={state} (last {years_back} years, limit={limit or 'none'})", flush=True)
    scrape_report = reviews.run(state, years_back=years_back, limit=limit)

    print("Classifying sentiment for every pending review...", flush=True)
    sentiment_report = sentiment.classify_pending()

    today = dt.date.today().isoformat()
    lines = [
        f"# Customer Voice - Phase 3 (reviews) run - {today} - state={state}",
        "",
        "## Scrape",
        f"- Locations processed: {scrape_report['n_locations']}",
        f"- Reviews written: {scrape_report['n_reviews_written']}",
        f"- Batches skipped (already done): {scrape_report['batches_skipped']}",
        f"- Failed batches: {len(scrape_report['failed_batches'])}",
    ]
    if scrape_report["failed_batches"]:
        lines.append("  Re-run to retry - failed batches are not marked done, so a re-run retries only these.")

    lines += [
        "",
        "## Sentiment classification",
        f"- Reviews classified this run: {sentiment_report['n_pending']}",
        f"  - Rating-only (no text, rule-based): {sentiment_report['n_rating_only']}",
        f"  - LLM-classified: {sentiment_report['n_llm_classified']}",
        f"  - LLM classification failures: {sentiment_report['n_llm_failed']}",
    ]

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    (logs_dir / f"voice-phase3-reviews-{today}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--limit", type=int, default=None, help="Cap on locations processed (validation runs)")
    parser.add_argument("--years-back", type=int, default=2)
    args = parser.parse_args()
    run(args.state, args.limit, args.years_back)
