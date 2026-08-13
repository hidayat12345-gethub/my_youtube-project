import sys
import os

import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db_reader as db
import api_client
from style import inject_css, section_title

st.set_page_config(page_title="System Settings — Holy Month AI", page_icon="⚙️", layout="wide")
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
    '<span style="font-size:1.6rem;">System Settings</span></div>',
    unsafe_allow_html=True,
)

# ============================================================
# HEALTH CHECK
# ============================================================
section_title(st, "Health Check")
if backend_live:
    import requests
    try:
        health = requests.get(f"{api_client.DEFAULT_BASE_URL}/health", timeout=5).json()
        hcols = st.columns(6)
        checks = [
            ("Gemini", health["config"]["gemini"]),
            ("YouTube", health["config"]["youtube_authorized"]),
            ("Telegram", health["config"]["telegram"]),
            ("FFmpeg", health["config"]["ffmpeg"]),
            ("Database", True),
            ("Backend", True),
        ]
        for col, (label, ok) in zip(hcols, checks):
            with col:
                icon = "🟢" if ok else "🔴"
                st.markdown(
                    f'<div class="hm-card" style="text-align:center;padding:14px;">'
                    f'<div style="font-size:1.4rem;">{icon}</div>'
                    f'<div class="hm-card-sub" style="margin-top:6px;">{label}</div></div>',
                    unsafe_allow_html=True,
                )
        if not health["config"]["ffmpeg"]:
            st.error("FFmpeg not found on the backend's machine — video assembly will fail. "
                     "Install it: `sudo apt install ffmpeg` (Ubuntu) or `brew install ffmpeg` (Mac).")
    except Exception as e:
        st.error(f"Health check failed: {e}")
else:
    cfg = db.fetch_config_status()
    st.info("Showing config presence from .env (read-only) — connect a live backend "
            "for a full health check including FFmpeg.")
    hcols = st.columns(4)
    for col, (label, ok) in zip(hcols, [("Gemini", cfg["gemini"]), ("YouTube", cfg["youtube_authorized"]),
                                          ("Telegram", cfg["telegram"]), ("Database", db.db_exists())]):
        with col:
            st.markdown(f"{'🟢' if ok else '⚪'} {label}")

st.write("")

# ============================================================
# OUTPUT FOLDER
# ============================================================
section_title(st, "Output Folder")
if not backend_live:
    st.info("Connect a live backend to browse/clean up the output folder.")
else:
    folder_result = api_client.get_output_folder()
    if not folder_result["ok"]:
        st.error(folder_result["error"])
    else:
        data = folder_result["data"]
        total_mb = data["total_size_bytes"] / (1024 * 1024)
        ocol1, ocol2, ocol3 = st.columns(3)
        with ocol1:
            st.metric("Total size", f"{total_mb:.1f} MB")
        with ocol2:
            st.metric("Final files", len(data["final_files"]))
        with ocol3:
            st.metric("Temp work folders", len(data["temp_dirs"]))

        if data["temp_dirs"]:
            temp_mb = sum(d["size_bytes"] for d in data["temp_dirs"]) / (1024 * 1024)
            st.caption(f"Temp folders (`work_*`/`regen_*`) are holding **{temp_mb:.1f} MB**. "
                       "Cleanup only removes folders no video currently references "
                       "(thumbnails live inside these folders, so this checks first).")
            if st.button("🧹 Clean up unreferenced temp folders"):
                with st.spinner("Checking every temp folder against the database before removing anything..."):
                    r = api_client.cleanup_temp_folders()
                if r["ok"]:
                    freed_mb = r["data"]["freed_bytes"] / (1024 * 1024)
                    st.success(f"Removed {len(r['data']['removed'])} folder(s), freed {freed_mb:.1f} MB.")
                    st.rerun()
                else:
                    st.error(r["error"])
        else:
            st.caption("No temp folders to clean up.")

        with st.expander("Final files"):
            for f in data["final_files"][:30]:
                st.caption(f"{f['name']} — {f['size_bytes']/1024/1024:.1f} MB — {f['modified'][:16]}")

st.write("")

# ============================================================
# BACKUP / RESTORE
# ============================================================
section_title(st, "Backup & Restore")
if not backend_live:
    st.info("Connect a live backend for backup/restore.")
else:
    bcol1, bcol2 = st.columns(2)
    with bcol1:
        st.markdown("**Backup**")
        db_bytes = api_client.download_backup_bytes()
        if db_bytes:
            st.download_button("⬇️ Download current database", data=db_bytes,
                                file_name="holy_month_backup.db", mime="application/octet-stream")
        if st.button("📸 Create server-side snapshot"):
            r = api_client.snapshot_db()
            st.success(f"Snapshot saved: {r['data']['path']}") if r["ok"] else st.error(r["error"])

        snaps = api_client.list_snapshots()
        if snaps["ok"] and snaps["data"]["snapshots"]:
            with st.expander(f"Server-side snapshots ({len(snaps['data']['snapshots'])})"):
                for s in snaps["data"]["snapshots"][:10]:
                    st.caption(f"{s['name']} — {s['size_bytes']/1024/1024:.1f} MB — {s['modified'][:16]}")

    with bcol2:
        st.markdown("**Restore**")
        st.warning("⚠️ This overwrites the live database. The current DB is auto-snapshotted "
                   "first (so this is reversible), but restart the server afterward — swapping "
                   "the file underneath a running connection isn't a fully clean hot-swap for SQLite.")
        uploaded = st.file_uploader("Upload a holy_month.db file", type=["db"])
        if uploaded is not None:
            confirm_key = "confirm_restore"
            if not st.session_state.get(confirm_key):
                if st.button("Restore from this file"):
                    st.session_state[confirm_key] = True
                    st.rerun()
            else:
                st.error("Are you sure? This replaces the live database right now.")
                if st.button("⚠️ Yes, restore now", type="primary"):
                    r = api_client.restore_db(uploaded.getvalue(), uploaded.name)
                    if r["ok"]:
                        st.success(r["data"]["message"])
                    else:
                        st.error(r["error"])
                    st.session_state[confirm_key] = False
