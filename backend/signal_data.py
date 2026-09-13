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
    {"id": "search", "name": "Paid Search", "short": "Paid Search", "paid": True, "unit": "ads tracked", "shape": "search"},
    {"id": "meta_ads", "name": "IG / FB Ads", "short": "Meta Ads", "paid": True, "unit": "ads tracked", "shape": "square"},
    {"id": "ig_organic", "name": "Instagram Organic", "short": "IG Organic", "paid": False, "unit": "posts", "shape": "square"},
    {"id": "tiktok", "name": "TikTok", "short": "TikTok", "paid": False, "unit": "videos", "shape": "vertical"},
    {"id": "youtube", "name": "YouTube", "short": "YouTube", "paid": False, "unit": "videos", "shape": "wide"},
    {"id": "x", "name": "X / Twitter", "short": "X", "paid": False, "unit": "posts", "shape": "quote"},
    {"id": "homepage", "name": "Homepage", "short": "Homepage", "paid": False, "unit": "snapshots", "shape": "vertical"},
]
CHANNEL_BY_ID = {c["id"]: c for c in CHANNELS}

# A channel counts as "active" if it averages at least this many posts/ads
# per month over the last 90 days (r["volume"] is the 90-day count, so ÷3
# gives the monthly rate) - a real, stated cadence bar, not a vague notion
# of "some activity".
ACTIVE_MONTHLY_THRESHOLD = 5


def is_channel_active(r: dict) -> bool:
    """Homepage is a special case: it's checked weekly regardless of whether
    the page changed, so it's always counted as active rather than judged by
    a posting-cadence threshold that doesn't apply to it."""
    return r["channel"]["id"] == "homepage" or (r["volume"] / 3) >= ACTIVE_MONTHLY_THRESHOLD


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


def _stage_volume_90(sub: pd.DataFrame, date_col: str, funnel_col: str) -> dict:
    """Absolute (not %) counts of each See/Think/Do stage in the last 90
    days - the % split alone can't tell you whether a stage is genuinely
    low-volume or just a small share of a huge total; this gives the real
    number so e.g. "we have good See content" can be checked against "but
    we only post 4 of them a quarter"."""
    if sub.empty or not date_col:
        return {"See": 0, "Think": 0, "Do": 0}
    now = _tz_naive_now(sub[date_col])
    recent = sub[sub[date_col] >= (now - dt.timedelta(days=90))]
    if not funnel_col or recent.empty:
        return {"See": 0, "Think": 0, "Do": 0}
    counts = recent[funnel_col].value_counts()
    return {s: int(counts.get(s, 0)) for s in ("See", "Think", "Do")}


def _weeks_last_12(sub: pd.DataFrame, date_col: str) -> tuple:
    """Returns (counts, week_start_labels) - labels are the Monday-ish start
    date of each 7-day bucket, so the cadence chart can show a real x-axis
    instead of 12 unlabeled bars."""
    now = _tz_naive_now(sub[date_col]) if not sub.empty else dt.datetime.now()
    counts, labels = [], []
    for i in range(11, -1, -1):
        start = now - dt.timedelta(days=(i + 1) * 7)
        end = now - dt.timedelta(days=i * 7)
        counts.append(0 if sub.empty else int(((sub[date_col] >= start) & (sub[date_col] < end)).sum()))
        labels.append(start.strftime("%b %-d"))
    return counts, labels


def _content_types(sub: pd.DataFrame, category_col: str) -> list:
    valid = sub[category_col].dropna()
    if valid.empty:
        return []
    counts = valid.value_counts(normalize=True) * 100
    return [{"name": k, "pct": round(v)} for k, v in counts.items()]


def _text_series_for(sub: pd.DataFrame, channel_id: str) -> pd.Series:
    """Search prefers `headline` - the ad's own visible copy, read via vision
    (e.g. "KIA Brake Repair - Save $100") - since that's real signal about
    what the ad targets. Google never exposes an advertiser's actual bid
    keyword, so `headline` is the best substitute; `search_term` is only
    which of OUR OWN queries found the ad, not their real targeting. Falls
    back to "advertiser — found via 'query'" when no headline was extracted
    (e.g. a video ad, or not yet backfilled) - `advertiser_name` alone was a
    bad fallback on its own since it's frequently a PARENT corporate entity
    (e.g. "Mavis Tire Supply LLC" for Brakes Plus), which made the LLM
    synthesis hallucinate a "competitor hijacking" narrative."""
    if channel_id == "search" and "advertiser_name" in sub.columns:
        adv = sub["advertiser_name"].fillna("")
        term = sub["search_term"].fillna("") if "search_term" in sub.columns else ""
        fallback = (adv + ' — found via "' + term + '"').where(adv != "", "")
        if "headline" in sub.columns:
            return sub["headline"].where(sub["headline"].notna() & (sub["headline"] != ""), fallback)
        return fallback
    text_col = _text_col_for(channel_id)
    return sub[text_col] if text_col in sub.columns else pd.Series(dtype=object, index=sub.index)


