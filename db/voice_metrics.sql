-- Customer Voice metrics layer (Phase 4) - a TEMPLATE, not a bare idempotent
-- schema file like the others in this directory. {shrinkage_m},
-- {ring_radius_km}, {min_locations_for_state}, {min_reviews_for_state} get
-- substituted in by scripts/refresh_voice_metrics.py from
-- config/voice_metrics.yaml before this is run - that's what "configurable"
-- means for a materialized view (no runtime parameters), per the user's
-- spec. Re-run the refresh script any time voice.rating_snapshots changes;
-- these views do not auto-refresh.
--
-- Every intermediate value the metrics spec calls for is its own queryable
-- view, in dependency order, each traceable back to the individual stores
-- that produced it - directly satisfying the acceptance criterion "trace
-- that number back through the materialized view to the individual stores
-- that produced it."

DROP MATERIALIZED VIEW IF EXISTS voice.competitor_county_rollup CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.competitor_state_rollup CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.brand_state_delta CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.county_town_delta CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.county_delta CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.town_delta CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.state_delta CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.location_benchmark CASCADE;
DROP MATERIALIZED VIEW IF EXISTS voice.location_adjusted_ratings CASCADE;

-- 4a: Bayesian-shrink each location's raw rating toward the global mean,
-- adj_rating = (n*r + m*C) / (n+m). One row per (location, source) that has
-- a rating at all (a location with zero reviews has nothing to shrink and
-- is correctly absent from every view downstream of this one).
--
-- Keyed by (location_id, source), NOT just location_id: rating_snapshots
-- now holds both 'google_maps' and 'apple_maps' rows per location (Phase 4b
-- added an Apple Maps pull into the same table, source column already
-- existed for exactly this). The original DISTINCT ON (location_id) alone
-- picked whichever source's snapshot happened to be captured most
-- recently, silently mixing Google and Apple ratings depending on scrape
-- order - confirmed live, not hypothetical, once both sources existed for
-- the same locations. global_mean is computed PER SOURCE too, since a raw
-- Apple Maps rating distribution isn't the same population as Google's -
-- shrinking a Google rating toward an Apple-derived mean (or vice versa)
-- would be comparing apples to a different orchard's oranges.
CREATE MATERIALIZED VIEW voice.location_adjusted_ratings AS
WITH latest_rating AS (
    SELECT DISTINCT ON (location_id, source) location_id, source, avg_rating, review_count, captured_at
    FROM voice.rating_snapshots
    WHERE avg_rating IS NOT NULL
    ORDER BY location_id, source, captured_at DESC
),
global_mean AS (
    SELECT source, avg(avg_rating) AS c FROM latest_rating GROUP BY source
)
SELECT
    l.location_id, l.brand_id, b.name AS brand_name, b.family,
    l.name AS location_name, l.city, l.state, l.county_fips, l.county_name, l.lat, l.lng,
    r.source,
    r.avg_rating AS raw_rating, r.review_count AS n,
    (r.review_count * r.avg_rating + {shrinkage_m} * g.c) / (r.review_count + {shrinkage_m}) AS adj_rating
FROM voice.locations l
JOIN voice.brands b ON b.brand_id = l.brand_id
JOIN latest_rating r ON r.location_id = l.location_id
JOIN global_mean g ON g.source = r.source;

CREATE UNIQUE INDEX ON voice.location_adjusted_ratings (location_id, source);
CREATE INDEX ON voice.location_adjusted_ratings (family, source);

