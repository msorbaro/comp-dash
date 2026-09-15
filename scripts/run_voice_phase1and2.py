"""Customer Voice - Phases 1 & 2 only (location census + ratings census),
per the user's explicit "do phases 1 and 2 first and stop" instruction.
Prints exactly what was asked to review before any further phase or
additional Apify spend: per-brand location counts by state, and the list of
place names that couldn't be confidently matched to a brand.

Run with:  python -m scripts.run_voice_phase1and2
"""
import datetime as dt
import pathlib

import yaml

from voice import places, ratings

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run():
    pilot_states = yaml.safe_load(
        (ROOT / "config" / "voice_pilot_states.yaml").read_text()
    )["pilot_states"]

    print(f"Running Phase 1 (locations) + Phase 2 (ratings) for states: {pilot_states}", flush=True)
    report = places.run(pilot_states)
    rating_stats = ratings.write_snapshots(report["rating_rows"])

    today = dt.date.today().isoformat()
    lines = [f"# Customer Voice - Phase 1 & 2 run - {today}", ""]

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
    (logs_dir / f"voice-phase1and2-{today}.md").write_text("\n".join(lines) + "\n")

    print("\n".join(lines))


if __name__ == "__main__":
    run()
