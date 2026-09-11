-- Competitor Research Dashboard — Postgres schema (Supabase)
-- Run once via scripts/init_db.py, which also seeds `categories` and `competitors`
-- from config/competitors.yaml and docs/content_taxonomy.md.

CREATE TABLE IF NOT EXISTS competitors (
    id                SERIAL PRIMARY KEY,
    name              TEXT NOT NULL,
    instagram_handle  TEXT NOT NULL UNIQUE,
    instagram_url     TEXT NOT NULL,
    follower_count    INTEGER,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

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
    like_count            INTEGER,
    comment_count         INTEGER,
    view_count            INTEGER,
    category              TEXT REFERENCES categories(name),
    category_confidence   TEXT CHECK (category_confidence IN ('high', 'medium', 'low')),
    scraped_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_posts_competitor  ON posts(competitor_id);
CREATE INDEX IF NOT EXISTS idx_posts_posted_at   ON posts(posted_at);
CREATE INDEX IF NOT EXISTS idx_posts_category    ON posts(category);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id                       SERIAL PRIMARY KEY,
    run_date                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_type                 TEXT NOT NULL CHECK (run_type IN ('backfill', 'weekly', 'manual')),
    competitors_scraped      INTEGER NOT NULL DEFAULT 0,
    posts_added              INTEGER NOT NULL DEFAULT 0,
    posts_skipped_duplicate  INTEGER NOT NULL DEFAULT 0,
    errors                   JSONB,
    status                   TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed'))
);
