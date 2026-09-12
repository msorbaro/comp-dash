"""Competitor Research Dashboard — Streamlit app.

Reads ONLY from the database (never scrapes live). Run with:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# Streamlit runs this script with only its own directory on sys.path, so the
# project root (containing the `db` package) needs to be added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base64

import pandas as pd
import plotly.express as px
import streamlit as st

from categorize.funnel_taxonomy import FUNNEL_DEFINITIONS
from db.connection import get_conn

st.set_page_config(page_title="Competitor Research Dashboard", layout="wide", page_icon="📊")

# ============================================================================
# DESIGN SYSTEM
# Fixed categorical order (validated: adjacent-pair CVD-safe) - one color per
# platform, used consistently everywhere that platform appears (charts,
# section headers, borders) so the eye learns "blue = Instagram" once.
# Chrome (nav, hero, cards, chips) is themed separately below, sampled from
# the Mavis HBS deck's teal/navy brand palette - the two systems are kept
# independent so restyling the chrome never touches data-color safety.
# ============================================================================
PLATFORM = {
    "Instagram":   {"icon": "📸", "color": "#2a78d6"},
    "Website":     {"icon": "🌐", "color": "#eb6834"},
    "Ads":         {"icon": "📣", "color": "#1baf7a"},
    "TikTok":      {"icon": "🎵", "color": "#eda100"},
    "YouTube":     {"icon": "▶️", "color": "#e87ba4"},
    "X":           {"icon": "𝕏", "color": "#008300"},
    "Google Ads":  {"icon": "🔍", "color": "#4a3aa7"},
}
INK_PRIMARY = "#0f2c30"
INK_SECONDARY = "#4f6266"
INK_MUTED = "#8ba0a4"
GRIDLINE = "#e3edee"
SURFACE = "#ffffff"
PAGE_PLANE = "#f4f9f9"
BORDER = "rgba(15,44,48,0.10)"
EMPHASIS_GRAY = "#c7d3d4"

FUNNEL_COLORS = {"See": "#2a78d6", "Think": "#eda100", "Do": "#e34948"}

# ---- Brand chrome tokens (sampled from the Mavis HBS deck) ----
TEAL_900 = "#0b3b40"   # hero gradient - dark end
TEAL_700 = "#137079"   # hero gradient - mid
TEAL_500 = "#1fb6c4"   # bright accent - active pill, links, rules
TEAL_100 = "#d9f1f3"   # pale accent - pill fills, hover backgrounds
CARD_BG = "#f4f8f8"
DIVIDER = "#e2e9ea"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}
    h1, h2, h3, .ds-hero-title, .brand-title, [data-testid="stMetricValue"] {{
        font-family: 'Poppins', sans-serif;
    }}

    .block-container {{ padding-top: 1.2rem; max-width: 1280px; }}

    /* ---- Hero banner ---- */
    .ds-hero {{
        position: relative; overflow: hidden; border-radius: 18px;
        padding: 2.1rem 2.4rem; margin-bottom: 1.1rem;
        background: linear-gradient(115deg, {TEAL_900} 0%, {TEAL_700} 60%, {TEAL_500} 130%);
        background-image:
            radial-gradient(rgba(255,255,255,0.16) 1.4px, transparent 1.4px),
            linear-gradient(115deg, {TEAL_900} 0%, {TEAL_700} 60%, {TEAL_500} 130%);
        background-size: 16px 16px, 100% 100%;
        background-position: right -10px top -10px, 0 0;
    }}
    .ds-hero-inner {{ position: relative; z-index: 1; max-width: 720px; }}
    .ds-eyebrow-pill {{
        display: inline-flex; align-items: center; gap: 0.4rem;
        background: rgba(255,255,255,0.14); color: #eafcfd;
        border: 1px solid rgba(255,255,255,0.28);
        padding: 0.28rem 0.85rem; border-radius: 999px;
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
        text-transform: uppercase; margin-bottom: 0.9rem;
    }}
    .ds-hero-title {{
        color: #ffffff; font-size: 2.1rem; font-weight: 800; margin: 0 0 0.35rem 0;
        line-height: 1.15;
    }}
    .ds-hero-sub {{ color: rgba(255,255,255,0.82); font-size: 0.95rem; margin: 0; }}

    /* ---- Top nav toolbar (Scope / View / context selectors) ---- */
    .ds-toolbar {{
        background: {SURFACE}; border: 1px solid {DIVIDER}; border-radius: 14px;
        padding: 0.9rem 1.1rem 0.3rem 1.1rem; margin-bottom: 1.1rem;
    }}
    .ds-nav-label {{
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.09em;
        text-transform: uppercase; color: {TEAL_500}; margin: 0 0 0.35rem 0.1rem;
    }}
    div[data-testid="stPills"] label p {{
        font-size: 0.68rem; font-weight: 700; letter-spacing: 0.09em;
        text-transform: uppercase; color: {TEAL_500} !important;
    }}
    div[data-testid="stPills"] button {{
        font-family: 'Inter', sans-serif; font-weight: 600; border-radius: 999px !important;
    }}

    /* ---- Active-view strip (--accent set per-page inline) ---- */
    .ds-active-strip {{
        display: flex; align-items: center; gap: 0.55rem;
        background: {PAGE_PLANE};
        background: color-mix(in srgb, var(--accent) 12%, white);
        border-left: 4px solid var(--accent);
        padding: 0.55rem 1rem; border-radius: 8px; margin-bottom: 1.2rem;
        font-family: 'Poppins', sans-serif; font-weight: 700; font-size: 0.95rem;
        color: {INK_PRIMARY};
    }}
    .ds-active-strip .tag {{
        font-size: 0.65rem; font-weight: 700; letter-spacing: 0.08em;
        color: var(--accent); text-transform: uppercase; margin-right: 0.15rem;
    }}

    [data-testid="stMetricValue"] {{ font-size: 1.65rem; color: {INK_PRIMARY}; }}
    [data-testid="stMetric"] {{
        background: {SURFACE};
        border: 1px solid {DIVIDER};
        border-top: 3px solid {TEAL_500};
        border-radius: 10px;
        padding: 0.9rem 1rem 0.6rem 1rem;
    }}

    /* ---- Section headers: eyebrow rule + bold title, deck-style ---- */
    .section-header {{
        display: flex; align-items: center; gap: 0.55rem;
        margin: 2.3rem 0 1rem 0;
    }}
    .section-header .rule {{ flex: none; width: 46px; height: 3px; background: var(--accent); border-radius: 2px; }}
    .section-header .rule-tail {{ flex: 1; height: 1px; background: {DIVIDER}; margin-left: 0.6rem; }}
    .section-header .icon {{ font-size: 1.3rem; }}
    .section-header .title {{
        font-family: 'Poppins', sans-serif; font-size: 1.2rem; font-weight: 700; color: {INK_PRIMARY};
    }}

    .brand-header {{
        padding: 1.2rem 1.5rem; border-radius: 14px; margin-bottom: 1.1rem;
        background: {CARD_BG}; border: 1px solid {DIVIDER};
    }}
    .brand-title {{ font-size: 1.7rem; font-weight: 800; color: {INK_PRIMARY}; }}
    .badge {{
        display: inline-block; padding: 0.18rem 0.65rem; border-radius: 999px;
        font-size: 0.7rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
        margin-left: 0.6rem; vertical-align: middle;
    }}
    .badge-own {{ background: {TEAL_100}; color: {TEAL_700}; }}
    .badge-competitor {{ background: #eef2f2; color: {INK_SECONDARY}; }}
    .empty-note {{ color: {INK_MUTED}; font-style: italic; padding: 0.5rem 0 1.2rem 0; }}
    .card-caption {{ color: {INK_SECONDARY}; font-size: 0.82rem; line-height: 1.3;
                      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                      overflow: hidden; margin: 0.3rem 0; }}
    .card-meta {{ color: {INK_MUTED}; font-size: 0.76rem; }}

    /* ---- Card galleries: rounded, lift-on-hover ---- */
    [data-testid="stVerticalBlockBorderWrapper"] {{
        border-radius: 12px !important;
        transition: box-shadow 0.15s ease, transform 0.15s ease;
    }}
    [data-testid="stVerticalBlockBorderWrapper"]:hover {{
        box-shadow: 0 6px 18px rgba(15,44,48,0.10);
        transform: translateY(-2px);
    }}

    /* ---- Buttons as pill chips ---- */
    .stButton button, .stLinkButton a {{
        border-radius: 999px !important; font-weight: 600;
    }}
</style>
""", unsafe_allow_html=True)


