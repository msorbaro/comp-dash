---
title: Competitor Research Dashboard — Project Plan & Decisions Log
status: in progress
last_updated: 2026-09-11
---

# Competitor Research Dashboard

Tracks six things for ~43 competitors (grouped into 10 competitive sets, see `Competitors.rtf` for the original source) **plus 9 of the user's own brands** (Mavis, Tire Kingdom, NTB, Pep Boys, Midas, Brakes Plus, Express Oil, Tuffy, Town Fair Tire — tagged `is_own_brand`, tracked identically but distinguishable in the dashboard), all stored in a database so the dashboard never has to re-scrape live:
1. **Instagram activity** — posts, captions, likes, content category, cadence.
2. **Website homepage tracker** — weekly screenshot per competitor, visual change detection (only stores a new image when the homepage actually changed), and a messaging-theme classification (deals vs. product vs. lifestyle, etc.).
3. **Facebook/Instagram Ads Library** — currently-running (and recently run) ads per competitor: creative, caption, headline, platforms, how long each has been running, and the same messaging-theme classification.
4. **TikTok videos** — caption, category, view/like/comment/share counts, duration, link.
5. **YouTube videos & Shorts** — title, description, category, view/like/comment counts, duration, link.
6. **X (Twitter) posts** — text, category, likes/retweets/replies/quotes/views, link.

The dashboard has a global **Scope** filter (All / My brands only / Competitors only) and, when viewing "All", a "Us vs. competitors" benchmark comparison (avg engagement, content mix) on the summary page.

## Decisions made (confirmed with the user)

