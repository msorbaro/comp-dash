"""Real-data aggregation layer for the "Brand Signal" dashboard redesign.

Mirrors the shape of the Claude-design mockup's invented `data.js` (STAGES,
CHANNELS, channelData/companyProfile/categoryProfile/creatives) but every
number here is computed from the actual scraped/classified rows already
loaded into pandas DataFrames by dashboard/app.py - nothing is fabricated.
Where the mock's field has no honest real-data equivalent (e.g. a generic
"engagement" number for a channel we don't track likes on), the field is
None and the caller renders an explicit "not tracked" state rather than a
fake number.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

STAGES = [
    {"id": "see", "name": "See", "color": "#22B8C4",
     "desc": "Broad reach to people who may or may not be in market. Goal is awareness and one memorable message."},
    {"id": "think", "name": "Think", "color": "#0B4F55",
     "desc": "People who have shown interest but are not ready. Goal is helping them choose."},
    {"id": "do", "name": "Do", "color": "#D97706",
     "desc": "Active intent. Goal is winning the transaction over every competitor."},
]
STAGE_COLOR = {s["name"]: s["color"] for s in STAGES}  # keyed by the real DB values ("See"/"Think"/"Do")
STAGE_ID_BY_NAME = {s["name"]: s["id"] for s in STAGES}

CHANNELS = [
    {"id": "meta_ads", "name": "IG / FB Ads", "short": "Meta Ads", "paid": True, "unit": "ads tracked", "shape": "square"},
    {"id": "ig_organic", "name": "Instagram Organic", "short": "IG Organic", "paid": False, "unit": "posts", "shape": "square"},
    {"id": "tiktok", "name": "TikTok", "short": "TikTok", "paid": False, "unit": "videos", "shape": "vertical"},
    {"id": "youtube", "name": "YouTube", "short": "YouTube", "paid": False, "unit": "videos", "shape": "wide"},
    {"id": "x", "name": "X / Twitter", "short": "X", "paid": False, "unit": "posts", "shape": "text"},
    {"id": "search", "name": "Paid Search", "short": "Paid Search", "paid": True, "unit": "ads tracked", "shape": "text"},
    {"id": "homepage", "name": "Homepage", "short": "Homepage", "paid": False, "unit": "snapshots", "shape": "wide"},
]
CHANNEL_BY_ID = {c["id"]: c for c in CHANNELS}

_NOW = pd.Timestamp.now(tz="UTC")


def _tz_naive_now(series: pd.Series) -> pd.Timestamp:
    if len(series) and getattr(series.dt, "tz", None) is not None:
        return _NOW
    return pd.Timestamp.now()


def _channel_frame(name: str, channel_id: str, data: dict) -> tuple:
    """Returns (sub_df, date_col, funnel_col, category_col) for one brand's
    slice of one channel's raw table, or (empty df, ...) if untracked."""
    if channel_id == "ig_organic":
        df = data["posts"]
        return df[df["competitor_name"] == name], "posted_at", "funnel_stage", "category"
    if channel_id == "tiktok":
        df = data["tiktok"]
        return df[df["competitor_name"] == name], "posted_at", "funnel_stage", "category"
    if channel_id == "youtube":
        df = data["youtube"]
        return df[df["competitor_name"] == name], "posted_at", "funnel_stage", "category"
    if channel_id == "x":
        df = data["x_posts"]
        return df[df["competitor_name"] == name], "posted_at", "funnel_stage", "category"
    if channel_id == "meta_ads":
        df = data["ads"]
        return df[df["competitor_name"] == name], "start_date", "funnel_stage", "category"
    if channel_id == "search":
        df = data["google_ads"]
        sub = df[(df["competitor_name"] == name) & (df["is_own_ad"])]
        return sub, "first_shown", "funnel_stage", "ad_format"
    if channel_id == "homepage":
        df = data["homepages"]
        return df[df["competitor_name"] == name], "captured_at", "funnel_stage", "theme"
    return pd.DataFrame(), None, None, None


_ENGAGEMENT_COL = {"ig_organic": "like_count", "tiktok": "view_count", "youtube": "view_count"}


def _engagement_series(channel_id: str, sub: pd.DataFrame):
    if channel_id == "x":
        return sub["like_count"].fillna(0) + sub["retweet_count"].fillna(0)
    col = _ENGAGEMENT_COL.get(channel_id)
    if col and col in sub.columns:
        return sub[col]
    return None


def _split_from_stages(sub: pd.DataFrame, funnel_col: str) -> list:
    classified = sub[funnel_col].dropna()
    if classified.empty:
        return [0, 0, 0]
    counts = classified.value_counts(normalize=True) * 100
    raw = [counts.get("See", 0), counts.get("Think", 0), counts.get("Do", 0)]
    rounded = [round(v) for v in raw]
    rounded[2] = 100 - rounded[0] - rounded[1]
    return rounded


