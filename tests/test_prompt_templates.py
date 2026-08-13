"""Prompt template tests. Uses string.Template ($placeholders), not
str.format — see holy_month/services/prompt_templates.py for why
(prompts contain literal JSON braces)."""


def test_default_planner_template_renders_with_placeholders():
    from holy_month.services import prompt_templates
    rendered = prompt_templates.render(
        "planner", count=5, theme="ramadan", holy_month="Ramadan",
        target_audience="new Muslims", language="en",
    )
    assert "Generate exactly 5 video ideas" in rendered
    assert '"ramadan"' in rendered
    assert "new Muslims" in rendered


def test_default_templates_contain_no_unescaped_curly_placeholders():
    """Regression guard: if someone edits a default template and
    accidentally reintroduces {curly} placeholders instead of
    $placeholders, string.Template will just ignore them silently
    (they're not $identifiers) — meaning the placeholder never gets
    filled and Gemini receives a literal '{theme}' in the prompt. This
    test at least confirms the CURRENT defaults render with all their
    real ($-prefixed) placeholders replaced, i.e. produce no leftover
    '$' followed by a known variable name."""
    from holy_month.services import prompt_templates
    rendered = prompt_templates.render(
        "planner", count=3, theme="X", holy_month="Y", target_audience="Z", language="en",
    )
    for leftover in ("$count", "$theme", "$holy_month", "$target_audience", "$language"):
        assert leftover not in rendered


def test_set_and_get_template_round_trips():
    from holy_month.services import prompt_templates
    custom_text = "Custom research prompt for $topic in theme $theme."
    prompt_templates.set_template("research", custom_text)
    assert prompt_templates.get_template("research") == custom_text
    # cleanup — don't leak state into other tests
    prompt_templates.reset_template("research")


def test_reset_template_restores_default():
    from holy_month.services import prompt_templates
    original = prompt_templates.get_template("script_writer")
    prompt_templates.set_template("script_writer", "temporary override")
    assert prompt_templates.get_template("script_writer") == "temporary override"
    restored = prompt_templates.reset_template("script_writer")
    assert restored == original
    assert prompt_templates.get_template("script_writer") == original


def test_unknown_template_key_raises():
    from holy_month.services import prompt_templates
    import pytest
    with pytest.raises(KeyError):
        prompt_templates.set_template("not_a_real_template", "text")


def test_render_falls_back_to_default_on_missing_placeholder():
    """If a user-edited template references a placeholder that isn't
    supplied at render time (e.g. a typo), render() should fall back
    to the default template rather than crash production."""
    from holy_month.services import prompt_templates
    prompt_templates.set_template("research", "This references $nonexistent_placeholder only.")
    # research is normally called with topic= and theme= — neither
    # matches $nonexistent_placeholder, so this should NOT raise, and
    # should instead fall back to the real default template.
    result = prompt_templates.render("research", topic="Test Topic", theme="ramadan")
    assert "Test Topic" in result  # came from the DEFAULT template, which does use $topic
    prompt_templates.reset_template("research")
