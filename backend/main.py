"""Brand Signal API - FastAPI backend serving the React frontend.

Wraps signal_data.py (pure Python, no framework dependency) with HTTP
endpoints. In production this process also serves the built React app as
static files, so the whole thing is one deployable service.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import hashlib
import math
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import urlparse

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import data_loaders as dl
import signal_data as sd
import synthesize
import voice_data
from categorize import theme_summary

app = FastAPI(title="Brand Signal API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Lightweight shared-password gate for this internal dashboard - not
# hardened auth (no per-user accounts, no rate limiting), just a speed bump
# so the app isn't wide open to anyone with the URL. The frontend shell
# always loads; every /api/* call (except the login call itself) requires
# the cookie set by a correct /api/login, so there's no real data without it.
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "mavis")
_AUTH_COOKIE = "bs_auth"
_AUTH_TOKEN = hashlib.sha256(SITE_PASSWORD.encode()).hexdigest()


@app.middleware("http")
async def _require_site_password(request: Request, call_next):
    if request.url.path == "/api/login" or not request.url.path.startswith("/api/"):
        return await call_next(request)
    if request.cookies.get(_AUTH_COOKIE) != _AUTH_TOKEN:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.post("/api/login")
def login(payload: dict):
    if payload.get("password") != SITE_PASSWORD:
        raise HTTPException(401, "Incorrect password")
    resp = JSONResponse({"ok": True})
    resp.set_cookie(_AUTH_COOKIE, _AUTH_TOKEN, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return resp

CATEGORY_COMPETES = {
    "Our Brands": "portfolio",
    "Automotive Full Service": "direct",
    "Oil Brands": "adjacent",
    "Car Washes": "adjacent",
    "Online Tires": "adjacent",
    "Automotive Discount": "adjacent",
    "Value Leaders": "read-across",
    "Big Box Retail + Services": "read-across",
    "Low Interest / Functional Categories": "read-across",
    "Maintenance": "read-across",
    "Best in Class Marketing": "read-across",
}
CATEGORY_NOTE = {
    "Our Brands": "The Mavis portfolio",
    "Automotive Full Service": "Direct competition",
    "Oil Brands": "Adjacent auto service",
    "Car Washes": "Adjacent auto service",
    "Online Tires": "DIY purchase path",
    "Automotive Discount": "Club and mass tire install",
    "Value Leaders": "Win on everyday low pricing",
    "Big Box Retail + Services": "Retail with a service arm",
    "Low Interest / Functional Categories": "Infrequent, need-driven purchase",
    "Maintenance": "Parallel service industry",
    "Best in Class Marketing": "Benchmark brand builders",
}


def _clean(obj):
    """Recursively strip pandas/internal fields and NaN so json.dumps is happy."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


# Result-level cache for the expensive pages (landscape, category rollups,
# brand deep-dives). data_loaders/synthesize only cache the raw DataFrames
# and individual LLM calls - the pandas aggregation across brands/channels
# in signal_data.py still re-ran on every request. On Render's throttled
# free-tier CPU that aggregation alone can take longer than the platform's
# own connection timeout, so a live request must never compute it inline -
# it has to read a result the background warm-up thread already produced.
_page_cache: dict = {}
_page_cache_lock = threading.Lock()
_PAGE_CACHE_TTL = 600  # seconds - warm thread refreshes every 480s, comfortably inside this


def _cached_page(key, compute_fn, block_on_miss: bool = True, ttl=_PAGE_CACHE_TTL):
    """block_on_miss=False (used for the pages the warm thread keeps fresh)
    never computes inline: it serves whatever is cached, even if stale (the
    warm thread will refresh it again shortly), and returns None only when
    nothing has been computed for this key yet at all."""
    with _page_cache_lock:
        entry = _page_cache.get(key)
    if entry is not None:
        fresh = ttl is None or (time.time() - entry[0]) < ttl
        if fresh or not block_on_miss:
            return entry[1]
    if not block_on_miss:
        return None
    result = compute_fn()
    with _page_cache_lock:
        _page_cache[key] = (time.time(), result)
    return result


def _refresh_page(key, compute_fn):
    result = compute_fn()
    with _page_cache_lock:
        _page_cache[key] = (time.time(), result)
    return result


def _get_data():
    return dl.load_all()


def _competitor_meta():
    return dl.load_competitor_meta()


def _groups_meta():
    meta = _competitor_meta()
    groups = dl.load_competitor_groups()
    return groups.merge(meta[["id", "name"]], left_on="competitor_id", right_on="id")


def _all_categories():
    return sorted(_groups_meta()["group_name"].unique())


def _all_brand_names():
    meta = _competitor_meta()
    return sorted(meta["name"].unique(), key=lambda n: (
        not meta.loc[meta["name"] == n, "is_own_brand"].iloc[0], n
    ))


def _brand_category(name: str) -> str:
    meta = _competitor_meta()
    is_own = meta.loc[meta["name"] == name, "is_own_brand"]
    if is_own.empty:
        raise HTTPException(404, f"Unknown brand: {name}")
    if is_own.iloc[0]:
        return "Our Brands"
    gm = _groups_meta()
    own_groups = gm.loc[gm["name"] == name, "group_name"]
    non_own = [g for g in own_groups if g != "Our Brands"]
    return non_own[0] if non_own else (own_groups.iloc[0] if len(own_groups) else "Our Brands")


# Brands whose real site has no proper favicon, so both Google's and
# DuckDuckGo's favicon services fall back to some unrelated cached image
# (confirmed for Tire Kingdom: tirekingdom.com serves its full HTML app
# shell at /favicon.ico instead of an actual icon). Manually excluded
# rather than shown wrong - the frontend's initial-letter fallback covers it.
LOGO_OVERRIDES = {"Tire Kingdom": None}


