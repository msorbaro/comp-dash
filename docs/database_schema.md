---
title: Database Schema
status: implemented in db/schema.sql (Postgres, hosted on Supabase)
---

# Database Schema

Hosted Postgres (Supabase). This is the single source of truth the dashboard reads from — the dashboard never scrapes live, it only queries this database. Local dev, the weekly GitHub Actions scraper, and the (eventually) deployed dashboard all point at the same database via the `DATABASE_URL` connection string.

See `db/schema.sql` for the actual DDL.

## `competitors`
| column | type | notes |
|---|---|---|
| id | SERIAL PK | |
| name | TEXT | e.g. "Walmart" |
| instagram_handle | TEXT UNIQUE | e.g. "walmart" (no @) |
| instagram_url | TEXT | full profile URL |
| follower_count | INTEGER | last known count, updated each scrape |
| is_active | BOOLEAN | false if account is dormant/private/not found — excluded from scraping but kept for reference |
| notes | TEXT | e.g. "private account", "franchise sub-account" |
| created_at | TIMESTAMPTZ | |

## `competitor_groups`
Handles the many-to-many reality that some brands (Walmart, Costco) sit in multiple competitive sets.
| column | type | notes |
|---|---|---|
| competitor_id | INTEGER FK → competitors.id | |
| group_name | TEXT | e.g. "Automotive Discount" |

## `categories`
Reference table mirroring `docs/content_taxonomy.md`, so the taxonomy is queryable and editable without touching code.
| column | type | notes |
|---|---|---|
| name | TEXT PK | |
| description | TEXT | |

## `posts`
| column | type | notes |
|---|---|---|
| id | SERIAL PK | |
| competitor_id | INTEGER FK → competitors.id | |
| instagram_post_id | TEXT UNIQUE | Instagram's own post/shortcode ID — used to dedupe on every re-scrape |
| post_url | TEXT | |
| post_type | TEXT | Image / Carousel / Reel |
| posted_at | TIMESTAMPTZ | when it was posted on Instagram |
| caption | TEXT | full caption text |
| media_url | TEXT | link to thumbnail/first image (for reference in the dashboard) |
| like_count | INTEGER | null if hidden by the account |
| comment_count | INTEGER | |
| view_count | INTEGER | Reels/video only, null otherwise |
| category | TEXT FK → categories.name | assigned from the taxonomy in `docs/content_taxonomy.md` |
| category_confidence | TEXT | high / medium / low |
| scraped_at | TIMESTAMPTZ | when we pulled this record |

## `scrape_runs`
Log of every weekly (or manual) run — lets the dashboard show "current as of X" without re-scraping to check, and gives a durable audit trail alongside the human-readable `logs/YYYY-MM-DD.md` files.
| column | type | notes |
|---|---|---|
| id | SERIAL PK | |
| run_date | TIMESTAMPTZ | |
| run_type | TEXT | "backfill" / "weekly" / "manual" |
| competitors_scraped | INTEGER | |
| posts_added | INTEGER | |
| posts_skipped_duplicate | INTEGER | |
| errors | JSONB | list of any competitor scrapes that failed, so failures are visible, not silent |
| status | TEXT | success / partial / failed |
