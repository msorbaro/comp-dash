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


def list_brands() -> list:
    """Every tracked brand (Mavis banners and named competitors alike), for
    the map's "set a main brand" selector."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT brand_id, name, family FROM voice.brands ORDER BY family, name")
            rows = cur.fetchall()
    return [{"brand_id": bid, "name": name, "family": family} for bid, name, family in rows]


def _locations_for_scope(state: str = None, county_fips: str = None) -> list:
    """Every rated location (any brand), state-wide or narrowed to one
    county - the raw material for the table's "always on" brand dropdown at
    state/county/town level. A live query, not a materialized view (the
    brand is chosen at runtime, same reasoning as the map's main-brand mode)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT state, county_fips, county_name, city, brand_id, n, raw_rating
                FROM voice.location_adjusted_ratings
                WHERE county_fips IS NOT NULL
                  AND (%(state)s::text IS NULL OR state = %(state)s::text)
                  AND (%(county_fips)s::text IS NULL OR county_fips = %(county_fips)s::text)
            """, {"state": state, "county_fips": county_fips})
            rows = cur.fetchall()
    return [
        {"state": s, "county_fips": cf, "county_name": cn, "city": c, "brand_id": bid, "n": n, "raw_rating": float(rr)}
        for s, cf, cn, c, bid, n, rr in rows
    ]


def _weighted_avg(items, value_key, weight_key="n"):
    total_w = sum(i[weight_key] for i in items)
    return sum(i[weight_key] * i[value_key] for i in items) / total_w if total_w else None


def brand_filtered_areas(brand_id: int, group_keys: list, state: str = None, county_fips: str = None) -> list:
    """One row per distinct area (group_keys = ["state"], ["county_fips",
    "county_name"], or ["city"]) where the given brand has a location: its
    own avg rating and avg reviews/store there, the area's own all-brand
    average rating (a benchmark that doesn't shift with which brand is
    selected), and what % of the brand's own locations in that area beat
    it. Works identically for a Mavis banner or a named competitor - unlike
    delta (specifically "Mavis vs. its local competitors"), this is just
    "this brand vs. the area it's in," so it doesn't care which family the
    brand belongs to."""
    all_locs = _locations_for_scope(state, county_fips)
    by_area = {}
    for loc in all_locs:
        by_area.setdefault(tuple(loc[k] for k in group_keys), []).append(loc)

    out = []
    for key, locs in by_area.items():
        brand_locs = [l for l in locs if l["brand_id"] == brand_id]
        if not brand_locs:
            continue
        area_avg = _weighted_avg(locs, "raw_rating")
        n_above = (
            sum(1 for l in brand_locs if area_avg is not None and l["raw_rating"] > area_avg)
            if area_avg is not None else None
        )
        total_reviews = sum(l["n"] for l in brand_locs)
        row = dict(zip(group_keys, key))
        row.update({
            "n_locations": len(brand_locs),
            "total_reviews": total_reviews,
            "avg_reviews_per_store": total_reviews / len(brand_locs),
            "avg_rating": _weighted_avg(brand_locs, "raw_rating"),
            "area_avg_rating": area_avg,
            "pct_above_area_avg": (n_above / len(brand_locs)) if n_above is not None else None,
        })
        out.append(row)
    return out


def brand_filtered_states(brand_id: int) -> list:
    return brand_filtered_areas(brand_id, ["state"])


def brand_filtered_counties(brand_id: int, state: str) -> list:
    return brand_filtered_areas(brand_id, ["county_fips", "county_name"], state=state)


def brand_filtered_towns(brand_id: int, state: str, county_fips: str) -> list:
    return brand_filtered_areas(brand_id, ["city"], state=state, county_fips=county_fips)


def _tier(brand_rating, avg_other, max_other):
    """green: beats every other location in the town (or there's no
    competition at all to lose to). yellow: beats the town average but not
    the best. red: at or below the town average."""
    if max_other is None:
        return "green"
    if brand_rating > max_other:
        return "green"
    if brand_rating > avg_other:
        return "yellow"
    return "red"


def _rollup_tier(child_tiers, green_tiers):
    """County-from-towns and state-from-counties share this same rule (per
    spec): any red child forces red, regardless of how many others are
    green - one bad town/county isn't washed out by an average. Otherwise:
    every child green -> light green, half or more green -> dark green,
    anything else -> yellow. `green_tiers` says which child tier(s) count as
    "green" here - just {"green"} for towns rolling up into a county, but
    {"dark_green", "light_green"} for counties rolling up into a state."""
    if any(t == "red" for t in child_tiers):
        return "red"
    n_green = sum(1 for t in child_tiers if t in green_tiers)
    total = len(child_tiers)
    if n_green == total:
        return "light_green"
    if n_green / total >= 0.5:
        return "dark_green"
    return "yellow"


def _brand_town_ratings(brand_id: int, state: str = None) -> list:
    """One row per town where the given brand has at least one rated
    location - the brand's own weighted-average adj_rating there, and the
    average/best adj_rating of every OTHER brand's location in that same
    town. Everything needed to classify green/yellow/red per spec ("does
    that brand's location beat everyone else / the average / neither").
    A single query regardless of how many states, so main_brand_state_tiers()
    below doesn't need one DB round-trip per state."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH brand_locs AS (
                    SELECT state, county_fips, county_name, city, n, adj_rating
                    FROM voice.location_adjusted_ratings
                    WHERE brand_id = %(brand_id)s AND county_fips IS NOT NULL
                      AND (%(state)s::text IS NULL OR state = %(state)s::text)
                ),
                brand_town AS (
                    SELECT state, county_fips, county_name, city,
                           sum(n * adj_rating) / NULLIF(sum(n), 0) AS brand_rating,
                           sum(n) AS brand_n, count(*) AS n_brand_locations
                    FROM brand_locs
                    GROUP BY state, county_fips, county_name, city
                ),
                other_agg AS (
                    SELECT lar.state, lar.county_fips, lar.city,
                           avg(lar.adj_rating) AS avg_other_rating,
                           max(lar.adj_rating) AS max_other_rating,
                           count(*) AS n_other_locations
                    FROM voice.location_adjusted_ratings lar
                    JOIN (SELECT DISTINCT state, county_fips, city FROM brand_locs) bt
                        ON bt.state = lar.state AND bt.county_fips = lar.county_fips AND bt.city = lar.city
                    WHERE lar.brand_id != %(brand_id)s
                    GROUP BY lar.state, lar.county_fips, lar.city
                )
                SELECT bt.state, bt.county_fips, bt.county_name, bt.city,
                       bt.brand_rating, bt.brand_n, bt.n_brand_locations,
                       o.avg_other_rating, o.max_other_rating, o.n_other_locations
                FROM brand_town bt
                LEFT JOIN other_agg o ON o.state = bt.state AND o.county_fips = bt.county_fips AND o.city = bt.city
            """, {"brand_id": brand_id, "state": state})
            rows = cur.fetchall()
    out = []
    for state_, fips, county_name, city, brand_rating, brand_n, n_brand_locs, avg_other, max_other, n_other in rows:
        if brand_rating is None:
            continue
        brand_rating = float(brand_rating)
        avg_other = float(avg_other) if avg_other is not None else None
        max_other = float(max_other) if max_other is not None else None
        out.append({
            "state": state_, "county_fips": fips, "county_name": county_name, "city": city,
            "brand_rating": brand_rating, "brand_n": brand_n, "n_brand_locations": n_brand_locs,
            "avg_other_rating": avg_other, "max_other_rating": max_other, "n_other_locations": n_other or 0,
            "tier": _tier(brand_rating, avg_other, max_other),
        })
    return out


def main_brand_towns(brand_id: int, state: str, county_fips: str = None) -> list:
    """Town-level green/yellow/red for one brand, in one state (optionally
    narrowed to one county) - the map's "main brand" town view."""
    rows = _brand_town_ratings(brand_id, state)
    if county_fips:
        rows = [r for r in rows if r["county_fips"] == county_fips]
    return rows


def _rollup_counties(town_rows: list) -> list:
    by_county = {}
    for t in town_rows:
        key = (t["state"], t["county_fips"], t["county_name"])
        by_county.setdefault(key, []).append(t)
    out = []
    for (state, fips, name), towns in by_county.items():
        n_green = sum(1 for t in towns if t["tier"] == "green")
        pct_green = n_green / len(towns)
        out.append({
            "state": state, "county_fips": fips, "county_name": name,
            "n_towns": len(towns), "n_green": n_green, "pct_green": pct_green,
            "tier": _rollup_tier([t["tier"] for t in towns], green_tiers={"green"}),
        })
    return out


def main_brand_counties(brand_id: int, state: str) -> list:
    """County-level tier for one brand, in one state - rolled up from
    main_brand_towns() per spec's dark/light green - yellow - red bands."""
    return _rollup_counties(_brand_town_ratings(brand_id, state))


# Points per county tier for the state-level score (see main_brand_states)
# and the score bands that map back to a color. Tunable.
_COUNTY_POINTS = {"light_green": 1.0, "dark_green": 0.8, "yellow": 0.5, "red": 0.0}


def _score_tier(score):
    if score >= 0.9:
        return "light_green"
    if score >= 0.75:
        return "dark_green"
    if score >= 0.5:
        return "yellow"
    return "red"


def main_brand_states(brand_id: int) -> list:
    """State-level color: a points average over its counties' own tiers
    (light green = 1, dark green = 0.8, yellow = 0.5, red = 0), divided by
    the county count, then bucketed - light green >=0.9, dark green >=0.75,
    yellow >=0.5, red otherwise. Scoped to the state view only, per
    instruction - main_brand_counties() keeps computing the county tiers
    this is built from."""
    all_towns = _brand_town_ratings(brand_id, state=None)
    counties = _rollup_counties(all_towns)
    by_state = {}
    for c in counties:
        by_state.setdefault(c["state"], []).append(c)

    out = []
    for state, state_counties in by_state.items():
        n = len(state_counties)
        score = sum(_COUNTY_POINTS[c["tier"]] for c in state_counties) / n
        tier_counts = {}
        for c in state_counties:
            tier_counts[c["tier"]] = tier_counts.get(c["tier"], 0) + 1
        out.append({
            "state": state, "n_counties": n, "score": score,
            "tier_counts": tier_counts, "tier": _score_tier(score),
        })
    return out


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


def competitor_state_summary(state: str) -> list:
    """Each named competitor's own footprint and average rating within a
    state - no delta/benchmark here (that's specifically Mavis vs. its
    nearby competitors; a competitor doesn't have one vs. itself)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_name, n_locations, total_reviews, avg_raw_rating, avg_adj_rating
                FROM voice.competitor_state_rollup
                WHERE state = %s
                ORDER BY avg_adj_rating DESC NULLS LAST
            """, (state,))
            rows = cur.fetchall()
    return [
        {
            "brand": brand, "n_locations": n_locations, "total_reviews": total_reviews,
            "avg_raw_rating": float(raw) if raw is not None else None,
            "avg_adj_rating": float(adj) if adj is not None else None,
        }
        for brand, n_locations, total_reviews, raw, adj in rows
    ]


