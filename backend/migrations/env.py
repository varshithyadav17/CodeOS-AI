from logging.config import fileConfig
import asyncio
from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine
from app.config import settings
from app.database import metadata

config = context.config
fileConfig(config.config_file_name)
target_metadata = metadata


def run(connection):
    if connection.dialect.name == "postgresql":
        # A free host can overlap old/new starts. Keep version-table creation
        # and upgrades in one transaction, with one migrator at a time.
        connection.execute(text("SET LOCAL lock_timeout = '60s'"))
        connection.execute(text("SELECT pg_advisory_xact_lock(74007774629715)"))
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(run)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