def section_header(platform: str, title: str):
    color = PLATFORM[platform]["color"]
    icon = PLATFORM[platform]["icon"]
    st.markdown(
        f'<div class="section-header" style="--accent:{color}">'
        f'<span class="rule"></span>'
        f'<span class="icon">{icon}</span><span class="title">{title}</span>'
        f'<span class="rule-tail"></span></div>',
        unsafe_allow_html=True,
    )


def empty_note(text: str):
    st.markdown(f'<div class="empty-note">{text}</div>', unsafe_allow_html=True)


def styled_bar(df: pd.DataFrame, x: str, y: str, color_hex: str, x_label: str):
    fig = px.bar(df, x=x, y=y, orientation="h", labels={x: x_label, y: ""})
    fig.update_traces(marker_color=color_hex)
    fig.update_layout(
        yaxis={"categoryorder": "total ascending"},
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
        font_color=INK_SECONDARY, margin=dict(l=0, r=10, t=10, b=0),
        xaxis=dict(gridcolor=GRIDLINE, zeroline=False),
        height=max(220, 34 * len(df)),
    )
    st.plotly_chart(fig, width="stretch")


def to_data_uri(raw: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(raw).decode()}"


def tiktok_embed_html(video_url: str) -> str:
    video_id = video_url.rstrip("/").split("/")[-1]
    return (
        f'<iframe src="https://www.tiktok.com/embed/v2/{video_id}" '
        f'style="width:100%;height:580px;border:none;overflow:hidden;" '
        f'allow="encrypted-media;" allowfullscreen></iframe>'
    )


def card_grid(rows: list, n_cols: int = 4, accent: str = INK_MUTED):
    """rows: list of dicts with keys image (data-uri or None), title, caption, meta, link,
    and optionally video_url (raw video bytes OR a playable URL - anything st.video()
    accepts) or embed_html (an iframe, e.g. a TikTok embed) to reveal in a "Play"
    expander instead of the static image."""
    if not rows:
        empty_note("Nothing to show yet.")
        return
    cols = st.columns(n_cols)
    for i, row in enumerate(rows):
        with cols[i % n_cols]:
            with st.container(border=True):
                if row.get("image"):
                    st.image(row["image"], width="stretch")
                else:
                    st.markdown(
                        f'<div style="height:120px;background:{PAGE_PLANE};border-radius:6px;'
                        f'display:flex;align-items:center;justify-content:center;color:{INK_MUTED};'
                        f'font-size:0.75rem;">No image</div>',
                        unsafe_allow_html=True,
                    )
                if row.get("video_url") or row.get("embed_html"):
                    with st.expander("▶ Play video"):
                        if row.get("embed_html"):
                            st.components.v1.html(row["embed_html"], height=600)
                        else:
                            st.video(row["video_url"])
                if row.get("title"):
                    st.markdown(f"**{row['title']}**")
                if row.get("caption"):
                    st.markdown(f'<div class="card-caption">{row["caption"]}</div>', unsafe_allow_html=True)
                if row.get("meta"):
                    st.markdown(f'<div class="card-meta">{row["meta"]}</div>', unsafe_allow_html=True)
                if row.get("link"):
                    st.link_button("Open", row["link"], width="stretch")


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
    """Returns raw video bytes (not a data-uri - st.video takes bytes directly)."""
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


def build_timeline(snapshots: pd.DataFrame) -> list:
    segments = []
    for _, row in snapshots.sort_values("captured_at").iterrows():
        if row["changed"] or not segments:
            segments.append({
                "snapshot_id": row["id"], "start": row["captured_at"],
                "end": row["captured_at"], "theme": row["theme"],
            })
        else:
            segments[-1]["end"] = row["captured_at"]
    return list(reversed(segments))


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
last_run = load_last_run()

if last_run is not None:
    _hero_sub = (f"Data current as of {last_run['run_date']:%b %d, %Y · %H:%M UTC} "
                 f"&nbsp;·&nbsp; {last_run['run_type']} run &nbsp;·&nbsp; status: {last_run['status']}")
else:
    _hero_sub = "No scrape runs logged yet."
