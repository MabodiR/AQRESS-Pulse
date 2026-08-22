import time

from app.config_manager import apply_sensor_configuration
from app.device_state import DeviceState


def state() -> DeviceState:
    return DeviceState(started_monotonic=time.monotonic())


def test_supported_bme280_configuration_is_stored() -> None:
    device = state()
    error = apply_sensor_configuration({"sensor_uid": "ENV-001", "driver_key": "bme280", "configuration": {"i2c_address": "0x76"}}, device)
    assert error is None
    assert device.sensor_configurations["ENV-001"]["driver_key"] == "bme280"


def test_unknown_driver_and_forced_failure_are_rejected() -> None:
    assert apply_sensor_configuration({"sensor_uid": "X", "driver_key": "unknown", "configuration": {}}, state()) == "Unsupported Sensor definition"
    assert apply_sensor_configuration({"sensor_uid": "ENV-001", "driver_key": "bme280", "configuration": {}}, state(), force_failure=True) == "Simulator failure mode is enabled"


def test_hardware_specific_bme280_address_failure() -> None:
    assert apply_sensor_configuration({"sensor_uid": "ENV-001", "driver_key": "bme280", "configuration": {"i2c_address": "0x75"}}, state()) == "Unsupported I2C address"
