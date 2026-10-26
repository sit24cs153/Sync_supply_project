"""
Alembic migration environment. Reads DATABASE_URL from the app's own
settings (same .env the API uses) rather than duplicating it in
alembic.ini, so migrations always target the same database the app will
actually run against.

This is the schema-migration path — distinct from app/data_loader.py,
which only loads/updates CSV *content* into existing tables.
Base.metadata.create_all() (used at app startup for a fresh dev DB) is
convenient for local SQLite but is not a migration tool: it only ever adds
tables that don't exist yet and never alters or drops anything.  For any
real schema change against a production Postgres database, generate and
apply an Alembic migration instead:

    alembic revision --autogenerate -m "describe the change"
    alembic upgrade head
"""
import sys
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings
from app.database import Base
from app import models  # noqa: F401 — registers all tables on Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
