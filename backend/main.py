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
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import data_loaders as dl
import signal_data as sd
import synthesize

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
    rows = [_attach_synthesis(name, r, data) for r in rows]
    lead_id = profile["lead"]["channel"]["id"]
    positioning = synthesize.brand_positioning(name, sd.brand_sample_texts(name, data))
    return _clean({
        "company": name, "category": _brand_category(name), "mix": profile["mix"],
        "total_all_time": profile["total_all_time"], "monthly_output": profile["monthly_output"],
        "active_channels": profile["active_channels"],
        "lead_channel_id": lead_id, "lead_is_recent": profile["lead_is_recent"], "rows": rows,
        "tagline": positioning["tagline"], "positioning": positioning["positioning"],
    })


@app.get("/api/brand/channel")
def get_channel(name: str, channel_id: str, n_creatives: int = 8, type_filter: str = ""):
    data = _get_data()
    if channel_id not in sd.CHANNEL_BY_ID:
        raise HTTPException(404, f"Unknown channel: {channel_id}")
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

    def compute():
        data = _get_data()
        gm = _groups_meta()
        brand_names = sorted(gm.loc[gm["group_name"] == category, "name"].unique())
        rows = sd.company_volume_breakdown(brand_names, data, days=days)
        meta = _competitor_meta()
        for r in rows:
            r["logo_url"] = _logo_url(r["company"], meta)
        rows.sort(key=lambda r: -r["total"])
        return _clean({"category": category, "days": days, "rows": rows})

    return _cached_page(f"volume:{category}:{days}", compute)


@app.post("/api/refresh")
def refresh_cache():
    dl.clear_cache()
    with _page_cache_lock:
        _page_cache.clear()
    return {"status": "ok"}


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
            for name in _all_brand_names():
                if _brand_category(name) == "Our Brands":
                    _refresh_page(f"brand:{name}", lambda name=name: _compute_brand(name))
        except Exception as e:
            print(f"[warm-cache] cycle failed: {e}", flush=True)
        time.sleep(480)  # 8 minutes: under Render free tier's 15-min idle sleep


threading.Thread(target=_warm_cache_loop, daemon=True).start()


# Serve the built React app (frontend/dist) if present, so this one process
# is the whole deployable app.
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
