"""Test harness setup.

IMPORTANT — a real quirk this works around: holy_month.config.settings
calls sys.exit(0) on first import if no .env exists in the current
working directory (intentional first-run UX for real users: "I created
a template, fill it in and restart"). Correct for a person running the
app, but it would kill a test run stumbling into a directory with no
.env.

ORDERING MATTERS HERE: pytest imports every conftest.py before it
collects/imports test files in that directory. A fixture (even
autouse, even session-scoped) only runs at TEST-RUN time, which is
after collection — too late, since a test file's own
`from holy_month... import ...` at module level would already have
triggered the exit during collection. So the working-directory and
.env setup below happens as plain MODULE-LEVEL code in this file, not
inside a fixture, specifically so it runs before any test file gets
imported.

This creates an isolated temp directory with a throwaway .env (fake,
non-functional credentials — NEVER real ones) and an isolated SQLite
file, so: tests never touch your real holy_month.db or .env, tests
never make real Gemini/YouTube/Telegram calls (nothing here has real
credentials, and every test that would cross a network boundary mocks
it explicitly), and the DB starts empty and fresh for every test
session.
"""

import atexit
import os
import shutil
import sys
import tempfile

_TEST_ENV_CONTENT = """\
GEMINI_API_KEY=test-fake-key-not-real
GEMINI_MODEL=gemini-2.5-flash
YOUTUBE_CLIENT_ID=test-fake-client-id
YOUTUBE_CLIENT_SECRET=test-fake-client-secret
YOUTUBE_REFRESH_TOKEN=test-fake-refresh-token
TELEGRAM_BOT_TOKEN=test-fake-bot-token
TELEGRAM_CHAT_ID=test-fake-chat-id
REQUIRE_HUMAN_REVIEW=true
AUTO_APPROVE_AFTER_HOURS=20
PUBLISH_HOUR=8
SCHEDULER_CHECK_INTERVAL_MINUTES=15
ENVIRONMENT=test
DEBUG=true
SECRET_KEY=test-secret-key
DATABASE_URL=sqlite:///./test_holy_month.db
ALLOWED_ORIGINS=http://localhost:8501
API_ACCESS_TOKEN=
"""

_original_cwd = os.getcwd()
_tmp_dir = tempfile.mkdtemp(prefix="holy_month_test_")
os.chdir(_tmp_dir)
with open(".env", "w", encoding="utf-8") as _f:
    _f.write(_TEST_ENV_CONTENT)

for _mod_name in list(sys.modules):
    if _mod_name == "holy_month" or _mod_name.startswith("holy_month."):
        del sys.modules[_mod_name]


def _cleanup():
    os.chdir(_original_cwd)
    shutil.rmtree(_tmp_dir, ignore_errors=True)


atexit.register(_cleanup)


def get_test_dir() -> str:
    """For any test that needs the isolated temp dir's path directly
    (e.g. checking a file the app wrote)."""
    return _tmp_dir


import pytest  # noqa: E402  (after the sys.path/env setup above, deliberately)


@pytest.fixture
def db_session():
    """A real (temp-file-backed) DB session against the isolated test
    database — not mocked, since exercising real SQLAlchemy queries is
    more valuable than mocking the DB layer itself."""
    from holy_month.db import SessionLocal
    session = SessionLocal()
    yield session
    session.close()
