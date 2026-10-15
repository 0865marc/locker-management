import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from adapters.database.connection import get_database_url

# Importar los modelos registra las tablas que compara Alembic.
from adapters.database.sqlmodel_repositories import DeliveryRow, ReturnRow
from adapters.database.sqlmodel_lockers import LockerRow, CompartmentRow, AssignmentRow

REGISTERED_TABLES = (DeliveryRow.__table__, ReturnRow.__table__, LockerRow.__table__,
                     CompartmentRow.__table__, AssignmentRow.__table__)


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(get_database_url(), poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
elif config.attributes.get("connection") is not None:
    # Tests and callers can supply an already isolated transactional connection.
    do_run_migrations(config.attributes["connection"])
else:
    asyncio.run(run_migrations_online())
