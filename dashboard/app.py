"""Brand Signal — Competitor Research Dashboard.

Reads ONLY from the database (never scrapes live). Run with:
    streamlit run dashboard/app.py

Visual design and information architecture are ported directly from the
Brand Signal design system (see `new designs/Design System.dc.html` and
`new designs/Brand Signal Dashboard.dc.html`) - colors, type, spacing and
component patterns are copied from those files. Every number rendered
here is computed from real scraped/classified data via signal_data.py;
none of the mock's invented numbers are used.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import base64

import pandas as pd
import streamlit as st

import signal_data as sd
from db.connection import get_conn

st.set_page_config(page_title="Brand Signal", layout="wide", page_icon="📡")

# ============================================================================
# DESIGN TOKENS — copied verbatim from new designs/Design System.dc.html
# ============================================================================
INK = "#141A21"
INK_80 = "#1F2831"
DEEP_TEAL = "#0B4F55"
TEAL = "#22B8C4"
TEAL_700 = "#0F7A84"
TEAL_WASH = "#EAF6F8"
AMBER = "#D97706"
ROSE = "#E11D48"
GREEN = "#16A34A"
SLATE_600 = "#475569"
SLATE_400 = "#94A3B8"
SLATE_200 = "#E2E8F0"
CANVAS = "#F6F8FA"
SURFACE = "#FFFFFF"
TRACK = "#EEF2F6"
ROW_LINE = "#F1F5F9"
INK_TEXT = "#1A1F26"
MUTED = "#6B7885"  # eyebrow / column-label grey used throughout the mock

STAGES = sd.STAGES
STAGE_COLOR = sd.STAGE_COLOR
MONO = "ui-monospace,Menlo,monospace"

# The mock's CATEGORIES were clearly modeled on our own real competitor_groups
# (identical names) - reuse its "how do they compete with us" classification
# and short notes, keyed onto the real group names in config/competitors.yaml.
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
COMPETES_LABEL = {"direct": "DIRECT COMPETITOR", "adjacent": "ADJACENT INDUSTRY",
                   "read-across": "READ-ACROSS", "portfolio": "OUR PORTFOLIO"}
CATEGORY_DOT_COLORS = ["#22B8C4", "#0B4F55", "#D97706", "#E11D48", "#16A34A", "#6366F1",
                        "#0F7A84", "#94A3B8", "#7C3AED", "#B45309", "#0EA5E9"]

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: Poppins, system-ui, sans-serif; }}
    body {{ background: {CANVAS}; }}
    .block-container {{ padding-top: 0.8rem; padding-bottom: 3rem; max-width: 1440px; }}
    a {{ color: {TEAL_700}; text-decoration: none; }}
    a:hover {{ color: {TEAL}; }}
    ::selection {{ background: #D5EFF1; }}

    [data-testid="stMetricValue"] {{ font-size: 1.5rem; color: {INK_TEXT}; font-weight: 600; }}
    [data-testid="stMetric"] {{ background: {SURFACE}; border: 1px solid {SLATE_200}; border-radius: 10px;
                                  padding: 0.8rem 0.9rem 0.5rem 0.9rem; }}

    /* Dark ink top nav bar */
    .st-key-topnav {{ background: {INK}; border-radius: 12px; padding: 10px 18px; margin-bottom: 14px; }}
    .st-key-topnav div[data-testid="stPills"] button {{
        font-family: Poppins, sans-serif !important; font-weight: 500; border-radius: 7px !important;
        color: #C7CED9 !important; border: none !important; background: transparent !important;
    }}
    .st-key-topnav div[data-testid="stPills"] button[aria-pressed="true"] {{
        background: {TEAL} !important; color: {INK} !important; font-weight: 600 !important;
    }}
    .st-key-topnav div[data-testid="stPills"] label {{ display: none; }}

    /* Category chip pills (st.pills, multi-look single-select) */
    .st-key-catchips div[data-testid="stPills"] button {{
        border-radius: 20px !important; font-weight: 500 !important; font-size: 11.5px !important;
        border: 1px solid {SLATE_200} !important; background: {SURFACE} !important; color: {SLATE_600} !important;
    }}
    .st-key-catchips div[data-testid="stPills"] button[aria-pressed="true"] {{
        background: {DEEP_TEAL} !important; color: #FFFFFF !important; border-color: {DEEP_TEAL} !important;
        font-weight: 600 !important;
    }}
    .st-key-catchips div[data-testid="stPills"] label {{ display: none; }}

    .stButton button {{ border-radius: 7px; font-family: Poppins, sans-serif; }}
    .stSelectbox div[data-baseweb="select"] {{ border-radius: 7px; font-family: Poppins, sans-serif; }}

    [data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px !important; }}

    .bs-eyebrow {{ font-size: 10px; letter-spacing: .16em; color: {TEAL_700}; font-weight: 600; }}
    .bs-h1 {{ margin: 0; font-size: 30px; font-weight: 600; letter-spacing: -.025em; line-height: 1.12; }}
    .bs-body {{ font-size: 13px; color: {SLATE_600}; line-height: 1.5; }}
    .bs-card {{ background: {SURFACE}; border: 1px solid {SLATE_200}; border-radius: 12px; padding: 20px 22px; }}
    .bs-ink-panel {{ background: {INK}; border-radius: 13px; padding: 24px 26px; color: #FFFFFF; }}
    .bs-mono {{ font-family: {MONO}; }}
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HTML COMPONENT BUILDERS — pixel values copied from the design mock
# ============================================================================
def fmt_num(n) -> str:
    if n is None:
        return "—"
    n = float(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n/1000:.0f}k"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(int(n))


def to_data_uri(raw: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(raw).decode()}"


def tiktok_embed_html(video_url: str) -> str:
    video_id = video_url.rstrip("/").split("/")[-1]
    return (f'<iframe src="https://www.tiktok.com/embed/v2/{video_id}" '
            f'style="width:100%;height:580px;border:none;overflow:hidden;" '
            f'allow="encrypted-media;" allowfullscreen></iframe>')


def stat_card(label: str, value: str, note: str = "") -> str:
    return (f'<div style="background:{SURFACE};border:1px solid {SLATE_200};border-radius:10px;padding:15px 16px">'
            f'<div style="font-size:9.5px;letter-spacing:.13em;color:{MUTED};font-weight:600">{label}</div>'
            f'<div style="font-size:26px;font-weight:600;letter-spacing:-.02em;margin:6px 0 2px;color:{DEEP_TEAL}">{value}</div>'
            f'<div style="font-size:11px;color:{SLATE_600};line-height:1.4">{note}</div></div>')


def stage_bar(mix: list, height: int = 11, radius: int = 6) -> str:
    segs = "".join(f'<div style="width:{max(mix[i],0)}%;background:{STAGES[i]["color"]}"></div>' for i in range(3))
    return f'<div style="display:flex;height:{height}px;border-radius:{radius}px;overflow:hidden;background:{TRACK}">{segs}</div>'


def mix_caption(mix: list, suffix: str = "see/think/do") -> str:
    tail = f"  {suffix}" if suffix else ""
    return f'<div style="font-size:10.5px;color:{MUTED};margin-top:7px;font-family:{MONO}">{sd.mix_label(mix)}{tail}</div>'


def paid_tag(paid: bool) -> str:
    if paid:
        return (f'<div style="display:inline-block;margin-top:5px;font-size:8.5px;letter-spacing:.1em;font-weight:600;'
                f'color:{AMBER};background:#FEF6E7;border:1px solid #F6E0BC;border-radius:4px;padding:2px 5px">PAID</div>')
    return (f'<div style="display:inline-block;margin-top:5px;font-size:8.5px;letter-spacing:.1em;font-weight:600;'
            f'color:{TEAL_700};background:{TEAL_WASH};border:1px solid #CFE9EC;border-radius:4px;padding:2px 5px">OWNED / ORGANIC</div>')


def competes_badge(kind: str, on_dark: bool = False) -> str:
    color = ROSE if kind == "direct" else (DEEP_TEAL if kind == "portfolio" else SLATE_600)
    bg = "rgba(255,255,255,.9)" if on_dark else ("#FDEEF2" if kind == "direct" else ("#EAF6F8" if kind == "portfolio" else "#F1F5F9"))
    border = "#F7CBD6" if kind == "direct" else ("#CFE9EC" if kind == "portfolio" else SLATE_200)
    return (f'<div style="display:inline-block;font-size:8.5px;letter-spacing:.11em;font-weight:600;padding:3px 6px;'
            f'border-radius:4px;color:{color};background:{bg};border:1px solid {border}">{COMPETES_LABEL.get(kind, kind)}</div>')


def read_line(text: str) -> str:
    return (f'<div style="font-size:12.5px;line-height:1.5;padding:13px 15px;background:{TEAL_WASH};border-radius:9px;'
            f'border-left:3px solid {TEAL}"><span style="font-weight:600;color:{DEEP_TEAL}">Read: </span>{text}</div>')


def trend_html(trend) -> str:
    if trend is None:
        return f'<div style="font-size:11px;color:{MUTED}">no prior-period data</div>'
    color = GREEN if trend >= 0 else ROSE
    arrow = "▲" if trend >= 0 else "▼"
    return f'<div style="font-size:11px;color:{color}">{arrow} {trend:+d}% vs prior 90d</div>'


def content_type_bars(content_types: list, limit: int = 5) -> str:
    if not content_types:
        return f'<div style="font-size:11px;color:{MUTED};font-style:italic">Not enough classified content yet.</div>'
    rows = []
    for ct in content_types[:limit]:
        rows.append(
            f'<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;'
            f'font-size:10.5px;color:{INK_TEXT};margin-bottom:3px"><span>{ct["name"]}</span>'
            f'<span style="color:{MUTED};font-family:{MONO}">{ct["pct"]}%</span></div>'
            f'<div style="height:5px;background:{TRACK};border-radius:3px;overflow:hidden">'
            f'<div style="height:100%;width:{ct["pct"]}%;background:{TEAL_700};border-radius:3px"></div></div></div>'
        )
    return "".join(rows)


def cadence_sparkline(weeks: list, height: int = 44) -> str:
    if not weeks or max(weeks) == 0:
        bars = "".join(f'<div style="flex:1;height:2px;background:{SLATE_200};border-radius:2px 2px 0 0"></div>' for _ in weeks)
    else:
        m = max(weeks)
        bars = "".join(
            f'<div style="flex:1;height:{max(4, (w / m) * height):.0f}px;background:#CFE9EC;border-radius:2px 2px 0 0"></div>'
            for w in weeks
        )
    return f'<div style="display:flex;gap:3px;align-items:flex-end;height:{height}px">{bars}</div>'


def message_chip(text: str, color: str) -> str:
    return (f'<div style="font-size:10px;padding:4px 8px;border-radius:5px;background:#F8FAFC;border:1px solid {SLATE_200};'
            f'border-left:2px solid {color};color:{INK_TEXT}">{text}</div>')


MEDIA_HEIGHT = {"vertical": "118px", "wide": "84px", "text": "76px", "square": "104px"}


def creative_card(cr: dict, big: bool = False) -> str:
    stage = cr.get("stage")
    stage_color = STAGE_COLOR.get(stage, MUTED)
    media_h = MEDIA_HEIGHT.get(cr.get("shape", "square"), "104px")
    if cr.get("image"):
        media = (f'<div style="position:relative;height:{media_h};overflow:hidden;border-bottom:1px solid {SLATE_200}">'
                  f'<img src="{cr["image"]}" style="width:100%;height:100%;object-fit:cover;display:block;" />')
    else:
        label = cr.get("why") or "no preview"
        media = (f'<div style="position:relative;height:{media_h};display:flex;align-items:center;justify-content:center;'
                  f'background:repeating-linear-gradient(135deg,{TRACK} 0 7px,#E4EAF1 7px 14px);border-bottom:1px solid {SLATE_200}">'
                  f'<div style="font-family:{MONO};font-size:9.5px;color:#5A6773;text-align:center;padding:0 10px;line-height:1.4">'
                  f'{cr.get("type") or "content"}</div>')
    if stage:
        media += (f'<div style="position:absolute;left:8px;top:8px;font-size:8.5px;font-weight:600;letter-spacing:.1em;'
                   f'color:#FFFFFF;background:{stage_color};border-radius:4px;padding:2px 6px">{stage}</div>')
    media += "</div>"
    eng_label = fmt_num(cr.get("engagement")) + " eng." if cr.get("engagement") is not None else "—"
    return (f'<div style="border:1px solid {SLATE_200};border-radius:10px;overflow:hidden;background:#FBFCFD">'
            f'{media}<div style="padding:{"12px 13px 13px" if big else "10px 11px 11px"}">'
            f'<div style="display:inline-block;font-size:9.5px;font-weight:600;letter-spacing:.06em;color:{SLATE_600};'
            f'background:#F1F5F9;border-radius:4px;padding:3px 7px">{cr.get("type") or "—"}</div>'
            f'<div style="font-size:{"11px" if big else "10.5px"};color:{INK_TEXT};line-height:1.4;margin-top:7px">{cr.get("why") or ""}</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:9px;font-size:9.5px;color:{MUTED};font-family:{MONO}">'
            f'<span>{eng_label}</span><span>{cr.get("date") or ""}</span></div></div></div>')


# ============================================================================
# DATA LOADERS
# ============================================================================
@st.cache_data(ttl=600)
def load_posts() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT p.id, p.competitor_id, p.instagram_post_id, p.post_url, p.post_type,
               p.posted_at, p.caption, p.media_url, p.like_count, p.comment_count,
               p.view_count, p.category, p.category_confidence, p.funnel_stage, p.scraped_at,
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


@st.cache_data(ttl=600)
def load_thumbnails(post_ids: tuple) -> dict:
    if not post_ids:
        return {}
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, thumbnail FROM posts WHERE id = ANY(%s)", (list(post_ids),))
        rows = cur.fetchall()
    return {pid: to_data_uri(t) for pid, t in rows if t}


def load_ig_thumbnail(post_id: int):
    return load_thumbnails((post_id,)).get(post_id)


@st.cache_data(ttl=600)
def load_last_run():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM scrape_runs ORDER BY run_date DESC LIMIT 1", conn)
    return df.iloc[0] if not df.empty else None


@st.cache_data(ttl=600)
def load_homepage_snapshots() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT h.id, h.competitor_id, h.captured_at, h.changed, h.theme, h.theme_confidence,
               h.funnel_stage, c.name AS competitor_name, c.is_own_brand
        FROM homepage_snapshots h
        JOIN competitors c ON c.id = h.competitor_id
        ORDER BY h.competitor_id, h.captured_at
        """,
        conn,
    )
    df["captured_at"] = pd.to_datetime(df["captured_at"])
    return df


