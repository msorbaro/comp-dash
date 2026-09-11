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
| website_url | TEXT | homepage URL used by the website tracker |
| facebook_url | TEXT | Facebook Page URL used by the ads library tracker (best-guess default: same slug as Instagram handle) |
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

## `homepage_snapshots`
One row per competitor per week. Only stores a new `screenshot` when the homepage actually visually changed (compared via perceptual hash) — an unchanged week just logs `changed = false` pointing at the same hash, so the timeline can collapse consecutive unchanged weeks without duplicating images.
| column | type | notes |
|---|---|---|
| id | SERIAL PK | |
| competitor_id | INTEGER FK → competitors.id | |
| captured_at | TIMESTAMPTZ | |
| screenshot | BYTEA | resized JPEG; NULL when `changed = false` (reuse the prior row's image) |
| image_hash | TEXT | perceptual hash (average_hash) of this capture, used to detect change |
| changed | BOOLEAN | true = new distinct screenshot, false = same as previous |
| theme | TEXT | messaging theme from `categorize/messaging_taxonomy.py` |
| theme_confidence | TEXT | high / medium / low |

## `ads`
One row per unique ad (by Facebook's own `ad_archive_id`), updated in place while it keeps running rather than re-inserted each week.
| column | type | notes |
|---|---|---|
| id | SERIAL PK | |
| competitor_id | INTEGER FK → competitors.id | |
| ad_archive_id | TEXT UNIQUE | Facebook Ads Library's own ID — dedupe key |
| ad_url | TEXT | link to the ad in the public Ads Library |
| creative_type | TEXT | Image / Video / Carousel |
| creative | BYTEA | resized JPEG of the primary creative/thumbnail |
| caption | TEXT | ad body text |
| headline | TEXT | ad title, when present |
| platforms | TEXT[] | e.g. `{FACEBOOK,INSTAGRAM}` |
| start_date | DATE | when the ad started running |
| end_date | DATE | last known active date; frozen once the ad stops running |
| is_active | BOOLEAN | currently running, per the most recent check |
| category | TEXT | messaging theme from `categorize/messaging_taxonomy.py` |
| category_confidence | TEXT | high / medium / low |
| first_seen_at | TIMESTAMPTZ | when we first found this ad |
| last_seen_at | TIMESTAMPTZ | updated every run it's still found; used to infer when an ad has stopped |

## `scrape_runs`
Log of every weekly (or manual) run, across all three pipelines — lets the dashboard show "current as of X" without re-scraping to check, and gives a durable audit trail alongside the human-readable `logs/YYYY-MM-DD.md` files.
| column | type | notes |
|---|---|---|
| id | SERIAL PK | |
| run_date | TIMESTAMPTZ | |
| source | TEXT | "instagram" / "homepage" / "ads" |
| run_type | TEXT | "backfill" / "weekly" / "manual" |
| competitors_scraped | INTEGER | |
| posts_added | INTEGER | reused for "changed" (homepage) / "ads added" (ads) |
| posts_skipped_duplicate | INTEGER | reused for "unchanged" (homepage) / "ads updated" (ads) |
| errors | JSONB | list of any competitor scrapes that failed, so failures are visible, not silent |
| status | TEXT | success / partial / failed |
