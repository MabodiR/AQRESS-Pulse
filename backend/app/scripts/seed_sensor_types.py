from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.sensor_type import (
    InterfaceType,
    MeasurementDefinition,
    MeasurementValueType,
    SensorType,
)
from app.services.configuration_validation_service import ConfigurationValidationService

OBJECT_SCHEMA = {"type": "object", "additionalProperties": False}

SENSOR_TYPE_SEEDS: list[dict[str, Any]] = [
    {"name": "DS18B20 Temperature Sensor", "code": "DS18B20", "manufacturer": None, "model": "DS18B20", "interface_type": InterfaceType.ONE_WIRE, "driver_key": "ds18b20", "configuration_schema": {**OBJECT_SCHEMA, "properties": {"gpio_pin": {"type": "integer", "title": "GPIO Pin", "minimum": 0}, "sample_interval_seconds": {"type": "integer", "title": "Sampling Interval", "minimum": 1, "default": 10}}, "required": ["gpio_pin", "sample_interval_seconds"]}, "measurements": [("temperature", "Temperature", MeasurementValueType.NUMERIC, "°C")]},
    {"name": "BME280 Environmental Sensor", "code": "BME280", "manufacturer": "Bosch", "model": "BME280", "interface_type": InterfaceType.I2C, "driver_key": "bme280", "configuration_schema": {**OBJECT_SCHEMA, "properties": {"i2c_address": {"type": "string", "title": "I2C Address", "default": "0x76"}, "sample_interval_seconds": {"type": "integer", "title": "Sampling Interval", "minimum": 1, "default": 10}}, "required": ["sample_interval_seconds"]}, "measurements": [("temperature", "Temperature", MeasurementValueType.NUMERIC, "°C"), ("humidity", "Humidity", MeasurementValueType.NUMERIC, "%"), ("pressure", "Pressure", MeasurementValueType.NUMERIC, "hPa")]},
    {"name": "Generic Digital Input", "code": "DIGITAL_INPUT", "manufacturer": None, "model": None, "interface_type": InterfaceType.GPIO, "driver_key": "digital_input", "configuration_schema": {**OBJECT_SCHEMA, "properties": {"gpio_pin": {"type": "integer", "title": "GPIO Pin", "minimum": 0}, "pull_mode": {"type": "string", "title": "Pull Mode", "enum": ["NONE", "PULL_UP", "PULL_DOWN"]}, "sample_interval_seconds": {"type": "integer", "title": "Sampling Interval", "minimum": 1, "default": 1}}, "required": ["gpio_pin"]}, "measurements": [("state", "State", MeasurementValueType.BOOLEAN, None)]},
    {"name": "Generic Analog Input", "code": "ANALOG_INPUT", "manufacturer": None, "model": None, "interface_type": InterfaceType.ADC, "driver_key": "analog_input", "configuration_schema": {**OBJECT_SCHEMA, "properties": {"adc_pin": {"type": "integer", "title": "ADC Pin", "minimum": 0}, "sample_interval_seconds": {"type": "integer", "title": "Sampling Interval", "minimum": 1, "default": 10}, "input_min": {"type": "number", "title": "Input Minimum"}, "input_max": {"type": "number", "title": "Input Maximum"}, "engineering_min": {"type": "number", "title": "Engineering Minimum"}, "engineering_max": {"type": "number", "title": "Engineering Maximum"}}, "required": ["adc_pin"]}, "measurements": [("value", "Value", MeasurementValueType.NUMERIC, None)]},
]


def seed_sensor_types(database_url: str | None = None) -> tuple[int, int]:
    engine = create_engine(database_url or settings.database_url)
    created_types = created_measurements = 0
    with Session(engine, expire_on_commit=False) as session, session.begin():
        for definition in SENSOR_TYPE_SEEDS:
            ConfigurationValidationService.validate_schema(definition["configuration_schema"])
            item = session.scalar(select(SensorType).options(selectinload(SensorType.measurements)).where(SensorType.code == definition["code"]))
            if item is None:
                item = SensorType(**{key: value for key, value in definition.items() if key != "measurements"})
                session.add(item)
                session.flush()
                created_types += 1
            existing = {measurement.key for measurement in item.measurements}
            for key, name, value_type, unit in definition["measurements"]:
                if key not in existing:
                    session.add(MeasurementDefinition(sensor_type_id=item.id, key=key, name=name, value_type=value_type, default_unit=unit))
                    created_measurements += 1
    engine.dispose()
    return created_types, created_measurements


def main() -> None:
    types, measurements = seed_sensor_types()
    print(f"Sensor Type catalogue ready; created {types} types and {measurements} measurements.")


if __name__ == "__main__":
    main()
