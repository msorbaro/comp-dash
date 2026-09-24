"""Customer Voice - a thin query layer over the voice schema's materialized
views (see db/voice_metrics.sql), mirroring signal_data.py's role for the
messaging side. Every function here is a direct SELECT off an already-
computed view - no Python-side recomputation of the metrics themselves, so
the API stays an honest pass-through of the same SQL the user can run
directly in Supabase Studio, not a second implementation of the math.
"""
from __future__ import annotations

import datetime as dt
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


def _locations_for_scope(state: str = None, county_fips: str = None, source: str = "google_maps") -> list:
    """Every rated location (any brand), state-wide or narrowed to one
    county - the raw material for the county table's per-Mavis-banner
    breakdown (county_brand_matrix, below)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT state, county_fips, county_name, city, brand_id, n, raw_rating
                FROM voice.location_adjusted_ratings
                WHERE county_fips IS NOT NULL AND source = %(source)s
                  AND (%(state)s::text IS NULL OR state = %(state)s::text)
                  AND (%(county_fips)s::text IS NULL OR county_fips = %(county_fips)s::text)
            """, {"state": state, "county_fips": county_fips, "source": source})
            rows = cur.fetchall()
    return [
        {"state": s, "county_fips": cf, "county_name": cn, "city": c, "brand_id": bid, "n": n, "raw_rating": float(rr)}
        for s, cf, cn, c, bid, n, rr in rows
    ]


def _weighted_avg(items, value_key, weight_key="n"):
    total_w = sum(i[weight_key] for i in items)
    return sum(i[weight_key] * i[value_key] for i in items) / total_w if total_w else None




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


def _brand_town_ratings(brand_id: int, state: str = None, source: str = "google_maps") -> list:
    """One row per town where the given brand has at least one rated
    location - the brand's own weighted-average adj_rating there, and the
    average/best adj_rating of every OTHER brand's location in that same
    town. Everything needed to classify green/yellow/red per spec ("does
    that brand's location beat everyone else / the average / neither").
    A single query regardless of how many states, so main_brand_state_tiers()
    below doesn't need one DB round-trip per state. `other_agg` is scoped to
    the same source as the brand's own locations - comparing a Google-rated
    store against an Apple Maps average would mix rating populations."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                WITH brand_locs AS (
                    SELECT state, county_fips, county_name, city, n, adj_rating
                    FROM voice.location_adjusted_ratings
                    WHERE brand_id = %(brand_id)s AND county_fips IS NOT NULL AND source = %(source)s
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
                    WHERE lar.brand_id != %(brand_id)s AND lar.source = %(source)s
                    GROUP BY lar.state, lar.county_fips, lar.city
                )
                SELECT bt.state, bt.county_fips, bt.county_name, bt.city,
                       bt.brand_rating, bt.brand_n, bt.n_brand_locations,
                       o.avg_other_rating, o.max_other_rating, o.n_other_locations
                FROM brand_town bt
                LEFT JOIN other_agg o ON o.state = bt.state AND o.county_fips = bt.county_fips AND o.city = bt.city
            """, {"brand_id": brand_id, "state": state, "source": source})
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


def main_brand_towns(brand_id: int, state: str, county_fips: str = None, source: str = "google_maps") -> list:
    """Town-level green/yellow/red for one brand, in one state (optionally
    narrowed to one county) - the map's "main brand" town view."""
    rows = _brand_town_ratings(brand_id, state, source)
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


def main_brand_counties(brand_id: int, state: str, source: str = "google_maps") -> list:
    """County-level tier for one brand, in one state - rolled up from
    main_brand_towns() per spec's dark/light green - yellow - red bands."""
    return _rollup_counties(_brand_town_ratings(brand_id, state, source))


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


def main_brand_states(brand_id: int, source: str = "google_maps") -> list:
    """State-level color: a points average over its counties' own tiers
    (light green = 1, dark green = 0.8, yellow = 0.5, red = 0), divided by
    the county count, then bucketed - light green >=0.9, dark green >=0.75,
    yellow >=0.5, red otherwise. Scoped to the state view only, per
    instruction - main_brand_counties() keeps computing the county tiers
    this is built from."""
    all_towns = _brand_town_ratings(brand_id, state=None, source=source)
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


def main_brand_national_summary(source: str = "google_maps") -> list:
    """Nationwide rollup for every Mavis banner that has at least one rated
    location - one row per banner, weighted the same way state_delta is (by
    each location's own review count). The root level of the table's
    brand-rooted drill tree (brand -> state -> county -> town -> store):
    this gives each root row its numbers up front, same as state_summary()
    does for the state-rooted tree."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_id, brand_name,
                       count(*) AS n_mavis_locations,
                       sum(mavis_n) AS total_mavis_reviews,
                       sum(CASE WHEN low_comparability THEN 1 ELSE 0 END) AS n_low_comparability_locations,
                       (sum(mavis_n * mavis_adj_rating) / NULLIF(sum(mavis_n), 0)) AS avg_mavis_adj_rating,
                       (sum(mavis_n * delta) / NULLIF(sum(mavis_n), 0)) AS brand_delta,
                       (sum(mavis_n * comp_benchmark_rating) / NULLIF(sum(mavis_n), 0)) AS avg_comp_benchmark_rating
                FROM voice.location_benchmark
                WHERE delta IS NOT NULL AND source = %(source)s
                GROUP BY brand_id, brand_name
                ORDER BY brand_delta DESC NULLS LAST
            """, {"source": source})
            rows = cur.fetchall()
    return [
        {
            "brand_id": bid, "name": name, "n_mavis_locations": n_loc, "total_mavis_reviews": total_rev,
            "n_low_comparability_locations": n_low,
            "mavis_rating": float(mavis_rating) if mavis_rating is not None else None,
            "delta": float(delta) if delta is not None else None,
            "comp_rating": float(comp_rating) if comp_rating is not None else None,
        }
        for bid, name, n_loc, total_rev, n_low, mavis_rating, delta, comp_rating in rows
    ]


