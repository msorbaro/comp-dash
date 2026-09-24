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

-- Tracks which (brand, city) Yelp rating searches have already completed -
-- same resumability purpose as location_census_runs below, one row per
-- (brand, city) group voice/yelp_ratings.py has searched (Yelp has no
-- place ID we can seed from, so this is searched by name+city instead of
-- crawled by ID like the Google census).
CREATE TABLE IF NOT EXISTS voice.yelp_rating_runs (
    brand_id      INTEGER NOT NULL REFERENCES voice.brands(brand_id) ON DELETE CASCADE,
    city          TEXT NOT NULL,
    state         TEXT NOT NULL,
    completed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_id, city, state)
);

-- Same as yelp_rating_runs above, for voice/apple_maps_ratings.py.
CREATE TABLE IF NOT EXISTS voice.apple_maps_rating_runs (
    brand_id      INTEGER NOT NULL REFERENCES voice.brands(brand_id) ON DELETE CASCADE,
    city          TEXT NOT NULL,
    state         TEXT NOT NULL,
    completed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_id, city, state)
);

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

-- Phase 3: individual review text + date, per location - not just the
-- aggregate rating_snapshots above. Sentiment columns are nullable and
-- filled by a separate classification pass (categorize/sentiment.py), not
-- at scrape time, so the (paid) scrape and the (separately paid) LLM pass
-- stay independently retryable - a failed/rerun classification pass never
-- re-pays for the Apify scrape.
CREATE TABLE IF NOT EXISTS voice.reviews (
    review_id            BIGSERIAL PRIMARY KEY,
    location_id          INTEGER NOT NULL REFERENCES voice.locations(location_id) ON DELETE CASCADE,
    source                TEXT NOT NULL DEFAULT 'google_maps',
    source_review_id      TEXT NOT NULL,
    rating                SMALLINT,
    review_date           TIMESTAMPTZ,
    text                  TEXT,
    language              TEXT,
    sentiment             TEXT CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    sentiment_confidence  TEXT,
    sentiment_reason      TEXT,
    fetched_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_review_id)
);
CREATE INDEX IF NOT EXISTS idx_voice_reviews_location ON voice.reviews(location_id, review_date);
CREATE INDEX IF NOT EXISTS idx_voice_reviews_date ON voice.reviews(review_date);

-- `themed_at` marks a review as processed by categorize/review_themes.py,
-- independent of whether it produced any theme rows below - a genuinely
-- theme-less review (e.g. "Good.") must still count as "done" or it would
-- get re-submitted (and re-paid for) on every subsequent run.
ALTER TABLE voice.reviews ADD COLUMN IF NOT EXISTS themed_at TIMESTAMPTZ;

-- Multi-label theme extraction from review text (categorize/review_themes.py) -
-- a many-to-one companion to voice.reviews rather than columns on it, since
-- one review can surface several themes (e.g. "fast service but overpriced"
-- = speed_wait_time:positive AND price_value:negative), each with its OWN
-- sentiment that can differ from the review's overall sentiment.
CREATE TABLE IF NOT EXISTS voice.review_themes (
    review_id        BIGINT NOT NULL REFERENCES voice.reviews(review_id) ON DELETE CASCADE,
    theme            TEXT NOT NULL,
    theme_sentiment  TEXT NOT NULL CHECK (theme_sentiment IN ('positive', 'neutral', 'negative')),
    PRIMARY KEY (review_id, theme)
);
CREATE INDEX IF NOT EXISTS idx_voice_review_themes_theme ON voice.review_themes(theme);

