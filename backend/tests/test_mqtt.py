import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device, DeviceStatus
from app.models.device_mqtt_credential import DeviceMqttCredential
from app.models.sensor import ConfigurationStatus, SensorConfiguration
from app.models.user import UserRole
from app.mqtt.control_plane import (
    InvalidControlMessage,
    mark_stale_devices_offline,
    process_control_message,
)
from app.mqtt.publisher import MqttPublisher, MqttPublishError
from app.mqtt.topics import (
    command_ack_topic,
    command_topic,
    config_ack_topic,
    config_topic,
    status_topic,
    telemetry_topic,
)
from app.scripts.seed_sensor_types import seed_sensor_types
from app.services.mqtt_auth_service import MqttAuthService
from tests.helpers import create_test_user, login


def headers(client: TestClient, role: UserRole = UserRole.ADMIN, email: str = "admin@aqress.dev") -> dict[str, str]:
    create_test_user(email=email, role=role)
    return {"Authorization": f"Bearer {login(client, email)['access_token']}"}


def setup_sensor(client: TestClient, auth: dict[str, str], *, device_uid: str = "ESP32-A8C339") -> tuple[dict, dict]:
    seed_sensor_types()
    site = client.post("/api/v1/sites", headers=auth, json={"name": f"Site {device_uid}", "description": None, "latitude": None, "longitude": None}).json()
    device = client.post("/api/v1/devices", headers=auth, json={"site_id": site["id"], "device_uid": device_uid, "name": "Controller", "description": None, "device_type": "ESP32", "manufacturer": "Espressif", "model": "ESP32", "firmware_version": "0.1.0", "connection_type": "WIFI"}).json()
    catalogue = client.get("/api/v1/sensor-types?search=BME280", headers=auth).json()["items"][0]
    sensor = client.post(f"/api/v1/devices/{device['id']}/sensors", headers=auth, json={"sensor_type_id": catalogue["id"], "sensor_uid": "ENV-001", "name": "Environment", "description": None, "configuration": {"i2c_address": "0x76", "sample_interval_seconds": 30}}).json()
    return device, sensor


def provision(client: TestClient, auth: dict[str, str], device_id: str) -> dict:
    response = client.post(f"/api/v1/devices/{device_id}/mqtt-credentials", headers=auth)
    assert response.status_code == 201
    return response.json()


def test_phase_6_topic_namespace_is_centralized() -> None:
    prefix = "aqress/pulse/v1/devices/ESP32-A8C339"
    assert status_topic("ESP32-A8C339") == f"{prefix}/status"
    assert config_topic("ESP32-A8C339") == f"{prefix}/config"
    assert config_ack_topic("ESP32-A8C339") == f"{prefix}/config/ack"
    assert telemetry_topic("ESP32-A8C339") == f"{prefix}/telemetry"
    assert command_topic("ESP32-A8C339") == f"{prefix}/command"
    assert command_ack_topic("ESP32-A8C339") == f"{prefix}/command/ack"


def test_credential_secret_is_one_time_and_hash_is_stored(client: TestClient) -> None:
    auth = headers(client)
    device, _sensor = setup_sensor(client, auth)
    secret = provision(client, auth, device["id"])
    status = client.get(f"/api/v1/devices/{device['id']}/mqtt-credentials/status", headers=auth).json()
    assert status["state"] == "ACTIVE" and "password" not in status
    assert client.post(f"/api/v1/devices/{device['id']}/mqtt-credentials", headers=auth).status_code == 409
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        credential = session.scalar(select(DeviceMqttCredential))
        assert credential is not None
        assert credential.password_hash != secret["password"]
        assert secret["password"] not in credential.password_hash
    engine.dispose()


def test_rotation_revoke_and_inactive_device_authentication(client: TestClient) -> None:
    auth = headers(client)
    device, _sensor = setup_sensor(client, auth)
    first = provision(client, auth, device["id"])
    second = client.post(f"/api/v1/devices/{device['id']}/mqtt-credentials/rotate", headers=auth).json()
    assert first["password"] != second["password"]

    async def authenticate(password: str) -> dict:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            return await MqttAuthService(session).authenticate(second["username"], password)

    assert asyncio.run(authenticate(first["password"]))["result"] == "deny"
    allowed = asyncio.run(authenticate(second["password"]))
    assert allowed["result"] == "allow"
    assert {rule["topic"] for rule in allowed["acl"] if rule["permission"] == "allow"} >= {status_topic(device["device_uid"]), config_ack_topic(device["device_uid"])}
    client.post(f"/api/v1/devices/{device['id']}/mqtt-credentials/revoke", headers=auth)
    assert asyncio.run(authenticate(second["password"]))["result"] == "deny"
    third = client.post(f"/api/v1/devices/{device['id']}/mqtt-credentials/rotate", headers=auth).json()
    client.patch(f"/api/v1/devices/{device['id']}/status", headers=auth, json={"is_active": False})
    assert asyncio.run(authenticate(third["password"]))["result"] == "deny"