st.markdown(
    '<div class="ds-hero"><div class="ds-hero-inner">'
    '<span class="ds-eyebrow-pill">● Competitive Intelligence</span>'
    '<h1 class="ds-hero-title">Competitor Research Dashboard</h1>'
    f'<p class="ds-hero-sub">{_hero_sub}</p>'
    '</div></div>',
    unsafe_allow_html=True,
)
_hero_spacer, _hero_refresh = st.columns([5, 1])
with _hero_refresh:
    if st.button("🔄 Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

if competitor_meta.empty:
    st.warning("No competitors in the database yet. Run `python -m scripts.init_db` first.")
    st.stop()

# Cross-page navigation (zoom into a brand, jump to a category) works by having
# button callbacks stash a request under a "_pending_*" key and call st.rerun() -
# Streamlit forbids writing to a widget's own session_state key after that
# widget has already been instantiated in the same run, so the request has to
# be applied here, before any of the widgets below are created.
for _widget_key, _pending_key in [
    ("nav_view", "_pending_view"), ("nav_brand_label", "_pending_brand_label"),
    ("nav_category", "_pending_category"),
]:
    if _pending_key in st.session_state:
        st.session_state[_widget_key] = st.session_state.pop(_pending_key)

with st.container():
    st.markdown('<div class="ds-toolbar">', unsafe_allow_html=True)
    _nav_col, _scope_col = st.columns([2.4, 1])
    with _nav_col:
        page = st.pills(
            "VIEW", ["Brand Profile", "Category Detail", "Category Rollup", "Cross-Competitor Trends"],
            key="nav_view", default="Brand Profile",
        )
    with _scope_col:
        scope = st.pills("SCOPE", ["All", "My brands only", "Competitors only"], key="nav_scope", default="All")
    st.markdown('</div>', unsafe_allow_html=True)

page = page or "Brand Profile"
scope = scope or "All"


def _scope_filter(df):
    if df.empty or "is_own_brand" not in df.columns:
        return df
    if scope == "My brands only":
        return df[df["is_own_brand"]]
    if scope == "Competitors only":
        return df[~df["is_own_brand"]]
    return df


posts_s, homepages_s, ads_s = _scope_filter(posts), _scope_filter(homepages), _scope_filter(ads)
tiktok_s, youtube_s, x_posts_s = _scope_filter(tiktok), _scope_filter(youtube), _scope_filter(x_posts)
google_ads_s = _scope_filter(google_ads)
meta_s = _scope_filter(competitor_meta)

def brand_label(name: str) -> str:
    is_own = competitor_meta.loc[competitor_meta["name"] == name, "is_own_brand"].iloc[0]
    return ("🏠 " + name) if is_own else name


def goto_brand(name: str):
    st.session_state["_pending_view"] = "Brand Profile"
    st.session_state["_pending_brand_label"] = brand_label(name)
    st.rerun()


def zoom_in_buttons(names: list, key_prefix: str, n_cols: int = 4):
    names = sorted(names)
    if not names:
        return
    cols = st.columns(min(n_cols, len(names)))
    for i, name in enumerate(names):
        with cols[i % len(cols)]:
            if st.button(f"🔎 {name}", key=f"{key_prefix}_{name}", width="stretch"):
                goto_brand(name)


PAGE_BANNERS = {
    "Brand Profile": ("🏢", "Brand Profile", "#2a78d6"),
    "Category Detail": ("📁", "Category View", "#eb6834"),
    "Category Rollup": ("🗂️", "Category Rollup — All Categories", "#4a3aa7"),
    "Cross-Competitor Trends": ("📈", "Cross-Competitor Trends", "#008300"),
}
_icon, _label, _color = PAGE_BANNERS[page]
st.markdown(
    f'<div class="ds-active-strip" style="--accent:{_color}">'
    f'<span class="tag">You are viewing</span>{_icon}&nbsp;{_label}</div>',
    unsafe_allow_html=True,
)

# ============================================================================================
# BRAND PROFILE — everything about one brand, one page, top to bottom
# ============================================================================================
if page == "Brand Profile":
    names_sorted = sorted(competitor_meta["name"].unique(), key=lambda n: (
        not competitor_meta.loc[competitor_meta["name"] == n, "is_own_brand"].iloc[0], n
    ))
    labels = {n: brand_label(n) for n in names_sorted}
    st.markdown('<div class="ds-nav-label">Brand</div>', unsafe_allow_html=True)
    chosen_label = st.selectbox("Brand", [labels[n] for n in names_sorted], key="nav_brand_label",
                                 label_visibility="collapsed", width=420)
    competitor_name = next(n for n in names_sorted if labels[n] == chosen_label)
    meta_row = competitor_meta[competitor_meta["name"] == competitor_name].iloc[0]

    ig = posts[posts["competitor_name"] == competitor_name]
    web = homepages[homepages["competitor_name"] == competitor_name]
    brand_ads = ads[ads["competitor_name"] == competitor_name]
    tt = tiktok[tiktok["competitor_name"] == competitor_name]
    yt = youtube[youtube["competitor_name"] == competitor_name]
    xp = x_posts[x_posts["competitor_name"] == competitor_name]
    gads = google_ads[google_ads["competitor_name"] == competitor_name]
    gads_own = gads[gads["is_own_ad"]]
    gads_conquest = gads[~gads["is_own_ad"]]

    # ---- Header ----
    badge = '<span class="badge badge-own">OWN BRAND</span>' if meta_row["is_own_brand"] else \
            '<span class="badge badge-competitor">COMPETITOR</span>'
    st.markdown(f'<div class="brand-header"><span class="brand-title">{competitor_name}</span>{badge}</div>',
                unsafe_allow_html=True)

    brand_groups = load_competitor_groups()
    my_groups = sorted(brand_groups.loc[brand_groups["competitor_id"] == meta_row["id"], "group_name"])
    if my_groups:
        st.caption("Competitive set(s): " + ", ".join(my_groups))
        group_cols = st.columns(len(my_groups))
        for col, g in zip(group_cols, my_groups):
            with col:
                if st.button(f"← Back to \"{g}\" category", key=f"back_to_{g}", width="stretch"):
                    st.session_state["_pending_view"] = "Category Detail"
                    st.session_state["_pending_category"] = g
                    st.rerun()

    links = [
        ("Instagram", meta_row["instagram_url"]), ("Website", meta_row["website_url"]),
        ("Facebook Ads", meta_row["facebook_url"]),
        ("TikTok", f"https://www.tiktok.com/@{meta_row['tiktok_handle']}" if meta_row["tiktok_handle"] else None),
        ("YouTube", meta_row["youtube_url"]),
        ("X", f"https://x.com/{meta_row['x_handle']}" if meta_row["x_handle"] else None),
    ]
    link_cols = st.columns(len(links))
    for col, (label, url) in zip(link_cols, links):
        with col:
            if url:
                st.link_button(label, url, width="stretch")
            else:
                st.button(label, disabled=True, width="stretch", help="No account found")

    # ---- Top summary ----
    total_pieces = len(ig) + len(web) + len(brand_ads) + len(tt) + len(yt) + len(xp)
    total_engagement = (
        ig["like_count"].fillna(0).sum() + tt["like_count"].fillna(0).sum()
        + yt["like_count"].fillna(0).sum() + xp["like_count"].fillna(0).sum() + xp["retweet_count"].fillna(0).sum()
    )
    platform_counts = {
        "Instagram": len(ig), "Website": len(web), "Ads": len(brand_ads),
        "TikTok": len(tt), "YouTube": len(yt), "X": len(xp), "Google Ads": len(gads_own),
    }
    active_platforms = sum(1 for v in platform_counts.values() if v > 0)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total content tracked", f"{total_pieces:,}")
    k2.metric("Combined engagement", f"{int(total_engagement):,}", help="Sum of likes across IG/TikTok/YouTube + likes+retweets on X")
    k3.metric("Active platforms", f"{active_platforms} / 7")
    k4.metric("Own brand" if meta_row["is_own_brand"] else "Competitive set",
              "Yes" if meta_row["is_own_brand"] else "—")

    st.markdown("<br>", unsafe_allow_html=True)
    overview = pd.DataFrame({"platform": list(platform_counts.keys()), "count": list(platform_counts.values())})
    overview = overview[overview["count"] > 0]
    if not overview.empty:
        fig = px.bar(overview, x="count", y="platform", orientation="h",
                     color="platform", color_discrete_map={p: PLATFORM[p]["color"] for p in PLATFORM},
                     labels={"count": "Content pieces tracked", "platform": ""})
        fig.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending"},
                           plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font_color=INK_SECONDARY,
                           margin=dict(l=0, r=10, t=10, b=0), height=220,
                           xaxis=dict(gridcolor=GRIDLINE, zeroline=False))
        st.plotly_chart(fig, width="stretch")

    # ---- Marketing Funnel: See / Think / Do ----
    st.markdown(
        '<div class="section-header" style="--accent:#6b6a63">'
        '<span class="icon">🎯</span><span class="title">Marketing Funnel — See / Think / Do</span></div>',
        unsafe_allow_html=True,
    )
    with st.expander("What do See / Think / Do mean for this segment?"):
        for stage in ["See", "Think", "Do"]:
            st.markdown(f"**{stage}** — {FUNNEL_DEFINITIONS[stage]}")

    funnel_frames = []
    for label, frame in [
        ("Instagram", ig), ("Website", web), ("Ads", brand_ads), ("TikTok", tt),
        ("YouTube", yt), ("X", xp), ("Google Ads", gads_own),
    ]:
        if not frame.empty and "funnel_stage" in frame.columns:
            sub = frame[["funnel_stage"]].dropna().rename(columns={"funnel_stage": "stage"})
            sub["platform"] = label
            funnel_frames.append(sub)

    if not funnel_frames or pd.concat(funnel_frames)["stage"].isna().all():
        empty_note("No content has been classified into See/Think/Do yet.")
    else:
        funnel_df = pd.concat(funnel_frames, ignore_index=True)
        media_filter = st.selectbox("Media type", ["All"] + sorted(funnel_df["platform"].unique()),
                                     key="funnel_media_filter")
        filtered = funnel_df if media_filter == "All" else funnel_df[funnel_df["platform"] == media_filter]

        col_pie, col_summary = st.columns(2)
        with col_pie:
            counts = filtered["stage"].value_counts().reindex(["See", "Think", "Do"]).fillna(0).reset_index()
            counts.columns = ["stage", "count"]
            fig = px.pie(counts, names="stage", values="count", color="stage",
                         color_discrete_map=FUNNEL_COLORS, hole=0.45)
            fig.update_traces(textinfo="percent+label")
            fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=0), height=280)
            st.plotly_chart(fig, width="stretch")
        with col_summary:
            pct = (filtered["stage"].value_counts(normalize=True) * 100).to_dict()
            see_pct, think_pct, do_pct = pct.get("See", 0), pct.get("Think", 0), pct.get("Do", 0)
            dominant_stage, dominant_pct = max(
                [("See", see_pct), ("Think", think_pct), ("Do", do_pct)], key=lambda t: t[1]
            )
            scope_label = media_filter if media_filter != "All" else "all content"
            if dominant_pct >= 50:
                lean = f"is heavily **{dominant_stage}-focused** ({dominant_pct:.0f}% of {scope_label})"
            elif max(see_pct, think_pct, do_pct) - min(see_pct, think_pct, do_pct) < 15:
                lean = "is **fairly balanced** across the funnel"
            else:
                lean = f"leans **{dominant_stage}-heavy** ({dominant_pct:.0f}% of {scope_label})"
            st.markdown(f"**{competitor_name}'s** marketing {lean}.")
            st.markdown(f"- 👀 See (awareness): **{see_pct:.0f}%**")
            st.markdown(f"- 🤔 Think (consideration): **{think_pct:.0f}%**")
            st.markdown(f"- 🛒 Do (conversion): **{do_pct:.0f}%**")
            if do_pct >= 60:
                st.caption("Skews toward bottom-funnel/promotional content - may be under-investing in broad "
                           "awareness and consideration.")
            elif see_pct >= 60:
                st.caption("Skews toward top-funnel/awareness content - lighter on direct conversion pushes.")
    st.divider()

    # ---- Instagram ----
    section_header("Instagram", "Instagram")
    if ig.empty:
        empty_note("No Instagram posts tracked for this brand.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Posts tracked", len(ig))
        c2.metric("Avg likes / post", f"{ig['like_count'].mean():,.0f}")
        span_weeks = max(ig["week"].nunique(), 1)
        c3.metric("Avg posts / week", f"{len(ig) / span_weeks:.1f}")

        mix = ig["category"].value_counts().reset_index()
        mix.columns = ["category", "count"]
        styled_bar(mix, "count", "category", PLATFORM["Instagram"]["color"], "# of posts")

        top = ig.sort_values("like_count", ascending=False).head(8)
        st.caption(f"Showing top {len(top)} of {len(ig)} posts, by likes.")
        thumbs = load_thumbnails(tuple(top["id"].tolist()))
        rows = [{
            "image": thumbs.get(r["id"]),
            "title": f"❤️ {r['like_count']:,} · 💬 {r['comment_count'] or 0:,}",
            "caption": (r["caption"] or "")[:140],
            "meta": f"{r['category']} · {r['posted_at']:%b %d, %Y}",
            "link": r["post_url"],
        } for _, r in top.iterrows()]
        card_grid(rows, accent=PLATFORM["Instagram"]["color"])

    # ---- Website ----
    section_header("Website", "Website Tracker")
    if web.empty:
        empty_note("No homepage snapshots tracked for this brand.")
    else:
        timeline = build_timeline(web)
        current = timeline[0]
        col_img, col_info = st.columns([1, 2])
        with col_img:
            img = load_screenshot(current["snapshot_id"])
            if img:
                st.image(img, width="stretch")
        with col_info:
            st.metric("Current messaging theme", current["theme"] or "Not classified")
            unchanged_since = current["start"]
            st.caption(f"Live since {unchanged_since:%b %d, %Y}" if current["start"] == current["end"]
                       else f"Unchanged {current['start']:%b %d} → {current['end']:%b %d, %Y}")
            if len(timeline) > 1:
                with st.expander(f"History ({len(timeline) - 1} earlier version(s))"):
                    for seg in timeline[1:]:
                        date_range = (f"{seg['start']:%Y-%m-%d}" if seg["start"] == seg["end"]
                                      else f"{seg['start']:%Y-%m-%d} → {seg['end']:%Y-%m-%d}")
                        st.markdown(f"- **{seg['theme'] or 'Not classified'}** — {date_range}")

    # ---- Ads ----
    section_header("Ads", "Facebook / Instagram Ads")
    if brand_ads.empty:
        empty_note("No ads found for this brand (may not be running Meta ads currently, or the Facebook page URL needs a correction).")
    else:
        active = brand_ads[brand_ads["is_active"]]
        c1, c2, c3 = st.columns(3)
        c1.metric("Currently running", len(active))
        c2.metric("Total tracked", len(brand_ads))
        c3.metric("Avg days running", f"{brand_ads['running_days'].mean():.0f}")

        mix = brand_ads["category"].value_counts().reset_index()
        mix.columns = ["category", "count"]
        styled_bar(mix, "count", "category", PLATFORM["Ads"]["color"], "# of ads")

        # Prioritize video ads into the visible set - sorting by date alone can
        # bury every video creative behind more-recent image/carousel ads.
        top = brand_ads.sort_values(["has_video", "start_date"], ascending=[False, False]).head(8)
        st.caption(f"Showing top {len(top)} of {len(brand_ads)} ads, prioritizing video and recency.")
        rows = [{
            "image": load_ad_creative(r["id"]),
            "video_url": load_ad_video(r["id"]) if r["has_video"] else None,
            "title": r["headline"] or r["creative_type"],
            "caption": (r["caption"] or "")[:140],
            "meta": f"{r['category']} · {'Running' if r['is_active'] else 'Ended'} · {', '.join(r['platforms'] or [])}",
            "link": r["ad_url"],
        } for _, r in top.iterrows()]
        card_grid(rows, accent=PLATFORM["Ads"]["color"])

    # ---- TikTok ----
    section_header("TikTok", "TikTok")
    if tt.empty:
        empty_note("No TikTok videos tracked for this brand.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Videos tracked", len(tt))
        c2.metric("Avg views", f"{tt['view_count'].mean():,.0f}")
        c3.metric("Avg likes", f"{tt['like_count'].mean():,.0f}")

        mix = tt["category"].value_counts().reset_index()
        mix.columns = ["category", "count"]
        styled_bar(mix, "count", "category", PLATFORM["TikTok"]["color"], "# of videos")

        top = tt.sort_values("view_count", ascending=False).head(8)
        st.caption(f"Showing top {len(top)} of {len(tt)} videos, by views.")
        rows = [{
            "image": load_tiktok_thumbnail(r["id"]),
            "embed_html": tiktok_embed_html(r["video_url"]),
            "title": f"▶️ {r['view_count']:,} · ❤️ {r['like_count']:,}",
            "caption": (r["caption"] or "")[:140],
            "meta": f"{r['category']} · {r['posted_at']:%b %d, %Y}",
            "link": r["video_url"],
        } for _, r in top.iterrows()]
        card_grid(rows, accent=PLATFORM["TikTok"]["color"])

    # ---- YouTube ----
    section_header("YouTube", "YouTube")
    if yt.empty:
        empty_note("No YouTube videos tracked for this brand.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Videos tracked", len(yt))
        c2.metric("Avg views", f"{yt['view_count'].mean():,.0f}")
        c3.metric("Avg likes", f"{yt['like_count'].mean():,.0f}")

        mix = yt["category"].value_counts().reset_index()
        mix.columns = ["category", "count"]
        styled_bar(mix, "count", "category", PLATFORM["YouTube"]["color"], "# of videos")

        top = yt.sort_values("view_count", ascending=False).head(8)
        st.caption(f"Showing top {len(top)} of {len(yt)} videos, by views.")
        rows = [{
            "image": load_youtube_thumbnail(r["id"]),
            "title": r["title"],
            "caption": (r["caption"] or "")[:140],
            "meta": f"{r['category']} · {r['video_type']} · {r['posted_at']:%b %d, %Y}",
            "link": r["video_url"],
        } for _, r in top.iterrows()]
        card_grid(rows, accent=PLATFORM["YouTube"]["color"])

    # ---- X ----
    section_header("X", "X (Twitter)")
    if xp.empty:
        empty_note("No X posts tracked for this brand.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Posts tracked", len(xp))
        c2.metric("Avg likes", f"{xp['like_count'].mean():,.0f}")
        c3.metric("Avg retweets", f"{xp['retweet_count'].mean():,.0f}")

        mix = xp["category"].value_counts().reset_index()
        mix.columns = ["category", "count"]
        styled_bar(mix, "count", "category", PLATFORM["X"]["color"], "# of posts")

        top = xp.sort_values("like_count", ascending=False).head(6)
        st.caption(f"Showing top {len(top)} of {len(xp)} posts, by likes.")
        for _, r in top.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r['category']}** &nbsp;·&nbsp; {r['posted_at']:%b %d, %Y}")
                st.markdown(r["text"] or "")
                st.markdown(
                    f'<span class="card-meta">❤️ {r["like_count"]:,} &nbsp; 🔁 {r["retweet_count"]:,} '
                    f'&nbsp; 💬 {r["reply_count"]:,} &nbsp; 👁️ {r["view_count"] or 0:,}</span>',
                    unsafe_allow_html=True,
                )
                st.link_button("Open on X", r["post_url"])

    # ---- Google Search Ads ----
    section_header("Google Ads", "Google Search Ads")
    if gads_own.empty and gads_conquest.empty:
        empty_note("No Google Search ad activity found for this brand.")
    else:
        if not gads_own.empty:
            active_gads = gads_own[gads_own["is_active"]]
            c1, c2 = st.columns(2)
            c1.metric("Currently running", len(active_gads))
            c2.metric("Total tracked", len(gads_own))

            top = gads_own.sort_values("last_shown", ascending=False).head(8)
            st.caption(f"Showing top {len(top)} of {len(gads_own)} ads, by most recently shown.")
            rows = [{
                "image": load_google_ad_creative(r["id"]),
                "title": r["ad_format"],
                "meta": f"{r['funnel_stage']} · {'Running' if r['is_active'] else 'Ended'} · "
                        f"~{r['approx_days_shown']} days shown",
                "link": r["ad_url"],
            } for _, r in top.iterrows()]
            card_grid(rows, accent=PLATFORM["Google Ads"]["color"])
        else:
            empty_note("No ads found running under this brand's own name on Google Search.")

        if not gads_conquest.empty:
            st.markdown("##### ⚠️ Competitors bidding on this brand's name")
            conquesters = gads_conquest["advertiser_name"].value_counts().reset_index()
            conquesters.columns = ["advertiser", "ad count"]
            st.dataframe(conquesters, hide_index=True, width="stretch")
            with st.expander("See their ad creatives"):
                top_c = gads_conquest.sort_values("last_shown", ascending=False).head(8)
                st.caption(f"Showing top {len(top_c)} of {len(gads_conquest)} ads, by most recently shown.")
                rows = [{
                    "image": load_google_ad_creative(r["id"]),
                    "title": r["advertiser_name"],
                    "meta": f"{r['funnel_stage']} · targeting \"{r['search_term']}\"",
                    "link": r["ad_url"],
                } for _, r in top_c.iterrows()]
                card_grid(rows, accent=PLATFORM["Google Ads"]["color"])

