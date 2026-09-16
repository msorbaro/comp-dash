"""Rebuilds the Customer Voice metrics layer (Phase 4) - the 4 materialized
views in db/voice_metrics.sql, with config/voice_metrics.yaml's values
substituted in. Safe to re-run any time voice.rating_snapshots changes
(a fresh Phase 1/2 pull) or the metrics config changes - views don't
auto-refresh, this is the only thing that rebuilds them.

Run with:  python -m scripts.refresh_voice_metrics
"""
import pathlib

import yaml

from db.connection import get_conn

ROOT = pathlib.Path(__file__).resolve().parent.parent
MILES_TO_KM = 1.609344


def run():
    config = yaml.safe_load((ROOT / "config" / "voice_metrics.yaml").read_text())
    template = (ROOT / "db" / "voice_metrics.sql").read_text()
    sql = template.format(
        shrinkage_m=config["shrinkage_m"],
        ring_radius_km=config["ring_radius_miles"] * MILES_TO_KM,
        min_locations_for_state=config["min_locations_for_state"],
        min_reviews_for_state=config["min_reviews_for_state"],
        min_locations_for_town=config["min_locations_for_town"],
        min_reviews_for_town=config["min_reviews_for_town"],
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM voice.location_adjusted_ratings")
            n_locations = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.location_benchmark")
            n_benchmarked = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.state_delta")
            n_states = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.state_delta WHERE NOT suppressed")
            n_states_visible = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.town_delta")
            n_towns = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.town_delta WHERE NOT suppressed")
            n_towns_visible = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.brand_state_delta")
            n_brand_states = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.county_delta")
            n_counties = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.county_delta WHERE NOT suppressed")
            n_counties_visible = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM voice.county_town_delta")
            n_county_towns = cur.fetchone()[0]

    print(f"Rebuilt with shrinkage_m={config['shrinkage_m']}, "
          f"ring_radius_miles={config['ring_radius_miles']}, "
          f"min_locations_for_state={config['min_locations_for_state']}, "
          f"min_reviews_for_state={config['min_reviews_for_state']}, "
          f"min_locations_for_town={config['min_locations_for_town']}, "
          f"min_reviews_for_town={config['min_reviews_for_town']}")
    print(f"location_adjusted_ratings: {n_locations} locations with a rating")
    print(f"location_benchmark: {n_benchmarked} Mavis locations benchmarked")
    print(f"state_delta: {n_states} states with data, {n_states_visible} pass the suppression threshold")
    print(f"town_delta: {n_towns} towns with data, {n_towns_visible} pass the suppression threshold")
    print(f"county_delta: {n_counties} counties with data, {n_counties_visible} pass the suppression threshold")
    print(f"county_town_delta: {n_county_towns} (county, town) rows")
    print(f"brand_state_delta: {n_brand_states} (state, brand) rows")


if __name__ == "__main__":
    run()