@st.cache_data(ttl=600)
def load_screenshot(snapshot_id: int):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT screenshot FROM homepage_snapshots WHERE id = %s", (snapshot_id,))
        row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@st.cache_data(ttl=600)
def load_ads() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT a.id, a.competitor_id, a.ad_url, a.creative_type,
               a.creative_video IS NOT NULL AS has_video, a.caption, a.headline,
               a.platforms, a.start_date, a.end_date, a.is_active, a.category, a.funnel_stage,
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


@st.cache_data(ttl=600)
def load_ad_creative(ad_id: int):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT creative FROM ads WHERE id = %s", (ad_id,))
        row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@st.cache_data(ttl=600)
def load_ad_video(ad_id: int):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT creative_video FROM ads WHERE id = %s", (ad_id,))
        row = cur.fetchone()
    return row[0] if row and row[0] else None


@st.cache_data(ttl=600)
def load_tiktok() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT t.id, t.competitor_id, t.video_url, t.caption, t.posted_at, t.duration_seconds,
               t.view_count, t.like_count, t.comment_count, t.share_count, t.category, t.funnel_stage,
               c.name AS competitor_name, c.is_own_brand
        FROM tiktok_videos t
        JOIN competitors c ON c.id = t.competitor_id
        ORDER BY t.posted_at DESC
        """,
        conn,
    )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df


@st.cache_data(ttl=600)
def load_tiktok_thumbnail(video_id: int):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT thumbnail FROM tiktok_videos WHERE id = %s", (video_id,))
        row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@st.cache_data(ttl=600)
def load_youtube() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT y.id, y.competitor_id, y.video_url, y.title, y.caption, y.posted_at, y.duration,
               y.video_type, y.view_count, y.like_count, y.comment_count, y.category, y.funnel_stage,
               c.name AS competitor_name, c.is_own_brand
        FROM youtube_videos y
        JOIN competitors c ON c.id = y.competitor_id
        ORDER BY y.posted_at DESC
        """,
        conn,
    )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df