def _logo_url(name: str, meta) -> Optional[str]:
    """A small brand mark for chart markers - there's no logo asset pipeline
    in this app, so this derives one from the brand's own website favicon
    via Google's public favicon service (no API key, no scraping needed)."""
    if name in LOGO_OVERRIDES:
        return LOGO_OVERRIDES[name]
    url = meta.loc[meta["name"] == name, "website_url"]
    if url.empty or not url.iloc[0]:
        return None
    domain = urlparse(url.iloc[0]).netloc
    if not domain:
        return None
    return f"https://www.google.com/s2/favicons?sz=64&domain={domain}"


@app.get("/api/meta")
def get_meta():
    meta = _competitor_meta()
    last_run = dl.load_last_run()
    return _clean({
        "categories": [
            {"name": c, "note": CATEGORY_NOTE.get(c, ""), "competes": CATEGORY_COMPETES.get(c, "read-across")}
            for c in _all_categories()
        ],
        "channels": sd.CHANNELS,
        "stages": sd.STAGES,
        "brands": [
            {"name": n, "category": _brand_category(n), "is_own_brand": bool(meta.loc[meta["name"] == n, "is_own_brand"].iloc[0])}
            for n in _all_brand_names()
        ],
        "last_run": last_run,
    })


@app.get("/api/landscape")
def get_landscape():
    result = _cached_page("landscape", _compute_landscape, block_on_miss=False)
    if result is None:
        raise HTTPException(503, "Still warming up after a restart - this can take a minute or two on first load. Refresh shortly.")
    return result


def _compute_landscape():
    data = _get_data()
    gm = _groups_meta()
    categories = _all_categories()
    category_brands = {
        cat_name: sorted(gm.loc[gm["group_name"] == cat_name, "name"].unique())
        for cat_name in categories
    }

    out = []
    stage_output_by_category = {}
    for cat_name, brand_names in category_brands.items():
        cp = sd.category_profile(cat_name, brand_names, data)
        if not cp["profiles"]:
            continue
        stage_output_by_category[cat_name] = sd.category_stage_output(brand_names, data)
        # Real per-channel volume alongside the stage mix, so the bottom
        # grid can toggle between "how this brand splits See/Think/Do" and
        # "which channels this brand actually runs" using the same layout.
        vol_by_name = {r["company"]: r for r in sd.company_volume_breakdown(brand_names, data, days=90)}
        channel_totals = {ch["id"]: 0 for ch in sd.CHANNELS}
        for r in vol_by_name.values():
            for ch_id, cnt in r["by_channel"].items():
                channel_totals[ch_id] += cnt
        out.append({
            "name": cat_name, "note": CATEGORY_NOTE.get(cat_name, ""),
            "competes": CATEGORY_COMPETES.get(cat_name, "read-across"),
            "mix": cp["mix"], "spread": cp["spread"],
            "stage_output": stage_output_by_category[cat_name],
            "channel_totals": channel_totals,
            "profiles": [
                {"company": p["company"], "mix": p["mix"], "monthly_output": p["monthly_output"],
                 "total_all_time": p["total_all_time"],
                 "channel_mix": vol_by_name.get(p["company"], {}).get("by_channel", {})}
                for p in sorted(cp["profiles"], key=lambda p: -p["total_all_time"])
            ],
        })

    all_brand_names = sorted({n for names in category_brands.values() for n in names})
    our_brand_names = category_brands.get("Our Brands", [])
    other_brand_names = [n for n in all_brand_names if n not in our_brand_names]

    # Industry-wide message ATTRIBUTES per stage - real classified counts
    # (see categorize/attribute_taxonomy.py), not an AI guess from a sample.
    # For each fixed attribute (Safety, Trust, Price, etc), what % of OUR
    # stage output touches it vs what % of EVERYONE ELSE's does - so "we
    # have good See content" can be checked against "but do we actually say
    # these things as often as the market, as a share of our own output."
    stage_themes = {}
    for s in sd.STAGES:
        our_breakdown = sd.stage_attribute_breakdown(our_brand_names, s["name"], data)
        other_breakdown = sd.stage_attribute_breakdown(other_brand_names, s["name"], data)
        stage_themes[s["name"]] = {"our": our_breakdown, "other": other_breakdown}

    # The headline comparison: Our Brands' See-stage output (raw count, not
    # %) against the highest-output competitor group, and Our Brands' Do%
    # against the average of every other group - the numbers behind "we
    # have decent See content but post so little of it that it gets drowned
    # out, while running Do-heavy compared to the rest of the market".
    our_stage_output = stage_output_by_category.get("Our Brands", {"See": 0, "Think": 0, "Do": 0})
    other_categories = [c for c in out if c["name"] != "Our Brands"]
    max_see_category = max(other_categories, key=lambda c: c["stage_output"]["See"], default=None)
    our_mix = next((c["mix"] for c in out if c["name"] == "Our Brands"), [0, 0, 0])
    other_do_avg = round(sum(c["mix"][2] for c in other_categories) / len(other_categories)) if other_categories else None

    insights = {
        "our_see_output_90d": our_stage_output["See"],
        "max_competitor_see_output_90d": max_see_category["stage_output"]["See"] if max_see_category else None,
        "max_competitor_see_category": max_see_category["name"] if max_see_category else None,
        "our_do_pct": our_mix[2],
        "other_categories_avg_do_pct": other_do_avg,
    }

    return _clean({"categories": out, "stage_themes": stage_themes, "insights": insights})


