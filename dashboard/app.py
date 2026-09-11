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

from db.connection import get_conn

st.set_page_config(page_title="Competitor Research Dashboard", layout="wide", page_icon="📊")

# ============================================================================
# DESIGN SYSTEM
# Fixed categorical order (validated: adjacent-pair CVD-safe) - one color per
# platform, used consistently everywhere that platform appears (charts,
# section headers, borders) so the eye learns "blue = Instagram" once.
# ============================================================================
PLATFORM = {
    "Instagram":  {"icon": "📸", "color": "#2a78d6"},
    "Website":    {"icon": "🌐", "color": "#eb6834"},
    "Ads":        {"icon": "📣", "color": "#1baf7a"},
    "TikTok":     {"icon": "🎵", "color": "#eda100"},
    "YouTube":    {"icon": "▶️", "color": "#e87ba4"},
    "X":          {"icon": "𝕏", "color": "#008300"},
}
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#ffffff"
PAGE_PLANE = "#f9f9f7"
BORDER = "rgba(11,11,11,0.10)"
EMPHASIS_GRAY = "#c3c2b7"

st.markdown(f"""
<style>
    .block-container {{ padding-top: 1.5rem; max-width: 1200px; }}
    [data-testid="stMetricValue"] {{ font-size: 1.7rem; }}
    [data-testid="stMetric"] {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 0.9rem 1rem 0.6rem 1rem;
    }}
    .section-header {{
        display: flex; align-items: center; gap: 0.55rem;
        margin: 2.2rem 0 0.9rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid var(--accent);
    }}
    .section-header .icon {{ font-size: 1.4rem; }}
    .section-header .title {{ font-size: 1.25rem; font-weight: 700; color: {INK_PRIMARY}; }}
    .brand-header {{
        padding: 1.1rem 1.4rem; border-radius: 12px; margin-bottom: 1.1rem;
        background: {PAGE_PLANE}; border: 1px solid {BORDER};
    }}
    .brand-title {{ font-size: 1.7rem; font-weight: 800; color: {INK_PRIMARY}; }}
    .badge {{
        display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
        font-size: 0.72rem; font-weight: 700; letter-spacing: .02em;
        margin-left: 0.6rem; vertical-align: middle;
    }}
    .badge-own {{ background: #eaf3e6; color: #0ca30c; }}
    .badge-competitor {{ background: #eef0f4; color: {INK_SECONDARY}; }}
    .empty-note {{ color: {INK_MUTED}; font-style: italic; padding: 0.5rem 0 1.2rem 0; }}
    .card-caption {{ color: {INK_SECONDARY}; font-size: 0.82rem; line-height: 1.3;
                      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                      overflow: hidden; margin: 0.3rem 0; }}
    .card-meta {{ color: {INK_MUTED}; font-size: 0.76rem; }}
</style>
""", unsafe_allow_html=True)


def section_header(platform: str, title: str):
    color = PLATFORM[platform]["color"]
    icon = PLATFORM[platform]["icon"]
    st.markdown(
        f'<div class="section-header" style="--accent:{color}">'
        f'<span class="icon">{icon}</span><span class="title">{title}</span></div>',
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


def card_grid(rows: list, n_cols: int = 4, accent: str = INK_MUTED):
    """rows: list of dicts with keys image (data-uri or None), title, caption, meta, link"""
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
               p.view_count, p.category, p.category_confidence, p.scraped_at,
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
               c.name AS competitor_name, c.is_own_brand
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
        SELECT a.id, a.competitor_id, a.ad_url, a.creative_type, a.caption, a.headline,
               a.platforms, a.start_date, a.end_date, a.is_active, a.category,
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
def load_tiktok() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT t.id, t.competitor_id, t.video_url, t.caption, t.posted_at, t.duration_seconds,
               t.view_count, t.like_count, t.comment_count, t.share_count, t.category,
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
               y.video_type, y.view_count, y.like_count, y.comment_count, y.category,
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
               x.category, c.name AS competitor_name, c.is_own_brand
        FROM x_posts x
        JOIN competitors c ON c.id = x.competitor_id
        ORDER BY x.posted_at DESC
        """,
        conn,
    )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df


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
competitor_meta = load_competitor_meta()
last_run = load_last_run()

st.title("📊 Competitor Research Dashboard")
if last_run is not None:
    st.caption(f"Data current as of {last_run['run_date']:%Y-%m-%d %H:%M UTC} "
               f"({last_run['run_type']} run, {last_run['status']})")
if st.button("🔄 Refresh from database"):
    st.cache_data.clear()
    st.rerun()

if competitor_meta.empty:
    st.warning("No competitors in the database yet. Run `python -m scripts.init_db` first.")
    st.stop()

scope = st.sidebar.radio("Scope", ["All", "My brands only", "Competitors only"])


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
meta_s = _scope_filter(competitor_meta)

page = st.sidebar.radio("View", ["Brand Profile", "Cross-Competitor Trends"])

# ============================================================================================
# BRAND PROFILE — everything about one brand, one page, top to bottom
# ============================================================================================
if page == "Brand Profile":
    names_sorted = sorted(meta_s["name"].unique(), key=lambda n: (
        not meta_s.loc[meta_s["name"] == n, "is_own_brand"].iloc[0], n
    ))
    labels = {n: ("🏠 " + n if meta_s.loc[meta_s["name"] == n, "is_own_brand"].iloc[0] else n) for n in names_sorted}
    chosen_label = st.sidebar.selectbox("Brand", [labels[n] for n in names_sorted])
    competitor_name = next(n for n in names_sorted if labels[n] == chosen_label)
    meta_row = competitor_meta[competitor_meta["name"] == competitor_name].iloc[0]

    ig = posts[posts["competitor_name"] == competitor_name]
    web = homepages[homepages["competitor_name"] == competitor_name]
    brand_ads = ads[ads["competitor_name"] == competitor_name]
    tt = tiktok[tiktok["competitor_name"] == competitor_name]
    yt = youtube[youtube["competitor_name"] == competitor_name]
    xp = x_posts[x_posts["competitor_name"] == competitor_name]

    # ---- Header ----
    badge = '<span class="badge badge-own">OWN BRAND</span>' if meta_row["is_own_brand"] else \
            '<span class="badge badge-competitor">COMPETITOR</span>'
    st.markdown(f'<div class="brand-header"><span class="brand-title">{competitor_name}</span>{badge}</div>',
                unsafe_allow_html=True)

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
        "TikTok": len(tt), "YouTube": len(yt), "X": len(xp),
    }
    active_platforms = sum(1 for v in platform_counts.values() if v > 0)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total content tracked", f"{total_pieces:,}")
    k2.metric("Combined engagement", f"{int(total_engagement):,}", help="Sum of likes across IG/TikTok/YouTube + likes+retweets on X")
    k3.metric("Active platforms", f"{active_platforms} / 6")
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

        top = brand_ads.sort_values("start_date", ascending=False).head(8)
        rows = [{
            "image": load_ad_creative(r["id"]),
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
        rows = [{
            "image": load_tiktok_thumbnail(r["id"]),
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

# ============================================================================================
# CROSS-COMPETITOR TRENDS — multi-brand comparisons (can't live on a single-brand page)
# ============================================================================================
else:
    all_groups = sorted({g for row in posts_s["groups"] for g in (row or []) if g}) if not posts_s.empty else []
    selected_groups = st.sidebar.multiselect("Competitive set(s)", all_groups, default=all_groups)
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