@st.cache_data(ttl=600)
def load_youtube_thumbnail(video_id: int):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT thumbnail FROM youtube_videos WHERE id = %s", (video_id,))
        row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@st.cache_data(ttl=600)
def load_x_posts() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT x.id, x.competitor_id, x.post_url, x.text, x.posted_at, x.like_count,
               x.retweet_count, x.reply_count, x.quote_count, x.view_count, x.is_retweet,
               x.category, x.funnel_stage, c.name AS competitor_name, c.is_own_brand
        FROM x_posts x
        JOIN competitors c ON c.id = x.competitor_id
        ORDER BY x.posted_at DESC
        """,
        conn,
    )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df


@st.cache_data(ttl=600)
def load_google_ads() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT g.id, g.competitor_id, g.advertiser_name, g.is_own_ad, g.search_term, g.ad_format,
               g.ad_url, g.first_shown, g.last_shown, g.approx_days_shown, g.is_active,
               g.funnel_stage, c.name AS competitor_name, c.is_own_brand
        FROM google_ads g
        JOIN competitors c ON c.id = g.competitor_id
        ORDER BY g.last_shown DESC
        """,
        conn,
    )
    df["first_shown"] = pd.to_datetime(df["first_shown"])
    df["last_shown"] = pd.to_datetime(df["last_shown"])
    return df


@st.cache_data(ttl=600)
def load_google_ad_creative(ad_id: int):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT creative FROM google_ads WHERE id = %s", (ad_id,))
        row = cur.fetchone()
    return to_data_uri(row[0]) if row and row[0] else None


@st.cache_data(ttl=600)
def load_competitor_groups() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql("SELECT competitor_id, group_name FROM competitor_groups", conn)


@st.cache_data(ttl=600)
def load_competitor_meta() -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(
        """SELECT id, name, instagram_handle, instagram_url, website_url, facebook_url,
                  tiktok_handle, youtube_url, x_handle, is_own_brand
           FROM competitors ORDER BY name""",
        conn,
    )


LOADERS = {
    "ig_thumb": load_ig_thumbnail, "tt_thumb": load_tiktok_thumbnail, "tt_embed": tiktok_embed_html,
    "yt_thumb": load_youtube_thumbnail, "ad_creative": load_ad_creative, "ad_video": load_ad_video,
    "gads_creative": load_google_ad_creative, "homepage_shot": load_screenshot,
}

# ============================================================================
# LOAD EVERYTHING (cached)
# ============================================================================
posts = load_posts()
homepages = load_homepage_snapshots()
ads = load_ads()
tiktok = load_tiktok()
youtube = load_youtube()
x_posts = load_x_posts()
google_ads = load_google_ads()
competitor_meta = load_competitor_meta()
groups_meta = load_competitor_groups().merge(competitor_meta[["id", "name"]], left_on="competitor_id", right_on="id")
last_run = load_last_run()

DATA = {"posts": posts, "homepages": homepages, "ads": ads, "tiktok": tiktok,
        "youtube": youtube, "x_posts": x_posts, "google_ads": google_ads}

if competitor_meta.empty:
    st.warning("No competitors in the database yet. Run `python -m scripts.init_db` first.")
    st.stop()


def brand_category(name: str) -> str:
    is_own = competitor_meta.loc[competitor_meta["name"] == name, "is_own_brand"].iloc[0]
    if is_own:
        return "Our Brands"
    own_groups = groups_meta.loc[groups_meta["name"] == name, "group_name"]
    non_own = [g for g in own_groups if g != "Our Brands"]
    return non_own[0] if non_own else (own_groups.iloc[0] if len(own_groups) else "Our Brands")


ALL_CATEGORIES = sorted(groups_meta["group_name"].unique())
ALL_BRAND_NAMES = sorted(competitor_meta["name"].unique(), key=lambda n: (
    not competitor_meta.loc[competitor_meta["name"] == n, "is_own_brand"].iloc[0], n
))


def brand_option_label(name: str) -> str:
    return f"{name} — {brand_category(name)}"


# ============================================================================
# NAVIGATION STATE — pending-nav pattern: button callbacks stash a request
# under a "_pending_*" key and rerun; Streamlit forbids writing directly to a
# widget's own session_state key after that widget has been instantiated in
# the same run, so the request is applied here, before any widget exists.
# ============================================================================
for _wkey, _pkey in [
    ("nav_screen", "_pending_screen"), ("nav_brand", "_pending_brand"),
    ("nav_channel", "_pending_channel"), ("nav_category", "_pending_category"),
    ("nav_compare", "_pending_compare"), ("viewing_channel", "_pending_viewing_channel"),
]:
    if _pkey in st.session_state:
        st.session_state[_wkey] = st.session_state.pop(_pkey)