def _attach_synthesis(name: str, r: dict, data: dict) -> dict:
    """Adds stage_summaries + an enriched read_line to one channel_data dict,
    via a cached Claude call - skipped entirely for channels with no content
    so an unused channel never costs a call."""
    if r["total_all_time"] == 0:
        r["stage_summaries"] = None
        r["read_line"] = None
        return r
    examples = sd.stage_examples_for_synthesis(name, r["channel"]["id"], data)
    dom_idx = sd.dominant_idx(r["split"])
    result = synthesize.channel_synthesis(
        name, r["channel"]["name"], r["split"][dom_idx], sd.STAGES[dom_idx]["name"], examples,
    )
    r["stage_summaries"] = {"See": result["see"], "Think": result["think"], "Do": result["do"]}
    read_line = result["read_line"]
    # volume is the 90-day count - total_all_time > 0 but volume == 0 means
    # this channel has real history but has gone quiet, which the read must
    # say up front rather than describing dead activity as if it's current.
    if r["volume"] == 0:
        read_line = f"No posts here in the last 90 days. Historically: {read_line}"
    r["read_line"] = read_line
    return r


@app.get("/api/brand")
def get_brand(name: str):
    # Not a path param: a brand name can contain "/" (e.g. "Mavis Discount
    # Tire / Mavis Tires and Brakes"), and Cloudflare (fronting the Render
    # deploy) normalizes a %2F in a path segment to a literal "/" before it
    # reaches this app, splitting the path before routing ever sees it.
    # A query param isn't subject to that normalization.
    if name not in _all_brand_names():
        raise HTTPException(404, f"Unknown brand: {name}")
    # Our own brands are kept warm by the background thread (like Landscape
    # and the "Our Brands" rollup) - never computed inline on a request.
    if _brand_category(name) == "Our Brands":
        result = _cached_page(f"brand:{name}", lambda: _compute_brand(name), block_on_miss=False)
        if result is None:
            raise HTTPException(503, "Still warming up after a restart - this can take a minute or two on first load. Refresh shortly.")
        return result
    return _cached_page(f"brand:{name}", lambda: _compute_brand(name))


def _compute_brand(name: str):
    data = _get_data()
    profile = sd.company_profile(name, data)
    rows = [{k: v for k, v in r.items() if k not in ("_sub", "_date_col")} for r in profile["rows"]]
    # Each row's synthesis and the brand positioning call are independent
    # Claude calls (one per active channel, plus one for positioning) -
    # running them sequentially took 28s for an active brand like PetSmart,
    # long enough to time out a cold visit since only "Our Brands" pages are
    # proactively warmed; every other tracked company computes live on
    # first request. Run them concurrently instead, same pattern as the
    # warm-cache loop.
    with ThreadPoolExecutor(max_workers=len(rows) + 1) as pool:
        positioning_future = pool.submit(synthesize.brand_positioning, name, sd.brand_sample_texts(name, data))
        rows = list(pool.map(lambda r: _attach_synthesis(name, r, data), rows))
        positioning = positioning_future.result()
    lead_id = profile["lead"]["channel"]["id"]
    return _clean({
        "company": name, "category": _brand_category(name), "mix": profile["mix"],
        "total_all_time": profile["total_all_time"], "monthly_output": profile["monthly_output"],
        "active_channels": profile["active_channels"],
        "lead_channel_id": lead_id, "lead_is_recent": profile["lead_is_recent"], "rows": rows,
        "tagline": positioning["tagline"], "positioning": positioning["positioning"],
    })


# The (n_creatives, type_filter) combos the frontend requests with no
# further user action: the Brand page's per-channel preview (see
# frontend/src/screens/Brand.jsx's SECTION_CREATIVE_FETCH_N) and the
# Channel "See all" page's full fetch (see Channel.jsx's CREATIVE_FETCH_N).
# The "See all" size was left on live-compute-then-cache at first since it
# used to be much more expensive - now that image loading is batched into
# one query per channel instead of one per item, it's cheap enough to
# proactively warm too, and a live "See all" click was still occasionally
# failing when it happened to land while the warm loop was mid-cycle,
# competing for the same throttled CPU/connections.
_DEFAULT_CHANNEL_N = 16
_FULL_CHANNEL_N = 500
_WARMED_CHANNEL_COMBOS = (_DEFAULT_CHANNEL_N, _FULL_CHANNEL_N)


@app.get("/api/brand/channel")
def get_channel(name: str, channel_id: str, n_creatives: int = 8, type_filter: str = ""):
    if channel_id not in sd.CHANNEL_BY_ID:
        raise HTTPException(404, f"Unknown channel: {channel_id}")
    key = f"channel:{name}:{channel_id}:{n_creatives}:{type_filter}"
    is_default_view = n_creatives in _WARMED_CHANNEL_COMBOS and not type_filter
    if is_default_view and _brand_category(name) == "Our Brands":
        result = _cached_page(key, lambda: _compute_channel(name, channel_id, n_creatives, type_filter), block_on_miss=False)
        if result is None:
            raise HTTPException(503, "Still warming up after a restart - this can take a minute or two on first load. Refresh shortly.")
        return result
    return _cached_page(key, lambda: _compute_channel(name, channel_id, n_creatives, type_filter))


def _compute_channel(name: str, channel_id: str, n_creatives: int, type_filter: str):
    data = _get_data()
    r = sd.channel_data(name, channel_id, data)
    r = {k: v for k, v in r.items() if k not in ("_sub", "_date_col")}
    r = _attach_synthesis(name, r, data)
    creatives = sd.creative_rows(name, channel_id, data, n_creatives, dl.LOADERS, type_filter=type_filter or None)
    return _clean({"channel_data": r, "creatives": creatives})


