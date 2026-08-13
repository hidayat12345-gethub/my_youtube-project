import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title, status_badge_html, STATUS_META, REGENERATABLE_STATUSES

st.set_page_config(page_title="Video Manager — Holy Month AI", page_icon="🎥", layout="wide")
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
    '<span style="font-size:1.6rem;">Video Manager</span></div>',
    unsafe_allow_html=True,
)

# ============================================================
# FILTERS
# ============================================================
fcol1, fcol2 = st.columns([1, 2])
with fcol1:
    status_options = ["All"] + list(STATUS_META.keys())
    status_filter = st.selectbox("Status", status_options, index=0)
with fcol2:
    search = st.text_input("Search by title", placeholder="e.g. Laylatul Qadr")

videos = db.fetch_videos(status=status_filter, search=search or None)
st.caption(f"{len(videos)} video(s)")

if not videos:
    st.info("No videos match these filters yet.")
    st.stop()

# ============================================================
# TABLE
# ============================================================
for v in videos:
    with st.container():
        cols = st.columns([0.12, 0.38, 0.12, 0.13, 0.12, 0.13])

        with cols[0]:
            if v.get("thumbnail_path") and os.path.exists(v["thumbnail_path"]):
                st.image(v["thumbnail_path"], use_container_width=True)
            else:
                st.markdown(
                    '<div style="width:100%;aspect-ratio:16/9;background:rgba(255,255,255,0.06);'
                    'border-radius:8px;display:flex;align-items:center;justify-content:center;'
                    'color:#94A3B8;font-size:0.7rem;">no thumbnail</div>',
                    unsafe_allow_html=True,
                )
        with cols[1]:
            st.markdown(f"**{v['title'] or 'Untitled'}**")
            st.caption(f"Day {v.get('day_index', '—')} · {(v.get('created_at') or '')[:16]}")
        with cols[2]:
            st.markdown(status_badge_html(v["status"]), unsafe_allow_html=True)
            # NEW (audit) — surfaces the YouTube disclosure choice right
            # in the table, not just buried in the editor.
            disclosure_icons = {"not_selected": "⚪ Disclosure: Not Selected",
                                 "yes": "🟡 Disclosure: Yes", "no": "⚪ Disclosure: No"}
            st.caption(disclosure_icons.get(v.get("ai_disclosure") or "not_selected"))
        with cols[3]:
            st.metric("Views", v.get("views") or 0, label_visibility="collapsed")
            st.caption("views")
        with cols[4]:
            st.metric("Likes", v.get("likes") or 0, label_visibility="collapsed")
            st.caption("likes")
        with cols[5]:
            if v.get("youtube_url"):
                st.link_button("Open ↗", v["youtube_url"], use_container_width=True)
            elif v.get("video_path"):
                st.caption("Saved locally (not uploaded)")

        with st.expander("Script preview, tags & quick actions"):
            dcol1, dcol2 = st.columns([2, 1])
            with dcol1:
                st.markdown("**Description**")
                st.write((v.get("description") or "—")[:600])
                if v.get("tags"):
                    st.markdown("**Tags**")
                    st.write(", ".join(v["tags"]) if isinstance(v["tags"], list) else v["tags"])
                if v.get("hashtags"):
                    st.markdown("**Hashtags**")
                    st.write(" ".join(v["hashtags"]) if isinstance(v["hashtags"], list) else v["hashtags"])
            with dcol2:
                st.markdown("**Quick actions**")
                if not backend_live:
                    st.caption("Connect a live backend to approve/reject/edit from here.")
                else:
                    if v["status"] == "pending_review":
                        acol1, acol2 = st.columns(2)
                        with acol1:
                            if st.button("✅ Approve", key=f"approve_{v['id']}", use_container_width=True):
                                result = api_client.approve_video(v["id"])
                                st.success("Approved!") if result["ok"] else st.error(result["error"])
                                st.rerun()
                        with acol2:
                            if st.button("❌ Reject", key=f"reject_{v['id']}", use_container_width=True):
                                result = api_client.reject_video(v["id"])
                                st.success("Rejected.") if result["ok"] else st.error(result["error"])
                                st.rerun()
                    else:
                        st.caption(f"No approve/reject for status `{v['status']}`.")

        editor_key = f"editor_open_{v['id']}"
        if st.button("✏️ Open Video Editor", key=f"open_editor_{v['id']}"):
            st.session_state[editor_key] = not st.session_state.get(editor_key, False)

        if st.session_state.get(editor_key):
            st.markdown('<div class="hm-card">', unsafe_allow_html=True)
            st.markdown(f"#### Editing: {v['title'] or 'Untitled'}")
            if not backend_live:
                st.warning("Editing needs a live backend — saving metadata/script and regenerating "
                           "all write to the DB or call Gemini/edge-tts/ffmpeg/YouTube. Run "
                           "`python holy_month_automation.py web` to unlock this.")

            tab_meta, tab_script, tab_regen = st.tabs(["📝 Metadata", "📜 Script", "🔁 Regenerate & Thumbnail"])

            # ---- METADATA ----
            with tab_meta:
                with st.form(key=f"meta_form_{v['id']}"):
                    new_title = st.text_input("Title", value=v.get("title") or "", max_chars=100)
                    new_desc = st.text_area("Description", value=v.get("description") or "", height=150)
                    tags_list = v.get("tags") if isinstance(v.get("tags"), list) else []
                    hashtags_list = v.get("hashtags") if isinstance(v.get("hashtags"), list) else []
                    new_tags = st.text_input("Tags (comma-separated)", value=", ".join(tags_list))
                    new_hashtags = st.text_input("Hashtags (comma-separated, include #)",
                                                  value=" ".join(hashtags_list))
                    if st.form_submit_button("💾 Save metadata", disabled=not backend_live):
                        payload = {
                            "title": new_title, "description": new_desc,
                            "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
                            "hashtags": [h.strip() for h in new_hashtags.split() if h.strip()],
                        }
                        r = api_client.update_video_metadata(v["id"], payload)
                        st.success("Saved.") if r["ok"] else st.error(r["error"])
                        if r["ok"]:
                            st.rerun()
                    st.caption("Note: this updates the database record. If the video is already "
                               "uploaded, push the same change on YouTube Studio too — this dashboard "
                               "doesn't sync metadata to an already-live upload yet.")

            # ---- SCRIPT ----
            with tab_script:
                script = v.get("script") if isinstance(v.get("script"), dict) else {}
                if not script:
                    st.info("No script stored for this video.")
                else:
                    with st.form(key=f"script_form_{v['id']}"):
                        s_title = st.text_input("Script title", value=script.get("title", ""))
                        s_hook = st.text_area("Hook", value=script.get("hook", ""), height=70)
                        s_intro = st.text_area("Introduction", value=script.get("introduction", ""), height=90)
                        body_list = script.get("body", []) if isinstance(script.get("body"), list) else []
                        s_body = st.text_area(
                            "Body scenes (one per line — each line becomes one narrated scene with its own image)",
                            value="\n".join(body_list), height=160,
                        )
                        s_ending = st.text_area("Ending", value=script.get("ending", ""), height=70)
                        s_cta = st.text_area("Call to action", value=script.get("call_to_action", ""), height=70)
                        if st.form_submit_button("💾 Save script", disabled=not backend_live):
                            payload = {
                                "title": s_title, "hook": s_hook, "introduction": s_intro,
                                "body": [line.strip() for line in s_body.split("\n") if line.strip()],
                                "ending": s_ending, "call_to_action": s_cta,
                            }
                            r = api_client.update_video_script(v["id"], payload)
                            st.success("Script saved. Use the Regenerate tab to re-render the "
                                       "video from it.") if r["ok"] else st.error(r["error"])
                            if r["ok"]:
                                st.rerun()

            # ---- REGENERATE & THUMBNAIL ----
            with tab_regen:
                can_regen = v["status"] in REGENERATABLE_STATUSES
                st.markdown("**Regenerate video (voice + images + assembly + re-upload)**")
                if not can_regen:
                    st.caption(f"⚠️ Not available for status `{v['status']}` — only unpublished videos "
                               f"({', '.join(sorted(REGENERATABLE_STATUSES))}) can be regenerated, since "
                               f"YouTube has no way to replace a public video's footage in place.")
                voice_options = {"en": "English — Aria (female)", "en-male": "English — Guy (male)",
                                  "ar": "Arabic — Salma", "ur": "Urdu — Asad"}
                rcol1, rcol2 = st.columns(2)
                with rcol1:
                    voice_choice = st.selectbox("Voice", list(voice_options.keys()),
                                                 format_func=lambda k: voice_options[k], key=f"voice_{v['id']}")
                with rcol2:
                    lang_override = st.selectbox("Language override (optional)", ["(use plan default)", "en", "ar", "ur"],
                                                  key=f"langover_{v['id']}")
                if st.button("🔁 Regenerate video now", key=f"regen_video_{v['id']}",
                              disabled=not (backend_live and can_regen), type="primary"):
                    with st.spinner("Regenerating voice, images, and video, then re-uploading — "
                                     "this can take a few minutes..."):
                        r = api_client.regenerate_video_full(
                            v["id"], voice=voice_choice,
                            language=None if lang_override == "(use plan default)" else lang_override,
                        )
                    if r["ok"]:
                        st.success(f"Regenerated — new status: {r['data']['status']}")
                        st.rerun()
                    else:
                        st.error(r["error"])

                st.divider()
                st.markdown("**Thumbnail**")
                tcol1, tcol2 = st.columns([1, 2])
                with tcol1:
                    if v.get("thumbnail_path") and os.path.exists(v["thumbnail_path"]):
                        st.image(v["thumbnail_path"], use_container_width=True)
                    else:
                        st.caption("No thumbnail yet.")
                with tcol2:
                    st.caption("Regenerating the thumbnail works even for already-published videos — "
                               "YouTube supports replacing a thumbnail directly.")
                    if st.button("🖼️ Regenerate thumbnail", key=f"regen_thumb_{v['id']}", disabled=not backend_live):
                        with st.spinner("Generating a new thumbnail..."):
                            r = api_client.regenerate_video_thumbnail(v["id"])
                        st.success("Thumbnail updated.") if r["ok"] else st.error(r["error"])
                        if r["ok"]:
                            st.rerun()

                st.divider()
                st.caption("Not implemented: **Background music** and a settable **video duration** — the "
                           "pipeline has no audio-mixing step and no global duration control (each scene's "
                           "length is derived from its own narration, not a target you set). Faking those "
                           "controls felt worse than leaving them out — see MODULE_4_NOTES.md.")

            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()
