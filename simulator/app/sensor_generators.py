import random
from typing import Any

from app.device_state import DeviceState


def generate_sensor_values(
    sensor: dict[str, Any], state: DeviceState, random_source: random.Random
) -> dict[str, float | bool]:
    driver = sensor["driver_key"]
    uid = sensor["sensor_uid"]
    configuration = sensor.get("configuration", {})
    if driver == "ds18b20":
        return {
            "temperature": _vary(
                state, uid, "temperature", 22.0, -20.0, 60.0, 0.18, random_source
            )
        }
    if driver == "bme280":
        return {
            "temperature": _vary(
                state, uid, "temperature", 24.0, -20.0, 60.0, 0.18, random_source
            ),
            "humidity": _vary(
                state, uid, "humidity", 55.0, 0.0, 100.0, 0.6, random_source
            ),
            "pressure": _vary(
                state, uid, "pressure", 1012.0, 850.0, 1100.0, 0.45, random_source
            ),
        }
    if driver == "digital_input":
        key = (uid, "state")
        value = not bool(state.last_values.get(key, False))
        state.last_values[key] = value
        return {"state": value}
    if driver == "analog_input":
        minimum = _number(configuration.get("engineering_min"), 0.0)
        maximum = _number(configuration.get("engineering_max"), 100.0)
        if maximum <= minimum:
            minimum, maximum = 0.0, 100.0
        return {
            "value": _vary(
                state,
                uid,
                "value",
                (minimum + maximum) / 2,
                minimum,
                maximum,
                (maximum - minimum) * 0.03,
                random_source,
            )
        }
    return {}


def _vary(
    state: DeviceState,
    sensor_uid: str,
    channel: str,
    initial: float,
    minimum: float,
    maximum: float,
    step: float,
    random_source: random.Random,
) -> float:
    key = (sensor_uid, channel)
    previous = float(state.last_values.get(key, initial))
    value = min(max(previous + random_source.uniform(-step, step), minimum), maximum)
    rounded = round(value, 3)
    state.last_values[key] = rounded
    return rounded


def _number(value: object, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    return float(value)
