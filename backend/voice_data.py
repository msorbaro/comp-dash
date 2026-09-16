"""Customer Voice - a thin query layer over the voice schema's materialized
views (see db/voice_metrics.sql), mirroring signal_data.py's role for the
messaging side. Every function here is a direct SELECT off an already-
computed view - no Python-side recomputation of the metrics themselves, so
the API stays an honest pass-through of the same SQL the user can run
directly in Supabase Studio, not a second implementation of the math.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from urllib.parse import urlparse

from db.connection import get_conn
from voice.us_states import STATE_NAME_BY_CODE

# Mirrors backend/main.py's LOGO_OVERRIDES - same brand, same broken favicon.
# Duplicated rather than imported to avoid a circular import (main.py already
# imports this module).
LOGO_OVERRIDES = {"Tire Kingdom": None}


def _favicon_url(brand_name: str, website_url: str | None) -> str | None:
    """Same derivation as main.py's _logo_url - there's no logo asset
    pipeline in this app, so a brand mark comes from its own website favicon
    via Google's public favicon service (no API key, no scraping)."""
    if brand_name in LOGO_OVERRIDES:
        return LOGO_OVERRIDES[brand_name]
    if not website_url:
        return None
    domain = urlparse(website_url).netloc
    return f"https://www.google.com/s2/favicons?sz=64&domain={domain}" if domain else None


def state_summary() -> list:
    """All 50 states (+ DC), left-joined to voice.state_delta so states
    with no pilot data at all come back with null fields - distinguished
    from a state that HAS data but is suppressed for being too small."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sd.state, sd.n_mavis_locations, sd.total_mavis_reviews, sd.n_low_comparability_locations,
                       sd.avg_mavis_adj_rating, sd.state_delta, sd.avg_comp_benchmark_rating, sd.suppressed
                FROM voice.state_delta sd
            """)
            by_state = {row[0]: row for row in cur.fetchall()}

    out = []
    for code, name in STATE_NAME_BY_CODE.items():
        if code == "DC":
            continue
        row = by_state.get(code)
        if row:
            _, n_locations, total_reviews, n_low_comp, mavis_rating, delta, comp_rating, suppressed = row
            out.append({
                "state": code, "state_name": name, "has_data": True,
                "n_mavis_locations": n_locations, "total_mavis_reviews": total_reviews,
                "n_low_comparability_locations": n_low_comp,
                "mavis_rating": float(mavis_rating) if mavis_rating is not None else None,
                "delta": float(delta) if delta is not None else None,
                "comp_rating": float(comp_rating) if comp_rating is not None else None,
                "suppressed": suppressed,
            })
        else:
            out.append({
                "state": code, "state_name": name, "has_data": False,
                "n_mavis_locations": 0, "total_mavis_reviews": 0, "n_low_comparability_locations": 0,
                "mavis_rating": None, "delta": None, "comp_rating": None, "suppressed": True,
            })
    return out


def brand_state_summary(state: str) -> list:
    """Per-Mavis-banner rollup within one state - e.g. how Midas alone
    compares to local competitors, distinct from the whole-portfolio number
    state_summary() gives."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_name, n_mavis_locations, total_mavis_reviews, n_low_comparability_locations,
                       avg_mavis_adj_rating, state_delta, avg_comp_benchmark_rating, suppressed
                FROM voice.brand_state_delta
                WHERE state = %s
                ORDER BY state_delta DESC NULLS LAST
            """, (state,))
            rows = cur.fetchall()
    return [
        {
            "brand": brand, "n_mavis_locations": n_locations, "total_mavis_reviews": total_reviews,
            "n_low_comparability_locations": n_low_comp,
            "mavis_rating": float(mavis_rating) if mavis_rating is not None else None,
            "delta": float(delta) if delta is not None else None,
            "comp_rating": float(comp_rating) if comp_rating is not None else None,
            "suppressed": suppressed,
        }
        for brand, n_locations, total_reviews, n_low_comp, mavis_rating, delta, comp_rating, suppressed in rows
    ]


