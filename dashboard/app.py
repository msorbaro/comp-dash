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

st.set_page_config(page_title="Competitor Research Dashboard", layout="wide")

# Palette: a fixed categorical order so the same category always gets the
# same color across every chart on the page.
CATEGORY_COLORS = {
    "Product Feature / New Arrival": "#4C78A8",
    "Promotion / Sale / Discount": "#F58518",
    "Educational / How-To / Tips": "#54A24B",
    "Behind-the-Scenes / Culture": "#E45756",
    "UGC / Customer Testimonial": "#72B7B2",
    "Holiday / Seasonal": "#EECA3B",
    "Community / Cause Marketing": "#B279A2",
    "Brand / Lifestyle / Awareness": "#FF9DA6",
    "Meme / Trending / Entertainment": "#9D755D",
    "Announcement / News": "#BAB0AC",
    "Contest / Giveaway": "#7BA3D0",
    "Influencer / Partnership Collab": "#D67195",
    "Other": "#999999",
}


@st.cache_data(ttl=600)
def load_posts() -> pd.DataFrame:
    # Deliberately excludes the `thumbnail` bytea column - it's fetched
    # separately, only for the handful of posts actually displayed at once,
    # so the cached working dataframe used for every chart stays small.
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
    return {
        post_id: f"data:image/jpeg;base64,{base64.b64encode(thumb).decode()}"
        for post_id, thumb in rows if thumb
    }


def with_thumbnails(top: pd.DataFrame) -> pd.DataFrame:
    thumbs = load_thumbnails(tuple(top["id"].tolist()))
    top = top.copy()
    top.insert(0, "image", top["id"].map(thumbs))
    return top


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
    if row and row[0]:
        return f"data:image/jpeg;base64,{base64.b64encode(row[0]).decode()}"
    return None


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
    if row and row[0]:
        return f"data:image/jpeg;base64,{base64.b64encode(row[0]).decode()}"
    return None


def with_ad_creatives(ads_df: pd.DataFrame) -> pd.DataFrame:
    ads_df = ads_df.copy()
    ads_df.insert(0, "image", ads_df["id"].map(load_ad_creative))
    return ads_df


def build_timeline(snapshots: pd.DataFrame) -> list:
    """Collapses consecutive unchanged rows into single segments: each
    segment is (snapshot_id_with_image, start_date, end_date, theme)."""
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


posts = load_posts()
last_run = load_last_run()

st.title("Competitor Research Dashboard")
if last_run is not None:
    st.caption(
        f"Data current as of {last_run['run_date']:%Y-%m-%d %H:%M UTC} "
        f"({last_run['run_type']} run, {last_run['status']})"
    )
if st.button("Refresh from database"):
    st.cache_data.clear()
    st.rerun()

if posts.empty:
    st.warning("No posts in the database yet. Run `python -m scripts.run_weekly --backfill` first.")
    st.stop()

scope = st.sidebar.radio("Scope", ["All", "My brands only", "Competitors only"])
if scope == "My brands only":
    posts = posts[posts["is_own_brand"]]
elif scope == "Competitors only":
    posts = posts[~posts["is_own_brand"]]

all_groups = sorted({g for row in posts["groups"] for g in (row or []) if g})
page = st.sidebar.radio(
    "View",
    ["Cross-competitor summary", "Competitor detail", "Website tracker", "Ads library"],
)

