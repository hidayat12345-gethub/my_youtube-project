"""
============================================================
CONFIGURATION & ENVIRONMENT BOOTSTRAP
============================================================
Moved verbatim from the original single-file holy_month_automation.py.
Behavior is unchanged: importing this module still auto-installs any
missing packages, still creates .env with defaults if absent (and
exits so the operator can fill in keys), and still exposes the same
Config class with the same attributes.
"""

import os
import sys
import subprocess

# ============================================================
# REQUIREMENTS CHECK - Install Missing Packages
# ============================================================

# import name != pip package name for several of these. Checking
# `import google-generativeai` (invalid syntax target, always
# "missing") would mean pip install runs on every single launch.
_PACKAGE_IMPORT_NAMES = {
    'google-genai': 'google.genai',
    'edge-tts': 'edge_tts',
    'python-dotenv': 'dotenv',
    'google-api-python-client': 'googleapiclient',
    'google-auth-oauthlib': 'google_auth_oauthlib',
    'Pillow': 'PIL',
}


def install_requirements():
    """Auto-install required packages if missing."""
    required = [
        # FIX (audit): removed 'pydantic-settings' — genuinely unused
        # (Config reads via plain os.getenv, not pydantic's
        # BaseSettings). Kept out of both requirements.txt and here so
        # a fresh install doesn't pull a dependency nothing imports.
        'fastapi', 'uvicorn', 'pydantic',
        'sqlalchemy', 'python-dotenv',
        'google-genai', 'edge-tts', 'requests',
        'Pillow', 'google-api-python-client', 'google-auth-oauthlib',
    ]

    missing = []
    for pkg in required:
        import_name = _PACKAGE_IMPORT_NAMES.get(pkg, pkg.replace('-', '_'))
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"📦 Installing missing packages: {', '.join(missing)}")
        for pkg in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
            except subprocess.CalledProcessError:
                # Modern Ubuntu (23.04+) and Debian (12+) block plain
                # `pip install` by default ("externally managed
                # environment", PEP 668) - without this fallback, the
                # "just run it, it installs everything" promise fails
                # immediately on a lot of current systems. A venv is the
                # "proper" fix, but this project is explicitly meant to
                # be zero-setup, so we retry with the override flag
                # instead of forcing venv setup first.
                print(f"   ({pkg}: system pip is locked down — retrying with --break-system-packages)")
                subprocess.check_call([sys.executable, "-m", "pip", "install",
                                        "--break-system-packages", pkg])
        print("✅ All packages installed!")
        return True
    return False


install_requirements()

# Safe to import now that install_requirements() has run.
from dotenv import load_dotenv  # noqa: E402
from google import genai  # noqa: E402

# ============================================================
# ENVIRONMENT SETUP
# ============================================================

ENV_PATH = '.env'

if not os.path.exists(ENV_PATH):
    with open(ENV_PATH, 'w') as f:
        f.write("""# ============================================================
# HOLY MONTH AI - API KEYS (all free-tier services)
# ============================================================

# Google Gemini - free tier, get key at https://aistudio.google.com/apikey
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

# YouTube OAuth - free. Create an OAuth Client ID (Desktop app) at
# https://console.cloud.google.com/apis/credentials, then run:
#   python holy_month_automation.py youtube-auth
# which fills in YOUTUBE_REFRESH_TOKEN below automatically.
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=
YOUTUBE_REFRESH_TOKEN=

# Telegram Bot (from @BotFather on Telegram) - free
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Human review gate - videos upload as UNLISTED and wait for your
# approval (POST /api/v1/videos/{id}/approve) before going public.
# Recommended to keep this "true", especially for religious citations.
REQUIRE_HUMAN_REVIEW=true

# If a pending_review video hasn't been manually approved within this
# many hours, it is auto-approved (made public) automatically so the
# daily-upload cadence never silently stalls. Set to 0 to disable.
AUTO_APPROVE_AFTER_HOURS=20

# What hour (0-23, server local time) the daily scheduler checks
# whether it's time to produce the next video in each active plan.
PUBLISH_HOUR=8
SCHEDULER_CHECK_INTERVAL_MINUTES=15

# System Settings
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=change-this-to-a-secret-key
""")
    print("✅ Created .env file! Please add your API keys and restart.")
    sys.exit(0)