def main_brand_locations(brand_id: int, source: str = "google_maps") -> list:
    """Every rated location for one Mavis brand, with its full per-location
    benchmark numbers straight from location_benchmark (state/county/town
    grouping info included). The raw material for the brand-rooted drill
    tree's state/county/town/store levels: fetched once per brand and
    rolled up to each level client-side, rather than one round-trip per
    tree node, since a single Mavis banner's location count (a few hundred
    at most) is small enough that this is both simpler and faster."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT location_id, location_name, state, county_fips, county_name, city,
                       mavis_n, mavis_raw_rating, mavis_adj_rating, comp_benchmark_rating, delta, low_comparability
                FROM voice.location_benchmark
                WHERE brand_id = %(brand_id)s AND delta IS NOT NULL AND source = %(source)s
                ORDER BY state, county_name, city, location_name
            """, {"brand_id": brand_id, "source": source})
            rows = cur.fetchall()
    return [
        {
            "location_id": loc_id, "name": name, "state": state, "county_fips": fips,
            "county_name": county_name, "city": city, "review_count": n,
            "raw_rating": float(raw) if raw is not None else None,
            "adj_rating": float(adj) if adj is not None else None,
            "comp_benchmark_rating": float(comp) if comp is not None else None,
            "delta": float(delta) if delta is not None else None,
            "low_comparability": low_comp,
        }
        for loc_id, name, state, fips, county_name, city, n, raw, adj, comp, delta, low_comp in rows
    ]