def town_summary(state: str) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT city, n_mavis_locations, total_mavis_reviews, n_low_comparability_locations,
                       avg_mavis_adj_rating, town_delta, avg_comp_benchmark_rating, suppressed
                FROM voice.town_delta
                WHERE state = %s
                ORDER BY town_delta DESC NULLS LAST
            """, (state,))
            rows = cur.fetchall()
    return [
        {
            "city": city, "n_mavis_locations": n_locations, "total_mavis_reviews": total_reviews,
            "n_low_comparability_locations": n_low_comp,
            "mavis_rating": float(mavis_rating) if mavis_rating is not None else None,
            "delta": float(delta) if delta is not None else None,
            "comp_rating": float(comp_rating) if comp_rating is not None else None,
            "suppressed": suppressed,
        }
        for city, n_locations, total_reviews, n_low_comp, mavis_rating, delta, comp_rating, suppressed in rows
    ]


def county_summary(state: str) -> list:
    """Same shape as town_summary(), grouped by county (from the HUD ZIP-COUNTY
    crosswalk backfill) instead of city - the map's state -> county drill."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT county_fips, county_name, n_mavis_locations, total_mavis_reviews, n_low_comparability_locations,
                       avg_mavis_adj_rating, county_delta, avg_comp_benchmark_rating, suppressed
                FROM voice.county_delta
                WHERE state = %s
                ORDER BY county_delta DESC NULLS LAST
            """, (state,))
            rows = cur.fetchall()
    return [
        {
            "county_fips": fips, "county_name": name, "n_mavis_locations": n_locations,
            "total_mavis_reviews": total_reviews, "n_low_comparability_locations": n_low_comp,
            "mavis_rating": float(mavis_rating) if mavis_rating is not None else None,
            "delta": float(delta) if delta is not None else None,
            "comp_rating": float(comp_rating) if comp_rating is not None else None,
            "suppressed": suppressed,
        }
        for fips, name, n_locations, total_reviews, n_low_comp, mavis_rating, delta, comp_rating, suppressed in rows
    ]


def county_town_summary(state: str, county_fips: str) -> list:
    """Towns within one county - the map's county -> town drill, one level
    deeper than county_summary(). Scoped to a single county (not state-wide
    like town_summary()) since the same town name can exist in different
    counties."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT city, n_mavis_locations, total_mavis_reviews, n_low_comparability_locations,
                       avg_mavis_adj_rating, town_delta, avg_comp_benchmark_rating, suppressed
                FROM voice.county_town_delta
                WHERE state = %(state)s AND county_fips = %(county_fips)s
                ORDER BY town_delta DESC NULLS LAST
            """, {"state": state, "county_fips": county_fips})
            rows = cur.fetchall()
    return [
        {
            "city": city, "n_mavis_locations": n_locations, "total_mavis_reviews": total_reviews,
            "n_low_comparability_locations": n_low_comp,
            "mavis_rating": float(mavis_rating) if mavis_rating is not None else None,
            "delta": float(delta) if delta is not None else None,
            "comp_rating": float(comp_rating) if comp_rating is not None else None,
            "suppressed": suppressed,
        }
        for city, n_locations, total_reviews, n_low_comp, mavis_rating, delta, comp_rating, suppressed in rows
    ]


def county_locations(state: str, county_fips: str, city: str = None) -> list:
    """Every rated location (Mavis AND competitor) in one county, optionally
    narrowed to one town within it - for the map's store-marker view. Unlike
    store_summary() (Mavis only, joined through location_benchmark), this
    pulls straight from location_adjusted_ratings so competitor pins show up
    too. Mavis rows also carry delta/low_comparability (left-joined from
    location_benchmark, NULL for competitors - a competitor has no "delta
    vs its neighbors")."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT lar.location_id, lar.brand_name, lar.family, lar.location_name, lar.city,
                       lar.lat, lar.lng, lar.raw_rating, lar.adj_rating, lar.n,
                       c.website_url,
                       lb.delta, lb.low_comparability, lb.comp_benchmark_rating, lb.n_competitors_in_ring
                FROM voice.location_adjusted_ratings lar
                JOIN voice.brands vb ON vb.brand_id = lar.brand_id
                LEFT JOIN competitors c ON c.id = vb.competitor_id
                LEFT JOIN voice.location_benchmark lb ON lb.location_id = lar.location_id
                WHERE lar.state = %(state)s AND lar.county_fips = %(county_fips)s
                  AND (%(city)s::text IS NULL OR lar.city = %(city)s::text)
                ORDER BY lar.family, lar.brand_name, lar.location_name
            """, {"state": state, "county_fips": county_fips, "city": city})
            rows = cur.fetchall()
    return [
        {
            "location_id": location_id, "brand": brand, "family": family, "name": name, "city": city,
            "lat": float(lat) if lat is not None else None, "lng": float(lng) if lng is not None else None,
            "raw_rating": float(raw_rating) if raw_rating is not None else None,
            "adj_rating": float(adj_rating) if adj_rating is not None else None,
            "review_count": n,
            "logo_url": _favicon_url(brand, website_url),
            "delta": float(delta) if delta is not None else None,
            "low_comparability": low_comp,
            "comp_benchmark_rating": float(comp_rating) if comp_rating is not None else None,
            "n_competitors_in_ring": n_ring,
        }
        for location_id, brand, family, name, city, lat, lng, raw_rating, adj_rating, n,
            website_url, delta, low_comp, comp_rating, n_ring in rows
    ]


def store_summary(state: str, city: str = None, county_fips: str = None) -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT location_name, brand_name, city, state, lat, lng,
                       mavis_adj_rating, mavis_raw_rating, mavis_n,
                       comp_benchmark_rating, comp_total_reviews, n_competitors_in_ring,
                       delta, low_comparability
                FROM voice.location_benchmark
                WHERE state = %(state)s
                  AND (%(city)s::text IS NULL OR city = %(city)s::text)
                  AND (%(county_fips)s::text IS NULL OR county_fips = %(county_fips)s::text)
                ORDER BY delta DESC NULLS LAST
            """, {"state": state, "city": city, "county_fips": county_fips})
            rows = cur.fetchall()
    return [
        {
            "name": name, "brand": brand, "city": city, "state": state, "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "mavis_adj_rating": float(mavis_adj) if mavis_adj is not None else None,
            "mavis_raw_rating": float(mavis_raw) if mavis_raw is not None else None,
            "mavis_review_count": mavis_n,
            "comp_benchmark_rating": float(comp_rating) if comp_rating is not None else None,
            "comp_review_count": comp_reviews, "n_competitors_in_ring": n_ring,
            "delta": float(delta) if delta is not None else None,
            "low_comparability": low_comp,
        }
        for name, brand, city, state, lat, lng, mavis_adj, mavis_raw, mavis_n,
            comp_rating, comp_reviews, n_ring, delta, low_comp in rows
    ]