if "nav_brand" not in st.session_state:
    st.session_state["nav_brand"] = ALL_BRAND_NAMES[0]
if "nav_compare" not in st.session_state:
    st.session_state["nav_compare"] = next((n for n in ALL_BRAND_NAMES if n != st.session_state["nav_brand"]), ALL_BRAND_NAMES[0])


def goto(screen: str, **kwargs):
    st.session_state["_pending_screen"] = screen
    st.session_state["_pending_viewing_channel"] = False
    for k, v in kwargs.items():
        st.session_state[f"_pending_{k}"] = v
    st.rerun()


def open_channel(channel_id: str):
    st.session_state["_pending_channel"] = channel_id
    st.session_state["_pending_viewing_channel"] = True
    st.rerun()


# ---- Header ----
st.markdown(
    f'<div style="display:flex;align-items:center;gap:9px;margin:2px 0 12px 4px">'
    f'<div style="width:9px;height:9px;border-radius:50%;background:{TEAL}"></div>'
    f'<div style="font-size:12.5px;font-weight:600;letter-spacing:.14em;color:{INK}">BRAND SIGNAL</div>'
    f'<div style="font-size:10px;color:{MUTED};letter-spacing:.1em;padding-left:8px;border-left:1px solid {SLATE_200}">'
    f'COMPETITIVE MARKETING INTELLIGENCE</div></div>',
    unsafe_allow_html=True,
)

with st.container(key="topnav"):
    nav_col, refresh_col = st.columns([5, 1])
    with nav_col:
        screen = st.pills(
            "nav", ["Landscape", "Brand", "Category", "Compare"],
            key="nav_screen", default="Landscape", label_visibility="collapsed",
        )
    with refresh_col:
        if st.button("🔄 Refresh", key="refresh_btn", width="stretch"):
            st.cache_data.clear()
            st.rerun()
screen = screen or "Landscape"
# "Channel" is a sub-view of Brand (reached by drilling into a channel row),
# not a tab of its own - nav_screen must always stay one of the 4 pill
# options above, so this is tracked as a separate boolean instead of a
# 5th screen value.
viewing_channel = screen == "Brand" and st.session_state.get("viewing_channel", False)

if last_run is not None:
    st.caption(f"Data current as of {last_run['run_date']:%b %d, %Y · %H:%M UTC} "
               f"· {last_run['run_type']} run · status: {last_run['status']}")


# ============================================================================
# SCREEN: LANDSCAPE — every category, every brand, See/Think/Do at a glance
# ============================================================================
if screen == "Landscape":
    cat_profiles = {c: sd.category_profile(c, sorted(groups_meta.loc[groups_meta["group_name"] == c, "name"].unique()), DATA)
                     for c in ALL_CATEGORIES}
    ours = cat_profiles.get("Our Brands")
    total_brands = len(ALL_BRAND_NAMES)
    see_sorted = sorted(cat_profiles.items(), key=lambda kv: kv[1]["mix"][0], reverse=True)
    do_sorted = sorted(cat_profiles.items(), key=lambda kv: kv[1]["mix"][2], reverse=True)

    col_head, col_legend = st.columns([2.2, 1])
    with col_head:
        st.markdown(
            f'<div class="bs-eyebrow">COMPETITIVE LANDSCAPE</div>'
            f'<h1 class="bs-h1">Who is buying attention, and who is buying intent</h1>'
            f'<p class="bs-body" style="margin-top:8px;max-width:760px">Every tracked brand scored across seven '
            f'channels. The bar is the share of that brand\'s output aimed at See, Think and Do. Click any brand '
            f'for its channel-by-channel evidence.</p>',
            unsafe_allow_html=True,
        )
    with col_legend:
        legend_html = "".join(
            f'<div style="display:flex;gap:7px;align-items:flex-start;margin-bottom:6px">'
            f'<div style="width:9px;height:9px;border-radius:2px;background:{s["color"]};margin-top:3px;flex:none"></div>'
            f'<div><div style="font-size:11px;font-weight:600">{s["name"]}</div>'
            f'<div style="font-size:10px;color:{MUTED};line-height:1.35">{s["desc"][:46]}</div></div></div>'
            for s in STAGES
        )
        st.markdown(legend_html, unsafe_allow_html=True)

    if ours and ours["mix"] != [0, 0, 0]:
        stat_cols = st.columns(4)
        stat_cols[0].markdown(stat_card("BRANDS TRACKED", str(total_brands),
                                         f"{len(ALL_CATEGORIES)} categories, {len(sd.CHANNELS)} channels each"), unsafe_allow_html=True)
        stat_cols[1].markdown(stat_card("OUR PORTFOLIO MIX", sd.mix_label(ours["mix"]), sd.verdict(ours["mix"]).lower()), unsafe_allow_html=True)
        top_see_name, top_see = see_sorted[0]
        stat_cols[2].markdown(stat_card("MOST SEE-WEIGHTED", f"{top_see['mix'][0]}%", f"{top_see_name} buys the most attention"), unsafe_allow_html=True)
        top_do_name, top_do = do_sorted[0]
        stat_cols[3].markdown(stat_card("MOST DO-WEIGHTED", f"{top_do['mix'][2]}%", f"{top_do_name} runs hardest at intent"), unsafe_allow_html=True)
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    for cat_name in ALL_CATEGORIES:
        cp = cat_profiles[cat_name]
        if not cp["profiles"]:
            continue
        with st.container(border=True):
            rail_col, mix_col, brands_col = st.columns([1.1, 1.0, 2.2])
            with rail_col:
                if st.button(cat_name, key=f"land_open_{cat_name}"):
                    goto("Category", category=cat_name)
                st.markdown(
                    f'<div style="font-size:11px;color:{MUTED};margin-top:-8px;line-height:1.35">{CATEGORY_NOTE.get(cat_name, "")}</div>'
                    + competes_badge(CATEGORY_COMPETES.get(cat_name, "read-across")),
                    unsafe_allow_html=True,
                )
            with mix_col:
                st.markdown(stage_bar(cp["mix"]) + mix_caption(cp["mix"]), unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:11.5px;color:{INK_TEXT};margin-top:7px;font-weight:500">{sd.verdict(cp["mix"])}</div>',
                            unsafe_allow_html=True)
                spread_note = f"See-share spread across brands: {cp['spread'][0]}pts"
                st.markdown(f'<div style="font-size:10.5px;color:{MUTED};margin-top:5px">{spread_note}</div>', unsafe_allow_html=True)
            with brands_col:
                sub_names = sorted(cp["profiles"], key=lambda p: -p["total_all_time"])[:6]
                mini_cols = st.columns(min(3, max(1, len(sub_names))))
                for i, p in enumerate(sub_names):
                    with mini_cols[i % len(mini_cols)]:
                        st.markdown(
                            f'<div style="font-size:11px;font-weight:500;line-height:1.25">{p["company"]}</div>'
                            + stage_bar(p["mix"], height=6, radius=3)
                            + f'<div style="font-size:9.5px;color:{MUTED};font-family:{MONO}">{fmt_num(p["monthly_output"])}/mo</div>',
                            unsafe_allow_html=True,
                        )
                        if st.button("open →", key=f"land_brand_{cat_name}_{p['company']}"):
                            goto("Brand", brand=p["company"])

