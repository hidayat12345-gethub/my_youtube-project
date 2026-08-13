import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title

st.set_page_config(page_title="About — Holy Month AI", page_icon="ℹ️", layout="wide")
inject_css(st)

with st.sidebar:
    st.markdown("## 🕌 Holy Month AI")
    backend_live = api_client.is_backend_available()
    st.success("🟢 Live backend connected") if backend_live else st.info("📖 Read-only mode")

st.markdown(
    '<div class="hm-section-title"><div class="bar"></div>'
    '<span style="font-size:1.6rem;">About</span></div>',
    unsafe_allow_html=True,
)

st.markdown(
    "**Holy Month AI** produces one Islamic educational YouTube video per day, fully "
    "automated, on free-tier services end to end — no paid API required to run it."
)

section_title(st, "Pipeline")
st.markdown(
    "Each video goes through 9 steps: **Research** (Quran/Hadith/facts via Gemini) → "
    "**Script** (hook, intro, body scenes, ending, CTA) → **Voice** (edge-tts, one clip "
    "per scene) → **Images** (Pollinations.ai, one per scene) → **Thumbnail** → "
    "**Assembly** (ffmpeg, scene durations matched exactly to narration length) → "
    "**SEO** → **Upload** (unlisted, pending your review) → **Notify** (Telegram)."
)
st.caption(
    "Ideas for a whole month are generated once, up front, and stored — so 'Day 12' "
    "always means the same topic, not something re-picked fresh (and possibly "
    "differently) every day."
)

section_title(st, "Two ways to run it")
rcol1, rcol2 = st.columns(2)
with rcol1:
    st.markdown("**GitHub Actions** (free, no owned machine)")
    st.caption(
        "A daily cron job (`daily-video.yml`) checks out the repo, produces one video, "
        "commits `holy_month.db` back. Nothing needs to stay running on your end. This "
        "dashboard reads that same `holy_month.db` directly — read-only, no server needed."
    )
with rcol2:
    st.markdown("**`web` mode** (a machine that stays on)")
    st.caption(
        "`python holy_month_automation.py web` runs a persistent FastAPI server with its "
        "own scheduler loop. Unlocks every live action in this dashboard — approve, "
        "reject, edit, regenerate, plan management, live YouTube stats."
    )

section_title(st, "Human review & consistency")
st.markdown(
    "Every video uploads **unlisted** and waits for approval — Gemini can misattribute a "
    "hadith's grading or a verse's numbering, so a human checking citations before "
    "anything goes public matters for this kind of content. If nothing reviews it within "
    "**20 hours** (configurable via `AUTO_APPROVE_AFTER_HOURS` in `.env`), it publishes "
    "itself automatically so the daily cadence never silently stalls."
)

section_title(st, "What this dashboard adds on top of the original pipeline")
st.markdown(
    "- Modular backend (was a single 1,580-line file)\n"
    "- The 20h auto-approval sweep\n"
    "- Full plan CRUD: edit, delete, duplicate, regenerate future ideas\n"
    "- Video Editor: metadata, script editing, full regeneration (pre-publish only), thumbnail regeneration\n"
    "- Real YouTube stats sync (views/likes/comments/subscribers/watch-time) — nothing collected this before\n"
    "- Editable AI prompt templates + temperature control\n"
    "- Persisted logs (the pipeline only ever used `print()` before)\n"
    "- DB backup/restore, output-folder cleanup"
)

section_title(st, "Known limitations")
st.markdown(
    "- **No background music support** — the pipeline has no audio-mixing step at all.\n"
    "- **No settable video duration** — each scene's length comes from its own narration time, not a target you choose.\n"
    "- **Can't regenerate an already-published video** — YouTube has no 'replace footage' API, only delete+reupload, which would break a live link.\n"
    "- **Logs don't persist for GitHub Actions runs** — that runner is thrown away each run; check the Actions tab for those.\n"
    "- **No authentication** on the backend API or this dashboard — fine for local/personal use, a real gap if either is ever exposed beyond your own machine.\n"
    "- **Not live-tested end-to-end** — built and verified for syntax correctness, but the environment this was built in has no network access to actually install and run FastAPI/Streamlit/edge-tts/ffmpeg together. Test locally before trusting it with a real month."
)

st.divider()
st.caption("Built module-by-module — see MODULE_1_NOTES.md through MODULE_6_NOTES.md for what shipped in each one.")
