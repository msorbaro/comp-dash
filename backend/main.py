"""Brand Signal API - FastAPI backend serving the React frontend.

Wraps signal_data.py (pure Python, no framework dependency) with HTTP
endpoints. In production this process also serves the built React app as
static files, so the whole thing is one deployable service.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import data_loaders as dl
import signal_data as sd

app = FastAPI(title="Brand Signal API")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

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
    data = _get_data()
    gm = _groups_meta()
    categories = _all_categories()
    out = []
    for cat_name in categories:
        brand_names = sorted(gm.loc[gm["group_name"] == cat_name, "name"].unique())
        cp = sd.category_profile(cat_name, brand_names, data)
        if not cp["profiles"]:
            continue
        out.append({
            "name": cat_name, "note": CATEGORY_NOTE.get(cat_name, ""),
            "competes": CATEGORY_COMPETES.get(cat_name, "read-across"),
            "mix": cp["mix"], "spread": cp["spread"],
            "profiles": [
                {"company": p["company"], "mix": p["mix"], "monthly_output": p["monthly_output"],
                 "total_all_time": p["total_all_time"]}
                for p in sorted(cp["profiles"], key=lambda p: -p["total_all_time"])
            ],
        })
    return _clean({"categories": out})


@app.get("/api/brand/{name}")
def get_brand(name: str):
    data = _get_data()
    if name not in _all_brand_names():
        raise HTTPException(404, f"Unknown brand: {name}")
    profile = sd.company_profile(name, data)
    rows = [{k: v for k, v in r.items() if k not in ("_sub", "_date_col")} for r in profile["rows"]]
    lead_id = profile["lead"]["channel"]["id"]
    return _clean({
        "company": name, "category": _brand_category(name), "mix": profile["mix"],
        "total_all_time": profile["total_all_time"], "monthly_output": profile["monthly_output"],
        "active_channels": profile["active_channels"], "consistency": profile["consistency"],
        "lead_channel_id": lead_id, "rows": rows,
    })


@app.get("/api/brand/{name}/channel/{channel_id}")
def get_channel(name: str, channel_id: str, n_creatives: int = 8):
    data = _get_data()
    if channel_id not in sd.CHANNEL_BY_ID:
        raise HTTPException(404, f"Unknown channel: {channel_id}")
    r = sd.channel_data(name, channel_id, data)
    r = {k: v for k, v in r.items() if k not in ("_sub", "_date_col")}
    creatives = sd.creative_rows(name, channel_id, data, n_creatives, dl.LOADERS)
    return _clean({"channel_data": r, "creatives": creatives})


@app.get("/api/category/{name}")
def get_category(name: str, focus_brand: str = ""):
    data = _get_data()
    gm = _groups_meta()
    if name not in _all_categories():
        raise HTTPException(404, f"Unknown category: {name}")
    brand_names = sorted(gm.loc[gm["group_name"] == name, "name"].unique())
    cp = sd.category_profile(name, brand_names, data)
    members = sorted(cp["profiles"], key=lambda p: -p["mix"][0])
    outlier_names = {o["company"] for o in cp["outliers"]}

    channel_rows = []
    for ch in sd.CHANNELS:
        rs_active = [r for r in (sd.channel_data(n, ch["id"], data) for n in brand_names) if r["total_all_time"] > 0]
        if not rs_active:
            continue
        avg_vol = round(sum(r["volume"] for r in rs_active) / len(rs_active))
        mix = [round(sum(r["split"][i] for r in rs_active) / len(rs_active)) for i in range(3)]
        mix[2] = 100 - mix[0] - mix[1]
        seen, msgs = set(), []
        for r in rs_active:
            for s in sd.STAGES:
                for m in r["messages"].get(s["name"], []):
                    if m not in seen:
                        seen.add(m)
                        msgs.append({"text": m, "color": s["color"]})
        channel_rows.append({"channel": ch, "avg_volume": avg_vol, "mix": mix, "messages": msgs[:5]})

    return _clean({
        "name": name, "note": CATEGORY_NOTE.get(name, ""), "competes": CATEGORY_COMPETES.get(name, "read-across"),
        "mix": cp["mix"], "spread": cp["spread"],
        "outliers": [
            {"company": o["company"], "mix": o["mix"]} for o in cp["outliers"]
        ],
        "members": [
            {"company": m["company"], "mix": m["mix"], "monthly_output": m["monthly_output"],
             "active_channels": m["active_channels"],
             "is_outlier": m["company"] in outlier_names, "is_focus": m["company"] == focus_brand}
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
        return {
            "company": name, "category": _brand_category(name), "mix": p["mix"],
            "monthly_output": p["monthly_output"], "active_channels": p["active_channels"],
            "consistency": p["consistency"], "lead_channel_name": p["lead"]["channel"]["name"],
        }

    rows = []
    for ch in sd.CHANNELS:
        ra, rb = sd.channel_data(a, ch["id"], data), sd.channel_data(b, ch["id"], data)
        if ra["total_all_time"] == 0 and rb["total_all_time"] == 0:
            continue
        rows.append({
            "channel": ch,
            "a": {"volume": ra["volume"], "split": ra["split"]},
            "b": {"volume": rb["volume"], "split": rb["split"]},
        })

    return _clean({"a": _profile_summary(pa, a), "b": _profile_summary(pb, b), "rows": rows})


@app.post("/api/refresh")
def refresh_cache():
    dl.clear_cache()
    return {"status": "ok"}


# Serve the built React app (frontend/dist) if present, so this one process
# is the whole deployable app.
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