def _messages_by_stage(sub: pd.DataFrame, funnel_col: str, channel_id: str, n: int = 2) -> dict:
    text_series = _text_series_for(sub, channel_id)
    out = {}
    for stage_id in ("See", "Think", "Do"):
        pool = text_series[sub[funnel_col] == stage_id].dropna()
        pool = pool[pool.str.strip() != ""] if len(pool) else pool
        picks = pool.head(n).tolist() if len(pool) else []
        out[stage_id] = [(t[:78] + "…") if len(t) > 78 else t for t in picks]
    return out


def stage_examples_for_synthesis(name: str, channel_id: str, data: dict, n: int = 15) -> dict:
    """Fuller (more examples, less truncation) version of _messages_by_stage,
    used only as LLM input for synthesize.channel_synthesis - the short
    version above is for direct display elsewhere."""
    sub, _date_col, funnel_col, _category_col = _channel_frame(name, channel_id, data)
    out = {}
    if not funnel_col or sub.empty:
        return {"See": [], "Think": [], "Do": []}
    text_series = _text_series_for(sub, channel_id)
    for stage_id in ("See", "Think", "Do"):
        pool = text_series[sub[funnel_col] == stage_id].dropna()
        pool = pool[pool.str.strip() != ""] if len(pool) else pool
        picks = pool.head(n).tolist() if len(pool) else []
        out[stage_id] = [(t[:160] + "…") if len(t) > 160 else t for t in picks]
    return out


def brand_sample_texts(name: str, data: dict, n_per_channel: int = 10, days: int = 180) -> list:
    """A cross-channel sample of a brand's real marketing copy from the last
    `days` days only, for synthesize.brand_positioning - the point of this is
    "what have we actually told customers lately", not a lifetime-average
    positioning that could be quoting messaging from years ago."""
    texts = []
    for ch in CHANNELS:
        sub, date_col, _funnel_col, _category_col = _channel_frame(name, ch["id"], data)
        if sub.empty:
            continue
        if date_col and date_col in sub.columns:
            sub = sub.copy()
            sub[date_col] = pd.to_datetime(sub[date_col])
            sub = sub.dropna(subset=[date_col])
            if len(sub):
                cutoff = _tz_naive_now(sub[date_col]) - dt.timedelta(days=days)
                sub = sub[sub[date_col] >= cutoff]
            sub = sub.sort_values(date_col, ascending=False)
        pool = _text_series_for(sub, ch["id"]).dropna()
        pool = pool[pool.str.strip() != ""]
        texts.extend(t[:200] for t in pool.head(n_per_channel).tolist())
    return texts


def category_stage_output(brand_names: list, data: dict) -> dict:
    """Absolute See/Think/Do volume in the last 90 days, summed across every
    channel and brand in a category - the real number behind a mix %, so a
    small stage's share isn't confused with a genuinely low-volume one (e.g.
    "60% See" means little if that's 3 posts total)."""
    totals = {"See": 0, "Think": 0, "Do": 0}
    for name in brand_names:
        for ch in CHANNELS:
            r = channel_data(name, ch["id"], data)
            for s in totals:
                totals[s] += r["stage_volume_90"][s]
    return totals


def stage_attribute_breakdown(brand_names: list, stage_name: str, data: dict, days: int = 90) -> dict:
    """REAL counts (not sampled) of each classified message_attribute among
    a stage's output for a list of brands, in the last `days` days - a
    mechanical census against the message_attribute column every content
    table now carries, not an AI estimate from a handful of examples. Returns
    {"counts": {attribute: n, ...}, "total": n} where total is the count of
    stage items that have a classification at all (the denominator for %)."""
    from categorize.attribute_taxonomy import MESSAGE_ATTRIBUTES

    counts = {a: 0 for a in MESSAGE_ATTRIBUTES}
    total = 0
    for name in brand_names:
        for ch in CHANNELS:
            sub, date_col, funnel_col, _category_col = _channel_frame(name, ch["id"], data)
            if sub.empty or not funnel_col or "message_attribute" not in sub.columns:
                continue
            sub = sub.copy()
            if date_col and date_col in sub.columns:
                sub[date_col] = pd.to_datetime(sub[date_col])
                sub = sub.dropna(subset=[date_col])
                if len(sub):
                    now = _tz_naive_now(sub[date_col])
                    sub = sub[sub[date_col] >= (now - dt.timedelta(days=days))]
            stage_sub = sub[sub[funnel_col] == stage_name]
            for attr in stage_sub["message_attribute"].dropna():
                if attr in counts:
                    counts[attr] += 1
                    total += 1
    return {"counts": counts, "total": total}


