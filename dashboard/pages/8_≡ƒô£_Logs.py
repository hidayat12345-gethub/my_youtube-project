import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
import logs_reader
from style import inject_css, section_title

st.set_page_config(page_title="Logs — Holy Month AI", page_icon="📜", layout="wide")
inject_css(st)

with st.sidebar:
    st.markdown("## 🕌 Holy Month AI")
    backend_live = api_client.is_backend_available()
    st.success("🟢 Live backend connected") if backend_live else st.info("📖 Read-only mode")

st.markdown(
    '<div class="hm-section-title"><div class="bar"></div>'
    '<span style="font-size:1.6rem;">Logs</span></div>',
    unsafe_allow_html=True,
)

st.info(
    "**GitHub Actions deployment:** each `produce-today` run happens on a fresh, throwaway "
    "runner — logs from a given day live in that run's output on GitHub's own **Actions** tab, "
    "not here. This page shows logs from a `web` mode process running on the same machine as "
    "this dashboard (or wherever `HOLY_MONTH_LOG_PATH` points)."
)

local_log_exists = logs_reader.log_exists()

if not local_log_exists and backend_live:
    st.caption("No local log file found — pulling the tail from the live backend instead.")
    log_text = api_client.get_logs(lines=500)
elif local_log_exists:
    log_text = logs_reader.read_log_tail(max_lines=1000)
else:
    log_text = ""

if not log_text:
    st.info("No logs yet. Logs start accumulating once `web` mode or `produce-today` runs at "
            "least once on this machine.")
    st.stop()

# ============================================================
# FILTERS
# ============================================================
fcol1, fcol2 = st.columns([1, 2])
with fcol1:
    level_filter = st.selectbox("Filter", ["All", "Errors only", "Warnings only", "Errors & Warnings"])
with fcol2:
    search = st.text_input("Search", placeholder="e.g. Gemini, upload, Day 12")

lines = log_text.splitlines()

def _matches_level(line: str) -> bool:
    if level_filter == "All":
        return True
    is_error = "❌" in line or "error" in line.lower()
    is_warning = "⚠️" in line or "warning" in line.lower()
    if level_filter == "Errors only":
        return is_error
    if level_filter == "Warnings only":
        return is_warning
    if level_filter == "Errors & Warnings":
        return is_error or is_warning
    return True

filtered = [ln for ln in lines if _matches_level(ln) and (not search or search.lower() in ln.lower())]

st.caption(f"Showing {len(filtered)} of {len(lines)} lines.")

st.markdown(
    f'<div class="hm-card" style="font-family:ui-monospace,monospace;font-size:0.8rem;'
    f'max-height:600px;overflow-y:auto;white-space:pre-wrap;line-height:1.5;">'
    + "\n".join(ln.replace("<", "&lt;").replace(">", "&gt;") for ln in filtered[-500:])
    + "</div>",
    unsafe_allow_html=True,
)

st.write("")
dcol1, dcol2 = st.columns(2)
with dcol1:
    st.download_button("⬇️ Download visible log tail", data="\n".join(filtered),
                        file_name="holy_month_log_tail.txt", mime="text/plain")
with dcol2:
    if local_log_exists:
        full_log = logs_reader.read_log_full()
        st.download_button("⬇️ Download full local log file", data=full_log,
                            file_name="holy_month.log", mime="text/plain")