# ---------------------------------------------------------------- SUMMARY --
if page == "Cross-competitor summary":
    selected_groups = st.sidebar.multiselect("Competitive set(s)", all_groups, default=all_groups)
    df = posts[posts["groups"].apply(lambda gs: any(g in selected_groups for g in (gs or [])))]

    col1, col2, col3 = st.columns(3)
    col1.metric("Competitors tracked", df["competitor_name"].nunique())
    col2.metric("Posts tracked", len(df))
    col3.metric("Avg likes / post", f"{df['like_count'].mean():,.0f}" if len(df) else "—")

    if scope == "All" and df["is_own_brand"].any() and (~df["is_own_brand"]).any():
        st.subheader("Us vs. competitors")
        bench = df.groupby(df["is_own_brand"].map({True: "My brands", False: "Competitors"})).agg(
            posts=("id", "count"), avg_likes=("like_count", "mean")
        ).reset_index(names="group")
        col_x, col_y = st.columns(2)
        with col_x:
            fig = px.bar(bench, x="group", y="avg_likes", labels={"avg_likes": "Avg likes / post", "group": ""})
            st.plotly_chart(fig, use_container_width=True)
        with col_y:
            mine = df[df["is_own_brand"]]["category"].value_counts(normalize=True)
            theirs = df[~df["is_own_brand"]]["category"].value_counts(normalize=True)
            compare = pd.DataFrame({"My brands": mine, "Competitors": theirs}).fillna(0).reset_index(names="category")
            compare = compare.melt(id_vars="category", var_name="group", value_name="share")
            fig = px.bar(compare, x="share", y="category", color="group", orientation="h", barmode="group",
                         labels={"share": "Share of posts", "category": ""})
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
        st.divider()

    st.subheader("Content mix across selected competitors")
    mix = df["category"].value_counts(normalize=True).reset_index()
    mix.columns = ["category", "share"]
    fig = px.bar(
        mix, x="share", y="category", orientation="h",
        color="category", color_discrete_map=CATEGORY_COLORS,
        labels={"share": "Share of posts", "category": ""},
    )
    fig.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Avg likes by content category")
        avg_likes = df.groupby("category")["like_count"].mean().sort_values(ascending=False).reset_index()
        fig = px.bar(
            avg_likes, x="like_count", y="category", orientation="h",
            color="category", color_discrete_map=CATEGORY_COLORS,
            labels={"like_count": "Avg likes", "category": ""},
        )
        fig.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Posting frequency by competitor")
        cadence = df.groupby("competitor_name")["week"].nunique().reset_index(name="active_weeks")
        counts = df.groupby("competitor_name").size().reset_index(name="posts")
        cadence = cadence.merge(counts, on="competitor_name")
        cadence["posts_per_week"] = (cadence["posts"] / cadence["active_weeks"]).round(1)
        cadence = cadence.sort_values("posts_per_week", ascending=False)
        fig = px.bar(cadence, x="posts_per_week", y="competitor_name", orientation="h",
                     labels={"posts_per_week": "Posts / week", "competitor_name": ""})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top posts across selected competitors")
    top = with_thumbnails(df.sort_values("like_count", ascending=False).head(20))
    st.dataframe(
        top[["image", "competitor_name", "posted_at", "category", "like_count", "comment_count", "caption", "post_url"]],
        column_config={
            "image": st.column_config.ImageColumn("Post"),
            "post_url": st.column_config.LinkColumn("Link", display_text="Open"),
        },
        hide_index=True,
        use_container_width=True,
    )

