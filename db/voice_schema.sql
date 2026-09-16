-- Customer Voice — Postgres schema (Supabase), namespaced in its own `voice`
-- schema rather than `public` (where everything else in this project lives)
-- so the messaging-side tables and the review-side tables stay cleanly
-- separated while still joinable in the same database. Run once via
-- scripts/init_voice_db.py, which also seeds voice.brands from
-- config/voice_brands.yaml.
--
-- Scoped to Phases 1-2 only (location census + ratings census) - reviews,
-- review_themes, and themes tables get added when Phase 3/5 is actually
-- planned, not created unused ahead of time.

CREATE SCHEMA IF NOT EXISTS voice;

CREATE TABLE IF NOT EXISTS voice.brands (
    brand_id       SERIAL PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,
    family         TEXT NOT NULL CHECK (family IN ('mavis', 'competitor')),
    competitor_id  INTEGER REFERENCES competitors(id),
    aliases        TEXT[] NOT NULL DEFAULT '{}',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS voice.locations (
    location_id      SERIAL PRIMARY KEY,
    brand_id         INTEGER NOT NULL REFERENCES voice.brands(brand_id) ON DELETE CASCADE,
    source           TEXT NOT NULL DEFAULT 'google_maps',
    source_place_id  TEXT NOT NULL,
    name             TEXT,
    street           TEXT,
    city             TEXT,
    state            TEXT,
    zip              TEXT,
    country_code     TEXT,
    lat              DOUBLE PRECISION,
    lng              DOUBLE PRECISION,
    category         TEXT,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_place_id)
);
CREATE INDEX IF NOT EXISTS idx_voice_locations_brand ON voice.locations(brand_id);
CREATE INDEX IF NOT EXISTS idx_voice_locations_state ON voice.locations(state);

-- County attribution (added for the map's state -> county -> store
-- drill-down) - derived from each location's own zip via a HUD ZIP-COUNTY
-- crosswalk, not fabricated or geocoded live. See
-- scripts/backfill_voice_counties.py; NULL means the zip had no crosswalk
-- match rather than a guess.
ALTER TABLE voice.locations ADD COLUMN IF NOT EXISTS county_fips TEXT;
ALTER TABLE voice.locations ADD COLUMN IF NOT EXISTS county_name TEXT;
CREATE INDEX IF NOT EXISTS idx_voice_locations_county ON voice.locations(county_fips);

-- Append-only time series (never overwritten) - one row per pull, so rating
-- movement can be trended over time instead of only ever showing "now".
CREATE TABLE IF NOT EXISTS voice.rating_snapshots (
    snapshot_id   SERIAL PRIMARY KEY,
    location_id   INTEGER NOT NULL REFERENCES voice.locations(location_id) ON DELETE CASCADE,
    source        TEXT NOT NULL,
    avg_rating    NUMERIC(3,2),
    review_count  INTEGER,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_voice_rating_snapshots_location ON voice.rating_snapshots(location_id, captured_at);

-- Tracks which (brand, state) location-census combos have already completed
-- a full fetch+write - not the same as "produced results": a combo that
-- legitimately found zero locations (e.g. a brand with no stores in that
-- state) still gets marked done, so a re-run skips it instead of re-paying
-- for the same Apify call. Confirmed necessary live: a pilot run got killed
-- (low local memory, unrelated to this code) partway through 105 combos -
-- without this, a re-run would have redone the ones that already succeeded.
CREATE TABLE IF NOT EXISTS voice.location_census_runs (
    brand_id      INTEGER NOT NULL REFERENCES voice.brands(brand_id) ON DELETE CASCADE,
    state         TEXT NOT NULL,
    completed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_id, state)
);
