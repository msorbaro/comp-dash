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
    tiktok_handle     TEXT,
    youtube_url       TEXT,
    x_handle          TEXT,
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
ALTER TABLE competitors ADD COLUMN IF NOT EXISTS tiktok_handle TEXT;
ALTER TABLE competitors ADD COLUMN IF NOT EXISTS youtube_url TEXT;
ALTER TABLE competitors ADD COLUMN IF NOT EXISTS x_handle TEXT;
ALTER TABLE ads ADD COLUMN IF NOT EXISTS video_url TEXT;

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
    video_url             TEXT,
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

CREATE TABLE IF NOT EXISTS tiktok_videos (
    id                    SERIAL PRIMARY KEY,
    competitor_id         INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    tiktok_video_id       TEXT NOT NULL UNIQUE,
    video_url             TEXT NOT NULL,
    caption               TEXT,
    posted_at             TIMESTAMPTZ,
    duration_seconds      INTEGER,
    thumbnail             BYTEA,
    view_count            INTEGER,
    like_count            INTEGER,
    comment_count         INTEGER,
    share_count           INTEGER,
    category              TEXT,
    category_confidence   TEXT CHECK (category_confidence IN ('high', 'medium', 'low')),
    scraped_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tiktok_competitor ON tiktok_videos(competitor_id);
CREATE INDEX IF NOT EXISTS idx_tiktok_posted_at ON tiktok_videos(posted_at);

CREATE TABLE IF NOT EXISTS youtube_videos (
    id                    SERIAL PRIMARY KEY,
    competitor_id         INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    youtube_video_id      TEXT NOT NULL UNIQUE,
    video_url             TEXT NOT NULL,
    title                 TEXT,
    caption               TEXT,
    posted_at             TIMESTAMPTZ,
    duration              TEXT,
    video_type            TEXT CHECK (video_type IN ('video', 'shorts')),
    thumbnail             BYTEA,
    view_count            INTEGER,
    like_count            INTEGER,
    comment_count         INTEGER,
    category              TEXT,
    category_confidence   TEXT CHECK (category_confidence IN ('high', 'medium', 'low')),
    scraped_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_youtube_competitor ON youtube_videos(competitor_id);
CREATE INDEX IF NOT EXISTS idx_youtube_posted_at ON youtube_videos(posted_at);

CREATE TABLE IF NOT EXISTS x_posts (
    id                    SERIAL PRIMARY KEY,
    competitor_id         INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    tweet_id              TEXT NOT NULL UNIQUE,
    post_url              TEXT NOT NULL,
    text                  TEXT,
    posted_at             TIMESTAMPTZ,
    like_count            INTEGER,
    retweet_count         INTEGER,
    reply_count           INTEGER,
    quote_count           INTEGER,
    view_count            INTEGER,
    is_retweet            BOOLEAN NOT NULL DEFAULT FALSE,
    category              TEXT,
    category_confidence   TEXT CHECK (category_confidence IN ('high', 'medium', 'low')),
    scraped_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_x_competitor ON x_posts(competitor_id);
CREATE INDEX IF NOT EXISTS idx_x_posted_at ON x_posts(posted_at);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id                       SERIAL PRIMARY KEY,
    run_date                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    source                   TEXT NOT NULL DEFAULT 'instagram' CHECK (source IN ('instagram', 'homepage', 'ads', 'tiktok', 'youtube', 'x')),
    run_type                 TEXT NOT NULL CHECK (run_type IN ('backfill', 'weekly', 'manual')),
    competitors_scraped      INTEGER NOT NULL DEFAULT 0,
    posts_added              INTEGER NOT NULL DEFAULT 0,
    posts_skipped_duplicate  INTEGER NOT NULL DEFAULT 0,
    errors                   JSONB,
    status                   TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed'))
);

-- Idempotent migration for tables created before the `source` column existed.
ALTER TABLE scrape_runs ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'instagram';
ALTER TABLE scrape_runs DROP CONSTRAINT IF EXISTS scrape_runs_source_check;
ALTER TABLE scrape_runs ADD CONSTRAINT scrape_runs_source_check
    CHECK (source IN ('instagram', 'homepage', 'ads', 'tiktok', 'youtube', 'x', 'google_ads'));

-- ============================================================================
-- See-Think-Do funnel stage (categorize/funnel_taxonomy.py) - one audience-
-- intent label per piece of content, across every content table.
-- ============================================================================
ALTER TABLE posts ADD COLUMN IF NOT EXISTS funnel_stage TEXT;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS funnel_stage_confidence TEXT;
ALTER TABLE ads ADD COLUMN IF NOT EXISTS funnel_stage TEXT;
ALTER TABLE ads ADD COLUMN IF NOT EXISTS funnel_stage_confidence TEXT;
ALTER TABLE tiktok_videos ADD COLUMN IF NOT EXISTS funnel_stage TEXT;
ALTER TABLE tiktok_videos ADD COLUMN IF NOT EXISTS funnel_stage_confidence TEXT;
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS funnel_stage TEXT;
ALTER TABLE youtube_videos ADD COLUMN IF NOT EXISTS funnel_stage_confidence TEXT;
ALTER TABLE x_posts ADD COLUMN IF NOT EXISTS funnel_stage TEXT;
ALTER TABLE x_posts ADD COLUMN IF NOT EXISTS funnel_stage_confidence TEXT;
ALTER TABLE homepage_snapshots ADD COLUMN IF NOT EXISTS funnel_stage TEXT;
ALTER TABLE homepage_snapshots ADD COLUMN IF NOT EXISTS funnel_stage_confidence TEXT;

-- ============================================================================
-- Google Search Ads (Google Ads Transparency Center) - both a competitor's own
-- search ads AND any OTHER advertiser conquesting on their brand/domain terms.
-- ============================================================================
CREATE TABLE IF NOT EXISTS google_ads (
    id                       SERIAL PRIMARY KEY,
    competitor_id            INTEGER NOT NULL REFERENCES competitors(id) ON DELETE CASCADE,
    creative_id              TEXT NOT NULL UNIQUE,
    advertiser_name          TEXT,
    is_own_ad                BOOLEAN NOT NULL DEFAULT TRUE,
    search_term              TEXT,
    ad_format                TEXT,
    ad_url                   TEXT,
    image_url                TEXT,
    creative                 BYTEA,
    first_shown              DATE,
    last_shown               DATE,
    approx_days_shown        INTEGER,
    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    funnel_stage             TEXT,
    funnel_stage_confidence  TEXT CHECK (funnel_stage_confidence IN ('high', 'medium', 'low')),
    first_seen_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    scraped_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_google_ads_competitor ON google_ads(competitor_id);
CREATE INDEX IF NOT EXISTS idx_google_ads_is_own_ad ON google_ads(is_own_ad);