| Decision | Choice | Why |
|---|---|---|
| Data source | **Apify** (paid Instagram scraper API) | Instagram has no free/official API for accounts we don't own; Apify is the most reliable structured-data option at ~40-account weekly-refresh scale. |
| Database | **Hosted Postgres (Supabase)** | User wants to eventually put the dashboard on the internet — a hosted DB works identically for local dev, scheduled scraping, and a deployed app, with no later migration. |
| Weekly re-scrape trigger | **GitHub Actions scheduled workflow (cron, Monday)** | Runs unattended regardless of whether any local machine is on. Secrets (Apify token, DB URL, Anthropic API key) live securely in GitHub repo settings — standard, well-supported pattern. (We initially considered an Anthropic cloud routine for this, but it requires the repo to exist on GitHub anyway, can't read local `.env` secrets, and needs a git commit-back step — GitHub Actions does the same job more simply once we're already using GitHub.) |
| Categorization | **Claude API call (Haiku)** from within the same weekly script, using the taxonomy in `docs/content_taxonomy.md` | Cheap at this volume (~100-150 posts/week total). Runs as plain code inside GitHub Actions, so it needs its own API key (separate from the user's Claude Code session). |
| Dashboard tech | **Streamlit (Python)** | One-command local launch now; the exact same code deploys later to Streamlit Community Cloud (or similar) once the user is ready to go live — just point it at the same hosted DB. |
| Repo | **GitHub, private** — `github.com/msorbaro/competitor-ig-dashboard` | Contains competitive business data; private by default. User has a GitHub account (`msorbaro`). |
| Stories | **Out of scope** | Ephemeral, not accessible for accounts we don't manage — only feed posts + Reels are tracked. |
| Homepage screenshot cadence | **Weekly**, same run as Instagram | User initially said "each day" then "each week" in the same message; confirmed weekly — ~7x cheaper and homepages rarely change daily. |
| Homepage screenshot actor | **Apify `apify/screenshot-url`** ("Website Screenshot Generator") | ~$0.0023/screenshot tested live — negligible cost (~$0.10/week for all 43). |
| Homepage change detection | **Always capture, then compare perceptual hash (average_hash, threshold 4) to the last stored one** | Only stores a new image + re-classifies theme when the homepage actually visually changed; unchanged weeks just log a "still the same" row pointing at the last real image. Avoids storage bloat and repeat classification cost. |
| Homepage/ad image storage | **Postgres BYTEA** (resized JPEG), not a separate object store | Avoids needing a 4th external service/credential; volume is small enough (~1000s of images) that this is simpler than wiring up Supabase Storage or S3. Apify's own screenshot storage only retains results ~7 days, so images are downloaded and stored permanently right after each capture. |
| Ads Library actor | **Apify `apify/facebook-ads-scraper`** (official, ~36k users), input = each competitor's Facebook Page URL | Verified live against Walmart's page — returns full ad creative, caption, platforms, dates, active status. |
| Facebook Page URLs | **Best-guess default**: `facebook.com/<same slug as Instagram handle>` | Not independently researched per-company (that would've meant a second full research pass) — most brands do use the same slug, and wrong guesses will simply return no ads, which surfaces naturally as a "0 ads found" competitor to spot-check rather than silently failing. |
| Ad/homepage messaging taxonomy | **Shared taxonomy** (`categorize/messaging_taxonomy.py`): Deals/Promotional, Product-Led, Lifestyle/Brand Imagery, Seasonal/Holiday, Announcement/Launch, Testimonial/Social Proof, Recruitment/Hiring, Mixed/Other | Same underlying question ("what is this trying to sell") for both homepages and ads, so one shared taxonomy keeps the dashboard's language consistent. Classified via Claude vision (Haiku) on the actual image. |
| TikTok actor | **Apify `clockworks/tiktok-scraper`** (277k users, by far the most popular) | ~$0.016 for 5 videos tested live against Walmart. |
| YouTube actor | **Apify `streamers/youtube-scraper`** (the detailed per-video variant, not the faster `youtube-channel-scraper`) | The fast channel-listing variant doesn't return likes/comments/full description — only the detailed variant does. ~$0.009 for 3 fully-detailed videos, but noticeably slower (~9s/video) than the other actors. |
| X/Twitter actor | **Apify `apidojo/tweet-scraper`** (99.5k users, "Tweet Scraper V2") | ~$0.002 for 5 tweets tested live; fast and cheap. |
| TikTok/YouTube/X content category | **Reuses the Instagram content taxonomy** (`docs/content_taxonomy.md`, via the new shared `classify_caption()` helper) | Same underlying question as Instagram post categorization — keeps cross-platform comparison meaningful instead of inventing a fourth taxonomy. |
| TikTok/YouTube/X handles | **Best-guess default**: same slug as the Instagram handle (TikTok, X) or `youtube.com/@<handle>` | Same pattern as `facebook_url` — not independently researched per-company for all 52 brands (that would mean 150+ more handle lookups); wrong guesses return 0 results, which surfaces in `logs/YYYY-MM-DD.md` rather than failing silently. |

## Open items / assumptions needing user confirmation

Handle research is done (`research/instagram_handles_research.md`, 39 companies, 2026-09-11 pass) and loaded into `config/competitors.yaml`. Three items were ambiguous in the source list and defaulted rather than blocking on the user (all clearly flagged with `notes:` in the yaml, easy to change):
- [ ] **"Storage units"** → defaulted to **Public Storage**.
- [ ] **"Monroe" (listed twice)** → interpreted as **Monro Auto Service and Tire Centers** (@monroauto), not the unrelated Monroe shocks/struts parts brand.
- [ ] **Goodyear Auto Service** → tracking the main **@goodyear** account as a stand-in (no separate confirmed account exists).

Also flagged, not blocking: **TJ Maxx, Firestone, Jiffy Lube, Mr. Appliance** all looked dormant (no posts in 2-4 months) as of the research date — still tracked, just don't expect much volume.

- [x] GitHub account confirmed (`msorbaro`), repo created private at `github.com/msorbaro/comp-dash` and pushed.
- [x] Supabase connection string provided and tested — working.
- [x] Apify API token provided and tested — working, billing added (cap raised from $5 to $19/month).
- [x] Anthropic API key provided and tested — working.
- [x] All three Apify actors confirmed + real costs measured (see `docs/apify_setup.md`).

### Own brands (added 2026-09-11)
Researched via web search (lighter-touch pass than the competitor list — spot-check before relying on these for benchmarking). Backfilled across all six pipelines (Instagram, website, Facebook ads, TikTok, YouTube, X) as of this date:
- [x] **Mavis Discount Tire / Mavis Tires and Brakes** — merged into one entry per user confirmation; they share one Instagram (@mavis_tires) and website (mavis.com). X handle verified as the *singular* `mavis_tire` (different from the IG handle).
- [x] **Tire Kingdom, National Tire and Battery** — X and YouTube handles corrected via search (different from their IG/default-guess slugs; YouTube channels are legacy non-@handle URLs). Their Instagram accounts are confirmed **dormant** — last posts from 2023, so the 90-day backfill window found nothing; the handful of historical posts found were inserted anyway (bypassing the date filter) so the dashboard reflects "dormant" rather than "no data."
- [x] **Town Fair Tire** — X handle corrected (no underscores). Instagram is even more dormant — last post found was from **2014**; inserted for the same reason as above.
- [x] **Tuffy** — no corporate TikTok/X/YouTube found at all (only Facebook/Instagram/LinkedIn); those fields are explicitly set to `null` in `config/competitors.yaml` rather than guessed. Its Instagram handle was later corrected to the real account (`tuffytireandauto`, config had already been fixed) but nothing had re-scraped it since — the 2026-09-11 full recheck (see below) picked this up and added 30 real posts.
- [x] **Pep Boys, Brakes Plus, Express Oil, Midas** — good coverage across most platforms.
- Several own brands show **0 currently-running Facebook ads** (Midas, NTB, Tire Kingdom, Town Fair Tire, Tuffy) — this may reflect that they simply aren't running Meta ads right now, or an incorrect `facebook_url` guess; not independently confirmed either way.
- [x] **Backfill age cutoff removed** (2026-09-11) — the original 90-day age filter on first backfill was silently discarding real posts for lower-frequency accounts (found via a "Brakes Plus only has 1 post" bug report — live re-check showed 29 real posts from Feb-July 2025 that had been fetched and thrown away). Same bug also hit Mavis and Express Oil. `_insert_posts` no longer filters by post age at all; `results_limit`/`BACKFILL_MAX_POSTS` alone bounds how much is fetched (and paid for) per account. Ran a one-time full re-check across all 52 competitors to recover any other hidden history: Tuffy (+30, previously thought to have no Instagram at all — its handle had been corrected in config but never re-scraped), Town Fair Tire (+12), plus small (1-3 post) additions for GEICO, Take 5, Jiffy Lube, Quick Quack, Trader Joe's, PetSmart, Costco, Firestone, Mr. Appliance, and Amazon. 57 new posts total, all classified.
- [x] **Card gallery clarity fix** (2026-09-11) — Brand Profile's per-platform "top posts/ads/videos" card galleries (capped at 6-8 items by design) had no caption distinguishing them from the true total, causing a "why does it only show 8?" report when the real count (shown in the stat tile above) was 30. Added a "Showing top N of M ..." caption above every capped gallery (Instagram, Ads, TikTok, YouTube, X, Google Ads, Google Ads conquest).
- [x] **"Brand Signal" redesign, attempt 1: Streamlit** (2026-09-12) — user provided an exact Claude-design mockup (`new designs/Design System.dc.html` + `Brand Signal Dashboard.dc.html`, not committed - reference only) specifying colors, type, and component patterns down to the pixel, and asked to match it exactly. Rebuilt the dashboard's UI on Streamlit with custom CSS: dark ink (`#141A21`) top nav, teal/deep-teal/amber See/Think/Do palette, Poppins throughout, stat cards, stage bars, creative-evidence cards. Two rounds of fixes against real screenshots still left visible gaps (a regressed nav bar, spacing/layout drift) - Streamlit's own widget DOM structure fights pixel-exact CSS control closely enough that this was the wrong tool for "match exactly."
- [x] **"Brand Signal" redesign, attempt 2: React + FastAPI** (2026-09-12) — replaced the Streamlit app with `frontend/` (React + Vite, plain inline styles ported directly from the design files) and `backend/` (FastAPI wrapping `backend/signal_data.py` - the same real-data aggregation logic as before, just exposed over HTTP instead of called in-process). In production the FastAPI process also serves the built React app, so it's still one deployable service. Verified by actually rendering the app in headless Chromium (Playwright, installed locally into the project) and screenshotting all 5 screens - not just API/logic tests - confirming a close pixel match to the reference screenshots/PDF. `dashboard/app.py` (Streamlit) is left in the repo unmaintained; `backend/`+`frontend/` are the live app now. See README's "Dashboard (Brand Signal)" section for how to run both pieces.

## Dashboard scope (per competitor + summary)
**Per-competitor view:**
- Content category breakdown (share of posts per category)
- Which category gets the most average likes / engagement
- Top posts by likes (with caption/date/thumbnail link)
- Posting frequency (posts per week over time)

**Cross-competitor summary page:**
- Trends across all groups (category mix comparison, engagement comparison, cadence comparison)
- Filterable by competitive set (Value Leaders, Automotive Full Service, etc.)

## Repo layout
```
Competitors.rtf              # original source file
PROJECT_PLAN.md              # this file — decisions log, kept up to date
README.md                    # setup + how to run everything
.env.example                 # required secrets/config, copy to .env locally
requirements.txt
docs/
  content_taxonomy.md        # category definitions
  database_schema.md         # DB schema reference (Postgres)
  apify_setup.md             # one-time manual setup steps for the user
research/
  instagram_handles_research.md
config/
  competitors.yaml           # final competitor list + handles + groups (source of truth for the DB seed)
db/
  schema.sql                 # Postgres DDL
scraper/
  apify_client.py            # Instagram: calls Apify, normalizes results
  ingest.py                  # Instagram: fetch new posts per competitor, upsert to DB
  media.py                   # shared: download + resize an image URL to store permanently
  homepage.py                # website homepage screenshot + change detection
  ads.py                     # Facebook/Instagram Ads Library tracker
  tiktok.py                  # TikTok video tracker
  youtube.py                 # YouTube video/Shorts tracker
  x.py                       # X (Twitter) post tracker
categorize/
  classify.py                # content taxonomy classification (classify_caption, reused across platforms)
  messaging_taxonomy.py      # shared "what is this selling" taxonomy (homepage + ads)
  vision.py                  # Claude-vision classifier for images (homepage + ads)
scripts/
  init_db.py                 # creates schema, seeds competitors/categories from config/competitors.yaml
  run_weekly.py              # orchestrates ingest -> categorize -> log, writes logs/YYYY-MM-DD.md
backend/
  main.py                    # FastAPI app: /api/* endpoints + serves frontend/dist in production
  data_loaders.py            # DB queries (TTL-cached), a framework-agnostic port of the old Streamlit loaders
  signal_data.py             # real-data aggregation layer backing every Brand Signal screen
frontend/                    # React + Vite app ("Brand Signal") - see README for dev/build commands
  src/
    App.jsx                  # top-level nav state machine (landscape/brand/channel/category/compare)
    api.js                   # fetch wrappers for the backend
    styles.js                # design tokens + style-builder helpers ported from the design files
    components/               # Header, ContextBar, shared widgets (StageBar, CreativeCard, etc.)
    screens/                  # Landscape.jsx, Brand.jsx, Channel.jsx, Category.jsx, Compare.jsx
dashboard/                   # OLD Streamlit app - unmaintained, superseded by backend/ + frontend/
  app.py
  signal_data.py
.github/workflows/
  weekly_scrape.yml          # cron trigger for scripts/run_weekly.py
logs/
  YYYY-MM-DD.md              # human-readable run log, one per week, committed to the repo
```
