"""Settings store tests. Uses tests/conftest.py's isolated temp
directory — holy_month_settings.json here is a throwaway test file,
never the real one."""


def test_defaults_before_any_write():
    from holy_month.services import settings_store
    settings_store.reset_settings()
    settings = settings_store.get_all_settings()
    assert settings["gemini_temperature"] == 0.9
    assert settings["thumbnail_text_color"] == "#FFD700"
    assert settings["gemini_model"] is None


def test_update_settings_persists_and_merges():
    from holy_month.services import settings_store
    settings_store.reset_settings()
    settings_store.update_settings({"gemini_temperature": 0.5})
    settings = settings_store.get_all_settings()
    assert settings["gemini_temperature"] == 0.5
    # untouched keys keep their defaults — this was a merge, not a replace
    assert settings["thumbnail_text_color"] == "#FFD700"


def test_unknown_keys_are_silently_ignored_not_persisted():
    """update_settings() only accepts keys already in DEFAULTS — this
    guards against a typo'd key (e.g. from a future API version
    mismatch) silently growing the settings file with junk."""
    from holy_month.services import settings_store
    settings_store.reset_settings()
    settings_store.update_settings({"totally_made_up_key": "should not appear"})
    settings = settings_store.get_all_settings()
    assert "totally_made_up_key" not in settings


def test_get_setting_single_key():
    from holy_month.services import settings_store
    settings_store.reset_settings()
    settings_store.update_settings({"caption_font_size": 30})
    assert settings_store.get_setting("caption_font_size") == 30


def test_reset_settings_restores_all_defaults():
    from holy_month.services import settings_store
    settings_store.update_settings({"gemini_temperature": 1.9, "caption_font_size": 40})
    settings_store.reset_settings()
    settings = settings_store.get_all_settings()
    assert settings["gemini_temperature"] == 0.9
    assert settings["caption_font_size"] == 20


def test_corrupted_settings_file_falls_back_to_defaults():
    """If holy_month_settings.json somehow gets corrupted (partial
    write, manual edit gone wrong), the app should still boot with
    defaults rather than crash on every settings read."""
    from holy_month.services import settings_store
    with open(settings_store.SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.write("{not valid json,,,")
    settings = settings_store.get_all_settings()
    assert settings["gemini_temperature"] == 0.9  # fell back to default, didn't crash
    settings_store.reset_settings()  # clean up for other tests