@app.get("/api/category")
def get_category(name: str, focus_brand: str = ""):
    # Not a path param: a category name can contain "/" (e.g. "Low Interest
    # / Functional Categories"), which Cloudflare normalizes out of a path
    # segment before this app ever sees the request - see get_brand above.
    if name not in _all_categories():
        raise HTTPException(404, f"Unknown category: {name}")
    # focus_brand only tweaks an is_focus flag on the already-computed
    # result, so it's applied as a cheap post-step rather than fragmenting
    # the cache (or, for "Our Brands", forcing a live recompute) per brand.
    if name == "Our Brands":
        # This is the page our own team actually lives in, so it's kept
        # warm by the background thread like Landscape - never computed inline.
        result = _cached_page("category:Our Brands", lambda: _compute_category(name), block_on_miss=False)
        if result is None:
            raise HTTPException(503, "Still warming up after a restart - this can take a minute or two on first load. Refresh shortly.")
    else:
        result = _cached_page(f"category:{name}", lambda: _compute_category(name))
    if focus_brand:
        result = {**result, "members": [{**m, "is_focus": m["company"] == focus_brand} for m in result["members"]]}
    return result


def _compute_category(name: str):
    data = _get_data()
    gm = _groups_meta()
    brand_names = sorted(gm.loc[gm["group_name"] == name, "name"].unique())
    cp = sd.category_profile(name, brand_names, data)
    members = sorted(cp["profiles"], key=lambda p: -p["mix"][0])
    outlier_names = {o["company"] for o in cp["outliers"]}

    channel_rows = []
    for ch in sd.CHANNELS:
        all_rows = [sd.channel_data(n, ch["id"], data) for n in brand_names]
        used_rows = [r for r in all_rows if sd.is_channel_active(r)]
        rs_active = [r for r in all_rows if r["total_all_time"] > 0]
        if not rs_active:
            continue
        # Popularity/adoption: how many brands in the category actually run
        # this channel (by the same "active" bar used everywhere else), not
        # just how many have ever posted on it once.
        total_volume_90 = sum(r["volume"] for r in all_rows)
        mix = [round(sum(r["split"][i] for r in rs_active) / len(rs_active)) for i in range(3)]
        mix[2] = 100 - mix[0] - mix[1]
        sample_texts = sd.category_channel_sample_texts(brand_names, ch["id"], data)
        themes = synthesize.category_channel_themes(name, ch["name"], sample_texts)
        channel_rows.append({
            "channel": ch, "mix": mix,
            "brands_using": len(used_rows), "brands_total": len(brand_names),
            "total_volume_90": total_volume_90, "avg_volume": round(total_volume_90 / len(brand_names), 1),
            "themes": themes,
        })
    channel_rows.sort(key=lambda cr: -cr["brands_using"])

    # Real classified attribute counts for this category's own stage output
    # (no our-vs-other split needed here - it's already scoped to one group).
    stage_themes = {s["name"]: sd.stage_attribute_breakdown(brand_names, s["name"], data) for s in sd.STAGES}

    return _clean({
        "name": name, "note": CATEGORY_NOTE.get(name, ""), "competes": CATEGORY_COMPETES.get(name, "read-across"),
        "mix": cp["mix"], "spread": cp["spread"], "stage_themes": stage_themes,
        "outliers": [
            {"company": o["company"], "mix": o["mix"]} for o in cp["outliers"]
        ],
        "members": [
            {"company": m["company"], "mix": m["mix"], "monthly_output": m["monthly_output"],
             "active_channels": m["active_channels"],
             "is_outlier": m["company"] in outlier_names, "is_focus": False}
            for m in members
        ],
        "channel_rows": channel_rows,
    })


@app.get("/api/compare")
def get_compare(a: str, b: str):
    data = _get_data()
    if a not in _all_brand_names() or b not in _all_brand_names():
        raise HTTPException(404, "Unknown brand")
    pa, pb = sd.company_profile(a, data), sd.company_profile(b, data)

    def _profile_summary(p, name):
        lead = p["lead"]
        return {
            "company": name, "category": _brand_category(name), "mix": p["mix"],
            "monthly_output": p["monthly_output"], "active_channels": p["active_channels"],
            "lead_channel_name": lead["channel"]["name"], "lead_channel_unit": lead["channel"]["unit"],
            "lead_channel_id": lead["channel"]["id"],
            "lead_channel_volume": lead["volume"], "lead_channel_engagement": lead["recent_engagement"],
            "lead_is_recent": p["lead_is_recent"],
        }

    rows = []
    for ch in sd.CHANNELS:
        ra, rb = sd.channel_data(a, ch["id"], data), sd.channel_data(b, ch["id"], data)
        # Only compare channels at least one brand is actively running today
        # (same bar as "active channels" everywhere else) - a channel neither
        # brand has touched in months just adds noise to a head-to-head read.
        if not (sd.is_channel_active(ra) or sd.is_channel_active(rb)):
            continue
        rows.append({
            "channel": ch,
            "a": {"volume": ra["volume"], "split": ra["split"]},
            "b": {"volume": rb["volume"], "split": rb["split"]},
        })

    return _clean({"a": _profile_summary(pa, a), "b": _profile_summary(pb, b), "rows": rows})


@app.get("/api/landscape/volume")
def get_landscape_volume(category: str = "Our Brands", days: int = 90):
    if category not in _all_categories():
        raise HTTPException(404, f"Unknown category: {category}")
    if days not in (30, 90, 180, 365):
        raise HTTPException(400, "days must be 30, 90, 180, or 365")

    return _cached_page(f"volume:{category}:{days}", lambda: _compute_volume(category, days))


def _compute_volume(category: str, days: int):
    data = _get_data()
    gm = _groups_meta()
    brand_names = sorted(gm.loc[gm["group_name"] == category, "name"].unique())
    rows = sd.company_volume_breakdown(brand_names, data, days=days)
    meta = _competitor_meta()
    for r in rows:
        r["logo_url"] = _logo_url(r["company"], meta)
    rows.sort(key=lambda r: -r["total"])
    return _clean({"category": category, "days": days, "rows": rows})