# ============================================================================
# SCREEN: BRAND — one company, every channel, top to bottom
# ============================================================================
elif screen == "Brand":
    tcol, ccol = st.columns([2, 1])
    with tcol:
        st.markdown('<div class="bs-eyebrow" style="margin-bottom:4px">BRAND IN FOCUS</div>', unsafe_allow_html=True)
        chosen = st.selectbox("Brand", ALL_BRAND_NAMES, key="nav_brand",
                               format_func=brand_option_label, label_visibility="collapsed")
    brand = chosen
    profile = sd.company_profile(brand, DATA)
    cat_name = brand_category(brand)
    competes = CATEGORY_COMPETES.get(cat_name, "read-across")

    takeaway = (
        f"{brand} is {sd.verdict(profile['mix']).lower()}. Its heaviest channel is "
        f"{profile['lead']['channel']['name']}, and {profile['active_channels']} of {len(sd.CHANNELS)} "
        f"channels are in active use"
        + (f" — message consistency across them scores {profile['consistency']}/100." if profile["consistency"] is not None else ".")
    )

    st.markdown(
        f'<div class="bs-ink-panel" style="margin-bottom:16px">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:30px;flex-wrap:wrap">'
        f'<div style="flex:1 1 330px;min-width:280px">'
        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:9px">'
        f'<div style="font-size:9.5px;letter-spacing:.15em;color:{TEAL};font-weight:600">{cat_name.upper()}</div>'
        f'{competes_badge(competes, on_dark=True)}</div>'
        f'<h1 style="margin:0;font-size:31px;font-weight:600;letter-spacing:-.022em">{brand}</h1>'
        f'<p style="margin:10px 0 0;font-size:13px;color:#C7CED9;max-width:620px;line-height:1.5">{takeaway}</p></div>'
        f'<div style="display:flex;gap:26px;flex:none;align-items:flex-start;flex-wrap:wrap">'
        + "".join(
            f'<div><div style="font-size:9.5px;letter-spacing:.12em;color:{SLATE_400};font-weight:600">{lbl}</div>'
            f'<div style="font-size:23px;font-weight:600;margin-top:5px">{val}</div>'
            f'<div style="font-size:10.5px;color:{SLATE_400}">{note}</div></div>'
            for lbl, val, note in [
                ("TRACKED OUTPUT", fmt_num(profile["monthly_output"]), "items / month"),
                ("ACTIVE CHANNELS", f"{profile['active_channels']}/{len(sd.CHANNELS)}", "of channels tracked"),
                ("CONSISTENCY", str(profile["consistency"]) if profile["consistency"] is not None else "—", "same story across channels"),
            ]
        )
        + f'<div style="width:190px"><div style="font-size:9.5px;letter-spacing:.12em;color:{SLATE_400};font-weight:600;margin-bottom:8px">PORTFOLIO MIX</div>'
        + stage_bar(profile["mix"], height=12).replace(f'background:{TRACK}', 'background:rgba(255,255,255,.12)')
        + f'<div style="font-size:10.5px;color:{SLATE_400};margin-top:7px;font-family:{MONO}">{sd.mix_label(profile["mix"])}  see/think/do</div></div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    action_cols = st.columns([1.4, 1, 1.6, 1])
    with action_cols[0]:
        if st.button(f"View {cat_name} rollup →", key="open_cat_from_brand"):
            goto("Category", category=cat_name)
    with action_cols[2]:
        compare_target = st.selectbox("Compare with", [n for n in ALL_BRAND_NAMES if n != brand],
                                       key="nav_compare", label_visibility="collapsed")
    with action_cols[3]:
        if st.button("Open comparison", key="open_compare_from_brand"):
            goto("Compare")

    if not viewing_channel:
        # ---- Channel summary table ----
        st.markdown('<div class="bs-card" style="padding:0;overflow:hidden;margin-bottom:22px">', unsafe_allow_html=True)
        st.markdown(
            f'<div style="padding:15px 18px 13px;border-bottom:1px solid {ROW_LINE}">'
            f'<div style="font-size:13px;font-weight:600">Channel summary</div>'
            f'<div style="font-size:11px;color:{MUTED};margin-top:3px">Scale of use, See/Think/Do split, and the '
            f'message being carried in each stage.</div></div>',
            unsafe_allow_html=True,
        )
        for r in profile["rows"]:
            ch = r["channel"]
            with st.container(border=True):
                name_col, vol_col, mix_col, msg_col, eng_col = st.columns([1.3, 1.1, 1.4, 2.4, 0.9])
                with name_col:
                    if st.button(ch["name"], key=f"open_ch_{ch['id']}"):
                        open_channel(ch["id"])
                    st.markdown(paid_tag(ch["paid"]), unsafe_allow_html=True)
                with vol_col:
                    st.markdown(f'<div style="font-size:17px;font-weight:600">{r["volume"]}</div>'
                                f'<div style="font-size:9.5px;color:{MUTED}">{ch["unit"]} / 90d</div>', unsafe_allow_html=True)
                    st.markdown(trend_html(r["trend"]), unsafe_allow_html=True)
                with mix_col:
                    st.markdown(stage_bar(r["split"]) + mix_caption(r["split"]), unsafe_allow_html=True)
                with msg_col:
                    stage_html = ""
                    for s in STAGES:
                        msgs = r["messages"].get(s["name"], [])
                        stage_html += (f'<div style="display:inline-block;width:32%;vertical-align:top;margin-right:1%">'
                                       f'<div style="font-size:9px;font-weight:600;letter-spacing:.06em;color:{SLATE_600}">{s["name"].upper()}</div>')
                        if msgs:
                            for m in msgs:
                                stage_html += f'<div style="font-size:10px;color:{INK_TEXT};line-height:1.35;margin-top:3px">{m}</div>'
                        else:
                            stage_html += f'<div style="font-size:10px;color:{MUTED};font-style:italic;margin-top:3px">no examples yet</div>'
                        stage_html += "</div>"
                    st.markdown(stage_html, unsafe_allow_html=True)
                with eng_col:
                    eng_label = fmt_num(r["engagement"]) if r["engagement"] is not None else "—"
                    st.markdown(f'<div style="text-align:right;font-size:15px;font-weight:600">{eng_label}</div>'
                                f'<div style="text-align:right;font-size:9.5px;color:{MUTED}">avg. engagement</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # ---- Per-channel sections: content types, cadence, creative evidence ----
        for r in profile["rows"]:
            ch = r["channel"]
            if r["total_all_time"] == 0:
                continue
            with st.container(border=True):
                top_lbl, top_bar = st.columns([3, 1.4])
                with top_lbl:
                    st.markdown(f'<h2 style="margin:0;font-size:18px;font-weight:600">{ch["name"]}</h2>' + paid_tag(ch["paid"]),
                                unsafe_allow_html=True)
                    top_ct = max(r["content_types"], key=lambda c: c["pct"])["name"].lower() if r["content_types"] else "unclassified content"
                    takeaway_ch = (f'{r["split"][sd.dominant_idx(r["split"])]}% {sd.dominant_word(r["split"]).replace("-led","")}. '
                                    f'Led by {top_ct} ({r["volume"]} in the last 90 days).')
                    st.markdown(read_line(takeaway_ch), unsafe_allow_html=True)
                with top_bar:
                    st.markdown(stage_bar(r["split"]) + mix_caption(r["split"]), unsafe_allow_html=True)

                left, right = st.columns([1, 2.2])
                with left:
                    st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600;margin-bottom:10px">CONTENT TYPES</div>', unsafe_allow_html=True)
                    st.markdown(content_type_bars(r["content_types"]), unsafe_allow_html=True)
                    st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600;margin:14px 0 6px">CADENCE · 12 WEEKS</div>', unsafe_allow_html=True)
                    st.markdown(cadence_sparkline(r["weeks"]), unsafe_allow_html=True)
                with right:
                    st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600;margin-bottom:10px">CREATIVE EVIDENCE</div>', unsafe_allow_html=True)
                    creatives = sd.creative_rows(brand, ch["id"], DATA, 4, LOADERS)
                    if not creatives:
                        st.markdown(f'<div style="font-size:11px;color:{MUTED};font-style:italic">Nothing captured on this channel yet.</div>', unsafe_allow_html=True)
                    else:
                        cr_cols = st.columns(len(creatives))
                        for i, cr in enumerate(creatives):
                            with cr_cols[i]:
                                st.markdown(creative_card(cr), unsafe_allow_html=True)
                                if cr.get("video_url") or cr.get("embed_html"):
                                    with st.expander("▶ Play"):
                                        if cr.get("embed_html"):
                                            st.components.v1.html(cr["embed_html"], height=500)
                                        else:
                                            st.video(cr["video_url"])
                                if cr.get("link"):
                                    st.link_button("Open", cr["link"], width="stretch")

    else:  # Channel drill-down
        channel_id = st.session_state.get("nav_channel") or sd.CHANNELS[0]["id"]
        r = sd.channel_data(brand, channel_id, DATA)
        ch = r["channel"]
        st.markdown(f'<span style="font-size:11px;color:{MUTED}">/ '
                    f'<a href="#" onclick="return false">{brand}</a> / <b style="color:{INK_TEXT}">{ch["name"]}</b></span>', unsafe_allow_html=True)
        if st.button("← back to all channels", key="back_to_brand"):
            goto("Brand")

        head_col, side_col = st.columns([1.6, 1])
        with head_col:
            st.markdown('<div class="bs-card">', unsafe_allow_html=True)
            st.markdown(f'<div style="display:flex;align-items:center;gap:10px">'
                        f'<h1 style="margin:0;font-size:26px;font-weight:600">{ch["name"]}</h1>{paid_tag(ch["paid"])}</div>'
                        f'<div style="font-size:12px;color:{SLATE_600};margin-top:6px">{brand} · {cat_name} · last 90 days</div>',
                        unsafe_allow_html=True)
            top_ct = max(r["content_types"], key=lambda c: c["pct"])["name"].lower() if r["content_types"] else "unclassified content"
            st.markdown(read_line(f'{r["split"][sd.dominant_idx(r["split"])]}% {sd.dominant_word(r["split"]).replace("-led","")}. '
                                    f'Led by {top_ct} ({r["volume"]} in the last 90 days).'), unsafe_allow_html=True)
            stage_cols = st.columns(3)
            for i, s in enumerate(STAGES):
                with stage_cols[i]:
                    msgs = r["messages"].get(s["name"], [])
                    msg_html = "".join(
                        f'<div style="font-size:11px;color:{INK_TEXT};line-height:1.4;padding:7px 9px;background:#FFFFFF;'
                        f'border:1px solid {SLATE_200};border-radius:7px;margin-top:6px">{m}</div>' for m in msgs
                    ) or f'<div style="font-size:10.5px;color:{MUTED};font-style:italic;margin-top:6px">no examples yet</div>'
                    st.markdown(
                        f'<div style="background:#FAFBFC;border:1px solid {SLATE_200};border-top:3px solid {s["color"]};'
                        f'border-radius:10px;padding:14px 15px">'
                        f'<div style="display:flex;align-items:center;justify-content:space-between">'
                        f'<div style="font-size:10px;font-weight:600;letter-spacing:.1em;color:{SLATE_600}">{s["name"].upper()}</div>'
                        f'<div style="font-size:22px;font-weight:600;color:{s["color"]}">{r["split"][i]}%</div></div>{msg_html}</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown('</div>', unsafe_allow_html=True)
        with side_col:
            st.markdown('<div class="bs-card">', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600">SCALE OF USE</div>'
                        f'<div style="display:flex;align-items:baseline;gap:6px;margin-top:6px">'
                        f'<div style="font-size:30px;font-weight:600">{r["volume"]}</div><div style="font-size:11px;color:{MUTED}">{ch["unit"]}</div></div>',
                        unsafe_allow_html=True)
            st.markdown(trend_html(r["trend"]), unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600;margin:16px 0 8px">CADENCE · 12 WEEKS</div>', unsafe_allow_html=True)
            st.markdown(cadence_sparkline(r["weeks"], height=56), unsafe_allow_html=True)
            eng_label = fmt_num(r["engagement"]) if r["engagement"] is not None else "—"
            st.markdown(f'<div style="display:flex;gap:20px;margin-top:16px">'
                        f'<div><div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600">AVG. ENGAGEMENT</div>'
                        f'<div style="font-size:19px;font-weight:600;margin-top:4px">{eng_label}</div></div></div>',
                        unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600;margin:16px 0 9px">CONTENT TYPES</div>', unsafe_allow_html=True)
            st.markdown(content_type_bars(r["content_types"]), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(f'<div style="font-size:14px;font-weight:600;margin:18px 0 3px">Every piece of creative we captured</div>'
                    f'<div style="font-size:11px;color:{MUTED};margin-bottom:14px">Tags are our read of the stage, the content type, and the caption itself.</div>',
                    unsafe_allow_html=True)
        creatives = sd.creative_rows(brand, channel_id, DATA, 8, LOADERS)
        if not creatives:
            st.markdown(f'<div style="font-size:12px;color:{MUTED};font-style:italic">Nothing captured on this channel yet.</div>', unsafe_allow_html=True)
        else:
            n_cols = 4
            for row_start in range(0, len(creatives), n_cols):
                row_items = creatives[row_start:row_start + n_cols]
                cols = st.columns(n_cols)
                for i, cr in enumerate(row_items):
                    with cols[i]:
                        st.markdown(creative_card(cr, big=True), unsafe_allow_html=True)
                        if cr.get("video_url") or cr.get("embed_html"):
                            with st.expander("▶ Play"):
                                if cr.get("embed_html"):
                                    st.components.v1.html(cr["embed_html"], height=500)
                                else:
                                    st.video(cr["video_url"])
                        if cr.get("link"):
                            st.link_button("Open", cr["link"], width="stretch")

# ============================================================================
# SCREEN: CATEGORY — one competitive set, every brand in it
# ============================================================================
elif screen == "Category":
    with st.container(key="catchips"):
        chosen_cat = st.pills("Category", ALL_CATEGORIES, key="nav_category",
                               default=ALL_CATEGORIES[0], label_visibility="collapsed")
    category = chosen_cat or ALL_CATEGORIES[0]
    brand_names = sorted(groups_meta.loc[groups_meta["group_name"] == category, "name"].unique())
    cp = sd.category_profile(category, brand_names, DATA)
    competes = CATEGORY_COMPETES.get(category, "read-across")
    spread_max = max(cp["spread"]) if cp["spread"] else 0
    consensus = "Fragmented" if spread_max > 34 else ("Loose" if spread_max > 20 else "Tight")
    if spread_max > 34:
        spread_note = "There is no shared playbook here: brands disagree sharply on where to spend attention."
    elif spread_max > 20:
        spread_note = "Most brands cluster, but a few run a materially different plan."
    else:
        spread_note = "Brands here behave almost identically, so differentiation has to come from the message, not the mix."
    takeaway = (f"The category averages {sd.mix_label(cp['mix'])} across See, Think and Do — "
                f"{sd.verdict(cp['mix']).lower()}. {spread_note}")

    head_col, out_col = st.columns([1.7, 1])
    with head_col:
        st.markdown('<div class="bs-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="bs-eyebrow">CATEGORY ROLLUP</div>'
                    f'<h1 style="margin:8px 0 0;font-size:28px;font-weight:600">{category}</h1>'
                    f'<div style="font-size:12px;color:{MUTED};margin-top:5px">{CATEGORY_NOTE.get(category,"")} · {len(cp["profiles"])} brands tracked</div>',
                    unsafe_allow_html=True)
        st.markdown(read_line(takeaway), unsafe_allow_html=True)
        mix_c, cons_c = st.columns(2)
        with mix_c:
            st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600;margin-bottom:8px">CATEGORY AVERAGE MIX</div>'
                        + stage_bar(cp["mix"], height=13, radius=7) + mix_caption(cp["mix"]), unsafe_allow_html=True)
        with cons_c:
            st.markdown(f'<div style="font-size:9.5px;letter-spacing:.12em;color:{MUTED};font-weight:600">CONSENSUS</div>'
                        f'<div style="font-size:22px;font-weight:600;margin-top:4px;color:{DEEP_TEAL}">{consensus}</div>'
                        f'<div style="font-size:10.5px;color:{MUTED};line-height:1.4">Widest gap between brands on any single stage is {spread_max} points.</div>',
                        unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with out_col:
        st.markdown(f'<div class="bs-ink-panel" style="padding:20px 21px">'
                    f'<div style="font-size:9.5px;letter-spacing:.13em;color:{TEAL};font-weight:600;margin-bottom:12px">OUTLIERS IN THIS CATEGORY</div>',
                    unsafe_allow_html=True)
        for o in cp["outliers"]:
            st.markdown(
                f'<div style="padding:13px 0;border-top:1px solid #253039">'
                f'<div style="display:flex;justify-content:space-between;gap:10px"><div style="font-size:13px;font-weight:600">{o["company"]}</div>'
                f'<div style="font-size:10px;color:{SLATE_400};font-family:{MONO}">{sd.mix_label(o["mix"])}</div></div>'
                + stage_bar(o["mix"], height=8, radius=4)
                + f'<div style="font-size:10.5px;color:#C7CED9;line-height:1.4;margin-top:7px">Runs {sd.dominant_word(o["mix"]).lower()} against a category average of {sd.mix_label(cp["mix"])}.</div></div>',
                unsafe_allow_html=True,
            )
            if st.button(f"Open {o['company']} →", key=f"cat_outlier_{o['company']}"):
                goto("Brand", brand=o["company"])
        if not cp["outliers"]:
            st.markdown(f'<div style="font-size:11px;color:{SLATE_400};font-style:italic">Not enough data yet to flag an outlier.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="bs-card" style="margin-top:14px">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:13px;font-weight:600;margin-bottom:3px">Brand by brand</div>'
                f'<div style="font-size:11px;color:{MUTED};margin-bottom:16px">Small multiples, sorted by See-weight. Wide spread means the category has no shared playbook.</div>',
                unsafe_allow_html=True)
    members = sorted(cp["profiles"], key=lambda p: -p["mix"][0])
    n_cols = 4
    for row_start in range(0, len(members), n_cols):
        row_items = members[row_start:row_start + n_cols]
        cols = st.columns(n_cols)
        for i, m in enumerate(row_items):
            with cols[i]:
                is_out = any(o["company"] == m["company"] for o in cp["outliers"])
                is_focus = m["company"] == st.session_state["nav_brand"]
                flag = "BRAND IN FOCUS" if is_focus else ("OUTLIER" if is_out else "IN LINE")
                flag_color = DEEP_TEAL if is_focus else (AMBER if is_out else SLATE_600)
                flag_bg = "#EAF6F8" if is_focus else ("#FEF6E7" if is_out else "#F1F5F9")
                with st.container(border=True):
                    st.markdown(
                        f'<div style="display:flex;justify-content:space-between;gap:8px">'
                        f'<div style="font-size:12px;font-weight:600;line-height:1.25">{m["company"]}</div>'
                        f'<div style="font-size:8.5px;font-weight:600;letter-spacing:.09em;padding:2px 5px;border-radius:4px;'
                        f'color:{"#FFFFFF" if is_focus else flag_color};background:{DEEP_TEAL if is_focus else flag_bg}">{flag}</div></div>'
                        + stage_bar(m["mix"], height=9, radius=5) + mix_caption(m["mix"], "")
                        + f'<div style="display:flex;justify-content:space-between;margin-top:10px;padding-top:9px;border-top:1px solid {ROW_LINE};'
                        f'font-size:10px;color:{SLATE_600}"><span>{fmt_num(m["monthly_output"])}/mo</span>'
                        f'<span>{m["active_channels"]}/{len(sd.CHANNELS)} channels</span></div>'
                        f'<div style="font-size:10.5px;color:{INK_TEXT};margin-top:8px;line-height:1.4">{sd.verdict(m["mix"])}</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button("Open →", key=f"cat_member_{category}_{m['company']}"):
                        goto("Brand", brand=m["company"])
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="bs-card" style="margin-top:14px">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:13px;font-weight:600;margin-bottom:3px">Channel behaviour across the category</div>'
                f'<div style="font-size:11px;color:{MUTED};margin-bottom:14px">Average scale of use and stage weighting per channel, with the messages that recur most.</div>',
                unsafe_allow_html=True)
    for ch in sd.CHANNELS:
        rs = [sd.channel_data(n, ch["id"], DATA) for n in brand_names]
        rs_active = [r for r in rs if r["total_all_time"] > 0]
        if not rs_active:
            continue
        avg_vol = round(sum(r["volume"] for r in rs_active) / len(rs_active))
        mix = [round(sum(r["split"][i] for r in rs_active) / len(rs_active)) for i in range(3)]
        mix[2] = 100 - mix[0] - mix[1]
        seen_msgs, msgs = set(), []
        for r in rs_active:
            for s in STAGES:
                for m in r["messages"].get(s["name"], []):
                    if m not in seen_msgs:
                        seen_msgs.add(m)
                        msgs.append((m, s["color"]))
        with st.container(border=True):
            name_c, vol_c, mix_c, msg_c = st.columns([1.1, 0.9, 1.2, 2.6])
            name_c.markdown(f'<div style="font-size:12px;font-weight:600">{ch["name"]}</div>', unsafe_allow_html=True)
            vol_c.markdown(f'<div style="font-size:16px;font-weight:600">{avg_vol}</div><div style="font-size:9.5px;color:{MUTED}">{ch["unit"]}</div>', unsafe_allow_html=True)
            mix_c.markdown(stage_bar(mix) + mix_caption(mix, ""), unsafe_allow_html=True)
            msg_c.markdown("".join(message_chip(m, c) for m, c in msgs[:5]) or f'<span style="font-size:10px;color:{MUTED};font-style:italic">no examples yet</span>',
                            unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# SCREEN: COMPARE — two brands, head to head
# ============================================================================
else:  # Compare
    a_col, vs_col, b_col = st.columns([2, 0.6, 2])
    with a_col:
        st.markdown(f'<div style="font-size:10px;letter-spacing:.15em;color:{TEAL_700};font-weight:600">SIDE A · BRAND IN FOCUS</div>', unsafe_allow_html=True)
        brand_a = st.selectbox("Side A", ALL_BRAND_NAMES, key="nav_brand", label_visibility="collapsed")
    with vs_col:
        st.markdown(f'<div style="text-align:center;font-size:10px;letter-spacing:.15em;color:{MUTED};font-weight:600;padding-top:10px">VS</div>', unsafe_allow_html=True)
    with b_col:
        st.markdown(f'<div style="font-size:10px;letter-spacing:.15em;color:{MUTED};font-weight:600">SIDE B</div>', unsafe_allow_html=True)
        options_b = [n for n in ALL_BRAND_NAMES if n != brand_a]
        if st.session_state.get("nav_compare") not in options_b:
            st.session_state["nav_compare"] = options_b[0]
        brand_b = st.selectbox("Side B", options_b, key="nav_compare", label_visibility="collapsed")

    pa, pb = sd.company_profile(brand_a, DATA), sd.company_profile(brand_b, DATA)
    head_cols = st.columns(2)
    for i, (p, brand_name) in enumerate([(pa, brand_a), (pb, brand_b)]):
        with head_cols[i]:
            dark = i == 0
            bg = INK if dark else SURFACE
            text_color = "#FFFFFF" if dark else INK_TEXT
            sub_color = SLATE_400 if dark else MUTED
            body_color = "#C7CED9" if dark else SLATE_600
            cat_color = TEAL if dark else TEAL_700
            border = "" if dark else f"border:1px solid {SLATE_200};"
            st.markdown(
                f'<div style="background:{bg};color:{text_color};{border}border-radius:12px;padding:22px 24px">'
                f'<div style="font-size:9.5px;letter-spacing:.13em;font-weight:600;color:{cat_color}">{brand_category(brand_name).upper()}</div>'
                f'<h2 style="margin:7px 0 0;font-size:23px;font-weight:600">{brand_name}</h2>'
                + stage_bar(p["mix"], height=12).replace(f'background:{TRACK}', f'background:{"rgba(255,255,255,.12)" if dark else TRACK}')
                + f'<div style="font-size:10.5px;font-family:{MONO};color:{sub_color};margin-top:8px">{sd.mix_label(p["mix"])}  see/think/do</div>'
                + '<div style="display:flex;gap:24px;margin-top:16px">'
                + "".join(
                    f'<div><div style="font-size:9px;letter-spacing:.12em;font-weight:600;color:{sub_color}">{lbl}</div>'
                    f'<div style="font-size:18px;font-weight:600;margin-top:3px">{val}</div></div>'
                    for lbl, val in [
                        ("OUTPUT / MO", fmt_num(p["monthly_output"])),
                        ("CHANNELS", f"{p['active_channels']}/{len(sd.CHANNELS)}"),
                        ("CONSISTENCY", str(p["consistency"]) if p["consistency"] is not None else "—"),
                    ]
                )
                + f'</div><div style="font-size:11.5px;line-height:1.45;margin-top:15px;color:{body_color}">'
                  f'{sd.verdict(p["mix"])}. Heaviest channel: {p["lead"]["channel"]["name"]}.</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="bs-card" style="margin-top:14px">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:13px;font-weight:600;margin-bottom:3px">Where they diverge</div>'
                f'<div style="font-size:11px;color:{MUTED};margin-bottom:16px">Channel by channel: scale of use, stage weighting, and the gap worth acting on.</div>',
                unsafe_allow_html=True)
    for ch in sd.CHANNELS:
        ra, rb = sd.channel_data(brand_a, ch["id"], DATA), sd.channel_data(brand_b, ch["id"], DATA)
        if ra["total_all_time"] == 0 and rb["total_all_time"] == 0:
            continue
        d_vol = ra["volume"] - rb["volume"]
        d_see, d_do = ra["split"][0] - rb["split"][0], ra["split"][2] - rb["split"][2]
        big = abs(d_see) >= abs(d_do)
        if abs(d_vol) < 3 and abs(d_see) < 6 and abs(d_do) < 6:
            gap = "Effectively the same play — no advantage either way."
        else:
            diff = d_see if big else d_do
            gap = (f"{brand_a} runs {abs(d_vol)} {'more' if d_vol >= 0 else 'fewer'} {ch['unit']} and is "
                   f"{abs(diff)}pts {'heavier' if diff >= 0 else 'lighter'} on {'See' if big else 'Do'}.")
        with st.container(border=True):
            name_c, a_c, b_c, gap_c = st.columns([0.9, 1.3, 1.3, 1.7])
            name_c.markdown(f'<div style="font-size:12px;font-weight:600">{ch["name"]}</div>', unsafe_allow_html=True)
            for col, r in [(a_c, ra), (b_c, rb)]:
                col.markdown(
                    f'<div style="display:flex;align-items:baseline;gap:5px;margin-bottom:6px">'
                    f'<div style="font-size:15px;font-weight:600">{r["volume"]}</div><div style="font-size:9.5px;color:{MUTED}">{ch["unit"]}</div></div>'
                    + stage_bar(r["split"], height=9, radius=5) + mix_caption(r["split"], ""),
                    unsafe_allow_html=True,
                )
            gap_c.markdown(f'<div style="font-size:11px;line-height:1.4;color:{INK_TEXT}">{gap}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown(
    f'<div style="margin-top:28px;padding-top:16px;border-top:1px solid {SLATE_200};display:flex;'
    f'justify-content:space-between;font-size:10px;color:{SLATE_400};flex-wrap:wrap;gap:6px">'
    f'<div>Brand Signal · competitive marketing intelligence</div>'
    f'<div>All figures are computed from tracked data; channels with no captured content show "—" rather than an estimate.</div></div>',
    unsafe_allow_html=True,
)
