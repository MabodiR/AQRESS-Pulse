import asyncio
import os
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from alembic import command
from alembic.config import Config

runtime_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://aqress_pulse:aqress-pulse-local-only@localhost:5433/aqress_pulse",
)
test_database_url = os.environ.get(
    "TEST_DATABASE_URL",
    make_url(runtime_url).set(database="aqress_pulse_test").render_as_string(False),
)
os.environ["DATABASE_URL"] = test_database_url

from app.core.config import settings  # noqa: E402
from app.db.session import engine as async_engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_DATABASE_NAME = make_url(test_database_url).database or "aqress_pulse_test"
admin_url = make_url(test_database_url).set(drivername="postgresql", database="postgres")


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(TEST_DATABASE_NAME)
            )
        )
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DATABASE_NAME)))
    command.upgrade(Config("alembic.ini"), "head")
    yield
    asyncio.run(async_engine.dispose())
    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(TEST_DATABASE_NAME)
            )
        )


@pytest.fixture(autouse=True)
def clean_database(migrated_database: None) -> Iterator[None]:
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE sensor_types, refresh_tokens, users CASCADE"))
    yield
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE sensor_types, refresh_tokens, users CASCADE"))
    engine.dispose()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