def head_to_head(state: str = None, city: str = None, source: str = "google_maps") -> dict:
    """Every Mavis banner vs. every named competitor - cell = the banner's
    own avg rating minus the competitor's. With no filter, computed
    nationwide with STATE as the sharing unit, so a banner's best state
    isn't held up against a rival's worst; filtered to one state, the
    sharing unit narrows to TOWN (still fair, just at the grain that state
    actually supports); filtered to one state + town, there's only one area
    left, so it's a direct comparison of whichever brands have a store in
    that exact town - no separate "shared by town" mode needed, this
    degrades into it automatically. Ratings are raw, review-count weighted,
    matching every other average in this app; each header's own avg
    reflects the same filtered scope, not always nationwide."""
    granularity = "state" if not state else ("town" if not city else "none")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_id, brand_name, family, state, city, n, raw_rating
                FROM voice.location_adjusted_ratings
                WHERE state IS NOT NULL AND source = %(source)s
                  AND (%(state)s::text IS NULL OR state = %(state)s::text)
                  AND (%(city)s::text IS NULL OR city = %(city)s::text)
            """, {"state": state, "city": city, "source": source})
            rows = cur.fetchall()

    by_brand = {}
    overall = {}
    for brand_id, name, family, st, ct, n, raw_rating in rows:
        if granularity == "state":
            area = st
        elif granularity == "town":
            area = f"{st}|{ct}"
        else:
            area = "_"
        entry = by_brand.setdefault(brand_id, {"name": name, "family": family, "areas": {}})
        entry["areas"].setdefault(area, []).append({"n": n, "raw_rating": float(raw_rating)})
        overall.setdefault(brand_id, []).append({"n": n, "raw_rating": float(raw_rating)})

    mavis_ids = [bid for bid, b in by_brand.items() if b["family"] == "mavis"]
    comp_ids = [bid for bid, b in by_brand.items() if b["family"] == "competitor"]

    def area_stats(brand_id, areas):
        locs = [loc for area in areas for loc in by_brand[brand_id]["areas"].get(area, [])]
        return _weighted_avg(locs, "raw_rating"), len(locs)

    columns = [
        {"brand_id": cid, "name": by_brand[cid]["name"], "avg": _weighted_avg(overall[cid], "raw_rating")}
        for cid in comp_ids
    ]
    columns.sort(key=lambda c: (c["avg"] is not None, c["avg"]), reverse=True)

    rows_out = []
    for mid in mavis_ids:
        m = by_brand[mid]
        cells = {}
        for cid in comp_ids:
            shared = set(m["areas"].keys()) & set(by_brand[cid]["areas"].keys())
            if not shared:
                cells[str(cid)] = None
                continue
            mavis_avg, n_mavis = area_stats(mid, shared)
            comp_avg, n_comp = area_stats(cid, shared)
            cells[str(cid)] = {
                "gap": None if mavis_avg is None or comp_avg is None else mavis_avg - comp_avg,
                "mavis_avg": mavis_avg, "comp_avg": comp_avg,
                "n_shared": len(shared), "n_mavis_locations": n_mavis, "n_comp_locations": n_comp,
            }
        rows_out.append({
            "brand_id": mid, "name": m["name"],
            "avg": _weighted_avg(overall[mid], "raw_rating"),
            "cells": cells,
        })
    rows_out.sort(key=lambda r: (r["avg"] is not None, r["avg"]), reverse=True)

    return {"granularity": granularity, "columns": columns, "rows": rows_out}


def review_states() -> list:
    """States that actually have review-level data (voice.reviews) - distinct
    from the ratings chain's `has_data` (location_adjusted_ratings), since
    the review-text scrape was Texas-only so far and the two datasets can
    diverge. Powers the Reviews page's state filter."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT vl.state FROM voice.reviews r
                JOIN voice.locations vl ON vl.location_id = r.location_id
                ORDER BY vl.state
            """)
            rows = cur.fetchall()
    return [{"state": s, "state_name": STATE_NAME_BY_CODE.get(s, s)} for (s,) in rows]


def review_towns(state: str = "TX") -> list:
    """Distinct cities with review data in this state - for the Reviews
    page's city filter. Independent of the ratings chain's state_towns
    (different underlying table, same reasoning as review_states above)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT vl.city FROM voice.reviews r
                JOIN voice.locations vl ON vl.location_id = r.location_id
                WHERE vl.state = %s AND vl.city IS NOT NULL
                ORDER BY vl.city
            """, (state,))
            rows = cur.fetchall()
    return [r[0] for r in rows]


def review_trend(state: str = "TX", city: str = None, split_competitors: bool = False) -> dict:
    """Monthly review volume + sentiment mix + star-rating histogram from
    the review-level dataset (voice.reviews, Phase 3) - one series per Mavis
    banner, plus (by default) one aggregate "Competitors" series; pass
    split_competitors=True to keep each competitor as its own series
    instead of folding them together. Optionally narrowed to one city.
    Powers the Reviews trend page - "are we trending up or down," per the
    user's original ask - and doubles as the source for the star-histogram
    chart (n_1..n_5 per point) so that chart needs no separate query."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT vb.family, vb.name, date_trunc('month', r.review_date) AS month,
                       count(*) AS n, avg(r.rating) AS avg_rating,
                       sum(CASE WHEN r.sentiment = 'positive' THEN 1 ELSE 0 END) AS n_pos,
                       sum(CASE WHEN r.sentiment = 'neutral' THEN 1 ELSE 0 END) AS n_neu,
                       sum(CASE WHEN r.sentiment = 'negative' THEN 1 ELSE 0 END) AS n_neg,
                       sum(CASE WHEN r.rating = 1 THEN 1 ELSE 0 END) AS n_1,
                       sum(CASE WHEN r.rating = 2 THEN 1 ELSE 0 END) AS n_2,
                       sum(CASE WHEN r.rating = 3 THEN 1 ELSE 0 END) AS n_3,
                       sum(CASE WHEN r.rating = 4 THEN 1 ELSE 0 END) AS n_4,
                       sum(CASE WHEN r.rating = 5 THEN 1 ELSE 0 END) AS n_5
                FROM voice.reviews r
                JOIN voice.locations vl ON vl.location_id = r.location_id
                JOIN voice.brands vb ON vb.brand_id = vl.brand_id
                WHERE vl.state = %(state)s AND r.review_date IS NOT NULL
                  AND (%(city)s::text IS NULL OR vl.city = %(city)s::text)
                GROUP BY vb.family, vb.name, month
                ORDER BY month
            """, {"state": state, "city": city})
            rows = cur.fetchall()

    by_series: dict = {}
    for family, name, month, n, avg_rating, n_pos, n_neu, n_neg, n_1, n_2, n_3, n_4, n_5 in rows:
        series_name = name if (family == "mavis" or split_competitors) else "Competitors"
        bucket = by_series.setdefault(series_name, {"mavis": family == "mavis"})
        m = bucket.setdefault(month, {
            "n": 0, "rating_sum": 0.0, "n_pos": 0, "n_neu": 0, "n_neg": 0,
            "n_1": 0, "n_2": 0, "n_3": 0, "n_4": 0, "n_5": 0,
        })
        m["n"] += n
        m["rating_sum"] += float(avg_rating) * n if avg_rating is not None else 0.0
        m["n_pos"] += n_pos
        m["n_neu"] += n_neu
        m["n_neg"] += n_neg
        m["n_1"] += n_1
        m["n_2"] += n_2
        m["n_3"] += n_3
        m["n_4"] += n_4
        m["n_5"] += n_5

    mavis_names = sorted(name for name, b in by_series.items() if b["mavis"])
    other_names = sorted(name for name, b in by_series.items() if not b["mavis"])
    ordered_names = mavis_names + other_names

    series_out = []
    for series_name in ordered_names:
        bucket = by_series[series_name]
        months = {k: v for k, v in bucket.items() if k != "mavis"}
        points = []
        for month in sorted(months):
            m = months[month]
            points.append({
                "month": month.date().isoformat(), "n_reviews": m["n"],
                "avg_rating": (m["rating_sum"] / m["n"]) if m["n"] else None,
                "pct_positive": m["n_pos"] / m["n"] if m["n"] else None,
                "pct_neutral": m["n_neu"] / m["n"] if m["n"] else None,
                "pct_negative": m["n_neg"] / m["n"] if m["n"] else None,
                "n_1": m["n_1"], "n_2": m["n_2"], "n_3": m["n_3"], "n_4": m["n_4"], "n_5": m["n_5"],
            })
        series_out.append({"name": series_name, "mavis": bucket["mavis"], "points": points})

    return {"state": state, "city": city, "series": series_out}


def review_yoy(state: str = "TX", city: str = None, split_competitors: bool = False) -> dict:
    """Year-over-year comparison, month by month, for the trailing 12
    months - "how did this month do vs. the same month last year" per the
    user's own framing. Pulls 24 months of raw data (this year's 12 +
    last year's matching 12) and pairs them client-side rather than trying
    to express the year-over-year join in SQL."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT vb.family, vb.name, date_trunc('month', r.review_date) AS month,
                       count(*) AS n, avg(r.rating) AS avg_rating
                FROM voice.reviews r
                JOIN voice.locations vl ON vl.location_id = r.location_id
                JOIN voice.brands vb ON vb.brand_id = vl.brand_id
                WHERE vl.state = %(state)s AND r.review_date IS NOT NULL
                  AND r.review_date >= date_trunc('month', now()) - interval '23 months'
                  AND (%(city)s::text IS NULL OR vl.city = %(city)s::text)
                GROUP BY vb.family, vb.name, month
                ORDER BY month
            """, {"state": state, "city": city})
            rows = cur.fetchall()

    by_series: dict = {}
    for family, name, month, n, avg_rating in rows:
        series_name = name if (family == "mavis" or split_competitors) else "Competitors"
        bucket = by_series.setdefault(series_name, {"mavis": family == "mavis", "months": {}})
        # Keyed by plain date, not the raw tz-aware timestamptz Postgres
        # returns - comparing a tz-aware datetime to the naive dt.date keys
        # built below always came back False (never raised, just silently
        # never matched), so every month showed up as 0 vs 0. Confirmed
        # live: Brakes Plus had 1,182 September reviews in review_trend but
        # 0/0 here before this fix.
        m = bucket["months"].setdefault(month.date(), {"n": 0, "rating_sum": 0.0})
        m["n"] += n
        m["rating_sum"] += float(avg_rating) * n if avg_rating is not None else 0.0

    # The trailing 12 calendar months as of now, oldest first - each paired
    # with the same month one year earlier.
    this_month_start = dt.date.today().replace(day=1)
    last_12 = []
    y, m = this_month_start.year, this_month_start.month
    for _ in range(12):
        last_12.append(dt.date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    last_12.reverse()

    def _prior_year(d):
        return dt.date(d.year - 1, d.month, 1)

    mavis_names = sorted(name for name, b in by_series.items() if b["mavis"])
    other_names = sorted(name for name, b in by_series.items() if not b["mavis"])

    series_out = []
    for series_name in mavis_names + other_names:
        bucket = by_series[series_name]
        months = bucket["months"]
        points = []
        for month_date in last_12:
            cur_key = month_date
            prior_key = _prior_year(month_date)
            cur_m = months.get(cur_key)
            prior_m = months.get(prior_key)
            cur_n, cur_rating = (cur_m["n"], cur_m["rating_sum"] / cur_m["n"]) if cur_m else (0, None)
            prior_n, prior_rating = (prior_m["n"], prior_m["rating_sum"] / prior_m["n"]) if prior_m else (0, None)
            points.append({
                "month": month_date.isoformat(),
                "n_this_year": cur_n, "n_last_year": prior_n,
                "pct_change_n": ((cur_n - prior_n) / prior_n) if prior_n else None,
                "avg_rating_this_year": cur_rating, "avg_rating_last_year": prior_rating,
                "delta_rating": (cur_rating - prior_rating) if (cur_rating is not None and prior_rating is not None) else None,
            })
        series_out.append({"name": series_name, "mavis": bucket["mavis"], "points": points})

    return {"state": state, "city": city, "series": series_out}


def review_theme_mix(state: str = "TX", city: str = None, brand: str = None) -> list:
    """Sentiment mix broken down by theme (price, speed, friendliness, etc. -
    see categorize/review_themes.py for the taxonomy) instead of just
    overall positive/neutral/negative - "what aspects are people speaking
    about positively or negatively," per the user's own framing. Not time-
    bucketed (themes are sparse enough per review that a monthly split
    would be too thin to read), scoped to a state/city/brand instead."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rt.theme, rt.theme_sentiment, count(*)
                FROM voice.review_themes rt
                JOIN voice.reviews r ON r.review_id = rt.review_id
                JOIN voice.locations vl ON vl.location_id = r.location_id
                JOIN voice.brands vb ON vb.brand_id = vl.brand_id
                WHERE vl.state = %(state)s
                  AND (%(city)s::text IS NULL OR vl.city = %(city)s::text)
                  AND (%(brand)s::text IS NULL OR vb.name = %(brand)s::text)
                GROUP BY rt.theme, rt.theme_sentiment
            """, {"state": state, "city": city, "brand": brand})
            rows = cur.fetchall()

    by_theme: dict = {}
    for theme, sentiment, n in rows:
        bucket = by_theme.setdefault(theme, {"positive": 0, "neutral": 0, "negative": 0})
        bucket[sentiment] = n

    out = [
        {"theme": theme, **counts, "total": counts["positive"] + counts["neutral"] + counts["negative"]}
        for theme, counts in by_theme.items()
    ]
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


def review_theme_texts(
    theme: str, state: str = "TX", city: str = None, brand: str = None, sentiment: str = "negative", limit: int = 25,
) -> list:
    """Real review text for one theme at one theme-sentiment ('negative' for
    complaints, 'positive' for praise), scoped exactly like review_theme_mix
    above - the raw material for a live summary call
    (categorize/theme_summary.py). Stays a plain SELECT per this module's
    own contract (no LLM calls in this file); the summary itself is
    computed by the caller in backend/main.py."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.text FROM voice.review_themes rt
                JOIN voice.reviews r ON r.review_id = rt.review_id
                JOIN voice.locations vl ON vl.location_id = r.location_id
                JOIN voice.brands vb ON vb.brand_id = vl.brand_id
                WHERE rt.theme = %(theme)s AND rt.theme_sentiment = %(sentiment)s
                  AND vl.state = %(state)s AND r.text IS NOT NULL
                  AND (%(city)s::text IS NULL OR vl.city = %(city)s::text)
                  AND (%(brand)s::text IS NULL OR vb.name = %(brand)s::text)
                ORDER BY random() LIMIT %(limit)s
            """, {"theme": theme, "state": state, "city": city, "brand": brand, "sentiment": sentiment, "limit": limit})
            rows = cur.fetchall()
    return [r[0] for r in rows]


def review_sample(
    state: str = "TX", city: str = None, brand: str = None, sentiment: str = None, month: str = None,
    theme: str = None, rating: int = None, limit: int = 30,
) -> list:
    """A browsable sample of individual reviews - rating, date, brand, text,
    sentiment label + reason - the "what was said" view under the trend
    chart. Optionally scoped to one city, one brand, one sentiment class,
    one month (pass the first-of-month date, e.g. "2026-03-01" - matches a
    `month` value from review_trend()'s points), one star rating (1-5),
    and/or one theme (from voice.review_themes - see
    categorize/review_themes.py's taxonomy).

    When `theme` is given, `sentiment` is read as that THEME's sentiment
    (rt.theme_sentiment), not the review's overall sentiment - the two can
    differ (a review can be positive overall but negative on one aspect),
    and the whole point of combining them is jumping here from one theme's
    "why negative?" complaint summary with the exact matching reviews, not
    a coincidentally-overall-negative one that isn't really about this
    theme. Without `theme`, `sentiment` filters the review's own overall
    sentiment as before."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT vb.name, vb.family, vl.city, r.rating, r.review_date, r.text,
                       r.sentiment, r.sentiment_reason
                FROM voice.reviews r
                JOIN voice.locations vl ON vl.location_id = r.location_id
                JOIN voice.brands vb ON vb.brand_id = vl.brand_id
                WHERE vl.state = %(state)s AND r.text IS NOT NULL
                  AND (%(city)s::text IS NULL OR vl.city = %(city)s::text)
                  AND (%(brand)s::text IS NULL OR vb.name = %(brand)s::text)
                  AND (%(month)s::text IS NULL OR date_trunc('month', r.review_date) = %(month)s::date)
                  AND (%(rating)s::int IS NULL OR r.rating = %(rating)s::int)
                  AND (
                    (%(theme)s::text IS NULL AND (%(sentiment)s::text IS NULL OR r.sentiment = %(sentiment)s::text))
                    OR (%(theme)s::text IS NOT NULL AND EXISTS (
                          SELECT 1 FROM voice.review_themes rt
                          WHERE rt.review_id = r.review_id AND rt.theme = %(theme)s::text
                            AND (%(sentiment)s::text IS NULL OR rt.theme_sentiment = %(sentiment)s::text)
                        ))
                  )
                ORDER BY r.review_date DESC
                LIMIT %(limit)s
            """, {
                "state": state, "city": city, "brand": brand, "sentiment": sentiment,
                "month": month, "theme": theme, "rating": rating, "limit": limit,
            })
            rows = cur.fetchall()
    return [
        {
            "brand": name, "mavis": family == "mavis", "city": city_,
            "rating": rating, "date": review_date.date().isoformat() if review_date else None,
            "text": text, "sentiment": sent, "reason": reason,
        }
        for name, family, city_, rating, review_date, text, sent, reason in rows
    ]


def reddit_brand_summary() -> list:
    """One row per tracked brand (Mavis banners + competitors) - how many
    Reddit posts/comments were scraped for it, how many were judged actually
    relevant (see categorize/reddit_sentiment.py's two-stage relevance+
    sentiment design - Reddit search returns real false positives), and the
    sentiment mix of the relevant ones. Powers the Reddit tab's per-brand
    comparison table."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT vb.brand_id, vb.name, vb.family, c.website_url,
                       count(rm.mention_id) AS n_scraped,
                       sum(CASE WHEN rm.is_relevant THEN 1 ELSE 0 END) AS n_relevant,
                       sum(CASE WHEN rm.is_relevant AND rm.sentiment = 'positive' THEN 1 ELSE 0 END) AS n_pos,
                       sum(CASE WHEN rm.is_relevant AND rm.sentiment = 'neutral' THEN 1 ELSE 0 END) AS n_neu,
                       sum(CASE WHEN rm.is_relevant AND rm.sentiment = 'negative' THEN 1 ELSE 0 END) AS n_neg
                FROM voice.brands vb
                LEFT JOIN competitors c ON c.id = vb.competitor_id
                LEFT JOIN voice.reddit_mentions rm ON rm.brand_id = vb.brand_id
                GROUP BY vb.brand_id, vb.name, vb.family, c.website_url
                ORDER BY vb.family, n_relevant DESC NULLS LAST, vb.name
            """)
            rows = cur.fetchall()
    return [
        {
            "brand_id": bid, "name": name, "mavis": family == "mavis",
            "logo": _favicon_url(name, website_url),
            "n_scraped": n_scraped, "n_relevant": n_relevant or 0,
            "n_positive": n_pos or 0, "n_neutral": n_neu or 0, "n_negative": n_neg or 0,
        }
        for bid, name, family, website_url, n_scraped, n_relevant, n_pos, n_neu, n_neg in rows
    ]


def reddit_comparisons() -> list:
    """Head-to-head Reddit mentions - every relevant mention with
    theme='comparison' and a resolved comparison_brand_id, aggregated into
    (Mavis banner, competitor) pairs. rm.sentiment is judged toward the
    brand that was SEARCHED for (rm.brand_id), not toward comparison_brand_id
    (see categorize/reddit_sentiment.py's prompt) - so which side a mention
    "favors" depends on which brand was searched: positive favors the
    searched brand, negative favors the other brand named in the comparison.
    A mention where both sides are Mavis, or both are competitors, isn't a
    Mavis-vs-competitor pair and is skipped."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT vb1.name, vb1.family, vb2.name, vb2.family, rm.sentiment
                FROM voice.reddit_mentions rm
                JOIN voice.brands vb1 ON vb1.brand_id = rm.brand_id
                JOIN voice.brands vb2 ON vb2.brand_id = rm.comparison_brand_id
                WHERE rm.is_relevant AND rm.theme = 'comparison' AND rm.comparison_brand_id IS NOT NULL
            """)
            rows = cur.fetchall()

    pairs: dict = {}
    for searched_name, searched_family, other_name, other_family, sentiment in rows:
        if (searched_family == "mavis") == (other_family == "mavis"):
            continue
        if searched_family == "mavis":
            mavis_name, comp_name = searched_name, other_name
            favors_mavis, favors_comp = sentiment == "positive", sentiment == "negative"
        else:
            mavis_name, comp_name = other_name, searched_name
            favors_mavis, favors_comp = sentiment == "negative", sentiment == "positive"
        bucket = pairs.setdefault(
            (mavis_name, comp_name),
            {"n_mentions": 0, "n_favor_mavis": 0, "n_favor_competitor": 0, "n_neutral": 0},
        )
        bucket["n_mentions"] += 1
        if favors_mavis:
            bucket["n_favor_mavis"] += 1
        elif favors_comp:
            bucket["n_favor_competitor"] += 1
        else:
            bucket["n_neutral"] += 1

    out = [{"mavis_brand": mn, "competitor_brand": cn, **stats} for (mn, cn), stats in pairs.items()]
    out.sort(key=lambda r: r["n_mentions"], reverse=True)
    return out


def reddit_sample(
    brand: str = None, sentiment: str = None, theme: str = None, aspect: str = None, limit: int = 30,
) -> list:
    """A browsable sample of individual relevant Reddit mentions - title/
    text, subreddit, score, permalink (links out to the real thread), date,
    sentiment/theme/reason - the "what people are saying" view under the
    Reddit tab's summary tables. Optionally scoped to one brand, one
    sentiment class, one post-purpose `theme` (complaint/question/etc. -
    categorize/reddit_sentiment.py), and/or one `aspect` (price/speed/
    honesty/etc. - categorize/reddit_mention_themes.py, a DIFFERENT
    classification pass from `theme`). Sorted by score (Reddit's own
    relevance/popularity signal), matching how a real customer would
    actually encounter these results.

    When `aspect` is given, `sentiment` is read as that aspect's own
    sentiment (rmt.theme_sentiment), not the mention's overall sentiment -
    same reasoning as review_sample's `theme` param: the two can differ,
    and jumping here from one aspect's "why negative?" summary should show
    the exact matching mentions, not a coincidentally-overall-negative one
    that isn't really about this aspect."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT vb.name, vb.family, rm.type, rm.subreddit, rm.title, rm.text,
                       rm.score, rm.permalink, rm.created_at, rm.sentiment, rm.theme, rm.reason
                FROM voice.reddit_mentions rm
                JOIN voice.brands vb ON vb.brand_id = rm.brand_id
                WHERE rm.is_relevant
                  AND (%(brand)s::text IS NULL OR vb.name = %(brand)s::text)
                  AND (%(theme)s::text IS NULL OR rm.theme = %(theme)s::text)
                  AND (
                    (%(aspect)s::text IS NULL AND (%(sentiment)s::text IS NULL OR rm.sentiment = %(sentiment)s::text))
                    OR (%(aspect)s::text IS NOT NULL AND EXISTS (
                          SELECT 1 FROM voice.reddit_mention_themes rmt
                          WHERE rmt.mention_id = rm.mention_id AND rmt.theme = %(aspect)s::text
                            AND (%(sentiment)s::text IS NULL OR rmt.theme_sentiment = %(sentiment)s::text)
                        ))
                  )
                ORDER BY rm.score DESC NULLS LAST, rm.created_at DESC
                LIMIT %(limit)s
            """, {"brand": brand, "sentiment": sentiment, "theme": theme, "aspect": aspect, "limit": limit})
            rows = cur.fetchall()
    return [
        {
            "brand": name, "mavis": family == "mavis", "type": mtype, "subreddit": subreddit,
            "title": title, "text": text, "score": score, "permalink": permalink,
            "date": created_at.date().isoformat() if created_at else None,
            "sentiment": sent, "theme": theme_val, "reason": reason,
        }
        for name, family, mtype, subreddit, title, text, score, permalink, created_at, sent, theme_val, reason in rows
    ]


def reddit_theme_mix(brand: str = None) -> list:
    """Sentiment mix broken down by aspect theme (price, speed, honesty,
    etc. - categorize/reddit_mention_themes.py) for relevant Reddit
    mentions, optionally scoped to one brand - the Reddit-side analogue of
    review_theme_mix, same shape so the frontend can reuse the same chart."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rmt.theme, rmt.theme_sentiment, count(*)
                FROM voice.reddit_mention_themes rmt
                JOIN voice.reddit_mentions rm ON rm.mention_id = rmt.mention_id
                JOIN voice.brands vb ON vb.brand_id = rm.brand_id
                WHERE rm.is_relevant
                  AND (%(brand)s::text IS NULL OR vb.name = %(brand)s::text)
                GROUP BY rmt.theme, rmt.theme_sentiment
            """, {"brand": brand})
            rows = cur.fetchall()

    by_theme: dict = {}
    for theme, sentiment, n in rows:
        bucket = by_theme.setdefault(theme, {"positive": 0, "neutral": 0, "negative": 0})
        bucket[sentiment] = n

    out = [
        {"theme": theme, **counts, "total": counts["positive"] + counts["neutral"] + counts["negative"]}
        for theme, counts in by_theme.items()
    ]
    out.sort(key=lambda r: r["total"], reverse=True)
    return out


def reddit_theme_texts(theme: str, brand: str = None, sentiment: str = "negative", limit: int = 25) -> list:
    """Real mention text (title + body combined) for one aspect theme at one
    theme-sentiment ('negative' for complaints, 'positive' for praise),
    optionally scoped to one brand - the raw material for a live summary
    call (categorize/theme_summary.py), same reasoning as
    review_theme_texts."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rm.title, rm.text FROM voice.reddit_mention_themes rmt
                JOIN voice.reddit_mentions rm ON rm.mention_id = rmt.mention_id
                JOIN voice.brands vb ON vb.brand_id = rm.brand_id
                WHERE rmt.theme = %(theme)s AND rmt.theme_sentiment = %(sentiment)s AND rm.is_relevant
                  AND (%(brand)s::text IS NULL OR vb.name = %(brand)s::text)
                ORDER BY random() LIMIT %(limit)s
            """, {"theme": theme, "brand": brand, "sentiment": sentiment, "limit": limit})
            rows = cur.fetchall()
    return [f"{title or ''}\n{text or ''}".strip() for title, text in rows]


def state_summary(source: str = "google_maps") -> list:
    """All 50 states (+ DC), left-joined to voice.state_delta so states
    with no pilot data at all come back with null fields - distinguished
    from a state that HAS data but is suppressed for being too small."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sd.state, sd.n_mavis_locations, sd.total_mavis_reviews, sd.n_low_comparability_locations,
                       sd.avg_mavis_adj_rating, sd.state_delta, sd.avg_comp_benchmark_rating, sd.suppressed
                FROM voice.state_delta sd
                WHERE sd.source = %(source)s
            """, {"source": source})
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


def brand_state_summary(state: str, source: str = "google_maps") -> list:
    """Per-Mavis-banner rollup within one state - e.g. how Midas alone
    compares to local competitors, distinct from the whole-portfolio number
    state_summary() gives."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_name, n_mavis_locations, total_mavis_reviews, n_low_comparability_locations,
                       avg_mavis_adj_rating, state_delta, avg_comp_benchmark_rating, suppressed
                FROM voice.brand_state_delta
                WHERE state = %(state)s AND source = %(source)s
                ORDER BY state_delta DESC NULLS LAST
            """, {"state": state, "source": source})
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


def competitor_state_summary(state: str, source: str = "google_maps") -> list:
    """Each named competitor's own footprint and average rating within a
    state - no delta/benchmark here (that's specifically Mavis vs. its
    nearby competitors; a competitor doesn't have one vs. itself)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_name, n_locations, total_reviews, avg_raw_rating, avg_adj_rating
                FROM voice.competitor_state_rollup
                WHERE state = %(state)s AND source = %(source)s
                ORDER BY avg_adj_rating DESC NULLS LAST
            """, {"state": state, "source": source})
            rows = cur.fetchall()
    return [
        {
            "brand": brand, "n_locations": n_locations, "total_reviews": total_reviews,
            "avg_raw_rating": float(raw) if raw is not None else None,
            "avg_adj_rating": float(adj) if adj is not None else None,
        }
        for brand, n_locations, total_reviews, raw, adj in rows
    ]


def competitor_county_summary(state: str, county_fips: str, source: str = "google_maps") -> list:
    """Same as competitor_state_summary(), scoped to one county."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT brand_name, n_locations, total_reviews, avg_raw_rating, avg_adj_rating
                FROM voice.competitor_county_rollup
                WHERE state = %(state)s AND county_fips = %(county_fips)s AND source = %(source)s
                ORDER BY avg_adj_rating DESC NULLS LAST
            """, {"state": state, "county_fips": county_fips, "source": source})
            rows = cur.fetchall()
    return [
        {
            "brand": brand, "n_locations": n_locations, "total_reviews": total_reviews,
            "avg_raw_rating": float(raw) if raw is not None else None,
            "avg_adj_rating": float(adj) if adj is not None else None,
        }
        for brand, n_locations, total_reviews, raw, adj in rows
    ]


def county_summary(state: str, source: str = "google_maps") -> list:
    """Same shape as town_summary(), grouped by county (from the HUD ZIP-COUNTY
    crosswalk backfill) instead of city - the map's state -> county drill."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT county_fips, county_name, n_mavis_locations, total_mavis_reviews, n_low_comparability_locations,
                       avg_mavis_adj_rating, county_delta, avg_comp_benchmark_rating, suppressed
                FROM voice.county_delta
                WHERE state = %(state)s AND source = %(source)s
                ORDER BY county_delta DESC NULLS LAST
            """, {"state": state, "source": source})
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


def county_brand_matrix(state: str, source: str = "google_maps") -> dict:
    """The county table's per-Mavis-banner breakdown: for every county in
    the state (same set county_summary() returns), the whole Mavis
    portfolio's own avg rating, the county's overall average rating across
    EVERY tracked brand (Mavis and competitor alike - the benchmark), and
    for each individual Mavis banner (Midas, Tire Kingdom, Tuffy, etc.)
    that has a location in that county, what % of that banner's own
    locations there beat the benchmark. A banner absent from a county gets
    no entry in that county's `brand_pct_above` (not 0% - it doesn't
    operate there, that's not the same as operating there and losing).
    `brands` (the fixed column set) is restricted to banners that actually
    operate SOMEWHERE in this state - a banner with zero locations in the
    whole state (e.g. Brakes Plus/Town Fair Tire in FL) gets no column at
    all, rather than an all-dash one.
    Returns {"brands": [ordered Mavis banner names], "counties": [...]} -
    `counties` is the row data."""
    mavis_name_by_id = {b["brand_id"]: b["name"] for b in list_brands() if b["family"] == "mavis"}

    base = county_summary(state, source)
    all_locs = _locations_for_scope(state=state, source=source)
    present_brand_ids = {loc["brand_id"] for loc in all_locs}
    mavis_names_ordered = sorted(
        name for bid, name in mavis_name_by_id.items() if bid in present_brand_ids
    )

    by_county_fips = {}
    for loc in all_locs:
        by_county_fips.setdefault(loc["county_fips"], []).append(loc)

    counties_out = []
    for c in base:
        locs = by_county_fips.get(c["county_fips"], [])
        area_avg = _weighted_avg(locs, "raw_rating")
        by_brand = {}
        for loc in locs:
            by_brand.setdefault(loc["brand_id"], []).append(loc)
        brand_pct_above = {}
        if area_avg is not None:
            for brand_id, brand_locs in by_brand.items():
                name = mavis_name_by_id.get(brand_id)
                if not name:
                    continue
                n_above = sum(1 for l in brand_locs if l["raw_rating"] > area_avg)
                brand_pct_above[name] = n_above / len(brand_locs)
        counties_out.append({**c, "area_avg_rating": area_avg, "brand_pct_above": brand_pct_above})

    return {"brands": mavis_names_ordered, "counties": counties_out}


def county_town_brand_matrix(state: str, county_fips: str, source: str = "google_maps") -> dict:
    """Same per-Mavis-banner breakdown as county_brand_matrix(), one level
    down: one row per town within a single county (matching
    county_town_summary()'s rows) instead of one row per county. Each
    town's "area avg rating" is that town's own all-brand average (the
    market here is the town, not the whole county), and the %-above
    columns are fixed to whichever Mavis banners operate anywhere in THIS
    county - not state-wide - so a banner two counties over doesn't add an
    all-dash column to a county it has nothing to do with."""
    mavis_name_by_id = {b["brand_id"]: b["name"] for b in list_brands() if b["family"] == "mavis"}

    base = county_town_summary(state, county_fips, source)
    locs_in_county = _locations_for_scope(state=state, county_fips=county_fips, source=source)
    present_brand_ids = {loc["brand_id"] for loc in locs_in_county}
    mavis_names_ordered = sorted(
        name for bid, name in mavis_name_by_id.items() if bid in present_brand_ids
    )

    by_city = {}
    for loc in locs_in_county:
        by_city.setdefault(loc["city"], []).append(loc)

    towns_out = []
    for t in base:
        locs = by_city.get(t["city"], [])
        area_avg = _weighted_avg(locs, "raw_rating")
        by_brand = {}
        for loc in locs:
            by_brand.setdefault(loc["brand_id"], []).append(loc)
        brand_pct_above = {}
        if area_avg is not None:
            for brand_id, brand_locs in by_brand.items():
                name = mavis_name_by_id.get(brand_id)
                if not name:
                    continue
                n_above = sum(1 for l in brand_locs if l["raw_rating"] > area_avg)
                brand_pct_above[name] = n_above / len(brand_locs)
        towns_out.append({**t, "area_avg_rating": area_avg, "brand_pct_above": brand_pct_above})

    return {"brands": mavis_names_ordered, "towns": towns_out}


def county_town_summary(state: str, county_fips: str, source: str = "google_maps") -> list:
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
                WHERE ctd.state = %(state)s AND ctd.county_fips = %(county_fips)s AND ctd.source = %(source)s
                ORDER BY ctd.town_delta DESC NULLS LAST
            """, {"state": state, "county_fips": county_fips, "source": source})
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


# Rating-mix bucket bounds for brand_rollup() below - matches the design's
# 5-band split (under 3.5, 3.5-4.0, 4.0-4.4, 4.4-4.7, 4.7+).
_MIX_BOUNDS = (3.5, 4.0, 4.4, 4.7)


def _mix_bucket(rating: float) -> int:
    for i, bound in enumerate(_MIX_BOUNDS):
        if rating < bound:
            return i
    return len(_MIX_BOUNDS)


def brand_rollup(state: str = None, city: str = None, source: str = "google_maps") -> dict:
    """Every tracked brand - Mavis banners and every named competitor alike
    - ranked on one list and scored against the category average rating
    within the given scope: nationwide by default, or narrowed to one state
    (optionally one town within that state). Unlike the county/town
    Mavis-banner breakdowns above, this is genuinely cross-brand - every row
    is a full brand, not just the Mavis portfolio - so it's computed
    straight off location_adjusted_ratings rather than any Mavis-only view.
    Powers the "league table" rollup view."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT lar.brand_id, vb.name, vb.family, lar.n, lar.raw_rating
                FROM voice.location_adjusted_ratings lar
                JOIN voice.brands vb ON vb.brand_id = lar.brand_id
                WHERE lar.source = %(source)s
                  AND (%(state)s::text IS NULL OR lar.state = %(state)s::text)
                  AND (%(city)s::text IS NULL OR lar.city = %(city)s::text)
            """, {"state": state, "city": city, "source": source})
            rows = cur.fetchall()

    if not rows:
        return {"category_avg": None, "brands": []}

    all_locs = [{"n": n, "raw_rating": float(r)} for _, _, _, n, r in rows]
    category_avg = _weighted_avg(all_locs, "raw_rating")

    by_brand = {}
    for brand_id, name, family, n, raw_rating in rows:
        by_brand.setdefault((brand_id, name, family), []).append({"n": n, "raw_rating": float(raw_rating)})

    out = []
    for (brand_id, name, family), locs in by_brand.items():
        dist = [0, 0, 0, 0, 0]
        for loc in locs:
            dist[_mix_bucket(loc["raw_rating"])] += 1
        out.append({
            "brand_id": brand_id, "name": name, "mavis": family == "mavis",
            "avg": _weighted_avg(locs, "raw_rating"),
            "locs": len(locs), "reviews": sum(l["n"] for l in locs),
            "dist": dist,
        })
    out.sort(key=lambda b: (b["avg"] is not None, b["avg"]), reverse=True)
    return {"category_avg": category_avg, "brands": out}


def state_towns(state: str, source: str = "google_maps") -> list:
    """Distinct towns with at least one rated location in this state - for
    the rollup view's town filter. Independent of county (unlike
    county_town_summary), since the rollup filters by state + town only."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT city FROM voice.location_adjusted_ratings
                WHERE state = %(state)s AND city IS NOT NULL AND source = %(source)s
                ORDER BY city
            """, {"state": state, "source": source})
            rows = cur.fetchall()
    return [r[0] for r in rows]


def county_locations(state: str, county_fips: str, city: str = None, source: str = "google_maps") -> list:
    """Every rated location (Mavis AND competitor) in one county, optionally
    narrowed to one town within it - for the map's store-marker view and the
    table's store-level drill. Pulls straight from location_adjusted_ratings
    (not the Mavis-only location_benchmark) so competitor locations show up
    too. Mavis rows also carry delta/low_comparability (left-joined from
    location_benchmark on the SAME source, NULL for competitors - a
    competitor has no "delta vs its neighbors")."""
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
                LEFT JOIN voice.location_benchmark lb ON lb.location_id = lar.location_id AND lb.source = lar.source
                WHERE lar.state = %(state)s AND lar.county_fips = %(county_fips)s AND lar.source = %(source)s
                  AND (%(city)s::text IS NULL OR lar.city = %(city)s::text)
                ORDER BY lar.family, lar.brand_name, lar.location_name
            """, {"state": state, "county_fips": county_fips, "city": city, "source": source})
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