-- Tracks which review-scrape batches (a batch = one Apify actor call over a
-- chunk of place IDs) have already completed, same crash-safety purpose as
-- location_census_runs above - a killed run resumes without re-paying for
-- batches already fetched. batch_key is a stable hash of the sorted place
-- IDs in that batch, computed by voice/reviews.py.
CREATE TABLE IF NOT EXISTS voice.review_scrape_runs (
    batch_key     TEXT PRIMARY KEY,
    n_places      INTEGER NOT NULL,
    n_reviews     INTEGER NOT NULL,
    completed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Reddit brand mentions (posts + comments) - not state-scoped like the
-- tables above, since a Reddit mention isn't tied to a physical location
-- the way a review is; one row per post or comment, one search per
-- tracked brand (Mavis banners AND competitors). Sentiment/theme columns
-- are nullable and filled by a separate classification pass
-- (categorize/reddit_sentiment.py), same reasoning as voice.reviews - the
-- (paid) scrape and the (separately paid) LLM pass stay independently
-- retryable.
CREATE TABLE IF NOT EXISTS voice.reddit_mentions (
    mention_id        BIGSERIAL PRIMARY KEY,
    brand_id          INTEGER NOT NULL REFERENCES voice.brands(brand_id) ON DELETE CASCADE,
    reddit_id         TEXT NOT NULL,
    type              TEXT NOT NULL CHECK (type IN ('post', 'comment')),
    parent_post_id    TEXT,
    subreddit         TEXT,
    author            TEXT,
    title             TEXT,
    text              TEXT,
    score             INTEGER,
    num_comments      INTEGER,
    permalink         TEXT,
    created_at        TIMESTAMPTZ,
    is_relevant       BOOLEAN,
    sentiment         TEXT CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    sentiment_confidence TEXT,
    theme             TEXT,
    comparison_brand_id INTEGER REFERENCES voice.brands(brand_id),
    reason            TEXT,
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (reddit_id, type)
);
CREATE INDEX IF NOT EXISTS idx_voice_reddit_mentions_brand ON voice.reddit_mentions(brand_id);
CREATE INDEX IF NOT EXISTS idx_voice_reddit_mentions_created ON voice.reddit_mentions(created_at);

-- `aspect_themed_at` marks a mention as processed by
-- categorize/reddit_mention_themes.py - separate from the `theme` column
-- above (that one is post-PURPOSE: complaint/question/recommendation/etc.,
-- filled by categorize/reddit_sentiment.py). This pass is aspect-based
-- (price, speed, honesty, etc. - same taxonomy as categorize/review_themes.py,
-- since it's the same tire/auto-repair domain), and a mention can surface
-- several aspects at once, hence the separate many-to-one table below
-- rather than another column here.
ALTER TABLE voice.reddit_mentions ADD COLUMN IF NOT EXISTS aspect_themed_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS voice.reddit_mention_themes (
    mention_id       BIGINT NOT NULL REFERENCES voice.reddit_mentions(mention_id) ON DELETE CASCADE,
    theme            TEXT NOT NULL,
    theme_sentiment  TEXT NOT NULL CHECK (theme_sentiment IN ('positive', 'neutral', 'negative')),
    PRIMARY KEY (mention_id, theme)
);
CREATE INDEX IF NOT EXISTS idx_voice_reddit_mention_themes_theme ON voice.reddit_mention_themes(theme);

-- Tracks which brands' Reddit searches have already completed - same
-- resumability purpose as the other _runs tables. Not state-scoped.
CREATE TABLE IF NOT EXISTS voice.reddit_scrape_runs (
    brand_id      INTEGER NOT NULL REFERENCES voice.brands(brand_id) ON DELETE CASCADE,
    completed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (brand_id)
);

-- Town (Census "place") boundary polygons, for the map's county -> town
-- drill-down - one row per (state, town) actually present in our own data.
-- Geometry comes from the real US Census TIGER Places dataset (see
-- scripts/backfill_town_boundaries.py), not drawn/approximated - a town
-- with no matching Census place is simply absent here (matched = false
-- logged, never a guessed shape).
CREATE TABLE IF NOT EXISTS voice.town_boundaries (
    state        TEXT NOT NULL,
    city         TEXT NOT NULL,
    geometry     JSONB NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (state, city)
);
