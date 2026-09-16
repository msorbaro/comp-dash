"""One-time (re-runnable) backfill of voice.town_boundaries, for the map's
county -> town drill-down (an actual colored polygon per town, matching the
state -> county map, not just a list).

Geometry comes from the real US Census TIGER Places dataset (2019), already
converted to per-city GeoJSON files by a public, MIT... actually GPL-3.0
mirror (generalpiston/geojson-us-city-boundaries on GitHub) - not drawn or
approximated. A town whose name doesn't match a file in that mirror is left
out and logged, never guessed at.

The mirror's own splitting convention (see its split.py) is simply
`name.lower().replace(' ', '-')` - applied here the same way to our own
`city` values, which are already clean single names (no parens/commas to
strip, unlike the raw Census NAME field this mirror was built from).

Run with:  python -m scripts.backfill_town_boundaries
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from db.connection import get_conn

BASE_URL = "https://raw.githubusercontent.com/generalpiston/geojson-us-city-boundaries/master/cities"
MAX_WORKERS = 8


def slugify(city: str) -> str:
    return city.strip().lower().replace(" ", "-")


def fetch_one(state: str, city: str):
    url = f"{BASE_URL}/{state.lower()}/{slugify(city)}.json"
    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException as e:
        return state, city, None, f"request error: {e}"
    if resp.status_code == 404:
        return state, city, None, "no matching Census place"
    if resp.status_code != 200:
        return state, city, None, f"HTTP {resp.status_code}"
    try:
        gj = resp.json()
        features = gj.get("features") or []
        if not features:
            return state, city, None, "empty FeatureCollection"
        geometry = features[0]["geometry"]
    except (ValueError, KeyError) as e:
        return state, city, None, f"parse error: {e}"
    return state, city, geometry, None


def run():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT state, city FROM voice.locations
                WHERE country_code = 'US' AND city IS NOT NULL AND county_fips IS NOT NULL
                ORDER BY state, city
            """)
            pairs = cur.fetchall()

    print(f"Fetching town boundaries for {len(pairs)} (state, city) pairs...")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = [pool.submit(fetch_one, state, city) for state, city in pairs]
        for i, fut in enumerate(as_completed(futures), 1):
            results.append(fut.result())
            if i % 100 == 0:
                print(f"  [{i}/{len(pairs)}]")

    matched = [(s, c, g) for s, c, g, err in results if g is not None]
    unmatched = [(s, c, err) for s, c, g, err in results if g is None]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO voice.town_boundaries (state, city, geometry)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (state, city) DO UPDATE SET geometry = EXCLUDED.geometry, fetched_at = now()""",
                [(s, c, json.dumps(g)) for s, c, g in matched],
            )
        conn.commit()

    print(f"Matched and stored: {len(matched)}")
    print(f"No match (left out, not guessed): {len(unmatched)}")
    if unmatched:
        print("Unmatched towns:")
        for s, c, err in sorted(unmatched):
            print(f"  {s} / {c}: {err}")


if __name__ == "__main__":
    run()
