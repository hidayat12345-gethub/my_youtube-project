import sys
import os
from collections import defaultdict
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title, STATUS_META

st.set_page_config(page_title="Analytics — Holy Month AI", page_icon="📊", layout="wide")
inject_css(st)

with st.sidebar:
    st.markdown("## 🕌 Holy Month AI")
    backend_live = api_client.is_backend_available()
    st.success("🟢 Live backend connected") if backend_live else st.info("📖 Read-only mode")

if not db.db_exists():
    st.error(f"Can't find `holy_month.db` at `{db.get_db_path()}`.")
    st.stop()

st.markdown(
    '<div class="hm-section-title"><div class="bar"></div>'
    '<span style="font-size:1.6rem;">Analytics</span></div>',
    unsafe_allow_html=True,
)

videos = db.fetch_videos()
if not videos:
    st.info("No videos produced yet — analytics will fill in once the pipeline starts running.")
    st.stop()

# ============================================================
# UPLOADS OVER TIME (from local DB — no live backend needed)
# ============================================================
section_title(st, "Uploads Over Time")
daily = defaultdict(int)
monthly = defaultdict(int)
for v in videos:
    created = v.get("created_at")
    if not created:
        continue
    try:
        d = datetime.fromisoformat(created)
        daily[d.date().isoformat()] += 1
        monthly[d.strftime("%Y-%m")] += 1
    except ValueError:
        continue

ucol1, ucol2 = st.columns(2)
with ucol1:
    st.caption("Daily")
    if daily:
        st.bar_chart(dict(sorted(daily.items())))
with ucol2:
    st.caption("Monthly")
    if monthly:
        st.bar_chart(dict(sorted(monthly.items())))

st.write("")

# ============================================================
# VIEWS GROWTH (live — needs YouTube Analytics scope)
# ============================================================
section_title(st, "Views & Watch Time (last 28 days)")
if not backend_live:
    st.info("Connect a live backend to pull day-by-day views/watch-time from YouTube Analytics. "
            "Run `python holy_month_automation.py web`.")
else:
    analytics_result = api_client.get_channel_analytics(days=28)
    if not analytics_result["ok"]:
        st.warning(analytics_result["error"])
    else:
        rows = analytics_result["data"].get("rows", [])
        if not rows:
            st.info("No analytics data yet for this period (a brand-new channel can take a "
                     "day or two before YouTube Analytics has anything to report).")
        else:
            try:
                import pandas as pd
                import plotly.graph_objects as go

                df = pd.DataFrame(rows)
                gcol1, gcol2 = st.columns(2)
                with gcol1:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df["date"], y=df["views"], mode="lines+markers",
                                              line=dict(color="#FFD700"), name="Views"))
                    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                       font=dict(color="#E6E8EB"), height=280,
                                       margin=dict(l=10, r=10, t=30, b=10), title="Views/day")
                    st.plotly_chart(fig, use_container_width=True)
                with gcol2:
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(x=df["date"], y=df["estimated_minutes_watched"],
                                               mode="lines+markers", line=dict(color="#3B82F6"),
                                               name="Watch time (min)"))
                    fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                        font=dict(color="#E6E8EB"), height=280,
                                        margin=dict(l=10, r=10, t=30, b=10), title="Watch time (minutes)/day")
                    st.plotly_chart(fig2, use_container_width=True)

                totals = df[["views", "estimated_minutes_watched", "subscribers_gained", "likes", "comments"]].sum()
                tcols = st.columns(5)
                labels = ["Total Views", "Watch Time (min)", "Subs Gained", "Likes", "Comments"]
                for col, label, key in zip(tcols, labels, totals.index):
                    with col:
                        st.metric(label, int(totals[key]))
            except ImportError:
                st.dataframe(rows, use_container_width=True)

st.write("")

# ============================================================
# TOP VIDEOS
# ============================================================
section_title(st, "Top Performing Videos")
if not backend_live:
    st.caption("Showing view/like/comment counts from the last sync (may be stale — "
               "connect a live backend and hit 'Sync now' on the YouTube page to refresh).")

sortable = [v for v in videos if v.get("youtube_video_id")]
top_videos = sorted(sortable, key=lambda v: v.get("views") or 0, reverse=True)[:10]

if not top_videos:
    st.info("No uploaded videos with stats yet.")
else:
    for v in top_videos:
        cols = st.columns([3, 1, 1, 1])
        with cols[0]:
            st.markdown(f"**{v['title'] or 'Untitled'}**")
            st.caption(f"Day {v.get('day_index','—')}")
        with cols[1]:
            st.metric("Views", v.get("views") or 0, label_visibility="collapsed")
            st.caption("views")
        with cols[2]:
            st.metric("Likes", v.get("likes") or 0, label_visibility="collapsed")
            st.caption("likes")
        with cols[3]:
            st.metric("Comments", v.get("comments") or 0, label_visibility="collapsed")
            st.caption("comments")
        st.divider()
