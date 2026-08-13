import sys
import os
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))
import db_reader as db
import api_client
from style import inject_css, metric_card, section_title, status_badge_html, STATUS_META

st.set_page_config(page_title="Holy Month AI — Dashboard", page_icon="🕌", layout="wide")
inject_css(st)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## 🕌 Holy Month AI")
    st.caption("YouTube automation control center")
    st.divider()

    backend_live = api_client.is_backend_available()
    if backend_live:
        st.success("🟢 Live backend connected")
    else:
        st.info("📖 Read-only mode (no live backend)")
        with st.expander("Why read-only?"):
            st.write(
                "No FastAPI server responded at "
                f"`{api_client.DEFAULT_BASE_URL}`. That's expected if you're "
                "only running the GitHub Actions / `produce-today` deployment — "
                "this dashboard still shows everything from `holy_month.db`. "
                "Run `python holy_month_automation.py web` locally to unlock "
                "live actions (approve, reject, produce now)."
            )

    st.divider()
    st.caption("Full navigation — pages beyond Dashboard / Video Manager / Review Center ship in later modules.")

# ============================================================
# GUARD: no DB found
# ============================================================
if not db.db_exists():
    st.error(
        f"Can't find `holy_month.db` at `{db.get_db_path()}`. Run this dashboard from your "
        f"repo root, or set the `HOLY_MONTH_DB_PATH` environment variable."
    )
    st.stop()

# ============================================================
# HEADER
# ============================================================
st.markdown(
    '<div class="hm-section-title"><div class="bar"></div>'
    '<span style="font-size:1.6rem;">Dashboard</span></div>',
    unsafe_allow_html=True,
)
st.caption(f"Last refreshed {datetime.now().strftime('%b %d, %Y — %I:%M %p')}")

# ============================================================
# KPI CARDS
# ============================================================
counts = db.fetch_status_counts()
cfg = db.fetch_config_status()

cols = st.columns(6)
with cols[0]:
    metric_card(st, "Total Videos", str(counts.get("total", 0)))
with cols[1]:
    metric_card(st, "Published", str(counts.get("published_total", 0)),
                f"{counts.get('auto_published', 0)} auto-approved")
with cols[2]:
    metric_card(st, "Pending Review", str(counts.get("pending_review", 0)))
with cols[3]:
    metric_card(st, "Rejected", str(counts.get("rejected", 0)))
with cols[4]:
    metric_card(st, "Failed", str(counts.get("failed", 0)))
with cols[5]:
    metric_card(st, "Saved Locally", str(counts.get("saved_locally", 0)),
                "not uploaded — check YouTube auth")

st.write("")

# ============================================================
# SERVICE STATUS
# ============================================================
section_title(st, "System Status")
scols = st.columns(6)
service_rows = [
    ("Gemini AI", cfg["gemini"]),
    ("YouTube OAuth", cfg["youtube_authorized"]),
    ("Telegram", cfg["telegram"]),
    ("Database", db.db_exists()),
    ("Live Backend", backend_live),
    ("Human Review Gate", cfg["require_human_review"]),
]
for col, (label, ok) in zip(scols, service_rows):
    with col:
        icon = "🟢" if ok else "⚪"
        st.markdown(
            f'<div class="hm-card" style="text-align:center;padding:14px;">'
            f'<div style="font-size:1.4rem;">{icon}</div>'
            f'<div class="hm-card-sub" style="margin-top:6px;">{label}</div></div>',
            unsafe_allow_html=True,
        )

if cfg["require_human_review"] and cfg["auto_approve_after_hours"] > 0:
    st.caption(
        f"⏰ Un-reviewed videos auto-approve after **{cfg['auto_approve_after_hours']:g}h**. "
        f"Daily production checks run at **{cfg['publish_hour']}:00**."
    )

st.write("")

# ============================================================
# STATUS BREAKDOWN + LATEST VIDEO
# ============================================================
left, right = st.columns([1.3, 1])

with left:
    section_title(st, "Video Status Breakdown")
    breakdown = {k: v for k, v in counts.items() if k not in ("total", "published_total") and v}
    if breakdown:
        try:
            import plotly.graph_objects as go
            labels = [STATUS_META.get(k, {}).get("label", k) for k in breakdown]
            values = list(breakdown.values())
            colors = [STATUS_META.get(k, {}).get("color", "#94A3B8") for k in breakdown]
            fig = go.Figure(data=[go.Pie(
                labels=labels, values=values, hole=0.55,
                marker=dict(colors=colors, line=dict(color="#0B1220", width=2)),
                textfont=dict(color="#E6E8EB"),
            )])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E6E8EB"), showlegend=True, height=320,
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", y=-0.1),
            )
            st.plotly_chart(fig, use_container_width=True)
        except ImportError:
            st.bar_chart(breakdown)
    else:
        st.info("No videos produced yet.")

with right:
    section_title(st, "Latest Video")
    latest = db.fetch_latest_video()
    if latest:
        st.markdown(
            f'<div class="hm-card">'
            f'<div style="font-weight:700;font-size:1.05rem;margin-bottom:6px;">{latest["title"] or "Untitled"}</div>'
            f'{status_badge_html(latest["status"])}'
            f'<div class="hm-card-sub" style="margin-top:10px;">Day {latest.get("day_index", "—")} · '
            f'{latest.get("created_at", "")[:16]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if latest.get("youtube_url"):
            st.link_button("🔗 Open on YouTube", latest["youtube_url"], use_container_width=True)
    else:
        st.info("No videos yet.")

st.write("")

# ============================================================
# MONTHLY PROGRESS
# ============================================================
section_title(st, "Monthly Progress")
plans = db.fetch_plans()
active_plans = [p for p in plans if p.get("is_active")]

if not active_plans:
    st.info("No active monthly plan. Create one via `POST /api/v1/monthly-plan` "
            "or the `create-plan` CLI command — the Monthly Planner page (coming soon) "
            "will do this from the UI directly.")
else:
    for plan in active_plans:
        total = plan.get("total_videos") or 1
        current = plan.get("current_day") or 0
        pct = min(1.0, current / total)
        paused_tag = " ⏸️ Paused" if plan.get("is_paused") else ""
        st.markdown(f"**{plan['theme'].title()} — {plan['holy_month']}**{paused_tag}")
        st.progress(pct, text=f"Day {current} of {total} ({pct*100:.0f}%)")
