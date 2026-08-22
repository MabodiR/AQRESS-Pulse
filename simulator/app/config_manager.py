from typing import Any

from app.device_state import DeviceState

SUPPORTED_DRIVERS = {"ds18b20", "bme280", "digital_input", "analog_input"}


def apply_sensor_configuration(sensor: dict[str, Any], state: DeviceState, *, force_failure: bool = False) -> str | None:
    sensor_uid = str(sensor.get("sensor_uid", ""))
    driver_key = str(sensor.get("driver_key", ""))
    configuration = sensor.get("configuration")
    if force_failure:
        return "Simulator failure mode is enabled"
    if not sensor_uid or driver_key not in SUPPORTED_DRIVERS or not isinstance(configuration, dict):
        return "Unsupported Sensor definition"
    if driver_key == "bme280" and configuration.get("i2c_address", "0x76") not in {"0x76", "0x77"}:
        return "Unsupported I2C address"
    if driver_key in {"ds18b20", "digital_input"} and not _non_negative_integer(configuration.get("gpio_pin")):
        return "A non-negative GPIO pin is required"
    if driver_key == "analog_input" and not _non_negative_integer(configuration.get("adc_pin")):
        return "A non-negative ADC pin is required"
    state.sensor_configurations[sensor_uid] = sensor
    return None


def _non_negative_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
