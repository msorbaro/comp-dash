"""Resolves which states a Customer Voice run should cover, from
config/voice_pilot_states.yaml plus optional --states/--batch overrides.

Shared by scripts/run_voice_phase1and2.py (Google census) and
scripts/run_voice_apple_maps.py, which both need the same resolution and
the same validation - an unrecognized state code silently doing nothing is
the kind of thing that wastes a batch's worth of Apify credits.
"""
from __future__ import annotations

import argparse
import pathlib

import yaml

from voice.us_states import STATE_NAME_BY_CODE

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "voice_pilot_states.yaml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def add_scope_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--states",
        help="Comma-separated USPS codes to run, e.g. NY,NJ,PA. Overrides the config's active_states.",
    )
    group.add_argument(
        "--batch",
        help="Named batch from the config's rollout_batches (e.g. northeast).",
    )


def resolve_states(args: argparse.Namespace) -> list:
    """--states wins, then --batch, then the config's active_states (falling
    back to the older pilot_states key). Always validated against the real
    USPS code list, and de-duplicated with order preserved."""
    config = load_config()

    if getattr(args, "states", None):
        codes = [s.strip().upper() for s in args.states.split(",") if s.strip()]
        source = "--states"
    elif getattr(args, "batch", None):
        batches = config.get("rollout_batches") or {}
        if args.batch not in batches:
            raise SystemExit(
                f"Unknown batch {args.batch!r}. Available: {', '.join(sorted(batches))}"
            )
        codes = list(batches[args.batch])
        source = f"--batch {args.batch}"
    else:
        codes = list(config.get("active_states") or config.get("pilot_states") or [])
        source = "config active_states"

    unknown = [c for c in codes if c not in STATE_NAME_BY_CODE]
    if unknown:
        raise SystemExit(f"Unrecognized state code(s) from {source}: {', '.join(unknown)}")
    if not codes:
        raise SystemExit(f"No states resolved from {source}.")

    deduped = list(dict.fromkeys(codes))
    print(f"Scope ({source}): {deduped}", flush=True)
    return deduped