# --------------------------------------------------------- COMPETITOR DETAIL --
elif page == "Competitor detail":
    competitor = st.sidebar.selectbox("Competitor", sorted(posts["competitor_name"].unique()))
    df = posts[posts["competitor_name"] == competitor]

    col1, col2, col3 = st.columns(3)
    col1.metric("Posts tracked", len(df))
    col2.metric("Avg likes / post", f"{df['like_count'].mean():,.0f}" if len(df) else "—")
    span_weeks = max(df["week"].nunique(), 1)
    col3.metric("Avg posts / week", f"{len(df) / span_weeks:.1f}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Content category breakdown")
        mix = df["category"].value_counts().reset_index()
        mix.columns = ["category", "count"]
        fig = px.pie(mix, names="category", values="count", color="category",
                     color_discrete_map=CATEGORY_COLORS)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Avg likes by category")
        avg_likes = df.groupby("category")["like_count"].mean().sort_values(ascending=False).reset_index()
        fig = px.bar(avg_likes, x="like_count", y="category", orientation="h",
                     color="category", color_discrete_map=CATEGORY_COLORS,
                     labels={"like_count": "Avg likes", "category": ""})
        fig.update_layout(showlegend=False, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Posting frequency over time")
    weekly = df.groupby("week").size().reset_index(name="posts")
    fig = px.line(weekly, x="week", y="posts", markers=True)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top posts by likes")
    top = with_thumbnails(df.sort_values("like_count", ascending=False).head(10))
    st.dataframe(
        top[["image", "posted_at", "post_type", "category", "like_count", "comment_count", "caption", "post_url"]],
        column_config={
            "image": st.column_config.ImageColumn("Post"),
            "post_url": st.column_config.LinkColumn("Link", display_text="Open"),
        },
        hide_index=True,
        use_container_width=True,
    )

# ------------------------------------------------------------- WEBSITE TRACKER --
elif page == "Website tracker":
    homepages = load_homepage_snapshots()
    if scope == "My brands only":
        homepages = homepages[homepages["is_own_brand"]]
    elif scope == "Competitors only":
        homepages = homepages[~homepages["is_own_brand"]]
    if homepages.empty:
        st.info("No homepage snapshots yet. Run `python -m scripts.run_weekly --backfill` "
                "(or the homepage capture step) first.")
        st.stop()

    st.subheader("Current homepage theme by competitor")
    latest = homepages.sort_values("captured_at").groupby("competitor_name").tail(1)
    theme_counts = latest["theme"].value_counts().reset_index()
    theme_counts.columns = ["theme", "competitors"]
    fig = px.bar(theme_counts, x="competitors", y="theme", orientation="h",
                 labels={"competitors": "# of competitors", "theme": ""})
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        latest[["competitor_name", "theme", "captured_at"]].sort_values("competitor_name"),
        hide_index=True, use_container_width=True,
    )

    st.divider()
    st.subheader("Homepage change timeline")
    competitor = st.selectbox("Competitor", sorted(homepages["competitor_name"].unique()))
    timeline = build_timeline(homepages[homepages["competitor_name"] == competitor])

    for i, seg in enumerate(timeline):
        img = load_screenshot(seg["snapshot_id"])
        col_img, col_info = st.columns([1, 3])
        with col_img:
            if img:
                st.image(img, use_container_width=True)
            else:
                st.write("(no image stored)")
        with col_info:
            label = "Current" if i == 0 else "Changed to this"
            date_range = (
                f"{seg['start']:%Y-%m-%d}" if seg["start"] == seg["end"]
                else f"{seg['start']:%Y-%m-%d} → {seg['end']:%Y-%m-%d} (unchanged)"
            )
            st.markdown(f"**{label}** — {date_range}")
            st.markdown(f"Theme: **{seg['theme'] or 'Not classified'}**")
        st.divider()

# ------------------------------------------------------------------ ADS LIBRARY --
else:
    ads = load_ads()
    if scope == "My brands only":
        ads = ads[ads["is_own_brand"]]
    elif scope == "Competitors only":
        ads = ads[~ads["is_own_brand"]]
    if ads.empty:
        st.info("No ads captured yet. Run the ads capture step "
                "(`python -c \"from scraper.ads import capture_ads; capture_ads()\"`) first.")
        st.stop()

    only_active = st.checkbox("Currently running only", value=True)
    view = ads[ads["is_active"]] if only_active else ads

    col1, col2, col3 = st.columns(3)
    col1.metric("Ads tracked", len(view))
    col2.metric("Competitors with active ads", view.loc[view["is_active"], "competitor_name"].nunique())
    col3.metric("Avg days running", f"{view['running_days'].mean():.0f}" if len(view) else "—")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("What are competitors' ads trying to say?")
        mix = view["category"].value_counts().reset_index()
        mix.columns = ["theme", "count"]
        fig = px.bar(mix, x="count", y="theme", orientation="h", labels={"count": "# of ads", "theme": ""})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Where are these ads running?")
        platform_counts = view.explode("platforms")["platforms"].value_counts().reset_index()
        platform_counts.columns = ["platform", "count"]
        fig = px.bar(platform_counts, x="count", y="platform", orientation="h",
                     labels={"count": "# of ads", "platform": ""})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Ad creatives")
    competitor_filter = st.selectbox("Competitor", ["All"] + sorted(ads["competitor_name"].unique()))
    table = view if competitor_filter == "All" else view[view["competitor_name"] == competitor_filter]
    table = with_ad_creatives(table.sort_values("start_date", ascending=False).head(50))
    table["status"] = table.apply(
        lambda r: "Running" if r["is_active"] else f"Ended {r['end_date']:%Y-%m-%d}", axis=1
    )
    st.dataframe(
        table[["image", "competitor_name", "creative_type", "category", "headline", "caption",
               "platforms", "start_date", "running_days", "status", "ad_url"]],
        column_config={
            "image": st.column_config.ImageColumn("Creative"),
            "ad_url": st.column_config.LinkColumn("Link", display_text="Open"),
            "running_days": st.column_config.NumberColumn("Days running"),
        },
        hide_index=True,
        use_container_width=True,
    )
