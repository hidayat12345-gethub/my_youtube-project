import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title, status_badge_html

st.set_page_config(page_title="YouTube — Holy Month AI", page_icon="📺", layout="wide")
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
    '<span style="font-size:1.6rem;">YouTube</span></div>',
    unsafe_allow_html=True,
)

cfg = db.fetch_config_status()

if not cfg["youtube_authorized"]:
    st.error(
        "YouTube isn't authorized yet. Run `python holy_month_automation.py youtube-auth` "
        "once, then come back here."
    )
    st.stop()

if not backend_live:
    st.warning(
        "Channel stats, analytics, and comments all come from live YouTube API calls — "
        "connect a live backend (`python holy_month_automation.py web`) to see them here. "
        "Recent uploads below still work from the local database."
    )

# ============================================================
# CHANNEL SUMMARY
# ============================================================
section_title(st, "Channel")
if backend_live:
    summary = api_client.get_channel_summary()
    if not summary["ok"]:
        st.warning(f"Couldn't load channel summary: {summary['error']}")
    else:
        data = summary["data"]
        ccol1, ccol2, ccol3, ccol4 = st.columns([1, 1, 1, 2])
        with ccol1:
            st.metric("Subscribers",
                      "Hidden" if data.get("hidden_subscriber_count") else f"{data['subscriber_count']:,}")
        with ccol2:
            st.metric("Total Views", f"{data['view_count']:,}")
        with ccol3:
            st.metric("Videos", data["video_count"])
        with ccol4:
            st.markdown(f"**{data.get('title', 'Your channel')}**")
            if data.get("thumbnail"):
                st.image(data["thumbnail"], width=64)

    if st.button("🔄 Sync video stats now (views/likes/comments)"):
        with st.spinner("Pulling fresh stats from YouTube..."):
            r = api_client.sync_youtube_stats()
        st.success(f"Synced {r['data']['updated']} video(s).") if r["ok"] else st.error(r["error"])
        if r["ok"]:
            st.rerun()
else:
    st.info("Live backend required for channel stats.")

st.write("")

# ============================================================
# RECENT UPLOADS (works read-only, from local DB)
# ============================================================
section_title(st, "Recent Uploads")
uploaded = [v for v in db.fetch_videos() if v.get("youtube_video_id")][:8]
if not uploaded:
    st.info("No videos uploaded to YouTube yet.")
else:
    for v in uploaded:
        cols = st.columns([0.15, 0.5, 0.15, 0.2])
        with cols[0]:
            if v.get("thumbnail_path") and os.path.exists(v["thumbnail_path"]):
                st.image(v["thumbnail_path"], use_container_width=True)
        with cols[1]:
            st.markdown(f"**{v['title'] or 'Untitled'}**")
            st.caption(f"Day {v.get('day_index','—')} · {(v.get('created_at') or '')[:16]}")
        with cols[2]:
            st.markdown(status_badge_html(v["status"]), unsafe_allow_html=True)
        with cols[3]:
            if v.get("youtube_url"):
                st.link_button("Open ↗", v["youtube_url"], use_container_width=True)

st.write("")

# ============================================================
# LATEST COMMENTS (live only)
# ============================================================
section_title(st, "Latest Comments")
if not backend_live:
    st.info("Live backend required to fetch comments.")
else:
    comments_result = api_client.get_recent_comments(max_results=10)
    if not comments_result["ok"]:
        st.warning(comments_result["error"])
    else:
        comments = comments_result["data"].get("comments", [])
        if not comments:
            st.info(comments_result["data"].get("note") or "No comments yet.")
        else:
            for c in comments:
                st.markdown(
                    f'<div class="hm-card" style="padding:12px 16px;">'
                    f'<b>{c["author"]}</b> <span class="hm-card-sub">· {c["like_count"]} likes</span>'
                    f'<div style="margin-top:4px;">{c["text"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
