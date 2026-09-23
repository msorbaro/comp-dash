"""Reddit brand mentions (posts + comments) - one search per tracked brand
(Mavis banners AND competitors; not state-scoped, unlike the review/rating
pipelines - a Reddit mention isn't tied to a physical location), via
automation-lab/reddit-scraper.

Live-tested against "Mavis Tires": the actor works (recovers from Reddit's
429 rate-limiting via automatic residential-proxy fallback after enough
retries, just takes a few minutes per call), but two things confirmed live
are handled here:

- A subset of posts come back with `createdAt` equal to the exact scrape
  timestamp - not a real post date, an actor fallback bug. Detected and
  nulled out rather than trusted (`_looks_like_scrape_time_bug`).
- Comment volume, not post volume, dominates both cost and result count
  (908 items from a 20-post cap in the live test, driven by one active
  thread) - so this caps comments per post too (`maxCommentsPerPost`), not
  just posts per brand (`maxPostsPerSource`).
"""
from __future__ import annotations

import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from apify_client import ApifyClient

from db.connection import get_conn
from scraper.apify_client import dataset_id

ACTOR_ID = "automation-lab/reddit-scraper"
MAX_WORKERS = 3  # each call already retries internally for a few minutes
POST_CAP = 100
COMMENT_CAP_PER_POST = 40


def _looks_like_scrape_time_bug(created_at: str, scraped_at: dt.datetime) -> bool:
    """The actor falls back to "now" for a post it can't parse a real date
    for, rather than leaving the field null - confirmed live (3 of 20 posts
    in the Mavis test). A real post landing within the same second as our
    own scrape call is not a real-world coincidence worth trusting."""
    if not created_at:
        return False
    try:
        ts = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return abs((ts - scraped_at).total_seconds()) < 5


def _brands() -> list:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT brand_id, name, aliases FROM voice.brands ORDER BY family, name")
            return [{"brand_id": bid, "name": name, "aliases": aliases} for bid, name, aliases in cur.fetchall()]


def _search_reddit(client: ApifyClient, query: str) -> list:
    run = client.actor(ACTOR_ID).call(run_input={
        "searchQuery": query,
        "timeFilter": "all",
        "sort": "relevance",
        "maxPostsPerSource": POST_CAP,
        "includeComments": True,
        "maxCommentsPerPost": COMMENT_CAP_PER_POST,
    })
    return list(client.dataset(dataset_id(run)).iterate_items())


def _write_items(brand_id: int, items: list) -> int:
    scraped_at = dt.datetime.now(dt.timezone.utc)
    n_written = 0
    with get_conn() as conn:
        with conn:
            with conn.cursor() as cur:
                for item in items:
                    is_post = bool(item.get("title"))
                    reddit_id = item.get("url") if is_post else item.get("permalink")
                    if not reddit_id:
                        continue
                    created_at = item.get("createdAt")
                    if _looks_like_scrape_time_bug(created_at, scraped_at):
                        created_at = None
                    cur.execute(
                        """INSERT INTO voice.reddit_mentions
                               (brand_id, reddit_id, type, parent_post_id, subreddit, author,
                                title, text, score, num_comments, permalink, created_at)
                           VALUES (%(brand_id)s, %(reddit_id)s, %(type)s, %(parent_post_id)s, %(subreddit)s,
                                   %(author)s, %(title)s, %(text)s, %(score)s, %(num_comments)s,
                                   %(permalink)s, %(created_at)s)
                           ON CONFLICT (reddit_id, type) DO NOTHING""",
                        {
                            "brand_id": brand_id, "reddit_id": reddit_id,
                            "type": "post" if is_post else "comment",
                            "parent_post_id": item.get("postId"),
                            "subreddit": item.get("subreddit"), "author": item.get("author"),
                            "title": item.get("title"), "text": item.get("selfText") if is_post else item.get("body"),
                            "score": item.get("score"), "num_comments": item.get("numComments"),
                            "permalink": item.get("url") if is_post else item.get("permalink"),
                            "created_at": created_at,
                        },
                    )
                    n_written += 1
                cur.execute(
                    """INSERT INTO voice.reddit_scrape_runs (brand_id) VALUES (%s)
                       ON CONFLICT (brand_id) DO NOTHING""",
                    (brand_id,),
                )
    return n_written


def _process_brand(client: ApifyClient, brand: dict) -> dict:
    # The brand's own display name is usually the best search term (it's
    # what people actually type); aliases exist for DB matching, not
    # search quality, so they're not queried separately here.
    items = _search_reddit(client, brand["name"])
    n_written = _write_items(brand["brand_id"], items)
    n_posts = sum(1 for i in items if i.get("title"))
    return {"brand_name": brand["name"], "n_items": len(items), "n_posts": n_posts, "n_written": n_written}


def run() -> dict:
    brands = _brands()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT brand_id FROM voice.reddit_scrape_runs")
            already_done = {row[0] for row in cur.fetchall()}

    tasks = [b for b in brands if b["brand_id"] not in already_done]
    skipped = len(brands) - len(tasks)
    if skipped:
        print(f"Skipping {skipped} already-completed brand(s) from a prior run.", flush=True)

    client = ApifyClient(os.environ["APIFY_TOKEN"])
    n_written_total = 0
    failed_brands = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_process_brand, client, b): b for b in tasks}
        for future in as_completed(futures):
            brand = futures[future]
            done += 1
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - one bad brand shouldn't abort the whole run
                print(f"[{done}/{len(tasks)}] {brand['name']} FAILED: {exc}", flush=True)
                failed_brands.append(brand["name"])
                continue
            n_written_total += result["n_written"]
            print(
                f"[{done}/{len(tasks)}] {result['brand_name']}: "
                f"{result['n_posts']} posts, {result['n_items'] - result['n_posts']} comments "
                f"({result['n_written']} written)",
                flush=True,
            )

    return {"n_brands": len(brands), "brands_skipped": skipped, "n_written": n_written_total, "failed_brands": failed_brands}