@app.get("/api/landscape/messaging-study")
def get_messaging_study():
    return _cached_page("messaging-study", _compute_messaging_study)


def _compute_messaging_study():
    """Live-computed backing for the Landscape page's "Messaging Study"
    section - a 10-matrix competitive messaging audit (territory heatmap,
    gap map vs. benchmarks, funnel posture, channel x territory, content
    mix, homepage leads, channel footprint, ad longevity, creative variety,
    and organic engagement by territory), plus verbatim quotes and a
    mechanically-generated synthesis. Pure pandas aggregation over the
    already-cached load_all() tables - no LLM calls, so this is cheap
    enough to compute on a normal cache miss rather than needing the
    proactive warm-cache loop."""
    from categorize.attribute_taxonomy import MESSAGE_ATTRIBUTES

    data = _get_data()
    gm = _groups_meta()
    meta = _competitor_meta()

    def _brands_in(group_name):
        return sorted(gm.loc[gm["group_name"] == group_name, "name"].unique())

    portfolio = [n for n in _all_brand_names() if _brand_category(n) == "Our Brands"]
    afs = _brands_in("Automotive Full Service")
    bic = _brands_in("Best in Class Marketing")
    lowint = _brands_in("Low Interest / Functional Categories")
    bigbox = _brands_in("Big Box Retail + Services")
    # "Adjacent" has no single matching group - it's the union of the 4
    # groups CATEGORY_COMPETES already tags "adjacent" (see top of file).
    adj = sorted({n for g in ("Oil Brands", "Car Washes", "Online Tires", "Automotive Discount") for n in _brands_in(g)})
    all_brands = _all_brand_names()
    core_brands = sorted(set(portfolio) | set(afs))

    # Matrix 01 - territory heatmap: per-brand attribute %, two brand sets
    # (the frontend toggle switches between these, both precomputed here
    # rather than round-tripping on toggle).
    def _heatmap_rows(brand_names):
        rows = sd.company_volume_breakdown(brand_names, data, days=365)
        out = []
        for r in rows:
            attr_total = sum(r["by_attribute"].values())
            pct = {a: (round(c / attr_total * 100, 1) if attr_total else 0.0) for a, c in r["by_attribute"].items()}
            out.append({"company": r["company"], "category": _brand_category(r["company"]), "n": r["total"], "attr": pct})
        return out

    heatmap = {"core": _heatmap_rows(core_brands), "all": _heatmap_rows(all_brands)}

    # Matrix 02 - gap map: portfolio's pooled territory mix vs. 5 benchmark
    # segments, all using the same pooled (not per-brand-averaged) measure.
    seg_mix = {
        "own": sd.territory_mix(portfolio, data), "afs": sd.territory_mix(afs, data),
        "adj": sd.territory_mix(adj, data), "bic": sd.territory_mix(bic, data),
        "lowint": sd.territory_mix(lowint, data), "bigbox": sd.territory_mix(bigbox, data),
    }
    gap = []
    for attr in MESSAGE_ATTRIBUTES:
        own_v, afs_v = seg_mix["own"]["attr"][attr], seg_mix["afs"]["attr"][attr]
        gap.append({
            "attribute": attr, "own": own_v, "afs": afs_v,
            "adj": seg_mix["adj"]["attr"][attr], "bic": seg_mix["bic"]["attr"][attr],
            "lowint": seg_mix["lowint"]["attr"][attr], "bigbox": seg_mix["bigbox"]["attr"][attr],
            "delta_vs_afs": round(own_v - afs_v, 1),
        })
    gap.sort(key=lambda g: g["delta_vs_afs"])

    # Matrix 03 - funnel posture: portfolio + direct competitors together,
    # sorted by Do% descending, same as the artifact.
    funnel_posture = []
    for r in sd.company_volume_breakdown(core_brands, data, days=365):
        stage_total = sum(r["by_stage"].values())
        pct = {s: (round(c / stage_total * 100, 1) if stage_total else 0.0) for s, c in r["by_stage"].items()}
        funnel_posture.append({"company": r["company"], "own": r["company"] in portfolio, "n": r["total"], **pct})
    funnel_posture.sort(key=lambda r: -r["Do"])

    # Matrix 04 - channel x territory: portfolio vs. best-in-class, per channel.
    channel_territory = [
        {"channel": ch, "own": sd.territory_mix(portfolio, data, channel_id=ch["id"]),
         "bic": sd.territory_mix(bic, data, channel_id=ch["id"])}
        for ch in sd.CHANNELS
    ]

    # Matrix 05 - content mix, portfolio + direct competitors.
    content_mix = sd.content_mix_breakdown(core_brands, data, days=365)
    for r in content_mix:
        r["own"] = r["company"] in portfolio

    # Matrix 06 - homepage leads (classified theme, not literal headline text).
    homepage_leads = sd.homepage_leads(core_brands, data)
    for r in homepage_leads:
        r["own"] = r["company"] in portfolio

    # Matrix 07 - footprint, with a "tracked" flag per channel so "no
    # content" and "no handle recorded" don't read as the same thing.
    footprint = sd.channel_footprint(core_brands, data)
    handle_col = {
        "meta_ads": "facebook_url", "ig_organic": "instagram_handle",
        "tiktok": "tiktok_handle", "youtube": "youtube_url", "x": "x_handle",
    }
    for r in footprint:
        row_meta = meta.loc[meta["name"] == r["company"]]
        tracked = {}
        for ch_id, col in handle_col.items():
            val = row_meta.iloc[0].get(col) if not row_meta.empty and col in row_meta.columns else None
            tracked[ch_id] = bool(val) and pd.notna(val)
        r["tracked"] = tracked
        r["own"] = r["company"] in portfolio

    # Matrix 08 - ad longevity (median days a search creative has been running).
    ad_longevity = sd.ad_longevity(core_brands, data)
    for r in ad_longevity:
        r["own"] = r["company"] in portfolio

    # Matrix 09 - creative variety (% distinct copy in sampled Meta ads).
    creative_variety = sd.creative_variety(core_brands, data)
    for r in creative_variety:
        r["own"] = r["company"] in portfolio

    # Matrix 10 - engagement by territory, pooled across every tracked brand.
    engagement_by_territory = sd.engagement_by_territory(data, days=365)

    # Evidence: verbatim quotes - portfolio's own paid social, and
    # competitors' copy in the territories the gap map flags as vacated.
    vacated = [g["attribute"] for g in gap if g["delta_vs_afs"] < 0][:3]
    quotes_own = sd.messaging_quotes(portfolio, data, channel_id="meta_ads", n=6)
    quotes_gap = sd.messaging_quotes(afs, data, attributes=vacated, n=6)

    # Synthesis - mechanical template sentences built from the numbers
    # already computed above, not an LLM call (per user preference: fast,
    # free, deterministic, no new place for the analysis to say something
    # wrong).
    synthesis = []
    widest = min(gap, key=lambda g: g["delta_vs_afs"])
    strongest = max(gap, key=lambda g: g["delta_vs_afs"])
    synthesis.append({
        "finding": f"The portfolio runs {abs(widest['delta_vs_afs']):.1f} points lighter on "
                   f"{widest['attribute']} than direct full-service competitors "
                   f"({widest['own']}% vs {widest['afs']}%).",
        "confidence": "high" if (widest["own"] + widest["afs"]) > 5 else "directional",
    })
    synthesis.append({
        "finding": f"The portfolio's strongest relative territory is {strongest['attribute']} "
                   f"({strongest['own']}% vs {strongest['afs']}% for direct competitors, "
                   f"+{strongest['delta_vs_afs']:.1f} points).",
        "confidence": "high",
    })
    own_do, afs_do = seg_mix["own"]["funnel"].get("Do", 0), seg_mix["afs"]["funnel"].get("Do", 0)
    synthesis.append({
        "finding": f"{own_do}% of portfolio messaging is bottom-funnel (Do), versus {afs_do}% for "
                   f"direct competitors.",
        "confidence": "high",
    })
    organic_ids = [ch["id"] for ch in sd.CHANNELS if not ch["paid"] and ch["id"] != "homepage"]
    no_organic = [r["company"] for r in footprint if r["own"] and not any(r[cid] for cid in organic_ids)]
    if no_organic:
        synthesis.append({
            "finding": f"{len(no_organic)} of {len(portfolio)} portfolio brands published no organic "
                       f"content in the last 12 months: {', '.join(no_organic)}.",
            "confidence": "high",
        })
    dup = [r for r in creative_variety if r["own"] and r["distinct_pct"] is not None]
    if dup:
        lowest = min(dup, key=lambda r: r["distinct_pct"])
        synthesis.append({
            "finding": f"{lowest['company']}'s paid social runs at {lowest['distinct_pct']}% creative "
                       f"variety ({lowest['n']} ads sampled) - the most duplicated in the portfolio.",
            "confidence": "directional",
        })

    return _clean({
        "window_days": 365, "heatmap": heatmap, "gap": gap, "seg_mix": seg_mix,
        "funnel_posture": funnel_posture, "channel_territory": channel_territory,
        "content_mix": content_mix, "homepage_leads": homepage_leads, "footprint": footprint,
        "ad_longevity": ad_longevity, "creative_variety": creative_variety,
        "engagement_by_territory": engagement_by_territory,
        "quotes_own": quotes_own, "quotes_gap": quotes_gap, "synthesis": synthesis,
    })


