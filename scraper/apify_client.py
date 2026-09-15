"""Thin wrapper around the Apify Instagram Scraper actor.

Uses the `apify/instagram-scraper` actor: given a list of profile URLs, it
returns recent posts (and Reels) per profile. We batch every competitor into
a single actor run per scrape (cheaper and faster than one run per account).
"""
from __future__ import annotations

import os

from apify_client import ApifyClient

ACTOR_ID = "apify/instagram-scraper"


def dataset_id(run) -> str:
    """The shape of an actor-run result has changed between apify-client
    versions - a plain subscriptable dict (confirmed: what's installed
    locally, 1.12.2) vs. a typed `Run` object needing attribute access.
    requirements.txt pins `apify-client>=1.7.1` with no upper bound, so a
    fresh CI install can silently pick up a newer client than what's been
    tested locally - confirmed live: the scheduled weekly scrape failed
    across Instagram, Meta ads, and TikTok with
    "'Run' object is not subscriptable", while every local run this same
    week (identical code, older installed client) worked fine. Handle both
    shapes here instead of hardcoding one."""
    try:
        return run["defaultDatasetId"]
    except TypeError:
        return getattr(run, "default_dataset_id", None) or getattr(run, "defaultDatasetId")


def fetch_posts(profile_urls: list[str], results_limit: int) -> list[dict]:
    """Returns raw Apify dataset items for the given profile URLs.

    results_limit is the max number of posts to fetch PER profile.
    """
    if not profile_urls:
        return []

    client = ApifyClient(os.environ["APIFY_TOKEN"])
    run_input = {
        "directUrls": profile_urls,
        "resultsType": "posts",
        "resultsLimit": results_limit,
        "addParentData": False,
    }
    run = client.actor(ACTOR_ID).call(run_input=run_input)
    return list(client.dataset(dataset_id(run)).iterate_items())


def normalize_post(item: dict) -> dict | None:
    """Maps a raw Apify item to our `posts` table shape. Returns None for
    items that aren't actually posts (e.g. error placeholders)."""
    post_id = item.get("id") or item.get("shortCode")
    if not post_id:
        return None

    if item.get("productType") == "clips" or item.get("type") == "Video":
        post_type = "Reel"
    elif item.get("type") == "Sidecar":
        post_type = "Carousel"
    else:
        post_type = "Image"

    return {
        "instagram_post_id": str(post_id),
        "post_url": item.get("url"),
        "post_type": post_type,
        "posted_at": item.get("timestamp"),
        "caption": item.get("caption"),
        "media_url": item.get("displayUrl"),
        "like_count": item.get("likesCount"),
        "comment_count": item.get("commentsCount"),
        "view_count": item.get("videoViewCount") or item.get("videoPlayCount"),
        "owner_username": (item.get("ownerUsername") or "").lower(),
    }
