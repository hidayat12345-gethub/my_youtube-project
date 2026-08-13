import sys
import os
from datetime import datetime, timedelta

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title, status_badge_html

st.set_page_config(page_title="Monthly Planner — Holy Month AI", page_icon="🗓️", layout="wide")
inject_css(st)

with st.sidebar:
    st.markdown("## 🕌 Holy Month AI")
    backend_live = api_client.is_backend_available()
    st.success("🟢 Live backend connected") if backend_live else st.info("📖 Read-only mode")
    if not backend_live:
        st.warning(
            "Creating, editing, duplicating, deleting, and regenerating plans all need "
            "a live backend (they call Gemini and/or write to the DB). Run "
            "`python holy_month_automation.py web` to unlock this page."
        )

if not db.db_exists():
    st.error(f"Can't find `holy_month.db` at `{db.get_db_path()}`.")
    st.stop()

st.markdown(
    '<div class="hm-section-title"><div class="bar"></div>'
    '<span style="font-size:1.6rem;">Monthly Planner</span></div>',
    unsafe_allow_html=True,
)

tab_plans, tab_create = st.tabs(["📋 Existing Plans", "➕ Create New Plan"])

# ============================================================
# TAB 1 — EXISTING PLANS
# ============================================================
with tab_plans:
    plans = db.fetch_plans()
    if not plans:
        st.info("No plans yet — create one in the **Create New Plan** tab.")

    for plan in plans:
        total = plan.get("total_videos") or 1
        current = plan.get("current_day") or 0
        pct = min(1.0, current / total)
        status_tag = "⏸️ Paused" if plan.get("is_paused") else ("✅ Active" if plan.get("is_active") else "⚪ Inactive")

        # Estimated completion — only meaningful for an active, non-paused,
        # roughly-one-a-day cadence; flagged as an estimate, not a promise.
        remaining = max(0, total - current)
        est_date = (datetime.now() + timedelta(days=remaining)).strftime("%b %d, %Y") if remaining else "Complete"

        with st.container():
            st.markdown('<div class="hm-card">', unsafe_allow_html=True)
            hcol1, hcol2 = st.columns([3, 1])
            with hcol1:
                st.markdown(f"### {plan['theme'].title()} — {plan['holy_month']}")
                st.caption(
                    f"{status_tag} · Audience: {plan.get('target_audience', '—')} · "
                    f"Language: {plan.get('language', 'en')} · Plan ID: {plan['id']}"
                )
            with hcol2:
                st.metric("Est. completion", est_date if remaining else "🎉 Done")

            st.progress(pct, text=f"Day {current} of {total} ({pct*100:.0f}%)")

            # ---- actions ----
            acols = st.columns(6)
            with acols[0]:
                if plan.get("is_paused"):
                    if st.button("▶️ Resume", key=f"resume_{plan['id']}", disabled=not backend_live, use_container_width=True):
                        r = api_client.resume_plan(plan["id"])
                        st.success("Resumed.") if r["ok"] else st.error(r["error"])
                        st.rerun()
                else:
                    if st.button("⏸️ Pause", key=f"pause_{plan['id']}", disabled=not backend_live, use_container_width=True):
                        r = api_client.pause_plan(plan["id"])
                        st.success("Paused.") if r["ok"] else st.error(r["error"])
                        st.rerun()
            with acols[1]:
                if st.button("⚡ Produce next now", key=f"next_{plan['id']}", disabled=not backend_live, use_container_width=True):
                    r = api_client.produce_next(plan["id"])
                    st.success("Queued — check Video Manager shortly.") if r["ok"] else st.error(r["error"])
            with acols[2]:
                if st.button("🔄 Regenerate future ideas", key=f"regen_{plan['id']}", disabled=not backend_live, use_container_width=True):
                    with st.spinner("Asking Gemini for fresh ideas for the remaining days..."):
                        r = api_client.regenerate_ideas(plan["id"])
                    if r["ok"]:
                        st.success(f"Regenerated {r['data']['regenerated_days']} day(s); "
                                   f"kept {r['data']['preserved_days']} already-produced day(s) untouched.")
                        st.rerun()
                    else:
                        st.error(r["error"])
            with acols[3]:
                if st.button("📄 Duplicate", key=f"dup_{plan['id']}", disabled=not backend_live, use_container_width=True):
                    with st.spinner("Creating a new plan with fresh ideas..."):
                        r = api_client.duplicate_plan(plan["id"], reuse_ideas=False)
                    st.success(f"New plan #{r['data']['plan_id']} created.") if r["ok"] else st.error(r["error"])
                    if r["ok"]:
                        st.rerun()
            with acols[4]:
                edit_key = f"editing_{plan['id']}"
                if st.button("✏️ Edit", key=f"edit_{plan['id']}", use_container_width=True):
                    st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            with acols[5]:
                confirm_key = f"confirm_delete_{plan['id']}"
                if not st.session_state.get(confirm_key):
                    if st.button("🗑️ Delete", key=f"del_{plan['id']}", disabled=not backend_live, use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    if st.button("⚠️ Confirm delete", key=f"del_confirm_{plan['id']}", use_container_width=True, type="primary"):
                        r = api_client.delete_plan(plan["id"])
                        st.success("Deleted. Produced videos are kept.") if r["ok"] else st.error(r["error"])
                        st.session_state[confirm_key] = False
                        st.rerun()

            # ---- inline edit form ----
            if st.session_state.get(f"editing_{plan['id']}"):
                with st.form(key=f"edit_form_{plan['id']}"):
                    st.caption("Theme and holy month aren't editable here — regenerating or "
                               "duplicating handles a real theme change without breaking already-produced days.")
                    new_audience = st.text_input("Target audience", value=plan.get("target_audience", ""))
                    new_lang = st.selectbox(
                        "Language", ["en", "ar", "ur"],
                        index=["en", "ar", "ur"].index(plan.get("language", "en")) if plan.get("language") in ("en", "ar", "ur") else 0,
                    )
                    new_total = st.number_input("Total videos", min_value=max(1, current), max_value=31,
                                                 value=total, help=f"Can't go below {current} — that many are already produced.")
                    if st.form_submit_button("Save changes", disabled=not backend_live):
                        r = api_client.update_plan(plan["id"], {
                            "target_audience": new_audience, "preferred_language": new_lang,
                            "total_videos": int(new_total),
                        })
                        if r["ok"]:
                            st.success("Saved.")
                            st.session_state[f"editing_{plan['id']}"] = False
                            st.rerun()
                        else:
                            st.error(r["error"])

            # ---- calendar view ----
            with st.expander("📅 Calendar — ideas & video status"):
                full_plan = db.fetch_plan(plan["id"])
                ideas = full_plan.get("ideas_json") or [] if full_plan else []
                produced = {v["day_index"]: v for v in db.fetch_plan_videos(plan["id"])}

                if not ideas:
                    st.caption("No ideas stored for this plan.")
                else:
                    grid_cols = st.columns(5)
                    for i, idea in enumerate(sorted(ideas, key=lambda x: x.get("day", 0))):
                        day = idea.get("day", i + 1)
                        video = produced.get(day)
                        with grid_cols[i % 5]:
                            border = "#22C55E55" if video else "#FFD70022"
                            st.markdown(
                                f'<div class="hm-card" style="border-color:{border};padding:12px;min-height:130px;">'
                                f'<div class="hm-card-sub">Day {day}</div>'
                                f'<div style="font-size:0.85rem;font-weight:600;margin:4px 0;">{idea.get("title","")[:60]}</div>'
                                f'{status_badge_html(video["status"]) if video else "<span class=hm-card-sub>not produced yet</span>"}'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# TAB 2 — CREATE NEW PLAN
# ============================================================
with tab_create:
    section_title(st, "Create a Monthly Plan")
    if not backend_live:
        st.warning("Creating a plan generates ideas via Gemini and writes to the database — "
                    "needs a live backend. Run `python holy_month_automation.py web` first.")

    with st.form("create_plan_form"):
        c1, c2 = st.columns(2)
        with c1:
            theme = st.selectbox("Theme", ["ramadan", "eid", "hajj", "muharram", "general_islamic", "custom"])
            if theme == "custom":
                theme = st.text_input("Custom theme name", value="")
            holy_month = st.text_input("Holy month name", value="Ramadan",
                                        help='e.g. "Ramadan", "Dhul Hijjah"')
            audience = st.text_input("Target audience", value="young adults, new Muslims")
        with c2:
            language = st.selectbox("Language", ["en", "ar", "ur"], index=0)
            duration = st.selectbox("Video duration", ["3min", "5min", "10min"], index=1)
            total_videos = st.slider("Total videos", min_value=1, max_value=31, value=30)

        est_completion = (datetime.now() + timedelta(days=total_videos)).strftime("%b %d, %Y")
        st.caption(f"At one video/day, this plan finishes around **{est_completion}** "
                   f"(assuming it's never paused).")

        submitted = st.form_submit_button("🚀 Generate plan", disabled=not backend_live, type="primary")

    if submitted:
        if not theme or not holy_month or not audience:
            st.error("Theme, holy month, and target audience are all required.")
        else:
            with st.spinner(f"Asking Gemini for {total_videos} video ideas — this can take a minute..."):
                result = api_client.create_plan({
                    "theme": theme, "holy_month": holy_month, "target_audience": audience,
                    "preferred_language": language, "video_duration": duration,
                    "total_videos": total_videos,
                })
            if result["ok"]:
                data = result["data"]
                st.success(f"Plan #{data['plan_id']} created with {data['idea_count']} ideas planned out.")
                st.caption(data.get("message", ""))

                preview = db.fetch_plan(data["plan_id"])
                if preview and preview.get("ideas_json"):
                    section_title(st, "Preview: generated ideas")
                    for idea in sorted(preview["ideas_json"], key=lambda x: x.get("day", 0))[:10]:
                        st.markdown(f"**Day {idea.get('day')}** — {idea.get('title')}")
                        st.caption(idea.get("summary", ""))
                    if len(preview["ideas_json"]) > 10:
                        st.caption(f"...and {len(preview['ideas_json']) - 10} more. "
                                   f"See the full calendar in the Existing Plans tab.")
            else:
                st.error(f"Failed to create plan: {result['error']}")
