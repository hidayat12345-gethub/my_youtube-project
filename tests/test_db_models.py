"""DB model tests — real SQLite (temp file, isolated), no mocking."""


def test_video_ai_disclosure_defaults_to_not_selected(db_session):
    from holy_month.db import Video
    video = Video(title="Test Video", status="pending_review")
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    assert video.ai_disclosure == "not_selected"


def test_video_comments_defaults_to_zero(db_session):
    from holy_month.db import Video
    video = Video(title="Test Video 2", status="pending")
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    assert video.comments == 0


def test_migration_added_ai_disclosure_column():
    """Directly checks the schema, not just the ORM default — this is
    what actually protects an upgrade from an older holy_month.db."""
    from sqlalchemy import text
    from holy_month.db import engine
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
    assert "ai_disclosure" in cols
    assert "comments" in cols


def test_monthly_plan_create_and_query(db_session):
    from holy_month.db import MonthlyPlan
    plan = MonthlyPlan(theme="ramadan", holy_month="Ramadan", target_audience="test audience",
                       language="en", total_videos=5, ideas_json=[{"day": 1, "title": "Test", "summary": "x"}])
    db_session.add(plan)
    db_session.commit()

    fetched = db_session.query(MonthlyPlan).filter(MonthlyPlan.theme == "ramadan").first()
    assert fetched is not None
    assert fetched.total_videos == 5
    assert fetched.current_day == 0  # default
    assert fetched.is_active is True  # default
    assert fetched.ideas_json[0]["title"] == "Test"


def test_video_plan_id_survives_plan_deletion_is_not_automatic():
    """Documents (doesn't just assert) that there's no ORM cascade
    configured — deleting a plan does NOT auto-delete or auto-null its
    videos at the DB layer; that nulling is done explicitly in
    api/routes_plans.py's delete_plan endpoint instead. This test would
    fail loudly if someone added a cascade='all,delete' later without
    realizing it changes that documented behavior."""
    from holy_month.db import MonthlyPlan
    import sqlalchemy
    mapper = sqlalchemy.inspect(MonthlyPlan)
    # No relationship() is defined on MonthlyPlan at all — Video links
    # back via a plain foreign key column, not an ORM relationship.
    assert mapper.relationships.keys() == []
