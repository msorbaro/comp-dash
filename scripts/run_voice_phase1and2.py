"""Customer Voice - Phases 1 & 2 only (location census + ratings census),
per the user's explicit "do phases 1 and 2 first and stop" instruction.
Prints exactly what was asked to review before any further phase or
additional Apify spend: per-brand location counts by state, and the list of
place names that couldn't be confidently matched to a brand.

Google Maps ratings (totalScore/reviewsCount) come back on the same actor
call as the location census, so this one run covers both phases for a
state - there's no separate Google ratings pass to run afterwards. Apple
Maps is a separate, much more expensive pass; see
scripts/run_voice_apple_maps.py.

Costs ~21 Apify actor runs per state (one per brand). Already-completed
(brand, state) combos are skipped via voice.location_census_runs, so
re-running after expanding the scope only pays for what's new.

Run with:  python -m scripts.run_voice_phase1and2                 # config scope
           python -m scripts.run_voice_phase1and2 --batch northeast
           python -m scripts.run_voice_phase1and2 --states NY,NJ,PA
"""
import argparse
import datetime as dt
import pathlib

from voice import places
from voice.scope import add_scope_args, resolve_states

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(states=None):
    if states is None:
        parser = argparse.ArgumentParser(description="Customer Voice Phase 1+2 (Google census)")
        add_scope_args(parser)
        states = resolve_states(parser.parse_args())
    pilot_states = states

    print(f"Running Phase 1 (locations) + Phase 2 (ratings) for states: {pilot_states}", flush=True)
    report = places.run(pilot_states)
    # Ratings are written inline per-combo by voice.places._process_one, in
    # the same transaction as the location upsert - report["rating_rows"]
    # is just the tally for this summary, not something left to write here.
    rating_stats = {
        "written": len(report["rating_rows"]),
        "null_rating": sum(1 for _loc_id, avg, _cnt in report["rating_rows"] if avg is None),
    }

    today = dt.date.today().isoformat()
    lines = [
        f"# Customer Voice - Phase 1 & 2 run - {today}",
        f"States: {', '.join(pilot_states)}",
        "",
    ]

    lines.append("## Location counts by brand x state")
    failed_combos = []
    brand_names = sorted({b for b, _s in report["counts"]})
    for brand in brand_names:
        row_counts = {s: report["counts"].get((brand, s)) for s in pilot_states}
        for s, n in row_counts.items():
            if n is None:
                failed_combos.append((brand, s))
        total = sum(n for n in row_counts.values() if n is not None)
        rendered = ", ".join(f"{s}={'FAILED' if n is None else n}" for s, n in row_counts.items())
        lines.append(f"- **{brand}** (total {total}): {rendered}")

    if failed_combos:
        lines.append("")
        lines.append(f"## Failed combos ({len(failed_combos)}) - re-run these specifically, not the whole pilot")
        for brand, state in failed_combos:
            lines.append(f"- {brand} / {state}")

    lines.append("")
    lines.append("## Category-filter drops by brand (non-automotive places excluded)")
    for brand, n in sorted(report["category_drops"].items(), key=lambda kv: -kv[1]):
        if n:
            lines.append(f"- {brand}: {n} dropped")

    lines.append("")
    lines.append(f"## Non-US places dropped: {report['non_us_dropped']}")

    lines.append("")
    lines.append(f"## Ratings written: {rating_stats['written']} (null rating: {rating_stats['null_rating']})")

    lines.append("")
    lines.append(f"## Unmatched place names ({len(report['unmatched'])}) - review before trusting counts above")
    for brand, state, title, category in report["unmatched"]:
        lines.append(f"- [{brand} / {state}] {title!r} (category: {category})")

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    # States in the filename, not just the date - rolling out east->west
    # means several batches can run on the same day, and the original
    # date-only name made each one clobber the last one's report.
    scope_slug = "-".join(pilot_states) if len(pilot_states) <= 6 else f"{len(pilot_states)}states"
    (logs_dir / f"voice-phase1and2-{today}-{scope_slug}.md").write_text("\n".join(lines) + "\n")

    print("\n".join(lines))


if __name__ == "__main__":
    run()
