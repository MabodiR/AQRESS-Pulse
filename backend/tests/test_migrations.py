from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from alembic import command
from alembic.config import Config
from app.core.config import settings

MIGRATION_TEST_DATABASE = "sensegrid_migration_test"


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
        command.upgrade(config, "head")
        engine = create_engine(test_url)
        assert {"users", "refresh_tokens", "alembic_version"}.issubset(
            set(inspect(engine).get_table_names())
        )
        engine.dispose()

        command.downgrade(config, "base")
        engine = create_engine(test_url)
        assert "users" not in inspect(engine).get_table_names()
        assert "refresh_tokens" not in inspect(engine).get_table_names()
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
