import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.reading import ReadingQuality, SensorReading
from app.models.sensor import Sensor, SensorChannel, SensorStatus
from app.models.sensor_type import MeasurementDefinition, MeasurementValueType
from app.models.user import UserRole
from app.mqtt.topics import telemetry_topic
from app.scripts.seed_sensor_types import seed_sensor_types
from app.telemetry.processor import InvalidTelemetryMessage, process_telemetry_message
from tests.helpers import create_test_user, login


def auth_headers(
    client: TestClient,
    role: UserRole = UserRole.ADMIN,
    email: str = "admin@aqress.dev",
) -> dict[str, str]:
    create_test_user(email=email, role=role)
    return {"Authorization": f"Bearer {login(client, email)['access_token']}"}


def setup_bme280(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict]:
    seed_sensor_types()
    site = client.post(
        "/api/v1/sites",
        headers=headers,
        json={"name": "Telemetry Site", "description": None, "latitude": None, "longitude": None},
    ).json()
    device = client.post(
        "/api/v1/devices",
        headers=headers,
        json={
            "site_id": site["id"],
            "device_uid": "ESP32-A8C339",
            "name": "Telemetry Device",
            "description": None,
            "device_type": "ESP32",
            "manufacturer": "Espressif",
            "model": "ESP32",
            "firmware_version": "0.1.0",
            "connection_type": "WIFI",
        },
    ).json()
    sensor_type = client.get(
        "/api/v1/sensor-types?search=BME280", headers=headers
    ).json()["items"][0]
    sensor = client.post(
        f"/api/v1/devices/{device['id']}/sensors",
        headers=headers,
        json={
            "sensor_type_id": sensor_type["id"],
            "sensor_uid": "ENV-001",
            "name": "Environment",
            "description": None,
            "configuration": {
                "i2c_address": "0x76",
                "sample_interval_seconds": 10,
            },
        },
    ).json()
    return device, sensor


def payload(
    readings: list[dict],
    *,
    device_uid: str = "ESP32-A8C339",
    message_id: uuid.UUID | None = None,
    sent_at: str | None = None,
) -> bytes:
    return json.dumps(
        {
            "message_id": str(message_id or uuid.uuid4()),
            "device_uid": device_uid,
            "sent_at": sent_at or datetime.now(UTC).isoformat(),
            "readings": readings,
        }
    ).encode()


def reading(
    channel: str,
    value: object,
    *,
    sensor_uid: str = "ENV-001",
    recorded_at: datetime | None = None,
    quality: str = "GOOD",
) -> dict:
    return {
        "sensor_uid": sensor_uid,
        "channel": channel,
        "recorded_at": (recorded_at or datetime.now(UTC)).isoformat(),
        "value": value,
        "quality": quality,
    }


def process(raw: bytes, *, received_at: datetime | None = None):
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        result = process_telemetry_message(
            session,
            telemetry_topic("ESP32-A8C339"),
            raw,
            received_at=received_at,
        )
    engine.dispose()
    return result


def test_bme280_typed_readings_unit_snapshot_and_idempotency(client: TestClient) -> None:
    headers = auth_headers(client)
    _device, sensor = setup_bme280(client, headers)
    recorded_at = datetime.now(UTC) - timedelta(minutes=1)
    received_at = datetime.now(UTC)
    message_id = uuid.uuid4()
    raw = payload(
        [
            reading("temperature", 24.7, recorded_at=recorded_at),
            reading("humidity", 58.2, recorded_at=recorded_at),
            reading("pressure", 1012.4, recorded_at=recorded_at),
        ],
        message_id=message_id,
    )
    first = process(raw, received_at=received_at)
    duplicate = process(raw, received_at=received_at + timedelta(seconds=1))
    assert (first.accepted_count, first.rejected_count, first.duplicate_count) == (3, 0, 0)
    assert (duplicate.accepted_count, duplicate.duplicate_count) == (0, 3)

    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        rows = list(session.scalars(select(SensorReading).order_by(SensorReading.reading_index)))
        assert len(rows) == 3
        assert [item.value_numeric for item in rows] == [24.7, 58.2, 1012.4]
        assert [item.unit for item in rows] == ["°C", "%", "hPa"]
        assert all(item.value_text is None and item.value_boolean is None for item in rows)
        assert all(item.recorded_at == recorded_at for item in rows)
        assert all(item.received_at == received_at for item in rows)
        assert rows[0].raw_payload["channel"] == "temperature"
        channel = session.get(SensorChannel, rows[0].sensor_channel_id)
        assert channel is not None
        channel.unit = "changed"
        session.commit()
        session.refresh(rows[0])
        assert rows[0].unit == "°C"
    engine.dispose()

    latest = client.get(f"/api/v1/sensors/{sensor['id']}/latest", headers=headers)
    assert latest.status_code == 200
    assert {item["channel"] for item in latest.json()["readings"]} == {
        "temperature",
        "humidity",
        "pressure",
    }