@pytest.mark.parametrize(("role", "expected"), [(UserRole.USER, 403), (UserRole.VIEWER, 403)])
def test_credential_management_is_admin_only(client: TestClient, role: UserRole, expected: int) -> None:
    admin = headers(client)
    device, _sensor = setup_sensor(client, admin)
    role_headers = headers(client, role, f"{role.value.lower()}@aqress.dev")
    assert client.post(f"/api/v1/devices/{device['id']}/mqtt-credentials", headers=role_headers).status_code == expected
    assert client.get(f"/api/v1/devices/{device['id']}/mqtt-credentials/status", headers=role_headers).status_code == 200


def heartbeat(uid: str, *, timestamp: str | None = None) -> bytes:
    return json.dumps({"device_uid": uid, "timestamp": timestamp or datetime.now(UTC).isoformat(), "status": "ONLINE", "uptime_seconds": 120}).encode()


def test_heartbeat_online_offline_and_reconnect(client: TestClient) -> None:
    auth = headers(client)
    device, _sensor = setup_sensor(client, auth)
    engine = create_engine(settings.database_url)
    received = datetime.now(UTC)
    with Session(engine) as session:
        process_control_message(session, status_topic(device["device_uid"]), heartbeat(device["device_uid"]), received_at=received)
        stored = session.get(Device, uuid.UUID(device["id"]))
        assert stored is not None and stored.status == DeviceStatus.ONLINE and stored.last_seen_at == received
        assert mark_stale_devices_offline(session, now=received + timedelta(seconds=91), timeout_seconds=90) == 1
        session.refresh(stored)
        assert stored.status == DeviceStatus.OFFLINE
        process_control_message(session, status_topic(device["device_uid"]), heartbeat(device["device_uid"]), received_at=received + timedelta(seconds=92))
        session.refresh(stored)
        assert stored.status == DeviceStatus.ONLINE
    engine.dispose()


@pytest.mark.parametrize("case", ["unknown", "mismatch", "invalid_timestamp", "inactive"])
def test_invalid_heartbeats_are_rejected(client: TestClient, case: str) -> None:
    auth = headers(client)
    device, _sensor = setup_sensor(client, auth)
    topic_uid = device["device_uid"]
    payload_uid = topic_uid
    timestamp = datetime.now(UTC).isoformat()
    if case == "unknown":
        topic_uid = payload_uid = "UNKNOWN"
    if case == "mismatch":
        payload_uid = "OTHER"
    if case == "invalid_timestamp":
        timestamp = "not-a-time"
    if case == "inactive":
        client.patch(f"/api/v1/devices/{device['id']}/status", headers=auth, json={"is_active": False})
    engine = create_engine(settings.database_url)
    with Session(engine) as session, pytest.raises(InvalidControlMessage):
        process_control_message(session, status_topic(topic_uid), heartbeat(payload_uid, timestamp=timestamp))
    engine.dispose()


def test_disabled_device_is_not_changed_by_offline_detection(client: TestClient) -> None:
    auth = headers(client)
    device, _sensor = setup_sensor(client, auth)
    client.patch(f"/api/v1/devices/{device['id']}/status", headers=auth, json={"is_active": False})
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        stored = session.get(Device, uuid.UUID(device["id"]))
        stored.last_seen_at = datetime.now(UTC) - timedelta(hours=1)  # type: ignore[union-attr]
        session.commit()
        assert mark_stale_devices_offline(session) == 0
        session.refresh(stored)
        assert stored.status == DeviceStatus.DISABLED
    engine.dispose()