def company_volume_breakdown(brand_names: list, data: dict, days: int = 90) -> list:
    """Per-company posting/ad volume in the last `days` days, broken down
    three ways: by funnel stage (See/Think/Do), by real classified message
    attribute, and by channel - the numbers behind "how often does each
    company post, what is that output made of, and where does it run."
    `total` counts every real post/ad in the window regardless of
    classification; by_stage/by_attribute counts are only over items that
    do have a classification (same convention as the mix/% fields
    elsewhere), so they can undercount total slightly for a brand with
    unclassified backlog. by_channel needs no classification, so it always
    sums to `total` exactly.
    Returns one dict per brand_names entry, in the same order given:
    {"company": name, "total": n, "by_stage": {...}, "by_attribute": {...}, "by_channel": {...}}."""
    from categorize.attribute_taxonomy import MESSAGE_ATTRIBUTES

    out = []
    for name in brand_names:
        total = 0
        by_stage = {s["name"]: 0 for s in STAGES}
        by_attribute = {a: 0 for a in MESSAGE_ATTRIBUTES}
        by_channel = {ch["id"]: 0 for ch in CHANNELS}
        for ch in CHANNELS:
            sub, date_col, funnel_col, _category_col = _channel_frame(name, ch["id"], data)
            if sub.empty:
                continue
            sub = sub.copy()
            if date_col and date_col in sub.columns:
                sub[date_col] = pd.to_datetime(sub[date_col])
                sub = sub.dropna(subset=[date_col])
                if len(sub):
                    now = _tz_naive_now(sub[date_col])
                    sub = sub[sub[date_col] >= (now - dt.timedelta(days=days))]
            total += len(sub)
            by_channel[ch["id"]] += len(sub)
            if funnel_col and funnel_col in sub.columns:
                for stage, cnt in sub[funnel_col].value_counts().items():
                    if stage in by_stage:
                        by_stage[stage] += int(cnt)
            if "message_attribute" in sub.columns:
                for attr, cnt in sub["message_attribute"].value_counts().items():
                    if attr in by_attribute:
                        by_attribute[attr] += int(cnt)
        out.append({"company": name, "total": total, "by_stage": by_stage, "by_attribute": by_attribute, "by_channel": by_channel})
    return out


def category_channel_sample_texts(brand_names: list, channel_id: str, data: dict, n_per_brand: int = 6) -> list:
    """A cross-BRAND sample of real copy on one channel, for
    synthesize.category_channel_themes - the point is finding recurring
    THEMES across an entire category on this channel, not any one brand's
    specific offers."""
    texts = []
    for name in brand_names:
        sub, date_col, _funnel_col, _category_col = _channel_frame(name, channel_id, data)
        if sub.empty:
            continue
        if date_col and date_col in sub.columns:
            sub = sub.sort_values(date_col, ascending=False)
        pool = _text_series_for(sub, channel_id).dropna()
        pool = pool[pool.str.strip() != ""]
        texts.extend(t[:200] for t in pool.head(n_per_brand).tolist())
    return texts


def _text_col_for(channel_id: str) -> str:
    return {
        "ig_organic": "caption", "tiktok": "caption", "youtube": "title",
        "x": "text", "meta_ads": "headline", "search": "advertiser_name", "homepage": "theme",
    }.get(channel_id, "caption")


