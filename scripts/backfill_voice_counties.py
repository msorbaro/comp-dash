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
STATES_TOPOLOGY_URL = "https://unpkg.com/us-atlas@3.0.1/states-10m.json"


def load_best_county_per_zip() -> dict:
    """zip -> (county_fips, usps_state). The state comes along because it's
    the authoritative answer to "which state is this store actually in" -
    see run()'s state-correction step for why that matters."""
    best: dict[str, tuple[str, str, float]] = {}
    with open(CROSSWALK_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            zip_code = row["ZIP"].strip()
            county_fips = row["COUNTY"].strip()
            state = (row.get("USPS_ZIP_PREF_STATE") or "").strip()
            ratio = float(row["TOT_RATIO"] or 0)
            current = best.get(zip_code)
            if current is None or ratio > current[2]:
                best[zip_code] = (county_fips, state, ratio)
    return {z: (fips, state) for z, (fips, state, _ratio) in best.items()}


def load_county_names() -> dict:
    import json

    with urllib.request.urlopen(COUNTIES_TOPOLOGY_URL) as resp:
        topology = json.load(resp)
    return {
        g["id"]: g["properties"]["name"]
        for g in topology["objects"]["counties"]["geometries"]
    }


def load_state_by_fips() -> dict:
    """2-digit state FIPS -> USPS code, from the same us-atlas source the
    county names come from, so a county's FIPS always implies exactly one
    state."""
    import json

    from voice.us_states import STATE_CODE_BY_NAME

    with urllib.request.urlopen(STATES_TOPOLOGY_URL) as resp:
        topology = json.load(resp)
    out = {}
    for g in topology["objects"]["states"]["geometries"]:
        code = STATE_CODE_BY_NAME.get(g["properties"]["name"])
        if code:
            out[str(g["id"]).zfill(2)] = code
    return out


def run():
    print("Loading ZIP-COUNTY crosswalk...")
    zip_to_fips = load_best_county_per_zip()
    print(f"  {len(zip_to_fips)} zips in crosswalk")

    print("Loading county names from us-atlas topology...")
    fips_to_name = load_county_names()
    print(f"  {len(fips_to_name)} counties")

    state_by_fips = load_state_by_fips()
    print(f"  {len(state_by_fips)} state FIPS prefixes")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT location_id, zip, state FROM voice.locations
                WHERE country_code = 'US' AND zip IS NOT NULL
            """)
            locations = cur.fetchall()

    print(f"Attributing county for {len(locations)} US locations with a zip...")
    updates = []
    n_no_match = 0
    # Also forces `state` to agree with the assigned county's own FIPS.
    # voice/places.py used to stamp every place with the state it was
    # SEARCHED in, and the actor legitimately returns border results from the
    # next state over - so e.g. a Killeen TX store found in an Oklahoma
    # search was stored as OK, then got its real county here, producing
    # "Tulsa County, FL"-style rows. Those broke county_delta's
    # UNIQUE (county_fips, source) index and blocked every metrics refresh.
    #
    # Deriving state from county_fips (not from the zip's USPS state) is what
    # makes that impossible by construction: the map rolls up by county, so a
    # county must imply exactly one state. The zip's USPS state is NOT always
    # consistent with its county - zip 42223 (Fort Campbell) is USPS "KY"
    # while the crosswalk maps it to Montgomery County, TN, because the base
    # straddles the line. Following the county keeps that location in the
    # same state as the county it rolls up into.
    state_fixes = []
    for location_id, zip_code, current_state in locations:
        zip_clean = (zip_code or "").strip()[:5].zfill(5)
        entry = zip_to_fips.get(zip_clean)
        if entry is None:
            n_no_match += 1
            continue
        fips, _usps_state = entry
        name = fips_to_name.get(fips)
        if name is None:
            n_no_match += 1
            continue
        updates.append((fips, name, location_id))
        county_state = state_by_fips.get(fips[:2])
        if county_state and current_state and county_state != current_state:
            state_fixes.append((county_state, current_state, location_id))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE voice.locations SET county_fips = %s, county_name = %s WHERE location_id = %s",
                updates,
            )
            if state_fixes:
                cur.executemany(
                    "UPDATE voice.locations SET state = %s WHERE location_id = %s",
                    [(true_state, lid) for true_state, _old, lid in state_fixes],
                )
        conn.commit()

    print(f"Updated {len(updates)} locations with county_fips/county_name")
    print(f"No crosswalk match (left NULL, not guessed): {n_no_match}")
    if state_fixes:
        from collections import Counter
        moves = Counter((old, new) for new, old, _lid in state_fixes)
        print(f"Corrected `state` on {len(state_fixes)} location(s) to match their zip's real state:")
        for (old, new), n in moves.most_common():
            print(f"  {old} -> {new}: {n}")


if __name__ == "__main__":
    run()