def competitor_county_summary(state: str, county_fips: str) -> list:
    """Same as competitor_state_summary(), scoped to one county."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_name, n_locations, total_reviews, avg_raw_rating, avg_adj_rating
                FROM voice.competitor_county_rollup
                WHERE state = %(state)s AND county_fips = %(county_fips)s
                ORDER BY avg_adj_rating DESC NULLS LAST
            """, {"state": state, "county_fips": county_fips})
            rows = cur.fetchall()
    return [
        {
            "brand": brand, "n_locations": n_locations, "total_reviews": total_reviews,
            "avg_raw_rating": float(raw) if raw is not None else None,
            "avg_adj_rating": float(adj) if adj is not None else None,
        }
        for brand, n_locations, total_reviews, raw, adj in rows
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
    counties. Left-joined to voice.town_boundaries (real Census place
    polygons, see scripts/backfill_town_boundaries.py) so the map can color
    an actual town shape the same way it colors counties - `geometry` is
    None for the minority of towns with no matching Census place (logged,
    not guessed, at backfill time), which the frontend falls back to a
    plain list entry for."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ctd.city, ctd.n_mavis_locations, ctd.total_mavis_reviews, ctd.n_low_comparability_locations,
                       ctd.avg_mavis_adj_rating, ctd.town_delta, ctd.avg_comp_benchmark_rating, ctd.suppressed,
                       tb.geometry
                FROM voice.county_town_delta ctd
                LEFT JOIN voice.town_boundaries tb ON tb.state = ctd.state AND tb.city = ctd.city
                WHERE ctd.state = %(state)s AND ctd.county_fips = %(county_fips)s
                ORDER BY ctd.town_delta DESC NULLS LAST
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
            "geometry": geometry,
        }
        for city, n_locations, total_reviews, n_low_comp, mavis_rating, delta, comp_rating, suppressed, geometry in rows
    ]


def county_locations(state: str, county_fips: str, city: str = None) -> list:
    """Every rated location (Mavis AND competitor) in one county, optionally
    narrowed to one town within it - for the map's store-marker view and the
    table's store-level drill. Pulls straight from location_adjusted_ratings
    (not the Mavis-only location_benchmark) so competitor locations show up
    too. Mavis rows also carry delta/low_comparability (left-joined from
    location_benchmark, NULL for competitors - a competitor has no "delta
    vs its neighbors")."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT lar.location_id, lar.brand_name, lar.family, lar.location_name, lar.city,
                       lar.lat, lar.lng, lar.raw_rating, lar.adj_rating, lar.n,
                       c.website_url,
                       lb.delta, lb.low_comparability, lb.comp_benchmark_rating, lb.n_competitors_in_ring,
                       vl.street, vl.zip
                FROM voice.location_adjusted_ratings lar
                JOIN voice.brands vb ON vb.brand_id = lar.brand_id
                JOIN voice.locations vl ON vl.location_id = lar.location_id
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
            "street": street, "zip": zip_code,
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
            website_url, delta, low_comp, comp_rating, n_ring, street, zip_code in rows
    ]


