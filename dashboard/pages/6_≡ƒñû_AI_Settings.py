import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title

st.set_page_config(page_title="AI Settings — Holy Month AI", page_icon="🤖", layout="wide")
inject_css(st)

with st.sidebar:
    st.markdown("## 🕌 Holy Month AI")
    backend_live = api_client.is_backend_available()
    st.success("🟢 Live backend connected") if backend_live else st.info("📖 Read-only mode")
    if not backend_live:
        st.warning("All AI Settings need a live backend to view or change — "
                    "they're read from/written to files the backend process owns. "
                    "Run `python holy_month_automation.py web`.")

st.markdown(
    '<div class="hm-section-title"><div class="bar"></div>'
    '<span style="font-size:1.6rem;">AI Settings</span></div>',
    unsafe_allow_html=True,
)

if not backend_live:
    st.stop()

cfg = db.fetch_config_status()
scol1, scol2 = st.columns(2)
with scol1:
    st.metric("Gemini API", "🟢 Configured" if cfg["gemini"] else "⚪ Not configured")
with scol2:
    st.caption(f"Model / temperature below apply to every Gemini call: plan ideas, "
               f"research, and script writing.")

tab_gen, tab_prompts, tab_style = st.tabs(["⚙️ Generation", "📝 Prompt Templates", "🎨 Thumbnail & Captions"])

settings_result = api_client.get_ai_settings()
settings = settings_result["data"] if settings_result["ok"] else {}
if not settings_result["ok"]:
    st.error(f"Couldn't load settings: {settings_result['error']}")
    st.stop()

# ============================================================
# GENERATION
# ============================================================
with tab_gen:
    with st.form("gen_settings_form"):
        st.markdown("**Model**")
        model_override = st.text_input(
            "Gemini model override (blank = use .env's GEMINI_MODEL)",
            value=settings.get("gemini_model") or "",
            help='e.g. "gemini-2.5-flash". Leave blank to use whatever GEMINI_MODEL is set to in .env. '
                 'Check current model names at https://ai.google.dev/gemini-api/docs/models — this app '
                 "doesn't validate the name against Google's API, it just passes through whatever you type.",
        )
        st.markdown("**Temperature**")
        temperature = st.slider(
            "Temperature", min_value=0.0, max_value=2.0,
            value=float(settings.get("gemini_temperature", 0.9)), step=0.05,
            help="Lower = more consistent/predictable output. Higher = more varied/creative. "
                 "Applies to plan ideas, research, and script generation alike.",
        )
        if st.form_submit_button("💾 Save generation settings"):
            payload = {"gemini_model": model_override or None, "gemini_temperature": temperature}
            r = api_client.update_ai_settings(payload)
            st.success("Saved.") if r["ok"] else st.error(r["error"])

    st.divider()
    if st.button("↩️ Reset generation settings to defaults"):
        r = api_client.reset_ai_settings()
        st.success("Reset to defaults.") if r["ok"] else st.error(r["error"])
        if r["ok"]:
            st.rerun()

# ============================================================
# PROMPT TEMPLATES
# ============================================================
with tab_prompts:
    st.caption(
        "Uses $placeholder syntax (not {curly braces}) — the prompts below contain literal "
        "JSON examples full of braces, so $placeholders avoid needing to escape every one. "
        "Available placeholders are listed under each box."
    )
    prompts_result = api_client.get_prompt_templates()
    if not prompts_result["ok"]:
        st.error(f"Couldn't load prompt templates: {prompts_result['error']}")
    else:
        prompts = prompts_result["data"]
        template_meta = {
            "planner": ("Planner (monthly idea generation)", "$count, $theme, $holy_month, $target_audience, $language"),
            "research": ("Research (per-video Quran/Hadith/facts)", "$topic, $theme"),
            "script_writer": ("Script Writer", "$title, $theme, $duration, $quran_json, $hadith_json, "
                                                "$facts_json, $keywords_json"),
        }
        for key, (label, placeholders) in template_meta.items():
            section_title(st, label)
            st.caption(f"Placeholders: `{placeholders}`")
            with st.form(key=f"prompt_form_{key}"):
                text = st.text_area("Template", value=prompts.get(key, ""), height=280,
                                     key=f"prompt_text_{key}", label_visibility="collapsed")
                pcol1, pcol2 = st.columns([1, 1])
                with pcol1:
                    save_clicked = st.form_submit_button(f"💾 Save {label.split(' ')[0]} template")
                with pcol2:
                    reset_clicked = st.form_submit_button(f"↩️ Reset to default")
                if save_clicked:
                    r = api_client.update_prompt_template(key, text)
                    st.success("Saved.") if r["ok"] else st.error(r["error"])
                if reset_clicked:
                    r = api_client.reset_prompt_template(key)
                    if r["ok"]:
                        st.success("Reset to default.")
                        st.rerun()
                    else:
                        st.error(r["error"])
            st.write("")

# ============================================================
# THUMBNAIL & CAPTIONS
# ============================================================
with tab_style:
    with st.form("style_settings_form"):
        st.markdown("**Thumbnail**")
        tcol1, tcol2 = st.columns(2)
        with tcol1:
            text_color = st.color_picker("Title text color", value=settings.get("thumbnail_text_color", "#FFD700"))
        with tcol2:
            font_size = st.slider("Title font size", min_value=20, max_value=120,
                                   value=int(settings.get("thumbnail_font_size", 56)))
        st.markdown("**Captions (burned-in subtitles)**")
        caption_size = st.slider("Caption font size", min_value=10, max_value=48,
                                  value=int(settings.get("caption_font_size", 20)))
        if st.form_submit_button("💾 Save styling"):
            r = api_client.update_ai_settings({
                "thumbnail_text_color": text_color, "thumbnail_font_size": font_size,
                "caption_font_size": caption_size,
            })
            st.success("Saved — applies to the next thumbnail/video generated or regenerated.") if r["ok"] else st.error(r["error"])

    st.divider()
    st.caption(
        "**Not implemented: Background music volume.** The pipeline has no audio-mixing step at all — "
        "there's no background track to set a volume for. A slider that didn't do anything felt worse "
        "than leaving it out; see MODULE_4_NOTES.md and MODULE_6_NOTES.md for what the pipeline does "
        "and doesn't support."
    )