load_dotenv(ENV_PATH)


# ============================================================
# CONFIGURATION
# ============================================================

class Config:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')

    YOUTUBE_CLIENT_ID = os.getenv('YOUTUBE_CLIENT_ID', '')
    YOUTUBE_CLIENT_SECRET = os.getenv('YOUTUBE_CLIENT_SECRET', '')
    YOUTUBE_REFRESH_TOKEN = os.getenv('YOUTUBE_REFRESH_TOKEN', '')

    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

    REQUIRE_HUMAN_REVIEW = os.getenv('REQUIRE_HUMAN_REVIEW', 'true').lower() == 'true'
    PUBLISH_HOUR = int(os.getenv('PUBLISH_HOUR', '8'))
    SCHEDULER_CHECK_INTERVAL_MINUTES = int(os.getenv('SCHEDULER_CHECK_INTERVAL_MINUTES', '15'))

    # NEW: auto-approval window. A pending_review video that hasn't been
    # manually approved within this many hours gets auto-published by
    # the scheduler / produce-today sweep, so the daily cadence never
    # silently stalls on a missed manual review. 0 disables the sweep.
    AUTO_APPROVE_AFTER_HOURS = float(os.getenv('AUTO_APPROVE_AFTER_HOURS', '20'))

    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    DEBUG = os.getenv('DEBUG', 'true').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')

    # FIX (audit): was previously hardcoded to "*" in main.py's CORS
    # middleware, which accepts requests from ANY origin — fine for a
    # dashboard running on the same machine, a real gap the moment this
    # is reachable from anywhere else. Defaults to localhost-only
    # Streamlit ports; override via .env for a non-default dashboard
    # port or a genuinely remote setup. Comma-separated.
    ALLOWED_ORIGINS = [o.strip() for o in
                        os.getenv('ALLOWED_ORIGINS', 'http://localhost:8501,http://127.0.0.1:8501').split(',')
                        if o.strip()]

    # FIX (audit): opt-in shared-secret protection for mutating API
    # endpoints — see holy_month/api/security.py for the full reasoning.
    # Empty by default = local/dev mode, unchanged from before.
    API_ACCESS_TOKEN = os.getenv('API_ACCESS_TOKEN', '')

    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./holy_month.db')

    VIDEO_RESOLUTION = '1080p'
    OUTPUT_DIR = os.path.join(os.getcwd(), 'output_videos')
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    @classmethod
    def check_keys(cls):
        missing = []
        if not cls.GEMINI_API_KEY:
            missing.append('GEMINI_API_KEY')
        if not cls.TELEGRAM_BOT_TOKEN:
            missing.append('TELEGRAM_BOT_TOKEN')
        if not cls.TELEGRAM_CHAT_ID:
            missing.append('TELEGRAM_CHAT_ID')
        if not cls.YOUTUBE_CLIENT_ID or not cls.YOUTUBE_CLIENT_SECRET:
            missing.append('YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET')

        if missing:
            print("⚠️  Missing configuration in .env file:")
            for key in missing:
                print(f"   - {key}")
            print("\nPlease add them and restart.")
            return False

        if not cls.YOUTUBE_REFRESH_TOKEN:
            print("⚠️  YouTube not authorized yet. Run this once:")
            print("   python holy_month_automation.py youtube-auth")
            return False
        return True


_genai_client = genai.Client(api_key=Config.GEMINI_API_KEY) if Config.GEMINI_API_KEY else None


def get_genai_client():
    """Accessor so other modules don't import the private module-level
    client directly (keeps the client lazily-testable/mockable)."""
    return _genai_client
