"""PostgreSQL-only fixtures: real commits in a disposable schema per case."""
import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from adapters.database.sqlmodel_repositories import SqlModelDeliveryRepository, SqlModelReturnRepository
from domain.models import Delivery, Return
from domain.lockers import Dimensions

from alembic import command
from alembic.config import Config
import httpx
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession


BACKEND = Path(__file__).resolve().parents[2]


def test_database_url():
    value = os.environ.get('TEST_DATABASE_URL', '').strip()
    if not value:
        raise RuntimeError('TEST_DATABASE_URL is required for PostgreSQL integration tests')
    try:
        url = make_url(value)
    except Exception:
        raise RuntimeError('TEST_DATABASE_URL must be a valid postgresql+asyncpg URL') from None
    if url.drivername != 'postgresql+asyncpg':
        raise RuntimeError('TEST_DATABASE_URL must use postgresql+asyncpg')
    return url


async def preflight(url):
    engine = create_async_engine(url, connect_args={'timeout': 5})
    try:
        async with asyncio.timeout(5):
            async with engine.connect() as connection:
                await connection.execute(text('SELECT 1'))
    except Exception:
        raise RuntimeError('PostgreSQL integration preflight failed: check test database connectivity and credentials') from None
    finally:
        await engine.dispose()


class PostgresTestCase(unittest.IsolatedAsyncioTestCase):
    initial_revision = 'head'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.url = test_database_url()
        asyncio.run(preflight(cls.url))

    async def asyncSetUp(self):
        # A stack is registered before any resource acquisition, including failed setup.
        self.resources = AsyncExitStack()
        self.addAsyncCleanup(self.resources.aclose)
        self.schema = 'test_' + uuid4().hex
        self.admin = create_async_engine(self.url, connect_args={'timeout': 5})
        self.resources.push_async_callback(self.admin.dispose)
        try:
            async with self.admin.begin() as connection:
                await connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        except Exception:
            raise RuntimeError('PostgreSQL integration setup failed: test user must be able to create schemas') from None
        self.resources.push_async_callback(self._drop_schema)
        self.engines = []
        self.applications = {}
        self.engine, self.sessions = self.database()
        if self.initial_revision is not None:
            await self.migrate('upgrade', self.initial_revision)

    async def _drop_schema(self):
        async with self.admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))

    def database(self):
        engine = create_async_engine(self.url, connect_args={
            'timeout': 5, 'server_settings': {'search_path': self.schema}})
        self.engines.append(engine)
        self.resources.push_async_callback(engine.dispose)
        return engine, async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def migrate(self, direction, revision=None):
        async with self.engine.begin() as connection:
            def run(sync_connection):
                config = Config(str(BACKEND / 'alembic.ini'))
                config.set_main_option('script_location', str(BACKEND / 'adapters/database/migrations'))
                config.attributes['connection'] = sync_connection
                # Alembic reflection must use this search_path's default schema.
                previous = sync_connection.dialect.default_schema_name
                sync_connection.dialect.default_schema_name = self.schema
                try:
                    operation = getattr(command, direction)
                    operation(config, revision) if revision is not None else operation(config)
                finally:
                    sync_connection.dialect.default_schema_name = previous
            await connection.run_sync(run)

    async def snapshot(self):
        async with self.engine.connect() as connection:
            def structure(sync_connection):
                inspector = inspect(sync_connection)
                definitions = {}
                for table in sorted(inspector.get_table_names(schema=self.schema)):
                    columns = inspector.get_columns(table, schema=self.schema)
                    for column in columns:
                        column['type'] = str(column['type'])
                    indexes = inspector.get_indexes(table, schema=self.schema)
                    for index in indexes:
                        index['dialect_options'] = {key: str(value) for key, value in index.get('dialect_options', {}).items()}
                    definitions[table] = (columns,
                        inspector.get_check_constraints(table, schema=self.schema),
                        inspector.get_foreign_keys(table, schema=self.schema),
                        inspector.get_unique_constraints(table, schema=self.schema),
                        indexes, inspector.get_pk_constraint(table, schema=self.schema))
                return definitions
            definitions = await connection.run_sync(structure)
            rows = {table: (await connection.execute(text(f'SELECT * FROM "{table}" ORDER BY 1'))).all()
                    for table in definitions}
            return definitions, rows

    async def application(self):
        from main import create_app
        engine, sessions = self.database()
        with patch('main.create_database', return_value=(engine, sessions)):
            app = create_app(str(self.url))
        lifetime = AsyncExitStack()
        self.resources.push_async_callback(lifetime.aclose)
        await lifetime.enter_async_context(app.router.lifespan_context(app))
        client = await lifetime.enter_async_context(httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url='http://test'))
        self.applications[client] = lifetime
        return app, client, engine

    async def actor(self):
        _, client, engine = await self.application()
        return client, engine

    async def close_application(self, client):
        await self.applications.pop(client).aclose()


async def save_parcel(
    repository: SqlModelDeliveryRepository | SqlModelReturnRepository,
    parcel: Delivery | Return,
) -> None:
    """Keep table-driven cases correlated at the repository boundary."""
    if isinstance(parcel, Delivery):
        assert isinstance(repository, SqlModelDeliveryRepository)
        await repository.save(parcel)
    else:
        assert isinstance(repository, SqlModelReturnRepository)
        await repository.save(parcel)


async def receive_parcel(
    repository: SqlModelDeliveryRepository | SqlModelReturnRepository,
    parcel: Delivery | Return,
    locker_id: UUID,
    dimensions: Dimensions,
) -> Delivery | Return:
    if isinstance(parcel, Delivery):
        assert isinstance(repository, SqlModelDeliveryRepository)
        return await repository.receive_in_locker(parcel, locker_id, dimensions)
    assert isinstance(repository, SqlModelReturnRepository)
    return await repository.receive_in_locker(parcel, locker_id, dimensions)