# ============================================================================================
# CATEGORY DETAIL — one competitive set, every brand in it, side by side by channel
# ============================================================================================
elif page == "Category Detail":
    groups_meta = load_competitor_groups().merge(
        competitor_meta[["id", "name"]], left_on="competitor_id", right_on="id"
    )
    all_categories = sorted(groups_meta["group_name"].unique())
    if not all_categories:
        empty_note("No competitive-set groups found.")
        st.stop()

    default_idx = all_categories.index(st.session_state["nav_category"]) \
        if st.session_state.get("nav_category") in all_categories else 0
    st.markdown('<div class="ds-nav-label">Category</div>', unsafe_allow_html=True)
    category = st.selectbox("Category", all_categories, index=default_idx, key="nav_category",
                             label_visibility="collapsed", width=420)

    st.header(f"📁 Category: {category}")
    brand_names = sorted(groups_meta.loc[groups_meta["group_name"] == category, "name"].unique())
    st.caption(f"{len(brand_names)} brand(s) in this competitive set: " + ", ".join(brand_names))

    def _channel_table(df: pd.DataFrame, date_col: str, category_col: str, engagement_col: str,
                        engagement_label: str, platform_key: str):
        sub = df[df["competitor_name"].isin(brand_names)].copy()
        if sub.empty:
            empty_note(f"No {platform_key} content tracked for brands in this category.")
            return
        sub[date_col] = pd.to_datetime(sub[date_col])
        sub["week"] = sub[date_col].dt.to_period("W").dt.start_time

        cadence = sub.groupby("competitor_name").agg(
            posts=("id", "count"), weeks=("week", "nunique")
        ).reset_index()
        cadence["posts_per_week"] = (cadence["posts"] / cadence["weeks"].clip(lower=1)).round(1)

        top_cat = (
            sub.dropna(subset=[category_col]).groupby("competitor_name")[category_col]
            .agg(lambda s: s.value_counts().idxmax() if len(s) else "—")
            .reset_index(name="Most common content")
        )
        engagement = sub.groupby("competitor_name")[engagement_col].mean().round(0).reset_index()

        summary = cadence.merge(top_cat, on="competitor_name", how="left") \
                          .merge(engagement, on="competitor_name", how="left") \
                          .sort_values("posts_per_week", ascending=False)

        styled_bar(summary[["competitor_name", "posts_per_week"]], "posts_per_week", "competitor_name",
                   PLATFORM[platform_key]["color"], "Posts / week")
        st.dataframe(
            summary.rename(columns={
                "competitor_name": "Brand", "posts": "Total posts", "posts_per_week": "Posts/week",
                engagement_col: f"Avg {engagement_label}",
            })[["Brand", "Total posts", "Posts/week", "Most common content", f"Avg {engagement_label}"]],
            hide_index=True, width="stretch",
        )
        st.markdown("**Zoom in on a brand:**")
        zoom_in_buttons(sub["competitor_name"].unique().tolist(), key_prefix=f"cat_{category}_{platform_key}")

    st.markdown('<div class="ds-nav-label">Channel</div>', unsafe_allow_html=True)
    channel = st.pills(
        "Channel", ["Instagram", "TikTok", "YouTube", "X", "Ads", "Google Ads", "Website"],
        key="nav_category_channel", default="Instagram", label_visibility="collapsed",
    )
    channel = channel or "Instagram"
    st.divider()

    if channel == "Instagram":
        _channel_table(posts, "posted_at", "category", "like_count", "likes", "Instagram")
    elif channel == "TikTok":
        _channel_table(tiktok, "posted_at", "category", "view_count", "views", "TikTok")
    elif channel == "YouTube":
        _channel_table(youtube, "posted_at", "category", "view_count", "views", "YouTube")
    elif channel == "X":
        _channel_table(x_posts, "posted_at", "category", "like_count", "likes", "X")
    elif channel == "Ads":
        sub = ads[ads["competitor_name"].isin(brand_names)]
        if sub.empty:
            empty_note("No Facebook/Instagram ads tracked for brands in this category.")
        else:
            summary = sub.groupby("competitor_name").agg(
                active_ads=("is_active", "sum"), total_ads=("id", "count"),
                avg_days_running=("running_days", "mean"),
            ).reset_index().sort_values("active_ads", ascending=False)
            top_theme = (sub.dropna(subset=["category"]).groupby("competitor_name")["category"]
                         .agg(lambda s: s.value_counts().idxmax() if len(s) else "—")
                         .reset_index(name="Most common theme"))
            summary = summary.merge(top_theme, on="competitor_name", how="left")
            styled_bar(summary[["competitor_name", "active_ads"]], "active_ads", "competitor_name",
                       PLATFORM["Ads"]["color"], "Currently running ads")
            st.dataframe(
                summary.rename(columns={"competitor_name": "Brand", "active_ads": "Active ads",
                                         "total_ads": "Total tracked", "avg_days_running": "Avg days running"}),
                hide_index=True, width="stretch",
            )
            zoom_in_buttons(sub["competitor_name"].unique().tolist(), key_prefix=f"cat_{category}_ads")
    elif channel == "Google Ads":
        sub = google_ads[google_ads["competitor_name"].isin(brand_names) & google_ads["is_own_ad"]]
        if sub.empty:
            empty_note("No Google Search ads tracked for brands in this category.")
        else:
            summary = sub.groupby("competitor_name").agg(
                active_ads=("is_active", "sum"), total_ads=("id", "count"),
            ).reset_index().sort_values("active_ads", ascending=False)
            styled_bar(summary[["competitor_name", "active_ads"]], "active_ads", "competitor_name",
                       PLATFORM["Google Ads"]["color"], "Currently running ads")
            st.dataframe(summary.rename(columns={"competitor_name": "Brand", "active_ads": "Active ads",
                                                  "total_ads": "Total tracked"}),
                         hide_index=True, width="stretch")
            zoom_in_buttons(sub["competitor_name"].unique().tolist(), key_prefix=f"cat_{category}_gads")
    else:  # Website
        sub = homepages[homepages["competitor_name"].isin(brand_names)]
        if sub.empty:
            empty_note("No homepage tracking data for brands in this category.")
        else:
            latest = sub.sort_values("captured_at").groupby("competitor_name").tail(1)
            changes = sub.groupby("competitor_name")["changed"].sum().reset_index(name="Times changed")
            summary = latest[["competitor_name", "theme"]].merge(changes, on="competitor_name")
            summary.columns = ["Brand", "Current theme", "Times changed"]
            st.dataframe(summary, hide_index=True, width="stretch")
            zoom_in_buttons(sub["competitor_name"].unique().tolist(), key_prefix=f"cat_{category}_web")

