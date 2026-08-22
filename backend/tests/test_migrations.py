from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from alembic import command
from alembic.config import Config
from app.core.config import settings

MIGRATION_TEST_DATABASE = "aqress_pulse_migration_test"


def test_migrations_upgrade_empty_database_and_downgrade() -> None:
    base_url = make_url(settings.database_url)
    admin_url = base_url.set(drivername="postgresql", database="postgres")
    test_url = base_url.set(database=MIGRATION_TEST_DATABASE)

    with psycopg.connect(
        admin_url.render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(MIGRATION_TEST_DATABASE)
            )
        )
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(MIGRATION_TEST_DATABASE))
        )

    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", test_url.render_as_string(hide_password=False))
    try:
        command.upgrade(config, "20260822_0001")
        engine = create_engine(test_url)
        phase_two_tables = set(inspect(engine).get_table_names())
        assert {"users", "refresh_tokens"}.issubset(phase_two_tables)
        assert "sites" not in phase_two_tables
        assert "devices" not in phase_two_tables
        engine.dispose()

        command.upgrade(config, "20260822_0002")
        engine = create_engine(test_url)
        phase_three_tables = set(inspect(engine).get_table_names())
        assert {"sites", "devices"}.issubset(phase_three_tables)
        assert "sensor_types" not in phase_three_tables
        engine.dispose()

        command.upgrade(config, "head")
        engine = create_engine(test_url)
        assert {"users", "refresh_tokens", "sites", "devices", "sensor_types", "measurement_definitions", "alembic_version"}.issubset(
            set(inspect(engine).get_table_names())
        )
        engine.dispose()

        command.downgrade(config, "base")
        engine = create_engine(test_url)
        assert "users" not in inspect(engine).get_table_names()
        assert "refresh_tokens" not in inspect(engine).get_table_names()
        assert "sites" not in inspect(engine).get_table_names()
        assert "devices" not in inspect(engine).get_table_names()
        assert "sensor_types" not in inspect(engine).get_table_names()
        assert "measurement_definitions" not in inspect(engine).get_table_names()
        engine.dispose()
    finally:
        with psycopg.connect(
            admin_url.render_as_string(hide_password=False), autocommit=True
        ) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(MIGRATION_TEST_DATABASE)
                )
            )
