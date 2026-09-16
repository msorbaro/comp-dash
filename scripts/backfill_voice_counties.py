"""One-time (re-runnable) backfill of voice.locations.county_fips/county_name,
for the map's state -> county -> store drill-down.

County is derived from each location's own zip via the HUD USPS ZIP-COUNTY
crosswalk (data/zip_county_crosswalk.csv - the real government file, not a
custom geocode) - a zip can span multiple counties, so we take the county
with the highest TOT_RATIO (the crosswalk's own "which county does most of
this zip's addresses" weighting), same convention HUD's own docs recommend
for a single best-guess county per zip. County *names* come from the same
us-atlas county topology already used to render the map, so the FIPS code
this script writes always matches a name the map can render - fetched once
into an in-memory dict, not stored as a repo dependency.

A zip with no crosswalk match is left NULL and logged - never guessed.

Run with:  python -m scripts.backfill_voice_counties
"""
import csv
import pathlib
import urllib.request

from db.connection import get_conn

ROOT = pathlib.Path(__file__).resolve().parent.parent
CROSSWALK_PATH = ROOT / "data" / "zip_county_crosswalk.csv"
COUNTIES_TOPOLOGY_URL = "https://unpkg.com/us-atlas@3.0.1/counties-10m.json"


def load_best_county_per_zip() -> dict:
    best: dict[str, tuple[str, float]] = {}
    with open(CROSSWALK_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            zip_code = row["ZIP"].strip()
            county_fips = row["COUNTY"].strip()
            ratio = float(row["TOT_RATIO"] or 0)
            current = best.get(zip_code)
            if current is None or ratio > current[1]:
                best[zip_code] = (county_fips, ratio)
    return {z: fips for z, (fips, _ratio) in best.items()}


def load_county_names() -> dict:
    import json

    with urllib.request.urlopen(COUNTIES_TOPOLOGY_URL) as resp:
        topology = json.load(resp)
    return {
        g["id"]: g["properties"]["name"]
        for g in topology["objects"]["counties"]["geometries"]
    }


def run():
    print("Loading ZIP-COUNTY crosswalk...")
    zip_to_fips = load_best_county_per_zip()
    print(f"  {len(zip_to_fips)} zips in crosswalk")

    print("Loading county names from us-atlas topology...")
    fips_to_name = load_county_names()
    print(f"  {len(fips_to_name)} counties")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT location_id, zip FROM voice.locations
                WHERE country_code = 'US' AND zip IS NOT NULL
            """)
            locations = cur.fetchall()

    print(f"Attributing county for {len(locations)} US locations with a zip...")
    updates = []
    n_no_match = 0
    for location_id, zip_code in locations:
        zip_clean = (zip_code or "").strip()[:5].zfill(5)
        fips = zip_to_fips.get(zip_clean)
        name = fips_to_name.get(fips) if fips else None
        if fips is None or name is None:
            n_no_match += 1
            continue
        updates.append((fips, name, location_id))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE voice.locations SET county_fips = %s, county_name = %s WHERE location_id = %s",
                updates,
            )
        conn.commit()

    print(f"Updated {len(updates)} locations with county_fips/county_name")
    print(f"No crosswalk match (left NULL, not guessed): {n_no_match}")


if __name__ == "__main__":
    run()
