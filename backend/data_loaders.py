"""DB-backed data loading for the FastAPI backend - a direct, framework-agnostic
port of dashboard/app.py's Streamlit-cached loaders. Same queries, same shapes;
just a plain in-memory TTL cache instead of st.cache_data."""
import base64
import functools
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from db.connection import get_conn

_CACHE: dict = {}
TTL_SECONDS = 600

# Per-key locks so a cold cache doesn't stampede: without this, N concurrent
# callers (e.g. the backend's warm-cache thread pool refreshing several
# brands at once) all see "not cached" at the same instant and each opens
# its own DB connection to reload the SAME table - confirmed as the actual
# cause of live 500s after a fresh restart (up to 9 threads x 7 loaders,
# comfortably exceeding Supabase's pooled connection limit). Keyed per
# cache key (not one global lock) so unrelated tables still load in
# parallel - only concurrent callers for the exact same key serialize.
_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(key):
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _LOCKS[key] = threading.Lock()
        return lock


def ttl_cache(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (fn.__name__, args, tuple(sorted(kwargs.items())))
        now = time.time()
        cached = _CACHE.get(key)
        if cached is not None and now < cached[1]:
            return cached[0]
        with _lock_for(key):
            # Another thread may have already populated this key while we
            # were waiting for the lock - re-check before hitting the DB.
            cached = _CACHE.get(key)
            if cached is not None and time.time() < cached[1]:
                return cached[0]
            value = fn(*args, **kwargs)
            _CACHE[key] = (value, time.time() + TTL_SECONDS)
            return value
    return wrapper


def clear_cache():
    _CACHE.clear()


def to_data_uri(raw: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(raw).decode()}"


@ttl_cache
def load_posts() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT p.id, p.competitor_id, p.instagram_post_id, p.post_url, p.post_type,
                   p.posted_at, p.caption, p.media_url, p.like_count, p.comment_count,
                   p.view_count, p.category, p.category_confidence, p.funnel_stage, p.message_attribute, p.scraped_at,
                   c.name AS competitor_name, c.instagram_handle, c.is_own_brand,
                   array_agg(cg.group_name) AS groups
            FROM posts p
            JOIN competitors c ON c.id = p.competitor_id
            LEFT JOIN competitor_groups cg ON cg.competitor_id = c.id
            GROUP BY p.id, c.name, c.instagram_handle, c.is_own_brand
            """,
            conn,
        )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    df["week"] = df["posted_at"].dt.to_period("W").dt.start_time
    return df


@ttl_cache
def load_ig_thumbnail(post_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT thumbnail FROM posts WHERE id = %s", (post_id,))
            row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@ttl_cache
def load_last_run():
    with get_conn() as conn:
        df = pd.read_sql("SELECT * FROM scrape_runs ORDER BY run_date DESC LIMIT 1", conn)
    return df.iloc[0].to_dict() if not df.empty else None


@ttl_cache
def load_homepage_snapshots() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT h.id, h.competitor_id, h.captured_at, h.changed, h.theme, h.theme_confidence,
                   h.funnel_stage, h.message_attribute, c.name AS competitor_name, c.is_own_brand
            FROM homepage_snapshots h
            JOIN competitors c ON c.id = h.competitor_id
            ORDER BY h.competitor_id, h.captured_at
            """,
            conn,
        )
    df["captured_at"] = pd.to_datetime(df["captured_at"])
    return df


@ttl_cache
def load_screenshot(snapshot_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT screenshot FROM homepage_snapshots WHERE id = %s", (snapshot_id,))
            row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@ttl_cache
def load_ads() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT a.id, a.competitor_id, a.ad_url, a.creative_type,
                   a.creative_video IS NOT NULL AS has_video, a.caption, a.headline,
                   a.platforms, a.start_date, a.end_date, a.is_active, a.category, a.funnel_stage, a.message_attribute,
                   c.name AS competitor_name, c.is_own_brand
            FROM ads a
            JOIN competitors c ON c.id = a.competitor_id
            ORDER BY a.start_date DESC
            """,
            conn,
        )
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    today = pd.Timestamp.now(tz=df["start_date"].dt.tz) if len(df) and df["start_date"].dt.tz else pd.Timestamp.now()
    df["running_days"] = ((df["end_date"].fillna(today) - df["start_date"]).dt.days).clip(lower=0)
    return df


@ttl_cache
def load_ad_creative(ad_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT creative FROM ads WHERE id = %s", (ad_id,))
            row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@ttl_cache
def load_ad_video_b64(ad_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT creative_video FROM ads WHERE id = %s", (ad_id,))
            row = cur.fetchone()
    if row and row[0]:
        return f"data:video/mp4;base64,{base64.b64encode(row[0]).decode()}"
    return None


@ttl_cache
def load_tiktok() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT t.id, t.competitor_id, t.video_url, t.caption, t.posted_at, t.duration_seconds,
                   t.view_count, t.like_count, t.comment_count, t.share_count, t.category, t.funnel_stage, t.message_attribute,
                   c.name AS competitor_name, c.is_own_brand
            FROM tiktok_videos t
            JOIN competitors c ON c.id = t.competitor_id
            ORDER BY t.posted_at DESC
            """,
            conn,
        )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df