def _volume_and_trend(sub: pd.DataFrame, date_col: str) -> tuple:
    if sub.empty:
        return 0, 0, None
    now = _tz_naive_now(sub[date_col])
    d90 = now - dt.timedelta(days=90)
    d180 = now - dt.timedelta(days=180)
    recent = (sub[date_col] >= d90).sum()
    prior = ((sub[date_col] >= d180) & (sub[date_col] < d90)).sum()
    trend = None if prior == 0 else round((recent - prior) / prior * 100)
    return int(recent), int(prior), trend


def _weeks_last_12(sub: pd.DataFrame, date_col: str) -> list:
    if sub.empty:
        return [0] * 12
    now = _tz_naive_now(sub[date_col])
    weeks = []
    for i in range(11, -1, -1):
        start = now - dt.timedelta(days=(i + 1) * 7)
        end = now - dt.timedelta(days=i * 7)
        weeks.append(int(((sub[date_col] >= start) & (sub[date_col] < end)).sum()))
    return weeks


def _content_types(sub: pd.DataFrame, category_col: str) -> list:
    valid = sub[category_col].dropna()
    if valid.empty:
        return []
    counts = valid.value_counts(normalize=True) * 100
    return [{"name": k, "pct": round(v)} for k, v in counts.items()]


def _messages_by_stage(sub: pd.DataFrame, funnel_col: str, text_col: str, n: int = 2) -> dict:
    out = {}
    for stage_id in ("See", "Think", "Do"):
        pool = sub[sub[funnel_col] == stage_id][text_col].dropna()
        pool = pool[pool.str.strip() != ""] if len(pool) else pool
        picks = pool.head(n).tolist() if len(pool) else []
        out[stage_id] = [(t[:78] + "…") if len(t) > 78 else t for t in picks]
    return out


def _text_col_for(channel_id: str) -> str:
    return {
        "ig_organic": "caption", "tiktok": "caption", "youtube": "title",
        "x": "text", "meta_ads": "headline", "search": "advertiser_name", "homepage": "theme",
    }.get(channel_id, "caption")


def channel_data(name: str, channel_id: str, data: dict) -> dict:
    ch = CHANNEL_BY_ID[channel_id]
    sub, date_col, funnel_col, category_col = _channel_frame(name, channel_id, data)
    sub = sub.copy()
    if date_col and date_col in sub.columns:
        sub[date_col] = pd.to_datetime(sub[date_col])
        sub = sub.dropna(subset=[date_col])

    volume, prior_volume, trend = _volume_and_trend(sub, date_col) if date_col else (len(sub), 0, None)
    split = _split_from_stages(sub, funnel_col) if funnel_col else [0, 0, 0]
    eng_series = _engagement_series(channel_id, sub)
    engagement = round(eng_series.mean()) if eng_series is not None and len(eng_series) else None
    weeks = _weeks_last_12(sub, date_col) if date_col else [0] * 12
    content_types = _content_types(sub, category_col) if category_col else []
    messages = _messages_by_stage(sub, funnel_col, _text_col_for(channel_id)) if funnel_col else {"See": [], "Think": [], "Do": []}

    return {
        "channel": ch, "company": name, "split": split, "volume": volume,
        "engagement": engagement, "trend": trend, "weeks": weeks,
        "content_types": content_types, "messages": messages,
        "total_all_time": len(sub), "_sub": sub, "_date_col": date_col,
    }


def dominant_idx(mix: list) -> int:
    return mix.index(max(mix))


def verdict(mix: list) -> str:
    labels = ["See-led · buying attention", "Think-led · educating shoppers", "Do-led · pushing conversion"]
    return labels[dominant_idx(mix)]


def dominant_word(mix: list) -> str:
    return ["See-led", "Think-led", "Do-led"][dominant_idx(mix)]


def mix_label(mix: list) -> str:
    return f"{mix[0]} / {mix[1]} / {mix[2]}"


