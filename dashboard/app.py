"""Competitor Research Dashboard — Streamlit app.

Reads ONLY from the database (never scrapes live). Run with:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

# Streamlit runs this script with only its own directory on sys.path, so the
# project root (containing the `db` package) needs to be added explicitly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
    conn = get_conn()
    df = pd.read_sql(
        """
        SELECT p.*, c.name AS competitor_name, c.instagram_handle,
               array_agg(cg.group_name) AS groups
        FROM posts p
        JOIN competitors c ON c.id = p.competitor_id
        LEFT JOIN competitor_groups cg ON cg.competitor_id = c.id
        GROUP BY p.id, c.name, c.instagram_handle
        """,
        conn,
    )
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    df["week"] = df["posted_at"].dt.to_period("W").dt.start_time
    return df


@st.cache_data(ttl=600)
def load_last_run():
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM scrape_runs ORDER BY run_date DESC LIMIT 1", conn)
    return df.iloc[0] if not df.empty else None


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

all_groups = sorted({g for row in posts["groups"] for g in (row or []) if g})
page = st.sidebar.radio("View", ["Cross-competitor summary", "Competitor detail"])

# ---------------------------------------------------------------- SUMMARY --
if page == "Cross-competitor summary":
    selected_groups = st.sidebar.multiselect("Competitive set(s)", all_groups, default=all_groups)
    df = posts[posts["groups"].apply(lambda gs: any(g in selected_groups for g in (gs or [])))]

    col1, col2, col3 = st.columns(3)
    col1.metric("Competitors tracked", df["competitor_name"].nunique())
    col2.metric("Posts tracked", len(df))
    col3.metric("Avg likes / post", f"{df['like_count'].mean():,.0f}" if len(df) else "—")

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
    top = df.sort_values("like_count", ascending=False).head(20)
    st.dataframe(
        top[["competitor_name", "posted_at", "category", "like_count", "comment_count", "caption", "post_url"]],
        use_container_width=True,
    )

# --------------------------------------------------------- COMPETITOR DETAIL --
else:
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
    top = df.sort_values("like_count", ascending=False).head(10)
    st.dataframe(
        top[["posted_at", "post_type", "category", "like_count", "comment_count", "caption", "post_url"]],
        use_container_width=True,
    )
