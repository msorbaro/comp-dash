---
title: Competitor Research Dashboard — Project Plan & Decisions Log
status: in progress
last_updated: 2026-09-11
---

# Competitor Research Dashboard

Tracks Instagram activity for ~40 competitors (grouped into 10 competitive sets, see `Competitors.rtf` for the original source) so we can compare content strategy, posting cadence, and engagement — without re-scraping Instagram every time someone opens the dashboard.

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

## Open items / assumptions needing user confirmation

Handle research is done (`research/instagram_handles_research.md`, 39 companies, 2026-09-11 pass) and loaded into `config/competitors.yaml`. Three items were ambiguous in the source list and defaulted rather than blocking on the user (all clearly flagged with `notes:` in the yaml, easy to change):
- [ ] **"Storage units"** → defaulted to **Public Storage**.
- [ ] **"Monroe" (listed twice)** → interpreted as **Monro Auto Service and Tire Centers** (@monroauto), not the unrelated Monroe shocks/struts parts brand.
- [ ] **Goodyear Auto Service** → tracking the main **@goodyear** account as a stand-in (no separate confirmed account exists).

Also flagged, not blocking: **TJ Maxx, Firestone, Jiffy Lube, Mr. Appliance** all looked dormant (no posts in 2-4 months) as of the research date — still tracked, just don't expect much volume.

- [x] GitHub account confirmed (`msorbaro`), repo will be private.
- [x] Supabase connection string provided and tested — working.
- [x] Apify API token provided and tested — working (free plan).
- [ ] Anthropic API key for the categorizer — still needed.
- [ ] Create the actual GitHub repo (`github.com/new`) and push.
- [ ] Confirm actual Apify actor + real cost after a small test run (1-2 accounts) before running the full list.
- [ ] Backfill window on first run: defaulting to **last 90 days** per account — adjustable in `.env` (`BACKFILL_DAYS`).

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
  apify_client.py            # calls Apify, normalizes results
  ingest.py                  # fetch new posts per competitor, upsert to DB
categorize/
  classify.py                # applies the content taxonomy to new posts via Claude API
scripts/
  init_db.py                 # creates schema, seeds competitors/categories from config/competitors.yaml
  run_weekly.py              # orchestrates ingest -> categorize -> log, writes logs/YYYY-MM-DD.md
dashboard/
  app.py                     # Streamlit dashboard
.github/workflows/
  weekly_scrape.yml          # cron trigger for scripts/run_weekly.py
logs/
  YYYY-MM-DD.md              # human-readable run log, one per week, committed to the repo
```