def company_profile(name: str, data: dict) -> dict:
    rows = [channel_data(name, ch["id"], data) for ch in CHANNELS]
    total_all_time = sum(r["total_all_time"] for r in rows)
    weighted = [0.0, 0.0, 0.0]
    for r in rows:
        w = r["total_all_time"]
        for i in range(3):
            weighted[i] += r["split"][i] * w
    mix = [round(v / total_all_time) for v in weighted] if total_all_time else [0, 0, 0]
    if total_all_time:
        mix[2] = 100 - mix[0] - mix[1]

    active_channels = sum(1 for r in rows if r["total_all_time"] > (2 if r["channel"]["id"] == "homepage" else 3))
    with_engagement = [r for r in rows if r["engagement"] is not None]
    lead = max(with_engagement, key=lambda r: r["engagement"]) if with_engagement else \
        max(rows, key=lambda r: r["total_all_time"])

    # Consistency: how similar the See/Do emphasis is across a brand's active
    # channels - a real, derived measure of "one story or several", not a
    # fabricated score. 100 = every active channel leans the same way.
    active_rows = [r for r in rows if r["total_all_time"] > 0]
    if len(active_rows) >= 2:
        see_vals = [r["split"][0] for r in active_rows]
        do_vals = [r["split"][2] for r in active_rows]
        spread = (max(see_vals) - min(see_vals) + max(do_vals) - min(do_vals)) / 2
        consistency = max(0, round(100 - spread))
    else:
        consistency = None

    monthly_output = round(sum(r["volume"] for r in rows) / 3)  # 90-day volume -> a monthly rate

    return {
        "company": name, "rows": rows, "mix": mix, "total_all_time": total_all_time,
        "monthly_output": monthly_output, "active_channels": active_channels,
        "consistency": consistency, "lead": lead,
    }


def category_profile(category_name: str, brand_names: list, data: dict) -> dict:
    profiles = [company_profile(n, data) for n in brand_names]
    with_data = [p for p in profiles if p["total_all_time"] > 0]
    if with_data:
        mix = [round(sum(p["mix"][i] for p in with_data) / len(with_data)) for i in range(3)]
        mix[2] = 100 - mix[0] - mix[1]
        spread = [max(p["mix"][i] for p in with_data) - min(p["mix"][i] for p in with_data) for i in range(3)]
        outliers = sorted(
            with_data,
            key=lambda p: abs(p["mix"][0] - mix[0]) + abs(p["mix"][2] - mix[2]),
            reverse=True,
        )[:2]
    else:
        mix, spread, outliers = [0, 0, 0], [0, 0, 0], []
    return {"name": category_name, "profiles": profiles, "mix": mix, "spread": spread, "outliers": outliers}


def creative_rows(name: str, channel_id: str, data: dict, n: int, loaders: dict) -> list:
    """Real creative cards for one brand+channel, newest/most-engaging first.
    loaders: dict of the dashboard's cached image-loading functions, kept as
    an argument so this module has no direct Streamlit/cache dependency."""
    sub, date_col, funnel_col, category_col = _channel_frame(name, channel_id, data)
    if sub.empty:
        return []
    sort_col = _ENGAGEMENT_COL.get(channel_id)
    if channel_id == "x":
        sub = sub.copy()
        sub["_eng"] = sub["like_count"].fillna(0) + sub["retweet_count"].fillna(0)
        sub = sub.sort_values("_eng", ascending=False)
    elif sort_col and sort_col in sub.columns:
        sub = sub.sort_values(sort_col, ascending=False)
    elif date_col:
        sub = sub.sort_values(date_col, ascending=False)
    top = sub.head(n)

    rows = []
    for _, r in top.iterrows():
        stage = r.get(funnel_col) if funnel_col else None
        text = r.get(_text_col_for(channel_id)) or ""
        date_val = r.get(date_col) if date_col else None
        date_label = pd.to_datetime(date_val).strftime("%b %d, %Y") if pd.notna(date_val) else ""
        eng = None
        if channel_id == "x":
            eng = int((r.get("like_count") or 0) + (r.get("retweet_count") or 0))
        elif sort_col and sort_col in r:
            eng = r.get(sort_col)

        image, video_url, embed_html, link = None, None, None, None
        if channel_id == "ig_organic":
            image = loaders["ig_thumb"](r["id"])
            link = r.get("post_url")
        elif channel_id == "tiktok":
            image = loaders["tt_thumb"](r["id"])
            embed_html = loaders["tt_embed"](r["video_url"])
            link = r.get("video_url")
        elif channel_id == "youtube":
            image = loaders["yt_thumb"](r["id"])
            link = r.get("video_url")
        elif channel_id == "meta_ads":
            image = loaders["ad_creative"](r["id"])
            if r.get("has_video"):
                video_url = loaders["ad_video"](r["id"])
            link = r.get("ad_url")
        elif channel_id == "search":
            image = loaders["gads_creative"](r["id"])
            link = r.get("ad_url")
        elif channel_id == "homepage":
            image = loaders["homepage_shot"](r["id"])

        rows.append({
            "image": image, "video_url": video_url, "embed_html": embed_html, "link": link,
            "stage": stage, "type": r.get(category_col) if category_col else None,
            "why": text[:110] if text else "", "engagement": eng, "date": date_label,
            "shape": CHANNEL_BY_ID[channel_id]["shape"],
        })
    return rows
