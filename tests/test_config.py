"""Config tests — verifies the audit's new settings (ALLOWED_ORIGINS,
API_ACCESS_TOKEN) parse correctly, and existing settings are untouched."""


def test_allowed_origins_parses_comma_separated_list():
    from holy_month.config import Config
    assert Config.ALLOWED_ORIGINS == ["http://localhost:8501"]


def test_api_access_token_defaults_empty_string():
    """Empty = local/dev mode, no auth required — see api/security.py."""
    from holy_month.config import Config
    assert Config.API_ACCESS_TOKEN == ""


def test_auto_approve_after_hours_is_float():
    from holy_month.config import Config
    assert isinstance(Config.AUTO_APPROVE_AFTER_HOURS, float)
    assert Config.AUTO_APPROVE_AFTER_HOURS == 20.0


def test_require_human_review_parses_bool_from_env_string():
    from holy_month.config import Config
    assert Config.REQUIRE_HUMAN_REVIEW is True


def test_database_url_points_at_isolated_test_db():
    """Guards against a test run ever accidentally touching a real
    holy_month.db — if this assertion ever fails, STOP, because it
    means test isolation broke."""
    from holy_month.config import Config
    assert "test_holy_month.db" in Config.DATABASE_URL
