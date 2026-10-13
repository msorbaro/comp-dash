"""Customer Voice - Apple Maps aggregate ratings, per state.

voice/apple_maps_ratings.py existed with no runner at all (it had only ever
been driven ad-hoc), which is why only TX ever got Apple Maps coverage
while the Google census had reached 5 states.

Reads from voice.locations, so a state must have had its Google census run
FIRST (scripts/run_voice_phase1and2.py) - there are no (brand, city) groups
to search for otherwise, and this will just report zero work to do.

Cost warning: this calls the Apify actor once per (brand, city) group, not
once per state. TX alone was 991 groups. Always --estimate first; that
reads straight from the DB and spends nothing.

Run with:
  python -m scripts.run_voice_apple_maps --batch northeast --estimate
  python -m scripts.run_voice_apple_maps --batch northeast
  python -m scripts.run_voice_apple_maps --states NY,NJ --limit 25
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib

from db.connection import get_conn
from voice import apple_maps_ratings
from voice.scope import add_scope_args, resolve_states

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _pending_groups(state: str) -> dict:
    """How many (brand, city) actor calls this state would cost right now,
    without spending anything - same grouping and same already-done filter
    voice.apple_maps_ratings.run() applies internally."""
    groups = apple_maps_ratings._locations_by_brand_city(state)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT brand_id, city FROM voice.apple_maps_rating_runs WHERE state = %s",
                (state,),
            )
            already_done = {(bid, city) for bid, city in cur.fetchall()}
    pending = {k: v for k, v in groups.items() if (k[0], k[3]) not in already_done}
    return {
        "n_groups": len(groups),
        "n_pending": len(pending),
        "n_locations_pending": sum(len(v) for v in pending.values()),
    }


def estimate(states: list) -> None:
    print("\nApple Maps cost estimate (1 Apify actor run per pending group):\n", flush=True)
    total_pending = 0
    total_locations = 0
    for state in states:
        stats = _pending_groups(state)
        total_pending += stats["n_pending"]
        total_locations += stats["n_locations_pending"]
        note = "" if stats["n_groups"] else "  <- no locations; run the Google census for this state first"
        print(
            f"  {state}: {stats['n_pending']:>5} pending actor runs "
            f"({stats['n_groups']} groups total, "
            f"{stats['n_locations_pending']} locations would get a rating){note}",
            flush=True,
        )
    print(f"\n  TOTAL: {total_pending} actor runs -> up to {total_locations} rated locations\n", flush=True)


def run(states=None, limit=None, do_estimate=False):
    if states is None:
        parser = argparse.ArgumentParser(description="Customer Voice Apple Maps ratings")
        add_scope_args(parser)
        parser.add_argument(
            "--estimate", action="store_true",
            help="Report how many actor runs this scope would cost, then exit without spending.",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Cap (brand, city) groups per state - useful for a cheap sanity check on a new state.",
        )
        args = parser.parse_args()
        states = resolve_states(args)
        limit, do_estimate = args.limit, args.estimate

    if do_estimate:
        estimate(states)
        return

    today = dt.date.today().isoformat()
    lines = [f"# Customer Voice - Apple Maps ratings - {today}", f"States: {', '.join(states)}", ""]
    grand_written = 0

    for state in states:
        print(f"\n=== Apple Maps: {state} ===", flush=True)
        report = apple_maps_ratings.run(state, limit=limit)
        grand_written += report["n_written"]
        lines.append(
            f"- **{state}**: {report['n_written']} ratings written across "
            f"{report['n_groups']} (brand, city) groups "
            f"({report['groups_skipped']} skipped as already done, "
            f"{len(report['unmatched_location_ids'])} locations unmatched)"
        )
        print(
            f"{state}: wrote {report['n_written']} ratings, "
            f"{len(report['unmatched_location_ids'])} unmatched",
            flush=True,
        )

    lines.append("")
    lines.append(f"## Total Apple Maps ratings written: {grand_written}")

    logs_dir = ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    scope_slug = "-".join(states) if len(states) <= 6 else f"{len(states)}states"
    (logs_dir / f"voice-apple-maps-{today}-{scope_slug}.md").write_text("\n".join(lines) + "\n")

    print("\n".join(lines))
    print("\nNext: python -m scripts.refresh_voice_metrics", flush=True)


if __name__ == "__main__":
    run()