# ============================================================================================
# CATEGORY ROLLUP — every category's marketing approach vs. your family of brands
# ============================================================================================
elif page == "Category Rollup":
    groups_meta = load_competitor_groups().merge(
        competitor_meta[["id", "name"]], left_on="competitor_id", right_on="id"
    )
    categories = sorted(g for g in groups_meta["group_name"].unique() if g != "Our Brands")
    own_brand_names = sorted(competitor_meta.loc[competitor_meta["is_own_brand"], "name"])

    st.markdown('<div class="ds-nav-label">Compare against</div>', unsafe_allow_html=True)
    compare_choice = st.selectbox("Compare against", ["My Brands (family average)"] + own_brand_names,
                                   label_visibility="collapsed", width=420)
    reference_names = own_brand_names if compare_choice == "My Brands (family average)" else [compare_choice]
    reference_label = compare_choice

    st.header("🗂️ How each category markets, vs. " + reference_label)

    def _names_in(cat: str) -> list:
        return groups_meta.loc[groups_meta["group_name"] == cat, "name"].tolist()

    # ---- Posting cadence (Instagram) ----
    st.subheader("Posting frequency (Instagram)")
    rows = []
    for cat in categories:
        names = _names_in(cat)
        sub = posts[posts["competitor_name"].isin(names)]
        if sub.empty:
            continue
        weeks = max(sub["week"].nunique(), 1)
        rows.append({"group": cat, "posts_per_week": len(sub) / weeks / max(len(names), 1)})
    ref_sub = posts[posts["competitor_name"].isin(reference_names)]
    if not ref_sub.empty:
        ref_weeks = max(ref_sub["week"].nunique(), 1)
        rows.append({"group": reference_label,
                     "posts_per_week": len(ref_sub) / ref_weeks / max(len(reference_names), 1)})
    cadence_df = pd.DataFrame(rows)
    if not cadence_df.empty:
        cadence_df["is_reference"] = cadence_df["group"] == reference_label
        fig = px.bar(cadence_df.sort_values("posts_per_week"), x="posts_per_week", y="group", orientation="h",
                     color="is_reference", color_discrete_map={True: PLATFORM["Instagram"]["color"], False: EMPHASIS_GRAY})
        fig.update_layout(showlegend=False, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font_color=INK_SECONDARY,
                           xaxis=dict(gridcolor=GRIDLINE, zeroline=False),
                           yaxis={"title": "", "categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")

    # ---- Marketing funnel mix, all platforms combined ----
    st.subheader("Marketing funnel mix — See / Think / Do")
    with st.expander("What do See / Think / Do mean for this segment?"):
        for stage in ["See", "Think", "Do"]:
            st.markdown(f"**{stage}** — {FUNNEL_DEFINITIONS[stage]}")

    def _combined_funnel(names: list) -> pd.Series:
        frames = []
        for frame in (posts, tiktok, youtube, x_posts, ads, google_ads):
            s = frame[frame["competitor_name"].isin(names)]["funnel_stage"].dropna()
            if len(s):
                frames.append(s)
        if not frames:
            return pd.Series(dtype=float)
        return pd.concat(frames)

    funnel_rows = []
    for cat in categories:
        stages = _combined_funnel(_names_in(cat))
        if stages.empty:
            continue
        pct = stages.value_counts(normalize=True) * 100
        for stage in ["See", "Think", "Do"]:
            funnel_rows.append({"group": cat, "stage": stage, "pct": pct.get(stage, 0)})
    ref_stages = _combined_funnel(reference_names)
    if not ref_stages.empty:
        pct = ref_stages.value_counts(normalize=True) * 100
        for stage in ["See", "Think", "Do"]:
            funnel_rows.append({"group": reference_label, "stage": stage, "pct": pct.get(stage, 0)})

    funnel_df = pd.DataFrame(funnel_rows)
    if not funnel_df.empty:
        order = list(funnel_df.groupby("group")["pct"].sum().sort_values().index)
        fig = px.bar(funnel_df, x="pct", y="group", color="stage", orientation="h", barmode="stack",
                     category_orders={"group": order}, color_discrete_map=FUNNEL_COLORS,
                     labels={"pct": "Share of content", "group": ""})
        fig.update_layout(plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font_color=INK_SECONDARY,
                           xaxis=dict(gridcolor=GRIDLINE, zeroline=False))
        st.plotly_chart(fig, width="stretch")
    else:
        empty_note("No funnel-stage data classified yet.")

    # ---- Engagement (Instagram likes) ----
    st.subheader("Avg engagement (Instagram likes)")
    eng_rows = []
    for cat in categories:
        sub = posts[posts["competitor_name"].isin(_names_in(cat))]
        if not sub.empty:
            eng_rows.append({"group": cat, "avg_likes": sub["like_count"].mean()})
    if not ref_sub.empty:
        eng_rows.append({"group": reference_label, "avg_likes": ref_sub["like_count"].mean()})
    eng_df = pd.DataFrame(eng_rows)
    if not eng_df.empty:
        eng_df["is_reference"] = eng_df["group"] == reference_label
        fig = px.bar(eng_df.sort_values("avg_likes"), x="avg_likes", y="group", orientation="h",
                     color="is_reference", color_discrete_map={True: PLATFORM["Instagram"]["color"], False: EMPHASIS_GRAY},
                     labels={"avg_likes": "Avg likes / post", "group": ""})
        fig.update_layout(showlegend=False, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font_color=INK_SECONDARY,
                           xaxis=dict(gridcolor=GRIDLINE, zeroline=False))
        st.plotly_chart(fig, width="stretch")

    st.divider()
    st.markdown("**Jump into a category:**")
    cat_cols = st.columns(min(4, len(categories)))
    for i, cat in enumerate(categories):
        with cat_cols[i % len(cat_cols)]:
            if st.button(f"📁 {cat}", key=f"rollup_to_{cat}", width="stretch"):
                st.session_state["_pending_view"] = "Category Detail"
                st.session_state["_pending_category"] = cat
                st.rerun()

# ============================================================================================
# CROSS-COMPETITOR TRENDS — multi-brand comparisons (can't live on a single-brand page)
# ============================================================================================
else:
    all_groups = sorted({g for row in posts_s["groups"] for g in (row or []) if g}) if not posts_s.empty else []
    st.markdown('<div class="ds-nav-label">Competitive set(s)</div>', unsafe_allow_html=True)
    selected_groups = st.pills("Competitive set(s)", all_groups, selection_mode="multi", default=all_groups,
                                key="nav_trend_groups", label_visibility="collapsed")
    df = posts_s[posts_s["groups"].apply(lambda gs: any(g in selected_groups for g in (gs or [])))] \
        if selected_groups else posts_s

    st.header("Cross-Competitor Trends")
    col1, col2, col3 = st.columns(3)
    col1.metric("Competitors tracked", df["competitor_name"].nunique())
    col2.metric("Posts tracked", len(df))
    col3.metric("Avg likes / post", f"{df['like_count'].mean():,.0f}" if len(df) else "—")

    if scope == "All" and not df.empty and df["is_own_brand"].any() and (~df["is_own_brand"]).any():
        st.markdown("### Us vs. competitors")
        bench = df.groupby(df["is_own_brand"].map({True: "My brands", False: "Competitors"})).agg(
            posts=("id", "count"), avg_likes=("like_count", "mean")
        ).reset_index(names="group")
        col_x, col_y = st.columns(2)
        with col_x:
            fig = px.bar(bench, x="group", y="avg_likes", labels={"avg_likes": "Avg likes / post", "group": ""},
                         color="group", color_discrete_map={"My brands": PLATFORM["Instagram"]["color"], "Competitors": EMPHASIS_GRAY})
            fig.update_layout(showlegend=False, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font_color=INK_SECONDARY)
            st.plotly_chart(fig, width="stretch")
        with col_y:
            mine = df[df["is_own_brand"]]["category"].value_counts(normalize=True)
            theirs = df[~df["is_own_brand"]]["category"].value_counts(normalize=True)
            compare = pd.DataFrame({"My brands": mine, "Competitors": theirs}).fillna(0).reset_index(names="category")
            compare = compare.melt(id_vars="category", var_name="group", value_name="share")
            fig = px.bar(compare, x="share", y="category", color="group", orientation="h", barmode="group",
                         labels={"share": "Share of posts", "category": ""},
                         color_discrete_map={"My brands": PLATFORM["Instagram"]["color"], "Competitors": EMPHASIS_GRAY})
            fig.update_layout(yaxis={"categoryorder": "total ascending"}, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font_color=INK_SECONDARY)
            st.plotly_chart(fig, width="stretch")
        st.divider()

    if df.empty:
        empty_note("No posts match this filter.")
    else:
        st.markdown("### Content mix across selected competitors")
        mix = df["category"].value_counts().reset_index()
        mix.columns = ["category", "count"]
        styled_bar(mix, "count", "category", PLATFORM["Instagram"]["color"], "# of posts")

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("### Avg likes by content category")
            avg_likes = df.groupby("category")["like_count"].mean().sort_values(ascending=False).reset_index()
            styled_bar(avg_likes, "like_count", "category", PLATFORM["Instagram"]["color"], "Avg likes")
        with col_b:
            st.markdown("### Posting frequency by competitor")
            cadence = df.groupby("competitor_name")["week"].nunique().reset_index(name="active_weeks")
            counts = df.groupby("competitor_name").size().reset_index(name="posts")
            cadence = cadence.merge(counts, on="competitor_name")
            cadence["posts_per_week"] = (cadence["posts"] / cadence["active_weeks"]).round(1)
            cadence = cadence.sort_values("posts_per_week", ascending=False).head(15)
            styled_bar(cadence, "posts_per_week", "competitor_name", INK_SECONDARY, "Posts / week")

        st.markdown("### Top posts across selected competitors")
        top = df.sort_values("like_count", ascending=False).head(20)
        thumbs = load_thumbnails(tuple(top["id"].tolist()))
        top = top.copy()
        top.insert(0, "image", top["id"].map(thumbs))
        st.dataframe(
            top[["image", "competitor_name", "posted_at", "category", "like_count", "comment_count", "caption", "post_url"]],
            column_config={
                "image": st.column_config.ImageColumn("Post"),
                "post_url": st.column_config.LinkColumn("Link", display_text="Open"),
            },
            hide_index=True, width="stretch",
        )