-- 4b: for each Mavis location, benchmark against the average RAW rating of
-- EVERY rated location - Mavis and competitor alike, including the store
-- itself - in the SAME TOWN (state + city), weighted by review count so a
-- busy store counts more than a dead one. "delta should be calculated for
-- now as the store rating - town average" (instruction) means literally
-- that: a store's own raw rating minus the town's own raw average, not a
-- competitor-only pool and not the shrinkage-adjusted rating - so this
-- joins to ALL families (not just 'competitor') and uses raw_rating (not
-- adj_rating) on both sides. Two consequences worth knowing: (1) the join
-- always matches at least the store's own row, so comp_benchmark_rating
-- and delta are never NULL anymore (previously a Mavis location in a town
-- with zero same-city competitors got dropped from every rollup below -
-- e.g. 3 of Citrus County FL's 4 Mavis towns were silently missing this
-- way); (2) a lone store in a town is being compared partly against
-- itself, which is intentional - "the average rating of stores in the
-- town" includes every store that's actually in the town.
-- {ring_radius_km}/ring_radius_miles are no longer used here - kept in
-- config in case this reverts. n_competitors_in_ring/low_comparability
-- keep their field names (many consumers reference them) but now mean "any
-- rated store in this town, including this one" - still flags fewer than 3
-- as thin evidence, per spec.
-- c.source = m.source is the second consequence of the same source-mixing
-- bug: a Google-rated Mavis store must be benchmarked against other
-- GOOGLE-rated stores in its town, not an Apple Maps average (or a blend
-- of both) - matching source on both sides of the join is what makes this
-- an apples-to-apples (pun acknowledged) comparison per source.
CREATE MATERIALIZED VIEW voice.location_benchmark AS
SELECT
    m.location_id, m.brand_id, m.brand_name, m.location_name,
    m.city, m.state, m.county_fips, m.county_name, m.lat, m.lng, m.source,
    m.raw_rating AS mavis_raw_rating, m.adj_rating AS mavis_adj_rating, m.n AS mavis_n,
    count(c.location_id) AS n_competitors_in_ring,
    sum(c.n) AS comp_total_reviews,
    (sum(c.n * c.raw_rating) / NULLIF(sum(c.n), 0)) AS comp_benchmark_rating,
    (m.raw_rating - (sum(c.n * c.raw_rating) / NULLIF(sum(c.n), 0))) AS delta,
    (count(c.location_id) < 3) AS low_comparability
FROM voice.location_adjusted_ratings m
LEFT JOIN voice.location_adjusted_ratings c
    ON c.state = m.state AND c.city = m.city AND c.source = m.source
WHERE m.family = 'mavis'
GROUP BY m.location_id, m.brand_id, m.brand_name, m.location_name, m.city, m.state, m.county_fips, m.county_name, m.lat, m.lng,
         m.source, m.raw_rating, m.adj_rating, m.n;

CREATE UNIQUE INDEX ON voice.location_benchmark (location_id, source);
CREATE INDEX ON voice.location_benchmark (state, source);
CREATE INDEX ON voice.location_benchmark (state, city, source);

