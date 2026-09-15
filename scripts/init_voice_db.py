"""One-time (and safe-to-rerun) setup for the Customer Voice project: creates
the `voice` schema and seeds `voice.brands` from config/voice_brands.yaml.

Also re-runs scripts.init_db first, since two of the competitor brands this
seeds against (Meineke, Tires Plus) were just added to config/competitors.yaml
and need to exist in `competitors` before voice.brands can look up their
competitor_id - then flips is_active=false on those two specifically, so
they don't get swept into the existing weekly messaging scrape (Instagram,
ads, etc.), which nobody asked for; they exist here only for the review-side
brand join.

Run with:  python -m scripts.init_voice_db
"""
import pathlib

import yaml

from db.connection import get_conn
from scripts import init_db

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Brands added to competitors.yaml solely for this project's FK join, not
# for messaging tracking - see the notes on their entries in that file.
_VOICE_ONLY_COMPETITOR_NAMES = ["Meineke", "Tires Plus"]


def run():
    # Ensures Meineke/Tires Plus (and anything else added to
    # config/competitors.yaml) exist before the lookup below.
    init_db.run()

    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE competitors SET is_active = FALSE WHERE name = ANY(%s)",
                (_VOICE_ONLY_COMPETITOR_NAMES,),
            )

        with conn.cursor() as cur:
            cur.execute((ROOT / "db" / "voice_schema.sql").read_text())

        brands = yaml.safe_load((ROOT / "config" / "voice_brands.yaml").read_text()) or []
        unmatched_competitor_names = []
        with conn.cursor() as cur:
            for brand in brands:
                competitor_id = None
                competitor_name = brand.get("competitor_name")
                if competitor_name:
                    cur.execute("SELECT id FROM competitors WHERE name = %s", (competitor_name,))
                    row = cur.fetchone()
                    if row:
                        competitor_id = row[0]
                    else:
                        unmatched_competitor_names.append((brand["name"], competitor_name))

                cur.execute(
                    """INSERT INTO voice.brands (name, family, competitor_id, aliases)
                       VALUES (%(name)s, %(family)s, %(competitor_id)s, %(aliases)s)
                       ON CONFLICT (name) DO UPDATE
                           SET family = EXCLUDED.family, competitor_id = EXCLUDED.competitor_id,
                               aliases = EXCLUDED.aliases""",
                    {
                        "name": brand["name"], "family": brand["family"],
                        "competitor_id": competitor_id, "aliases": brand.get("aliases", []),
                    },
                )

    if unmatched_competitor_names:
        print("WARNING: competitor_name not found in `competitors` table (competitor_id left null):")
        for brand_name, competitor_name in unmatched_competitor_names:
            print(f"  - {brand_name!r} -> {competitor_name!r}")

    print(f"Seeded voice schema with {len(brands)} brands.")


if __name__ == "__main__":
    run()
