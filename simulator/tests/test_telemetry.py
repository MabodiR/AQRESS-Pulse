import json
import random
import time
from datetime import UTC, datetime

from app.device_state import DeviceState
from app.mqtt_client import SimulatorMqttClient
from app.sensor_generators import generate_sensor_values
from app.settings import SimulatorSettings
from app.telemetry import collect_due_readings


def state() -> DeviceState:
    return DeviceState(started_monotonic=time.monotonic())


def configured_sensor(
    driver_key: str,
    channels: list[str],
    *,
    enabled: bool = True,
    configuration: dict | None = None,
) -> dict:
    return {
        "sensor_uid": f"{driver_key.upper()}-001",
        "driver_key": driver_key,
        "enabled": enabled,
        "configuration": configuration or {"sample_interval_seconds": 10},
        "channels": [
            {"key": key, "enabled": True, "unit": None} for key in channels
        ],
    }


def test_no_telemetry_before_applied_configuration() -> None:
    assert collect_due_readings(
        state(),
        random.Random(1),
        now_monotonic=1,
        recorded_at=datetime.now(UTC),
    ) == []


def test_seeded_generators_are_bounded_and_deterministic() -> None:
    first_state = state()
    second_state = state()
    source_a = random.Random(42)
    source_b = random.Random(42)
    definitions = [
        configured_sensor("ds18b20", ["temperature"]),
        configured_sensor("bme280", ["temperature", "humidity", "pressure"]),
        configured_sensor("digital_input", ["state"]),
        configured_sensor(
            "analog_input",
            ["value"],
            configuration={"engineering_min": 10, "engineering_max": 20},
        ),
    ]
    for definition in definitions:
        assert generate_sensor_values(definition, first_state, source_a) == generate_sensor_values(
            definition, second_state, source_b
        )
    bme = generate_sensor_values(definitions[1], first_state, source_a)
    analog = generate_sensor_values(definitions[3], first_state, source_a)
    assert -20 <= bme["temperature"] <= 60
    assert 0 <= bme["humidity"] <= 100
    assert 850 <= bme["pressure"] <= 1100
    assert 10 <= analog["value"] <= 20


def test_sampling_interval_and_enabled_states() -> None:
    device = state()
    sensor = configured_sensor(
        "bme280",
        ["temperature", "humidity", "pressure"],
        configuration={"sample_interval_seconds": 10},
    )
    sensor["channels"][1]["enabled"] = False
    device.sensor_configurations[sensor["sensor_uid"]] = sensor
    first = collect_due_readings(
        device,
        random.Random(1),
        now_monotonic=100,
        recorded_at=datetime.now(UTC),
    )
    second = collect_due_readings(
        device,
        random.Random(1),
        now_monotonic=105,
        recorded_at=datetime.now(UTC),
    )
    third = collect_due_readings(
        device,
        random.Random(1),
        now_monotonic=110,
        recorded_at=datetime.now(UTC),
    )
    assert {item["channel"] for item in first} == {"temperature", "pressure"}
    assert second == []
    assert len(third) == 2
    sensor["enabled"] = False
    assert collect_due_readings(
        device,
        random.Random(1),
        now_monotonic=120,
        recorded_at=datetime.now(UTC),
    ) == []


def test_mqtt_telemetry_uses_qos_one_without_retain() -> None:
    device = state()
    sensor = configured_sensor(
        "bme280",
        ["temperature", "humidity", "pressure"],
        configuration={"sample_interval_seconds": 1},
    )
    device.sensor_configurations[sensor["sensor_uid"]] = sensor
    settings = SimulatorSettings(
        device_uid="ESP32-A8C339",
        mqtt_username="device:ESP32-A8C339",
        mqtt_password="test-password",
        random_seed=7,
    )
    simulator = SimulatorMqttClient(settings, device)
    published: list[tuple[str, str, int, bool]] = []

    class FakeClient:
        def publish(
            self, topic: str, payload: str, *, qos: int, retain: bool
        ) -> None:
            published.append((topic, payload, qos, retain))

    simulator.client = FakeClient()  # type: ignore[assignment]
    simulator.publish_telemetry(now_monotonic=10)
    assert len(published) == 1
    topic, raw_payload, qos, retain = published[0]
    value = json.loads(raw_payload)
    assert topic == "aqress/pulse/v1/devices/ESP32-A8C339/telemetry"
    assert qos == 1 and retain is False
    assert len(value["readings"]) == 3