@ttl_cache
def load_tiktok_thumbnail(video_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT thumbnail FROM tiktok_videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@ttl_cache
def load_youtube() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT y.id, y.competitor_id, y.video_url, y.title, y.caption, y.posted_at, y.duration,
                   y.video_type, y.view_count, y.like_count, y.comment_count, y.category, y.funnel_stage, y.message_attribute,
                   c.name AS competitor_name, c.is_own_brand
            FROM youtube_videos y
            JOIN competitors c ON c.id = y.competitor_id
            ORDER BY y.posted_at DESC
            """,
            conn,
        )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df


@ttl_cache
def load_youtube_thumbnail(video_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT thumbnail FROM youtube_videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@ttl_cache
def load_x_posts() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT x.id, x.competitor_id, x.post_url, x.text, x.posted_at, x.like_count,
                   x.retweet_count, x.reply_count, x.quote_count, x.view_count, x.is_retweet,
                   x.category, x.funnel_stage, x.message_attribute, c.name AS competitor_name, c.is_own_brand
            FROM x_posts x
            JOIN competitors c ON c.id = x.competitor_id
            ORDER BY x.posted_at DESC
            """,
            conn,
        )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df


@ttl_cache
def load_google_ads() -> pd.DataFrame:
    with get_conn() as conn:
        df = pd.read_sql(
            """
            SELECT g.id, g.competitor_id, g.advertiser_name, g.is_own_ad, g.search_term, g.headline, g.ad_format,
                   g.ad_url, g.first_shown, g.last_shown, g.approx_days_shown, g.is_active,
                   g.funnel_stage, g.message_attribute, c.name AS competitor_name, c.is_own_brand
            FROM google_ads g
            JOIN competitors c ON c.id = g.competitor_id
            ORDER BY g.last_shown DESC
            """,
            conn,
        )
    df["first_shown"] = pd.to_datetime(df["first_shown"])
    df["last_shown"] = pd.to_datetime(df["last_shown"])
    return df


@ttl_cache
def load_google_ad_creative(ad_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT creative FROM google_ads WHERE id = %s", (ad_id,))
            row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


def _bulk_blob_map(table: str, col: str, ids: list) -> dict:
    """One query for every id instead of one query per id - "See all" on a
    channel with real volume (confirmed: Instagram Organic, Meta Ads, and
    Google Ads all do this) was doing up to ~200 separate DB round trips
    to load each creative's image individually, which is what made those
    specific channels take 20-35+ seconds (sometimes long enough to be
    killed by the platform's own request timeout) while lower-volume
    channels stayed fast on the exact same per-item code path."""
    ids = [int(i) for i in ids]
    if not ids:
        return {}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, {col} FROM {table} WHERE id = ANY(%s)", (ids,))
            rows = cur.fetchall()
    return {row_id: to_data_uri(blob) for row_id, blob in rows if blob}


# @ttl_cache (not just a bare function) matters here, not only for repeat-
# request speed: it's what gives these bulk queries the same per-key
# locking as every other loader, so N concurrent warm-loop threads asking
# for the same (brand, channel) can't each open their own simultaneous
# connection the way the old per-item loaders could before that was fixed.
# `ids` must be a hashable tuple, not a list, to be usable as a cache key.
@ttl_cache
def load_ig_thumbnails_bulk(ids: tuple) -> dict:
    return _bulk_blob_map("posts", "thumbnail", ids)


@ttl_cache
def load_ad_creatives_bulk(ids: tuple) -> dict:
    return _bulk_blob_map("ads", "creative", ids)


@ttl_cache
def load_google_ad_creatives_bulk(ids: tuple) -> dict:
    return _bulk_blob_map("google_ads", "creative", ids)


@ttl_cache
def load_competitor_groups() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql("SELECT competitor_id, group_name FROM competitor_groups", conn)


@ttl_cache
def load_competitor_meta() -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql(
            """SELECT id, name, instagram_handle, instagram_url, website_url, facebook_url,
                      tiktok_handle, youtube_url, x_handle, is_own_brand
               FROM competitors ORDER BY name""",
            conn,
        )


def load_all() -> dict:
    """The `data` dict shape signal_data.py's functions expect."""
    return {
        "posts": load_posts(), "homepages": load_homepage_snapshots(), "ads": load_ads(),
        "tiktok": load_tiktok(), "youtube": load_youtube(), "x_posts": load_x_posts(),
        "google_ads": load_google_ads(),
    }


LOADERS = {
    "ig_thumb": load_ig_thumbnail, "tt_thumb": load_tiktok_thumbnail,
    "tt_embed": lambda url: url.rstrip("/").split("/")[-1],  # frontend builds the embed URL
    "yt_thumb": load_youtube_thumbnail, "ad_creative": load_ad_creative,
    "ad_video": load_ad_video_b64, "gads_creative": load_google_ad_creative,
    "homepage_shot": load_screenshot,
    "ig_thumb_bulk": load_ig_thumbnails_bulk, "ad_creative_bulk": load_ad_creatives_bulk,
    "gads_creative_bulk": load_google_ad_creatives_bulk,
}
