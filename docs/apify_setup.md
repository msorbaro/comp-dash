---
title: Apify Setup Instructions (one-time, manual — you have to do this part)
status: pending — waiting on you to complete this before scraping can run
---

# Apify Setup

We're using [Apify](https://apify.com) to fetch Instagram post data because Instagram has no public API for accounts you don't own. Apify runs a hosted "Instagram Scraper" actor that reads public profile data on a schedule. This costs a small amount of usage credit (see estimate below) — there's no way around a paid step here since Instagram itself blocks free/unauthenticated bulk scraping.

## Steps (you do these — I can't create accounts on your behalf)

1. Go to https://apify.com and click **Sign up** (free account, no credit card required to start — they include $5/month of free platform credit on the free tier as of 2025, which may cover light usage on its own).
2. Once logged in, go to the **Apify Console** → **Settings** → **Integrations** (or **API & Integrations**) and copy your **Personal API token**.
3. Send me that token and I'll store it in a local `.env` file in this project (never committed to git — `.env` is in `.gitignore`).
4. If the free credit runs out, add a small amount of billing credit (a card on file) — for ~40 competitor accounts scraped weekly, expect roughly **$5–$15/month** depending on the actor's exact pricing and how many posts per profile we pull. I'll confirm actual cost after the first real run so you're not guessing.

## What we use it for — three actors, one token

| Actor | Used for | Tested cost |
|---|---|---|
| `apify/instagram-scraper` | Post captions, likes, comments, media, per competitor | ~$0.0027/post. The 90-day, 43-account backfill cost **$4.64** one-time; weekly runs (only new posts, capped at `MAX_POSTS_PER_RUN`) cost far less. |
| `apify/screenshot-url` ("Website Screenshot Generator") | Weekly homepage screenshot per competitor | ~$0.0023/screenshot → ~$0.10/week for all 43. Slow (browser-based, low concurrency) — expect 20-40 min for a full run of 43. |
| `apify/facebook-ads-scraper` (official "Facebook Ads Library Scraper") | Running ads per competitor's Facebook Page | ~$0.02-0.03/page regardless of ad count (fixed overhead to resolve the page + open the Ads Library) → roughly $1-1.50 for all 43/week. |

- Instagram: pulls each competitor's most recent posts (capped at `MAX_POSTS_PER_RUN` weekly, `BACKFILL_MAX_POSTS` for the initial pull) and Reels, diffs against the database, inserts only new posts.
- Homepage: screenshots all competitor websites in one batched actor run, compares each to last week's via perceptual hash, only stores a new image + re-classifies when it actually changed.
- Ads: pulls currently-active ads per competitor's Facebook Page (`facebook_url` in `config/competitors.yaml`, defaulted to the same slug as the Instagram handle — not independently verified per company, see the README note on this).

Apify's own result storage only retains data for ~7 days on most plans, so all three pipelines download and store images/screenshots into Postgres immediately rather than linking to Apify's URLs.

## Status
- [x] Apify account created
- [x] API token provided and saved to `.env`
- [x] Test scrapes run for all three actors — costs confirmed above
