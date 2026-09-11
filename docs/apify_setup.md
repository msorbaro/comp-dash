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

## What we'll use it for
- Actor: Apify's Instagram Post/Profile Scraper (exact actor ID confirmed at build time — there are a few maintained options, e.g. `apify/instagram-scraper` or `apify/instagram-post-scraper`; I'll pick the one with the best cost/reliability tradeoff and document the final choice here).
- Weekly run: pull each competitor's most recent posts (capped at a reasonable number, e.g. last ~20) and Reels, diff against what's already in the database, insert only new posts.
- Initial run: one-time backfill of the last 90 days per your instructions.

## Status
- [ ] Apify account created
- [ ] API token provided and saved to `.env`
- [ ] First test scrape run against 1-2 accounts to confirm actor choice and cost before running against the full list