-- 4c + 4d: roll up to state, weighted by each location's own review count;
-- suppressed = fewer than {min_locations_for_state} Mavis locations OR
-- fewer than {min_reviews_for_state} total Mavis reviews in that state.
-- avg_comp_benchmark_rating is a direct weighted average of each location's
-- own (raw-rating-based) comp_benchmark_rating - not derived by subtracting
-- state_delta from avg_mavis_adj_rating, since the former is on the raw
-- scale and the latter (mavis' own rating) stays shrinkage-adjusted; mixing
-- the two via subtraction would silently produce a nonsense number.
CREATE MATERIALIZED VIEW voice.state_delta AS
SELECT
    state, source,
    count(*) AS n_mavis_locations,
    sum(mavis_n) AS total_mavis_reviews,
    sum(CASE WHEN low_comparability THEN 1 ELSE 0 END) AS n_low_comparability_locations,
    (sum(mavis_n * mavis_adj_rating) / NULLIF(sum(mavis_n), 0)) AS avg_mavis_adj_rating,
    (sum(mavis_n * delta) / NULLIF(sum(mavis_n), 0)) AS state_delta,
    (sum(mavis_n * comp_benchmark_rating) / NULLIF(sum(mavis_n), 0)) AS avg_comp_benchmark_rating,
    (count(*) < {min_locations_for_state} OR coalesce(sum(mavis_n), 0) < {min_reviews_for_state}) AS suppressed
FROM voice.location_benchmark
WHERE delta IS NOT NULL
GROUP BY state, source;

CREATE UNIQUE INDEX ON voice.state_delta (state, source);

-- Same as state_delta, grouped by (state, city) instead - the table's
-- town/metro drill level and the map's state-click-to-towns drill-down.
-- Its own, much lower suppression bar: a single town having only 1 Mavis
-- store is normal, not thin data, so reusing the state-level "5+ locations"
-- threshold here was wrong (it flagged real towns like Corsicana, TX - 1
-- store, 411 reviews - as insufficient).
CREATE MATERIALIZED VIEW voice.town_delta AS
SELECT
    state, city, source,
    count(*) AS n_mavis_locations,
    sum(mavis_n) AS total_mavis_reviews,
    sum(CASE WHEN low_comparability THEN 1 ELSE 0 END) AS n_low_comparability_locations,
    (sum(mavis_n * mavis_adj_rating) / NULLIF(sum(mavis_n), 0)) AS avg_mavis_adj_rating,
    (sum(mavis_n * delta) / NULLIF(sum(mavis_n), 0)) AS town_delta,
    (sum(mavis_n * comp_benchmark_rating) / NULLIF(sum(mavis_n), 0)) AS avg_comp_benchmark_rating,
    (count(*) < {min_locations_for_town} OR coalesce(sum(mavis_n), 0) < {min_reviews_for_town}) AS suppressed
FROM voice.location_benchmark
WHERE delta IS NOT NULL
GROUP BY state, city, source;

CREATE UNIQUE INDEX ON voice.town_delta (state, city, source);

-- Same again, grouped by (state, county) instead of (state, city) - the
-- map's state-click-to-counties drill-down. County comes from each
-- location's zip via a HUD crosswalk (scripts/backfill_voice_counties.py),
-- not city-name text, so this is a clean administrative-boundary rollup
-- independent of how a place lists its own town name. Same town-level
-- suppression bar (a county is a similarly small slice as a town).
CREATE MATERIALIZED VIEW voice.county_delta AS
SELECT
    state, county_fips, county_name, source,
    count(*) AS n_mavis_locations,
    sum(mavis_n) AS total_mavis_reviews,
    sum(CASE WHEN low_comparability THEN 1 ELSE 0 END) AS n_low_comparability_locations,
    (sum(mavis_n * mavis_adj_rating) / NULLIF(sum(mavis_n), 0)) AS avg_mavis_adj_rating,
    (sum(mavis_n * delta) / NULLIF(sum(mavis_n), 0)) AS county_delta,
    (sum(mavis_n * comp_benchmark_rating) / NULLIF(sum(mavis_n), 0)) AS avg_comp_benchmark_rating,
    (count(*) < {min_locations_for_town} OR coalesce(sum(mavis_n), 0) < {min_reviews_for_town}) AS suppressed
FROM voice.location_benchmark
WHERE delta IS NOT NULL AND county_fips IS NOT NULL
GROUP BY state, county_fips, county_name, source;

CREATE UNIQUE INDEX ON voice.county_delta (county_fips, source);
CREATE INDEX ON voice.county_delta (state, source);

-- Towns within one county - the map's county-click-to-towns drill-down
-- (one level deeper than county_delta, scoped to a single county instead
-- of state-wide, since the same town name can appear in different
-- counties). Same town-level suppression bar.
CREATE MATERIALIZED VIEW voice.county_town_delta AS
SELECT
    state, county_fips, county_name, city, source,
    count(*) AS n_mavis_locations,
    sum(mavis_n) AS total_mavis_reviews,
    sum(CASE WHEN low_comparability THEN 1 ELSE 0 END) AS n_low_comparability_locations,
    (sum(mavis_n * mavis_adj_rating) / NULLIF(sum(mavis_n), 0)) AS avg_mavis_adj_rating,
    (sum(mavis_n * delta) / NULLIF(sum(mavis_n), 0)) AS town_delta,
    (sum(mavis_n * comp_benchmark_rating) / NULLIF(sum(mavis_n), 0)) AS avg_comp_benchmark_rating,
    (count(*) < {min_locations_for_town} OR coalesce(sum(mavis_n), 0) < {min_reviews_for_town}) AS suppressed
FROM voice.location_benchmark
WHERE delta IS NOT NULL AND county_fips IS NOT NULL
GROUP BY state, county_fips, county_name, city, source;

CREATE UNIQUE INDEX ON voice.county_town_delta (county_fips, city, source);

-- Per-brand state rollup - same shape as state_delta, but grouped by Mavis
-- banner too, so "how does Midas do in Texas vs local competitors" is its
-- own number instead of being pooled into the whole portfolio's average.
-- Uses the town-level (not state-level) suppression bar, since one brand
-- within one state is a similarly small slice as one town.
CREATE MATERIALIZED VIEW voice.brand_state_delta AS
SELECT
    state, brand_id, brand_name, source,
    count(*) AS n_mavis_locations,
    sum(mavis_n) AS total_mavis_reviews,
    sum(CASE WHEN low_comparability THEN 1 ELSE 0 END) AS n_low_comparability_locations,
    (sum(mavis_n * mavis_adj_rating) / NULLIF(sum(mavis_n), 0)) AS avg_mavis_adj_rating,
    (sum(mavis_n * delta) / NULLIF(sum(mavis_n), 0)) AS state_delta,
    (sum(mavis_n * comp_benchmark_rating) / NULLIF(sum(mavis_n), 0)) AS avg_comp_benchmark_rating,
    (count(*) < {min_locations_for_town} OR coalesce(sum(mavis_n), 0) < {min_reviews_for_town}) AS suppressed
FROM voice.location_benchmark
WHERE delta IS NOT NULL
GROUP BY state, brand_id, brand_name, source;

CREATE INDEX ON voice.brand_state_delta (state, source);

-- Per-competitor rollups - each named competitor's own footprint and
-- average rating within a state/county, independent of Mavis entirely (no
-- delta/benchmark here - "delta" is specifically Mavis vs. its nearby
-- competitors, and a competitor doesn't have one vs. itself). Same
-- shrinkage-adjusted rating already computed in location_adjusted_ratings,
-- just pooled per brand instead of per location.
CREATE MATERIALIZED VIEW voice.competitor_state_rollup AS
SELECT
    state, brand_id, brand_name, source,
    count(*) AS n_locations,
    sum(n) AS total_reviews,
    (sum(n * raw_rating) / NULLIF(sum(n), 0)) AS avg_raw_rating,
    (sum(n * adj_rating) / NULLIF(sum(n), 0)) AS avg_adj_rating
FROM voice.location_adjusted_ratings
WHERE family = 'competitor'
GROUP BY state, brand_id, brand_name, source;

CREATE INDEX ON voice.competitor_state_rollup (state, source);

CREATE MATERIALIZED VIEW voice.competitor_county_rollup AS
SELECT
    state, county_fips, county_name, brand_id, brand_name, source,
    count(*) AS n_locations,
    sum(n) AS total_reviews,
    (sum(n * raw_rating) / NULLIF(sum(n), 0)) AS avg_raw_rating,
    (sum(n * adj_rating) / NULLIF(sum(n), 0)) AS avg_adj_rating
FROM voice.location_adjusted_ratings
WHERE family = 'competitor' AND county_fips IS NOT NULL
GROUP BY state, county_fips, county_name, brand_id, brand_name, source;

CREATE INDEX ON voice.competitor_county_rollup (county_fips, source);