def test_configuration_snapshot_publish_and_republish(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    auth = headers(client)
    device, sensor = setup_sensor(client, auth)
    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(MqttPublisher, "publish", lambda _self, topic, payload, **_kwargs: published.append((topic, json.loads(payload))))
    response = client.post(f"/api/v1/devices/{device['id']}/sync-configuration", headers=auth)
    assert response.status_code == 200
    snapshot = published[0][1]
    assert snapshot["device_uid"] == device["device_uid"]
    assert snapshot["sensors"][0]["sensor_uid"] == "ENV-001"
    assert snapshot["sensors"][0]["configuration_version"] == 1
    assert {item["key"] for item in snapshot["sensors"][0]["channels"]} == {"temperature", "humidity", "pressure"}
    detail = client.get(f"/api/v1/sensors/{sensor['id']}", headers=auth).json()
    assert detail["current_configuration"]["status"] == "PUBLISHED" and detail["current_configuration"]["published_at"]
    assert client.post(f"/api/v1/devices/{device['id']}/sync-configuration", headers=auth).status_code == 200
    assert len(client.get(f"/api/v1/sensors/{sensor['id']}/configurations", headers=auth).json()) == 1


def test_publish_failure_keeps_configuration_pending_and_viewer_cannot_sync(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    auth = headers(client)
    device, sensor = setup_sensor(client, auth)
    monkeypatch.setattr(MqttPublisher, "publish", lambda *_args, **_kwargs: (_ for _ in ()).throw(MqttPublishError("failed")))
    assert client.post(f"/api/v1/devices/{device['id']}/sync-configuration", headers=auth).status_code == 503
    assert client.get(f"/api/v1/sensors/{sensor['id']}", headers=auth).json()["current_configuration"]["status"] == "PENDING"
    viewer = headers(client, UserRole.VIEWER, "viewer@aqress.dev")
    assert client.post(f"/api/v1/devices/{device['id']}/sync-configuration", headers=viewer).status_code == 403


def ack(uid: str, sensor_uid: str, version: int, result: str = "APPLIED") -> bytes:
    return json.dumps({"message_id": str(uuid.uuid4()), "device_uid": uid, "timestamp": datetime.now(UTC).isoformat(), "results": [{"sensor_uid": sensor_uid, "configuration_version": version, "status": result, "error": "simulated" if result == "FAILED" else None}]}).encode()


@pytest.mark.parametrize("result", ["APPLIED", "FAILED"])
def test_configuration_ack_and_duplicate_are_idempotent(client: TestClient, result: str) -> None:
    auth = headers(client)
    device, sensor = setup_sensor(client, auth)
    engine = create_engine(settings.database_url)
    payload = ack(device["device_uid"], "ENV-001", 1, result)
    with Session(engine) as session:
        configuration = session.scalar(select(SensorConfiguration).where(SensorConfiguration.sensor_id == uuid.UUID(sensor["id"])))
        configuration.status = ConfigurationStatus.PUBLISHED  # type: ignore[union-attr]
        session.commit()
        process_control_message(session, config_ack_topic(device["device_uid"]), payload)
        process_control_message(session, config_ack_topic(device["device_uid"]), payload)
        session.refresh(configuration)
        assert configuration.status.value == result
        assert (configuration.applied_at is not None) is (result == "APPLIED")
    engine.dispose()


def test_stale_ack_does_not_change_current_configuration(client: TestClient) -> None:
    auth = headers(client)
    device, sensor = setup_sensor(client, auth)
    client.put(f"/api/v1/sensors/{sensor['id']}/configuration", headers=auth, json={"configuration": {"i2c_address": "0x76", "sample_interval_seconds": 60}})
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        process_control_message(session, config_ack_topic(device["device_uid"]), ack(device["device_uid"], "ENV-001", 1))
        configurations = session.scalars(select(SensorConfiguration).where(SensorConfiguration.sensor_id == uuid.UUID(sensor["id"])).order_by(SensorConfiguration.config_version)).all()
        assert configurations[0].status == ConfigurationStatus.SUPERSEDED and configurations[0].is_current is False
        assert configurations[1].status == ConfigurationStatus.PENDING and configurations[1].is_current is True
    engine.dispose()


@pytest.mark.parametrize("case", ["unknown_device", "unknown_sensor", "unknown_version", "mismatch"])
def test_invalid_configuration_acks_are_rejected(client: TestClient, case: str) -> None:
    auth = headers(client)
    device, _sensor = setup_sensor(client, auth)
    topic_uid = payload_uid = device["device_uid"]
    sensor_uid, version = "ENV-001", 1
    if case == "unknown_device":
        topic_uid = payload_uid = "UNKNOWN"
    if case == "unknown_sensor":
        sensor_uid = "UNKNOWN"
    if case == "unknown_version":
        version = 999
    if case == "mismatch":
        payload_uid = "OTHER"
    engine = create_engine(settings.database_url)
    with Session(engine) as session, pytest.raises(InvalidControlMessage):
        process_control_message(session, config_ack_topic(topic_uid), ack(payload_uid, sensor_uid, version))
    engine.dispose()