@app.post("/api/refresh")
def refresh_cache():
    dl.clear_cache()
    with _page_cache_lock:
        _page_cache.clear()
    return {"status": "ok"}


# Customer Voice (Phases 1-2-4 only for now - review text/theme coding and
# the Complaints view come later). These read straight off the voice schema's
# materialized views (db/voice_metrics.sql) - cheap direct queries, not
# expensive pandas aggregation like the messaging side, so no _cached_page
# wrapper is needed.
@app.get("/api/voice/states")
def get_voice_states(source: str = "google_maps"):
    return _clean(voice_data.state_summary(source))


@app.get("/api/voice/brands")
def get_voice_brands(state: str, source: str = "google_maps"):
    return _clean(voice_data.brand_state_summary(state, source))


@app.get("/api/voice/counties")
def get_voice_counties(state: str, source: str = "google_maps"):
    return _clean(voice_data.county_summary(state, source))


@app.get("/api/voice/county-locations")
def get_voice_county_locations(state: str, county_fips: str, city: str = None, source: str = "google_maps"):
    return _clean(voice_data.county_locations(state, county_fips, city, source))


@app.get("/api/voice/county-towns")
def get_voice_county_towns(state: str, county_fips: str, source: str = "google_maps"):
    return _clean(voice_data.county_town_summary(state, county_fips, source))


@app.get("/api/voice/state-towns")
def get_voice_state_towns(state: str, source: str = "google_maps"):
    return _clean(voice_data.state_towns(state, source))


# Cross-brand league table (Mavis banners + every named competitor, one
# ranked list) - nationwide by default, narrowed by state and/or city.
@app.get("/api/voice/rollup")
def get_voice_rollup(state: str = None, city: str = None, source: str = "google_maps"):
    return _clean(voice_data.brand_rollup(state, city, source))


