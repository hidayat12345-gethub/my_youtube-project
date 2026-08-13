"""Shared visual language for every dashboard page: CSS injection,
status → color/label mapping, and small HTML-snippet builders (cards,
badges) so pages don't repeat markup.

Palette intentionally reuses the navy/gold combination the pipeline
itself already renders onto thumbnails and fallback scene cards
(ImageGenerationAgent / ThumbnailAgent use navy #0d1b2a + gold
#ffd700) — so the dashboard visually matches the videos it's managing
instead of introducing an unrelated color scheme.
"""

# Mirrors holy_month/services/video_editor.py's REGENERATABLE_STATUSES —
# duplicated here (rather than imported) because the dashboard is
# deliberately kept independent of the backend package's dependency
# chain (see dashboard/README.md).
REGENERATABLE_STATUSES = {"pending_review", "rejected", "failed", "saved_locally"}

STATUS_META = {
    "pending":        {"label": "Pending",         "color": "#94A3B8", "bg": "rgba(148,163,184,0.15)"},
    "producing":      {"label": "Producing",       "color": "#3B82F6", "bg": "rgba(59,130,246,0.15)"},
    "pending_review": {"label": "Pending Review",  "color": "#F59E0B", "bg": "rgba(245,158,11,0.15)"},
    "published":      {"label": "Published",       "color": "#22C55E", "bg": "rgba(34,197,94,0.15)"},
    "auto_published": {"label": "Auto-Published",  "color": "#22C55E", "bg": "rgba(34,197,94,0.15)"},
    "rejected":       {"label": "Rejected",        "color": "#EF4444", "bg": "rgba(239,68,68,0.15)"},
    "failed":         {"label": "Failed",          "color": "#EF4444", "bg": "rgba(239,68,68,0.15)"},
    "saved_locally":  {"label": "Saved Locally",   "color": "#A78BFA", "bg": "rgba(167,139,250,0.15)"},
}


def status_badge_html(status: str) -> str:
    meta = STATUS_META.get(status, {"label": status or "Unknown", "color": "#94A3B8", "bg": "rgba(148,163,184,0.15)"})
    return (f'<span class="hm-badge" style="color:{meta["color"]};background:{meta["bg"]};'
            f'border:1px solid {meta["color"]}55;">{meta["label"]}</span>')


CSS = """
<style>
:root {
    --hm-navy: #0b1220;
    --hm-navy-soft: #111a2e;
    --hm-card: rgba(255,255,255,0.045);
    --hm-border: rgba(255,215,0,0.14);
    --hm-gold: #ffd700;
    --hm-gold-soft: #f4c430;
    --hm-text: #e6e8eb;
    --hm-text-muted: #94a3b8;
}

.stApp {
    background:
        radial-gradient(1200px 600px at 15% -10%, rgba(255,215,0,0.06), transparent 60%),
        radial-gradient(1000px 500px at 100% 0%, rgba(59,130,246,0.05), transparent 55%),
        var(--hm-navy);
}

section[data-testid="stSidebar"] {
    background: var(--hm-navy-soft);
    border-right: 1px solid var(--hm-border);
}
section[data-testid="stSidebar"] * { color: var(--hm-text) !important; }

h1, h2, h3, h4, p, span, label, div { color: var(--hm-text); }

/* ---- Glass cards ---- */
.hm-card {
    background: var(--hm-card);
    border: 1px solid var(--hm-border);
    border-radius: 16px;
    padding: 20px 22px;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.25);
    margin-bottom: 14px;
}
.hm-card-title {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--hm-text-muted);
    margin-bottom: 6px;
}
.hm-card-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--hm-text);
}
.hm-card-sub {
    font-size: 0.78rem;
    color: var(--hm-text-muted);
    margin-top: 4px;
}

/* ---- Status badge pill ---- */
.hm-badge {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}

/* ---- Section header with gold accent bar ---- */
.hm-section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 6px 0 14px 0;
}
.hm-section-title .bar {
    width: 4px;
    height: 22px;
    background: linear-gradient(180deg, var(--hm-gold), var(--hm-gold-soft));
    border-radius: 3px;
}
.hm-section-title span {
    font-size: 1.15rem;
    font-weight: 700;
}

/* ---- Buttons ---- */
.stButton > button {
    border-radius: 10px;
    border: 1px solid var(--hm-border);
    font-weight: 600;
}
.stButton > button:hover {
    border-color: var(--hm-gold);
    color: var(--hm-gold);
}

/* ---- Dataframe / table polish ---- */
[data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

/* ---- Countdown chip ---- */
.hm-countdown {
    font-family: ui-monospace, monospace;
    font-size: 0.8rem;
    padding: 2px 8px;
    border-radius: 6px;
    background: rgba(245,158,11,0.12);
    color: #F59E0B;
    border: 1px solid rgba(245,158,11,0.35);
}
.hm-countdown.overdue {
    background: rgba(239,68,68,0.12);
    color: #EF4444;
    border-color: rgba(239,68,68,0.35);
}
</style>
"""


def inject_css(st):
    st.markdown(CSS, unsafe_allow_html=True)


def metric_card(st, title: str, value: str, sub: str = ""):
    st.markdown(
        f'<div class="hm-card"><div class="hm-card-title">{title}</div>'
        f'<div class="hm-card-value">{value}</div>'
        f'{f"<div class=hm-card-sub>{sub}</div>" if sub else ""}</div>',
        unsafe_allow_html=True,
    )


def section_title(st, text: str):
    st.markdown(
        f'<div class="hm-section-title"><div class="bar"></div><span>{text}</span></div>',
        unsafe_allow_html=True,
    )