def _monthly_avg_all_time(sub: pd.DataFrame, date_col: str) -> float:
    """Long-run posting rate: total items / months between the first and last
    tracked item - honest for channels that were active once and have gone
    quiet, unlike a 90-day-window rate which reads as ~0 for them."""
    if sub.empty or not date_col:
        return 0.0
    span_days = (sub[date_col].max() - sub[date_col].min()).days
    months = max(span_days / 30.44, 1.0)
    return round(len(sub) / months, 1)


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
    recent_engagement = None
    if eng_series is not None and date_col and len(sub):
        now = _tz_naive_now(sub[date_col])
        recent_mask = sub[date_col] >= (now - dt.timedelta(days=90))
        recent_vals = eng_series[recent_mask]
        recent_engagement = round(recent_vals.mean()) if len(recent_vals) else None
    weeks, week_labels = _weeks_last_12(sub, date_col) if date_col else ([0] * 12, [""] * 12)
    content_types = _content_types(sub, category_col) if category_col else []
    messages = _messages_by_stage(sub, funnel_col, channel_id) if funnel_col else {"See": [], "Think": [], "Do": []}
    last_posted = sub[date_col].max().strftime("%b %d, %Y") if date_col and len(sub) else None
    # Stale = real history exists but nothing in over a year - distinct from
    # simply "not tracked" (no history at all). A channel with old posts but
    # a year-plus gap reads as "could be worth pursuing" if only shown as a
    # small number, when it's actually abandoned - this makes that explicit
    # rather than leaving it to be inferred from a date.
    stale = bool(date_col and len(sub) and (_tz_naive_now(sub[date_col]) - sub[date_col].max()).days > 365)
    stage_volume_90 = _stage_volume_90(sub, date_col, funnel_col)

    return {
        "channel": ch, "company": name, "split": split, "volume": volume,
        "engagement": engagement, "recent_engagement": recent_engagement, "trend": trend,
        "weeks": weeks, "week_labels": week_labels,
        "content_types": content_types, "messages": messages, "stage_volume_90": stage_volume_90,
        "total_all_time": len(sub), "monthly_avg_all_time": _monthly_avg_all_time(sub, date_col),
        "last_posted": last_posted, "stale": stale, "_sub": sub, "_date_col": date_col,
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
    total_volume_90 = sum(r["volume"] for r in rows)
    max_volume_90 = max((r["volume"] for r in rows), default=0)
    max_total_all_time = max((r["total_all_time"] for r in rows), default=0)
    for r in rows:
        r["share"] = round(r["volume"] / total_volume_90 * 100) if total_volume_90 else None
        r["vol_bar_pct"] = round(r["volume"] / max_volume_90 * 100) if max_volume_90 else 0
        r["total_bar_pct"] = round(r["total_all_time"] / max_total_all_time * 100) if max_total_all_time else 0
    total_all_time = sum(r["total_all_time"] for r in rows)

    # The brand's overall See/Think/Do mix must reflect what it's doing NOW,
    # not what it did years ago - a channel abandoned since 2021 shouldn't
    # get to dictate today's mix just because it racked up a lot of volume
    # while it was still active. Exclude stale (dormant 1yr+) channels from
    # the weighting; fall back to every channel only in the edge case where
    # literally nothing is currently active (better than an all-zero mix).
    mix_rows = [r for r in rows if not r["stale"]]
    if not any(r["total_all_time"] for r in mix_rows):
        mix_rows = rows
    mix_weight_total = sum(r["total_all_time"] for r in mix_rows)
    weighted = [0.0, 0.0, 0.0]
    for r in mix_rows:
        w = r["total_all_time"]
        for i in range(3):
            weighted[i] += r["split"][i] * w
    mix = [round(v / mix_weight_total) for v in weighted] if mix_weight_total else [0, 0, 0]
    if mix_weight_total:
        mix[2] = 100 - mix[0] - mix[1]

    active_channels = sum(1 for r in rows if is_channel_active(r))

    # "Heaviest channel" must be something actually happening now, not a
    # channel that got lucky years ago - a handful of old TikTok videos with
    # high view counts previously outranked channels the brand is genuinely
    # running today. So: only channels with real volume in the last 90 days
    # are eligible, ranked by recent volume weighted by recent engagement
    # (when engagement is tracked for that channel at all - paid channels
    # aren't, and shouldn't be penalized for that).
    recently_active = [r for r in rows if r["volume"] > 0]
    if recently_active:
        max_vol = max(r["volume"] for r in recently_active)
        max_eng = max((r["recent_engagement"] or 0 for r in recently_active), default=0)

        def _weight(r):
            vol_score = r["volume"] / max_vol if max_vol else 0
            eng_score = (r["recent_engagement"] / max_eng) if (r["recent_engagement"] and max_eng) else 1
            return vol_score * eng_score

        lead = max(recently_active, key=_weight)
        lead_is_recent = True
    else:
        lead = max(rows, key=lambda r: r["total_all_time"]) if any(r["total_all_time"] for r in rows) else rows[0]
        lead_is_recent = False

    monthly_output = round(sum(r["volume"] for r in rows) / 3)  # 90-day volume -> a monthly rate

    return {
        "company": name, "rows": rows, "mix": mix, "total_all_time": total_all_time,
        "monthly_output": monthly_output, "active_channels": active_channels,
        "lead": lead, "lead_is_recent": lead_is_recent,
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


def creative_rows(name: str, channel_id: str, data: dict, n: int, loaders: dict, type_filter: str = None) -> list:
    """Real creative cards for one brand+channel, newest/most-engaging first.
    loaders: dict of the dashboard's cached image-loading functions, kept as
    an argument so this module has no direct Streamlit/cache dependency.

    type_filter, when given, restricts to that one content type BEFORE
    truncating to `n` - filtering client-side on an already-small `n`-sized
    batch would frequently find zero matches for a less-common type that
    just didn't happen to fall within the most recent N items fetched for
    the unfiltered view."""
    sub, date_col, funnel_col, category_col = _channel_frame(name, channel_id, data)
    if sub.empty:
        return []
    if type_filter and category_col and category_col in sub.columns:
        sub = sub[sub[category_col] == type_filter]
        if sub.empty:
            return []
    # Launch order - most recently posted/run first - not engagement, so the
    # evidence reads as a timeline of what the brand is doing now rather than
    # surfacing old high-engagement outliers.
    sort_col = _ENGAGEMENT_COL.get(channel_id)
    if channel_id == "homepage":
        # Show distinct versions over time, not every weekly capture of the
        # same unchanged page - always keep the most recent capture (today's
        # live version) plus every capture flagged as an actual change.
        sub = sub.sort_values(date_col, ascending=False)
        sub = pd.concat([sub.head(1), sub[sub["changed"] == True]]).drop_duplicates(subset=["id"])  # noqa: E712
        sub = sub.sort_values(date_col, ascending=False)
    elif date_col:
        sub = sub.sort_values(date_col, ascending=False)

    if channel_id == "ig_organic" and not type_filter and date_col and len(sub):
        # Instagram-specific retention rule: an active account should show
        # its whole last year of posting, not an arbitrary fixed count - but
        # a dormant one (nothing posted in over a year) falls back to a
        # fixed recent sample so the section isn't empty. The year window is
        # anchored to the brand's OWN most recent post, not today's date -
        # anchoring to today would shrink a sparse/inactive account's window
        # to almost nothing (e.g. one recent post after a long gap would
        # exclude all the real history just outside a today-anchored year).
        now = _tz_naive_now(sub[date_col])
        most_recent = sub[date_col].iloc[0]
        if (now - most_recent).days > 365:
            top = sub.head(min(30, n))
        else:
            # Never fewer than 30 (or everything we have, if less) - but if
            # more than 30 posts fall within that year, show all of those
            # instead of capping at 30.
            cutoff = most_recent - dt.timedelta(days=365)
            within_year = len(sub[sub[date_col] >= cutoff])
            top = sub.head(min(max(30, within_year), n))
    else:
        top = sub.head(n)

    rows = []
    for _, r in top.iterrows():
        stage = r.get(funnel_col) if funnel_col else None
        if channel_id == "search":
            text = r.get("headline") or (f"{r.get('advertiser_name')} — found via \"{r.get('search_term')}\"" if r.get("advertiser_name") else "")
        else:
            text = r.get(_text_col_for(channel_id)) or ""
        date_val = r.get(date_col) if date_col else None
        date_label = pd.to_datetime(date_val).strftime("%b %d, %Y") if pd.notna(date_val) else ""
        eng = None
        if channel_id == "x":
            eng = int((r.get("like_count") or 0) + (r.get("retweet_count") or 0))
        elif sort_col and sort_col in r:
            eng = r.get(sort_col)

        image, video_url, embed_html, link, search_term = None, None, None, None, None
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
            search_term = r.get("search_term")
        elif channel_id == "homepage":
            image = loaders["homepage_shot"](r["id"])
        elif channel_id == "x":
            link = r.get("post_url")

        rows.append({
            "image": image, "video_url": video_url, "embed_html": embed_html, "link": link,
            "stage": stage, "type": r.get(category_col) if category_col else None,
            "why": text[:110] if text else "", "engagement": eng, "date": date_label,
            "shape": CHANNEL_BY_ID[channel_id]["shape"], "search_term": search_term,
            "channel_id": channel_id,
            "quote_text": r.get("text") if channel_id == "x" else None,
        })
    return rows
