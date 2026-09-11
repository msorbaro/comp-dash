-- Competitor Research Dashboard — Postgres schema (Supabase)
-- Run once via scripts/init_db.py, which also seeds `categories` and `competitors`
-- from config/competitors.yaml and docs/content_taxonomy.md.

CREATE TABLE IF NOT EXISTS competitors (
    id                SERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    instagram_handle  TEXT NOT NULL UNIQUE,
    instagram_url     TEXT NOT NULL,
    website_url       TEXT,
    facebook_url      TEXT,
    follower_count    INTEGER,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    is_own_brand      BOOLEAN NOT NULL DEFAULT FALSE,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent migrations for tables created before these columns existed.
ALTER TABLE competitors ADD COLUMN IF NOT EXISTS website_url TEXT;
ALTER TABLE competitors ADD COLUMN IF NOT EXISTS facebook_url TEXT;
ALTER TABLE competitors ADD COLUMN IF NOT EXISTS is_own_brand BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS competitor_groups (
    competitor_id  INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    group_name     TEXT NOT NULL,
    PRIMARY KEY (competitor_id, group_name)
);

CREATE TABLE IF NOT EXISTS categories (
    name         TEXT PRIMARY KEY,
    description  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id                    SERIAL PRIMARY KEY,
    competitor_id         INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    instagram_post_id     TEXT NOT NULL UNIQUE,
    post_url              TEXT NOT NULL,
    post_type             TEXT NOT NULL CHECK (post_type IN ('Image', 'Carousel', 'Reel')),
    posted_at             TIMESTAMPTZ NOT NULL,
    caption               TEXT,
    media_url             TEXT,
    thumbnail             BYTEA,
    like_count            INTEGER,
    comment_count         INTEGER,
    view_count            INTEGER,
    category              TEXT REFERENCES categories(name),
    category_confidence   TEXT CHECK (category_confidence IN ('high', 'medium', 'low')),
    scraped_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent migration for tables created before the `thumbnail` column existed.
ALTER TABLE posts ADD COLUMN IF NOT EXISTS thumbnail BYTEA;

CREATE INDEX IF NOT EXISTS idx_posts_competitor  ON posts(competitor_id);
CREATE INDEX IF NOT EXISTS idx_posts_posted_at   ON posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_posts_category    ON posts(category);

CREATE TABLE IF NOT EXISTS homepage_snapshots (
    id                    SERIAL PRIMARY KEY,
    competitor_id         INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    captured_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    screenshot            BYTEA,
    image_hash            TEXT NOT NULL,
    changed               BOOLEAN NOT NULL,
    theme                 TEXT,
    theme_confidence      TEXT CHECK (theme_confidence IN ('high', 'medium', 'low')),
    notes                 TEXT
);

CREATE INDEX IF NOT EXISTS idx_homepage_competitor ON homepage_snapshots(competitor_id);
CREATE INDEX IF NOT EXISTS idx_homepage_captured_at ON homepage_snapshots(captured_at);

CREATE TABLE IF NOT EXISTS ads (
    id                    SERIAL PRIMARY KEY,
    competitor_id         INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    ad_archive_id         TEXT NOT NULL UNIQUE,
    ad_url                TEXT NOT NULL,
    creative_type         TEXT NOT NULL CHECK (creative_type IN ('Image', 'Video', 'Carousel')),
    creative              BYTEA,
    caption               TEXT,
    headline              TEXT,
    platforms             TEXT[],
    start_date            DATE,
    end_date              DATE,
    is_active             BOOLEAN NOT NULL DEFAULT TRUE,
    category              TEXT,
    category_confidence   TEXT CHECK (category_confidence IN ('high', 'medium', 'low')),
    first_seen_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ads_competitor ON ads(competitor_id);
CREATE INDEX IF NOT EXISTS idx_ads_is_active ON ads(is_active);
CREATE INDEX IF NOT EXISTS idx_ads_category ON ads(category);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id                       SERIAL PRIMARY KEY,
    run_date                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    source                   TEXT NOT NULL DEFAULT 'instagram' CHECK (source IN ('instagram', 'homepage', 'ads')),
    run_type                 TEXT NOT NULL CHECK (run_type IN ('backfill', 'weekly', 'manual')),
    competitors_scraped      INTEGER NOT NULL DEFAULT 0,
    posts_added              INTEGER NOT NULL DEFAULT 0,
    posts_skipped_duplicate  INTEGER NOT NULL DEFAULT 0,
    errors                   JSONB,
    status                   TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed'))
);

-- Idempotent migration for tables created before the `source` column existed.
ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'instagram';
