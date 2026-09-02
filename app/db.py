import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

logger = logging.getLogger(__name__)

# pool_pre_ping avoids "server closed the connection unexpectedly" errors
# after the DB has been idle — cheap insurance for a long-running API.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_lightweight_migrations():
    """No Alembic yet -- this is the stopgap. `Base.metadata.create_all()`
    only creates tables that don't exist; it never adds columns to a table
    that's already there. Without this, adding a column to a model and
    deploying against an existing database (like Render's Postgres) causes
    every insert to fail with "column does not exist".

    This adds any missing columns as NULLable, regardless of the model's
    nullable=False -- existing rows can't retroactively get a NOT NULL
    value, so we don't try to enforce that at the DB level here. New rows
    still get the Python-side default via the ORM.

    Fine for a solo project; replace with real Alembic migrations once
    more than one person touches this schema.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  # brand-new table -- create_all() already handles this

            existing_columns = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing_columns:
                    continue

                col_type = column.type.compile(engine.dialect)
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'
                logger.info("Auto-migration: %s", ddl)
                conn.execute(text(ddl))
