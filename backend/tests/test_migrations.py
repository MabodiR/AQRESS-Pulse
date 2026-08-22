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

        command.upgrade(config, "20260822_0003")
        engine = create_engine(test_url)
        phase_four_tables = set(inspect(engine).get_table_names())
        assert {"sensor_types", "measurement_definitions"}.issubset(phase_four_tables)
        assert "sensors" not in phase_four_tables
        engine.dispose()

        command.upgrade(config, "20260822_0004")
        engine = create_engine(test_url)
        phase_five_tables = set(inspect(engine).get_table_names())
        assert {"sensors", "sensor_channels", "sensor_configurations"}.issubset(phase_five_tables)
        assert "device_mqtt_credentials" not in phase_five_tables
        engine.dispose()

        command.upgrade(config, "20260822_0005")
        engine = create_engine(test_url)
        phase_six_tables = set(inspect(engine).get_table_names())
        assert "device_mqtt_credentials" in phase_six_tables
        assert "sensor_readings" not in phase_six_tables
        engine.dispose()

        command.upgrade(config, "head")
        engine = create_engine(test_url)
        inspector = inspect(engine)
        assert {"users", "refresh_tokens", "sites", "devices", "sensor_types", "measurement_definitions", "sensors", "sensor_channels", "sensor_configurations", "alembic_version"}.issubset(
            set(inspector.get_table_names())
        )
        assert "device_mqtt_credentials" in inspector.get_table_names()
        assert "sensor_readings" in inspector.get_table_names()
        assert "uq_sensors_device_id_sensor_uid" in {item["name"] for item in inspector.get_unique_constraints("sensors")}
        assert "uq_sensor_channels_sensor_id_measurement_definition_id" in {item["name"] for item in inspector.get_unique_constraints("sensor_channels")}
        assert "uq_sensor_configurations_sensor_id_config_version" in {item["name"] for item in inspector.get_unique_constraints("sensor_configurations")}
        current_index = next(item for item in inspector.get_indexes("sensor_configurations") if item["name"] == "uq_sensor_configurations_current")
        assert current_index["unique"] is True
        assert current_index["dialect_options"]["postgresql_where"] == "is_current"
        assert {item["name"] for item in inspector.get_unique_constraints("device_mqtt_credentials")} >= {"uq_device_mqtt_credentials_device_id", "uq_device_mqtt_credentials_username"}
        assert "uq_sensor_readings_device_message_index" in {
            item["name"] for item in inspector.get_unique_constraints("sensor_readings")
        }
        assert {item["name"] for item in inspector.get_check_constraints("sensor_readings")} >= {
            "ck_sensor_readings_exactly_one_value",
            "ck_sensor_readings_reading_index_nonnegative",
        }
        assert {item["name"] for item in inspector.get_indexes("sensor_readings")} >= {
            "ix_sensor_readings_channel_recorded",
            "ix_sensor_readings_sensor_recorded",
            "ix_sensor_readings_device_recorded",
            "ix_sensor_readings_recorded_at",
        }
        reading_columns = {item["name"]: item for item in inspector.get_columns("sensor_readings")}
        assert reading_columns["recorded_at"]["type"].timezone is True
        assert reading_columns["received_at"]["type"].timezone is True
        reading_foreign_keys = {
            item["name"]: item for item in inspector.get_foreign_keys("sensor_readings")
        }
        assert {
            reading_foreign_keys[name]["options"].get("ondelete")
            for name in (
                "fk_sensor_readings_device_id_devices",
                "fk_sensor_readings_sensor_id_sensors",
                "fk_sensor_readings_sensor_channel_id_sensor_channels",
            )
        } == {"RESTRICT"}
        engine.dispose()

        command.downgrade(config, "base")
        engine = create_engine(test_url)
        assert "users" not in inspect(engine).get_table_names()
        assert "refresh_tokens" not in inspect(engine).get_table_names()
        assert "sites" not in inspect(engine).get_table_names()
        assert "devices" not in inspect(engine).get_table_names()
        assert "sensor_types" not in inspect(engine).get_table_names()
        assert "measurement_definitions" not in inspect(engine).get_table_names()
        assert "sensors" not in inspect(engine).get_table_names()
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
