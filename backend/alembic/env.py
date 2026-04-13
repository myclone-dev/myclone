from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from shared.database.base import Base
from shared.database.config import POSTGRES_HOST, get_database_url

# Import all models to register with Base.metadata for Alembic autogenerate
from shared.database.models import (  # noqa: F401
    database,
    document,
    linkedin,
    livekit,
    persona,
    scraping,
    twitter,
    user,
    user_session,
    voice_clone,
    website,
)
from shared.database.voice_job_model import VoiceProcessingJob  # noqa: F401

config = context.config

# Convert async URL to sync for Alembic (psycopg2)
database_url = get_database_url()
if database_url.startswith("postgresql+asyncpg://"):
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    # psycopg2 requires explicit SSL for RDS (asyncpg handles it automatically)
    # Docker postgres (hostname 'postgres') doesn't support SSL
    if POSTGRES_HOST in ("postgres", "localhost", "127.0.0.1"):
        database_url += "?sslmode=disable"
    else:
        # Production (RDS, etc.) requires SSL
        database_url += "?sslmode=require"
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    """
    Filter out tables we don't want Alembic to track.
    This is used to ignore LlamaIndex-created tables and Voyage AI embeddings table.
    """
    if type_ == "table":
        # Ignore Voyage AI embedding table (managed separately)
        if name in [
            "data_llamaindex_embeddings",
            "data_data_llamaindex_embeddings",
            "data_llamalite_embeddings",
        ]:
            return False
    return True


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