def test_latest_uses_recorded_time_not_arrival_order(client: TestClient) -> None:
    headers = auth_headers(client)
    _device, sensor = setup_bme280(client, headers)
    newest = datetime.now(UTC)
    process(payload([reading("temperature", 25.0, recorded_at=newest)]))
    process(
        payload(
            [
                reading(
                    "temperature",
                    18.0,
                    recorded_at=newest - timedelta(hours=2),
                )
            ]
        )
    )
    response = client.get(
        f"/api/v1/sensors/{sensor['id']}/latest", headers=headers
    ).json()
    assert response["readings"][0]["value"] == 25.0
    assert datetime.fromisoformat(
        response["readings"][0]["recorded_at"].replace("Z", "+00:00")
    ) == newest


def test_partial_acceptance_and_bad_quality_is_persisted(client: TestClient) -> None:
    headers = auth_headers(client)
    setup_bme280(client, headers)
    result = process(
        payload(
            [
                reading("temperature", 20.5, quality="BAD"),
                reading("unknown", 1),
                reading("humidity", 50.0),
            ]
        )
    )
    assert (result.accepted_count, result.rejected_count) == (2, 1)
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        rows = list(session.scalars(select(SensorReading).order_by(SensorReading.reading_index)))
        assert [item.reading_index for item in rows] == [0, 2]
        assert rows[0].quality == ReadingQuality.BAD
    engine.dispose()


def test_boolean_and_text_values_require_exact_json_types(client: TestClient) -> None:
    headers = auth_headers(client)
    _device, sensor = setup_bme280(client, headers)
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        channels = list(
            session.scalars(
                select(SensorChannel)
                .where(SensorChannel.sensor_id == uuid.UUID(sensor["id"]))
                .order_by(SensorChannel.name)
            )
        )
        boolean_definition = session.get(
            MeasurementDefinition, channels[0].measurement_definition_id
        )
        text_definition = session.get(
            MeasurementDefinition, channels[1].measurement_definition_id
        )
        assert boolean_definition is not None and text_definition is not None
        boolean_definition.key = "state"
        boolean_definition.value_type = MeasurementValueType.BOOLEAN
        text_definition.key = "label"
        text_definition.value_type = MeasurementValueType.TEXT
        session.commit()
    engine.dispose()

    result = process(
        payload(
            [
                reading("state", True),
                reading("state", 1),
                reading("label", "RUNNING"),
                reading("label", 7),
            ]
        )
    )
    assert (result.accepted_count, result.rejected_count) == (2, 2)
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        rows = list(
            session.scalars(select(SensorReading).order_by(SensorReading.reading_index))
        )
        assert rows[0].value_boolean is True
        assert rows[0].value_numeric is None and rows[0].value_text is None
        assert rows[1].value_text == "RUNNING"
        assert rows[1].value_numeric is None and rows[1].value_boolean is None
    engine.dispose()


@pytest.mark.parametrize(
    "raw",
    [
        b"not-json",
        b"{}",
        payload([reading("temperature", 1)], sent_at="naive"),
        payload([reading("temperature", 1)], device_uid="OTHER"),
    ],
)
def test_invalid_envelopes_are_rejected(client: TestClient, raw: bytes) -> None:
    headers = auth_headers(client)
    setup_bme280(client, headers)
    with pytest.raises(InvalidTelemetryMessage):
        process(raw)


def test_batch_limit_unknown_and_inactive_devices(client: TestClient) -> None:
    headers = auth_headers(client)
    device, _sensor = setup_bme280(client, headers)
    raw = payload([reading("temperature", 1), reading("humidity", 2)])
    engine = create_engine(settings.database_url)
    with Session(engine) as session, pytest.raises(InvalidTelemetryMessage):
        process_telemetry_message(
            session,
            telemetry_topic("ESP32-A8C339"),
            raw,
            max_readings=1,
        )
    with Session(engine) as session, pytest.raises(InvalidTelemetryMessage):
        process_telemetry_message(
            session,
            telemetry_topic("UNKNOWN"),
            payload([reading("temperature", 1)], device_uid="UNKNOWN"),
        )
    client.patch(
        f"/api/v1/devices/{device['id']}/status",
        headers=headers,
        json={"is_active": False},
    )
    with Session(engine) as session, pytest.raises(InvalidTelemetryMessage):
        process_telemetry_message(session, telemetry_topic("ESP32-A8C339"), raw)
    engine.dispose()


