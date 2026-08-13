import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title

st.set_page_config(page_title="Review Center — Holy Month AI", page_icon="✅", layout="wide")
inject_css(st)

with st.sidebar:
    st.markdown("## 🕌 Holy Month AI")
    backend_live = api_client.is_backend_available()
    st.success("🟢 Live backend connected") if backend_live else st.info("📖 Read-only mode")
    if not backend_live:
        st.warning("Approve/Reject need a live backend — see Dashboard sidebar for why.")

if not db.db_exists():
    st.error(f"Can't find `holy_month.db` at `{db.get_db_path()}`.")
    st.stop()

st.markdown(
    '<div class="hm-section-title"><div class="bar"></div>'
    '<span style="font-size:1.6rem;">Review Center</span></div>',
    unsafe_allow_html=True,
)
st.caption("Videos uploaded as unlisted, waiting for approval before going public.")

pending = db.fetch_pending_review()

if not pending:
    st.success("Nothing waiting for review right now. 🎉")
    st.stop()

# sort soonest-to-auto-approve first, so the most time-sensitive review sits on top
pending.sort(key=lambda v: (v.get("hours_until_auto_approve") is None, v.get("hours_until_auto_approve", 999)))

for v in pending:
    with st.container():
        st.markdown('<div class="hm-card">', unsafe_allow_html=True)
        col_player, col_meta = st.columns([1.1, 1])

        with col_player:
            if v.get("youtube_url"):
                video_id = v["youtube_url"].split("v=")[-1].split("&")[0]
                st.markdown(
                    f'<iframe width="100%" height="280" style="border-radius:12px;border:none;" '
                    f'src="https://www.youtube.com/embed/{video_id}" allowfullscreen></iframe>',
                    unsafe_allow_html=True,
                )
            elif v.get("thumbnail_path") and os.path.exists(v["thumbnail_path"]):
                st.image(v["thumbnail_path"], use_container_width=True)
            else:
                st.info("No preview available.")

        with col_meta:
            st.markdown(f"### {v['title'] or 'Untitled'}")
            st.caption(f"Day {v.get('day_index', '—')} · uploaded {(v.get('uploaded_at') or '')[:16]}")

            hours_left = v.get("hours_until_auto_approve")
            overdue = v.get("auto_approve_overdue")
            if hours_left is not None:
                if overdue:
                    st.markdown(
                        '<span class="hm-countdown overdue">⏰ Overdue — will auto-approve on next sweep</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    h, m = int(hours_left), int((hours_left % 1) * 60)
                    st.markdown(
                        f'<span class="hm-countdown">⏳ Auto-approves in {h}h {m}m unless reviewed</span>',
                        unsafe_allow_html=True,
                    )
            else:
                st.caption("Auto-approval timing unavailable (missing upload timestamp or sweep disabled).")

            with st.expander("Description & tags"):
                st.write(v.get("description") or "—")
                if v.get("tags"):
                    st.caption(", ".join(v["tags"]) if isinstance(v["tags"], list) else str(v["tags"]))

            st.write("")
            # NEW (audit) — AI Generated is always true for this
            # pipeline's output (display-only, not a choice). YouTube
            # Disclosure is the human's separate, explicit publishing
            # decision — kept as two distinct concepts, never converted
            # from one into the other automatically.
            st.caption("🤖 **AI Generated:** Yes  ·  *(this project's entire pipeline is AI-produced — informational only)*")
            disclosure_labels = {"not_selected": "Not Selected", "yes": "Yes", "no": "No"}
            current_disclosure = v.get("ai_disclosure") or "not_selected"
            st.markdown(f"**YouTube Altered/Synthetic Content Disclosure:** {disclosure_labels[current_disclosure]}")
            with st.expander("What does this mean?"):
                st.caption(
                    "YouTube requires creators to disclose when a video contains realistic "
                    "altered or synthetic (\"deepfake-style\") content — e.g. making a real "
                    "person appear to say/do something they didn't, altering real footage, or "
                    "generating a realistic scene that didn't happen. This pipeline's stylized "
                    "AI-narrated/illustrated videos may or may not meet that bar depending on "
                    "the specific content — **you** decide, this tool doesn't decide for you. "
                    "Selecting 'Yes' sets YouTube's official `containsSyntheticMedia` field on "
                    "this video (a real, current YouTube Data API field). 'No' explicitly clears "
                    "it. 'Not Selected' leaves it untouched on YouTube."
                )
            new_disclosure = st.radio(
                "Set disclosure", options=["not_selected", "yes", "no"],
                format_func=lambda x: disclosure_labels[x],
                index=["not_selected", "yes", "no"].index(current_disclosure),
                key=f"disclosure_{v['id']}", horizontal=True, label_visibility="collapsed",
            )
            if new_disclosure != current_disclosure:
                if st.button("💾 Save disclosure choice", key=f"save_disclosure_{v['id']}", disabled=not backend_live):
                    result = api_client.set_ai_disclosure(v["id"], new_disclosure)
                    if result["ok"]:
                        data = result["data"]
                        if data.get("push_error"):
                            st.warning(data["push_error"])
                        else:
                            st.success("Saved.")
                        st.rerun()
                    else:
                        st.error(result["error"])

            st.write("")
            acol1, acol2 = st.columns(2)
            with acol1:
                approve_disabled = not backend_live
                if st.button("✅ Approve & publish", key=f"rc_approve_{v['id']}",
                              use_container_width=True, disabled=approve_disabled, type="primary"):
                    result = api_client.approve_video(v["id"])
                    if result["ok"]:
                        st.success("Published!")
                        st.rerun()
                    else:
                        st.error(result["error"])
            with acol2:
                if st.button("❌ Reject", key=f"rc_reject_{v['id']}",
                              use_container_width=True, disabled=not backend_live):
                    result = api_client.reject_video(v["id"])
                    if result["ok"]:
                        st.warning("Rejected.")
                        st.rerun()
                    else:
                        st.error(result["error"])

        st.markdown('</div>', unsafe_allow_html=True)