# Review-level dataset (Phase 3) - monthly volume + sentiment trend, and a
# browsable sample of the underlying review text.
@app.get("/api/voice/review-states")
def get_voice_review_states():
    return _clean(voice_data.review_states())


@app.get("/api/voice/review-towns")
def get_voice_review_towns(state: str = "TX"):
    return _clean(voice_data.review_towns(state))


@app.get("/api/voice/review-trend")
def get_voice_review_trend(state: str = "TX", city: str = None, split_competitors: bool = False):
    return _clean(voice_data.review_trend(state, city, split_competitors))


@app.get("/api/voice/review-yoy")
def get_voice_review_yoy(state: str = "TX", city: str = None, split_competitors: bool = False):
    return _clean(voice_data.review_yoy(state, city, split_competitors))


@app.get("/api/voice/review-theme-mix")
def get_voice_review_theme_mix(state: str = "TX", city: str = None, brand: str = None):
    return _clean(voice_data.review_theme_mix(state, city, brand))


# On-demand (not precomputed) - a live single Haiku call over that theme's
# reviews (negative by default - "complaints" - or positive - "praise") in
# the current filter scope, so it stays correct as the state/city/brand
# filters change instead of being baked in for one scope.
@app.get("/api/voice/review-theme-complaints")
def get_voice_review_theme_complaints(theme: str, state: str = "TX", city: str = None, brand: str = None, sentiment: str = "negative"):
    texts = voice_data.review_theme_texts(theme, state, city, brand, sentiment)
    summary = theme_summary.summarize_theme_texts(theme, texts, sentiment)
    return _clean({"theme": theme, "n_reviews": len(texts), "summary": summary})


@app.get("/api/voice/review-sample")
def get_voice_review_sample(state: str = "TX", city: str = None, brand: str = None, sentiment: str = None, month: str = None, theme: str = None, rating: int = None, limit: int = 30):
    return _clean(voice_data.review_sample(state, city, brand, sentiment, month, theme, rating, limit))


# Head-to-head grid: every Mavis banner vs. every named competitor, cell =
# the gap computed only over states (or towns) where both operate. Filtered
# to a state and/or town, the sharing unit narrows automatically (see
# voice_data.head_to_head's docstring).
@app.get("/api/voice/head-to-head")
def get_voice_head_to_head(state: str = None, city: str = None, source: str = "google_maps"):
    return _clean(voice_data.head_to_head(state, city, source))


@app.get("/api/voice/competitors-by-state")
def get_voice_competitors_by_state(state: str, source: str = "google_maps"):
    return _clean(voice_data.competitor_state_summary(state, source))


@app.get("/api/voice/competitors-by-county")
def get_voice_competitors_by_county(state: str, county_fips: str, source: str = "google_maps"):
    return _clean(voice_data.competitor_county_summary(state, county_fips, source))


@app.get("/api/voice/brand-options")
def get_voice_brand_options():
    return _clean(voice_data.list_brands())


@app.get("/api/voice/main-brand/states")
def get_main_brand_states(brand_id: int, source: str = "google_maps"):
    return _clean(voice_data.main_brand_states(brand_id, source))


@app.get("/api/voice/main-brand/counties")
def get_main_brand_counties(brand_id: int, state: str, source: str = "google_maps"):
    return _clean(voice_data.main_brand_counties(brand_id, state, source))


@app.get("/api/voice/main-brand/towns")
def get_main_brand_towns(brand_id: int, state: str, county_fips: str = None, source: str = "google_maps"):
    return _clean(voice_data.main_brand_towns(brand_id, state, county_fips, source))


# Root level + drill data for the table's brand-rooted tree (brand -> state
# -> county -> town -> store) - distinct from the map's tier-based
# main-brand endpoints above, this carries real rating/benchmark/gap
# numbers, not a green/yellow/red tier.
@app.get("/api/voice/main-brand/national-summary")
def get_main_brand_national_summary(source: str = "google_maps"):
    return _clean(voice_data.main_brand_national_summary(source))


@app.get("/api/voice/main-brand/locations")
def get_main_brand_locations(brand_id: int, source: str = "google_maps"):
    return _clean(voice_data.main_brand_locations(brand_id, source))


# County table's per-Mavis-banner breakdown - fixed columns (every Mavis
# banner), each county row filled in for whichever banners actually operate
# there.
@app.get("/api/voice/county-brand-matrix")
def get_county_brand_matrix(state: str, source: str = "google_maps"):
    return _clean(voice_data.county_brand_matrix(state, source))


# Same breakdown, one level down - one row per town within a single county.
@app.get("/api/voice/county-town-brand-matrix")
def get_county_town_brand_matrix(state: str, county_fips: str, source: str = "google_maps"):
    return _clean(voice_data.county_town_brand_matrix(state, county_fips, source))


# Reddit brand-mention dataset - scraped + classified separately from the
# ratings chain above (no `source` param, unrelated data).
@app.get("/api/voice/reddit-summary")
def get_voice_reddit_summary():
    return _clean(voice_data.reddit_brand_summary())


@app.get("/api/voice/reddit-comparisons")
def get_voice_reddit_comparisons():
    return _clean(voice_data.reddit_comparisons())


@app.get("/api/voice/reddit-sample")
def get_voice_reddit_sample(brand: str = None, sentiment: str = None, theme: str = None, aspect: str = None, limit: int = 30):
    return _clean(voice_data.reddit_sample(brand, sentiment, theme, aspect, limit))


@app.get("/api/voice/reddit-theme-mix")
def get_voice_reddit_theme_mix(brand: str = None):
    return _clean(voice_data.reddit_theme_mix(brand))