@pytest.mark.parametrize(
    ("item", "mutate"),
    [
        (reading("temperature", "24.5"), None),
        (reading("temperature", True), None),
        (reading("temperature", 24.5, sensor_uid="UNKNOWN"), None),
        (reading("temperature", 24.5), "sensor_disabled"),
        (reading("temperature", 24.5), "sensor_error"),
        (reading("temperature", 24.5), "channel_disabled"),
        (
            reading(
                "temperature",
                24.5,
                recorded_at=datetime.now(UTC) + timedelta(minutes=10),
            ),
            None,
        ),
    ],
)
def test_invalid_reading_items_are_rejected(
    client: TestClient, item: dict, mutate: str | None
) -> None:
    headers = auth_headers(client)
    _device, sensor = setup_bme280(client, headers)
    if mutate:
        engine = create_engine(settings.database_url)
        with Session(engine) as session:
            stored = session.get(Sensor, uuid.UUID(sensor["id"]))
            assert stored is not None
            if mutate == "sensor_disabled":
                stored.enabled = False
                stored.status = SensorStatus.DISABLED
            elif mutate == "sensor_error":
                stored.status = SensorStatus.ERROR
            else:
                channel = session.get(SensorChannel, uuid.UUID(sensor["channels"][0]["id"]))
                assert channel is not None
                channel.enabled = False
                item["channel"] = sensor["channels"][0]["key"]
            session.commit()
        engine.dispose()
    result = process(payload([item]))
    assert (result.accepted_count, result.rejected_count) == (0, 1)


def test_exactly_one_typed_value_constraint(client: TestClient) -> None:
    headers = auth_headers(client)
    device, sensor = setup_bme280(client, headers)
    channel_id = sensor["channels"][0]["id"]
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        session.add(
            SensorReading(
                device_id=uuid.UUID(device["id"]),
                sensor_id=uuid.UUID(sensor["id"]),
                sensor_channel_id=uuid.UUID(channel_id),
                message_id=uuid.uuid4(),
                reading_index=0,
                recorded_at=datetime.now(UTC),
                received_at=datetime.now(UTC),
                value_numeric=1.0,
                value_text="also set",
                raw_payload={},
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    engine.dispose()


def test_history_filters_cursor_authorization_and_channel_scope(client: TestClient) -> None:
    headers = auth_headers(client)
    _device, sensor = setup_bme280(client, headers)
    base = datetime.now(UTC) - timedelta(hours=1)
    for offset in range(3):
        process(payload([reading("temperature", 20 + offset, recorded_at=base + timedelta(minutes=offset))]))
    url = f"/api/v1/sensors/{sensor['id']}/readings"
    first = client.get(url, headers=headers, params={"limit": 2}).json()
    second = client.get(url, headers=headers, params={"limit": 2, "cursor": first["next_cursor"]}).json()
    assert first["has_more"] is True and second["has_more"] is False
    assert {item["id"] for item in first["items"]}.isdisjoint(
        {item["id"] for item in second["items"]}
    )
    assert [item["value"] for item in first["items"]] == [22.0, 21.0]
    filtered = client.get(
        url,
        headers=headers,
        params={
            "from": (base + timedelta(seconds=30)).isoformat(),
            "to": (base + timedelta(minutes=1, seconds=30)).isoformat(),
        },
    ).json()
    assert [item["value"] for item in filtered["items"]] == [21.0]
    assert client.get(url, headers=headers, params={"cursor": "invalid"}).status_code == 400
    assert client.get(
        url,
        headers=headers,
        params={"from": datetime.now(UTC).isoformat(), "to": base.isoformat()},
    ).status_code == 422
    assert client.get(url, params={"limit": 1}).status_code == 401
    viewer = auth_headers(client, UserRole.VIEWER, "viewer@aqress.dev")
    assert client.get(url, headers=viewer, params={"limit": 1}).status_code == 200
    channel_id = sensor["channels"][0]["id"]
    channel_url = f"/api/v1/sensors/{sensor['id']}/channels/{channel_id}/readings"
    assert client.get(channel_url, headers=headers).status_code == 200
    assert client.get(
        f"/api/v1/sensors/{sensor['id']}/channels/{uuid.uuid4()}/readings",
        headers=headers,
    ).status_code == 404
