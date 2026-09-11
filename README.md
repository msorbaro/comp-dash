# Competitor Research Dashboard

Tracks ~40 competitors' Instagram activity (post content, captions, likes, cadence) in a
database, auto-refreshed weekly, viewed through a local Streamlit dashboard. See
`PROJECT_PLAN.md` for the full decisions log and `docs/` for schema/taxonomy/setup details.

## One-time setup

You need four things before this can run: a GitHub repo, a Supabase (Postgres) database,
an Apify account, and an Anthropic API key.

### 1. GitHub repo
Create an empty **private** repo at github.com named `competitor-ig-dashboard` (or your
preferred name) under your account. Don't initialize it with a README/license — this
project already has one. Then, from this folder:

```bash
git remote add origin https://github.com/<your-username>/competitor-ig-dashboard.git
git branch -M main
git add .
git commit -m "Initial project scaffold"
git push -u origin main
```

### 2. Supabase (hosted Postgres)
1. supabase.com → sign up → New project (set a database password, save it).
2. On the project page, click **Connect** → **URI** tab → mode **Transaction pooler** →
   copy the connection string, then swap in your real password.
3. This becomes `DATABASE_URL`.

### 3. Apify (Instagram scraping)
1. apify.com → sign up.
2. Console → Settings → Integrations → copy your **Personal API token** → this is `APIFY_TOKEN`.
3. See `docs/apify_setup.md` for cost expectations.

### 4. Anthropic API key (post categorization)
1. console.anthropic.com → API Keys → create a key → this is `ANTHROPIC_API_KEY`.
   (This is separate from any Claude Code / claude.ai subscription — the weekly job runs
   as plain code in GitHub Actions, not inside a Claude Code session.)

### 5. Local environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in DATABASE_URL, APIFY_TOKEN, ANTHROPIC_API_KEY
```

### 6. GitHub Actions secrets (for the automated weekly run)
In the GitHub repo: Settings → Secrets and variables → Actions → New repository secret.
Add `DATABASE_URL`, `APIFY_TOKEN`, `ANTHROPIC_API_KEY` with the same values as your `.env`.

## Running it

```bash
# 1. Create tables + seed competitors/categories (safe to re-run any time config/competitors.yaml changes)
python -m scripts.init_db

# 2. First historical pull (last BACKFILL_DAYS, default 90)
python -m scripts.run_weekly --backfill

# 3. View the dashboard
streamlit run dashboard/app.py
```

After that, the GitHub Actions workflow (`.github/workflows/weekly_scrape.yml`) runs
automatically every Monday and appends a log to `logs/YYYY-MM-DD.md`. You can also
trigger it manually any time from the repo's **Actions** tab ("Run workflow"), or run
`python -m scripts.run_weekly` locally.

To see this week's new data in the dashboard, just click **Refresh from database** in
the app (or restart it) — it always reads from Supabase, never re-scrapes on its own.

## Going live later
The dashboard code doesn't need to change to be deployed publicly — e.g. push this repo
to Streamlit Community Cloud and set the same three secrets there. It already reads from
the same hosted database as local dev and the weekly job.
