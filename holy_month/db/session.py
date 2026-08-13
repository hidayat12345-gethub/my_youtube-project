from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from holy_month.config import Config
from .models import Base

engine = create_engine(Config.DATABASE_URL, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)


def _ensure_schema_migrations():
    """create_all() only creates missing TABLES, not new COLUMNS on a
    table that already exists — so an existing holy_month.db from
    before Module 5 (comments) or this audit (ai_disclosure) won't have
    those columns yet. Adds any missing ones in place (SQLite ALTER
    TABLE ADD COLUMN is safe and non-destructive) instead of requiring
    anyone to manually migrate or, worse, drop and lose their existing
    video history.

    Wrapped defensively: this project only ships targeting SQLite
    (PRAGMA table_info is SQLite-specific), so if DATABASE_URL was
    pointed at something else, this quietly no-ops rather than
    crashing app startup over a non-essential migration step."""
    # column_name -> ALTER TABLE ... ADD COLUMN fragment
    required_columns = {
        "comments": "comments INTEGER DEFAULT 0",
        "ai_disclosure": "ai_disclosure VARCHAR(20) DEFAULT 'not_selected'",
    }
    try:
        with engine.connect() as conn:
            existing_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(videos)"))}
            for col_name, ddl_fragment in required_columns.items():
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE videos ADD COLUMN {ddl_fragment}"))
                    conn.commit()
                    print(f"🔧 Migrated schema: added videos.{col_name} column.")
    except Exception as e:
        print(f"⚠️  Schema migration check skipped ({e}) — fine unless you're missing "
              f"one of {list(required_columns)}, in which case add it manually.")


_ensure_schema_migrations()

SessionLocal = sessionmaker(bind=engine)