# Same on-demand (not precomputed) live-summary pattern as
# /api/voice/review-theme-complaints - complaints (negative, default) or
# praise (positive) - reuses categorize/theme_summary.py, which is generic
# over "a theme label + a list of texts + a polarity," not review-specific.
@app.get("/api/voice/reddit-theme-complaints")
def get_voice_reddit_theme_complaints(theme: str, brand: str = None, sentiment: str = "negative"):
    texts = voice_data.reddit_theme_texts(theme, brand, sentiment)
    summary = theme_summary.summarize_theme_texts(theme, texts, sentiment)
    return _clean({"theme": theme, "n_mentions": len(texts), "summary": summary})


def _warm_cache_loop():
    # On a CPU-throttled free-tier host, the expensive pages (Landscape,
    # the "Our Brands" rollup, each own brand) are too slow to compute
    # inline within a user's request - Render's own edge/proxy drops the
    # connection well before a cold computation finishes. Compute them here
    # on a timer instead, straight into _page_cache, so a live request only
    # ever reads an already-finished result. Runs in a plain thread (not an
    # async task) because this is blocking pandas/DB/LLM work.
    time.sleep(20)  # let the app finish booting first
    while True:
        try:
            _refresh_page("landscape", _compute_landscape)
            _refresh_page("category:Our Brands", lambda: _compute_category("Our Brands"))
            our_brand_names = [n for n in _all_brand_names() if _brand_category(n) == "Our Brands"]

            # Every brand/channel/category combo below is independent and
            # dominated by I/O wait (LLM calls, DB reads), not CPU - running
            # them one at a time made a full cold cycle take many minutes
            # (confirmed: 148s locally just for 9 brands' main pages,
            # sequentially, on a fast machine with a fast network - Render's
            # throttled CPU made the live version far worse, and one slow
            # brand blocked every other brand's page from ever becoming
            # available). A thread pool runs them concurrently instead;
            # _safe_refresh keeps one failing brand/channel from aborting
            # the rest of the batch.
            with ThreadPoolExecutor(max_workers=9) as pool:
                # Pass 1: every own brand's main page, all at once.
                list(pool.map(
                    lambda name: _safe_refresh(f"brand:{name}", lambda: _compute_brand(name)),
                    our_brand_names,
                ))
                # Pass 2: the Brand deep-dive page fires one of these per
                # active channel on load (n=16), and the Channel "See all"
                # page fires the full n=500 fetch - previously totally
                # uncached, so every visit re-ran synthesis + creative
                # loading from scratch. Both combos are warmed now that
                # image loading is batched (one query per channel instead
                # of one per item), which made n=500 cheap enough to warm
                # too instead of leaving it to occasionally collide with
                # this very warm cycle on a live user's request.
                channel_tasks = [
                    (name, ch["id"], n)
                    for ch in sd.CHANNELS for name in our_brand_names for n in _WARMED_CHANNEL_COMBOS
                ]
                list(pool.map(
                    lambda t: _safe_refresh(
                        f"channel:{t[0]}:{t[1]}:{t[2]}:",
                        lambda: _compute_channel(t[0], t[1], t[2], ""),
                    ),
                    channel_tasks,
                ))
                # Default view for each Landscape volume-chart section
                # (Posting Cadence, Brand Matrix) - each fetches "Our
                # Brands" plus a comparison category at a specific `days`
                # window on first load. Not warming these left every one of
                # those charts doing a live 3-4s compute on a cache that
                # expired every 10 minutes.
                volume_tasks = [(c, d) for c in ("Our Brands", "Automotive Full Service") for d in (90, 365)]
                list(pool.map(
                    lambda t: _safe_refresh(f"volume:{t[0]}:{t[1]}", lambda: _compute_volume(t[0], t[1])),
                    volume_tasks,
                ))
        except Exception as e:
            print(f"[warm-cache] cycle failed: {e}", flush=True)
        time.sleep(480)  # 8 minutes: under Render free tier's 15-min idle sleep


_warm_status: dict = {}
_warm_status_lock = threading.Lock()


def _safe_refresh(key, compute_fn):
    """Same as _refresh_page, but swallows its own exception so one bad
    brand/channel in a parallel warm batch doesn't take the rest down with
    it (ThreadPoolExecutor.map re-raises on the first failed result when
    you iterate it). Also records the outcome in _warm_status so a failure
    is visible via /api/debug/warm-status without needing Render's own log
    dashboard - the print() alone was invisible from here."""
    t0 = time.time()
    try:
        _refresh_page(key, compute_fn)
        with _warm_status_lock:
            _warm_status[key] = {"ok": True, "at": time.time(), "took": time.time() - t0}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[warm-cache] {key} failed: {e}\n{tb}", flush=True)
        with _warm_status_lock:
            _warm_status[key] = {
                "ok": False, "at": time.time(), "took": time.time() - t0,
                "error": f"{type(e).__name__}: {e}", "traceback": tb,
            }


@app.get("/api/debug/warm-status")
def get_warm_status():
    with _warm_status_lock:
        return dict(_warm_status)


threading.Thread(target=_warm_cache_loop, daemon=True).start()


# Serve the built React app (frontend/dist) if present, so this one process
# is the whole deployable app.
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    # The React app is client-side routed (App.jsx reads/writes these paths
    # via the History API, no router library) - a direct/refreshed request
    # to one of these URLs would otherwise 404 inside StaticFiles(html=True),
    # which only auto-serves index.html for "/" and real directories, not
    # arbitrary unknown paths. Each of these just hands back the same built
    # index.html; the client JS then reads location.pathname to pick the screen.
    for _spa_path in ("/brand", "/category", "/compare", "/voice"):
        app.add_api_route(
            _spa_path,
            lambda: FileResponse(str(_dist / "index.html")),
            methods=["GET"],
            include_in_schema=False,
        )
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
