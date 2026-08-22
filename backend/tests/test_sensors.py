import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.sensor import Sensor, SensorChannel, SensorConfiguration
from app.models.user import UserRole
from app.scripts.seed_sensor_types import seed_sensor_types
from tests.helpers import create_test_user, login


def auth_headers(client: TestClient, role: UserRole = UserRole.ADMIN, email: str = "admin@aqress.dev") -> dict[str, str]:
    create_test_user(email=email, role=role)
    return {"Authorization": f"Bearer {login(client, email)['access_token']}"}


def create_site(client: TestClient, headers: dict[str, str], name: str = "Sensor Lab") -> dict[str, object]:
    response = client.post("/api/v1/sites", headers=headers, json={"name": name, "description": None, "latitude": None, "longitude": None})
    assert response.status_code == 201
    return response.json()


def create_device(client: TestClient, headers: dict[str, str], site_id: str, uid: str = "DEVICE-A") -> dict[str, object]:
    payload = {"site_id": site_id, "device_uid": uid, "name": uid, "description": None, "device_type": "ESP32", "manufacturer": None, "model": None, "firmware_version": None, "connection_type": "WIFI"}
    response = client.post("/api/v1/devices", headers=headers, json=payload)
    assert response.status_code == 201
    return response.json()


def sensor_type_id(code: str) -> str:
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        from app.models.sensor_type import SensorType
        result = str(session.scalar(select(SensorType.id).where(SensorType.code == code)))
    engine.dispose()
    return result


def sensor_payload(sensor_type: str, uid: str = "ENV-001", interval: int = 10) -> dict[str, object]:
    return {"sensor_type_id": sensor_type, "sensor_uid": uid, "name": "Lab Environment Sensor", "description": "BME280 in the lab", "configuration": {"i2c_address": "0x76", "sample_interval_seconds": interval}}


def setup_device(client: TestClient, headers: dict[str, str], uid: str = "DEVICE-A") -> tuple[dict[str, object], str]:
    seed_sensor_types()
    site = create_site(client, headers, f"Site {uid}")
    return create_device(client, headers, site["id"], uid), sensor_type_id("BME280")


def create_sensor(client: TestClient, headers: dict[str, str], device_id: str, type_id: str, uid: str = "ENV-001") -> dict[str, object]:
    response = client.post(f"/api/v1/devices/{device_id}/sensors", headers=headers, json=sensor_payload(type_id, uid))
    assert response.status_code == 201
    return response.json()


def test_sensor_creation_is_atomic_and_generates_channels_and_config(client: TestClient) -> None:
    headers = auth_headers(client)
    device, type_id = setup_device(client, headers)
    item = create_sensor(client, headers, device["id"], type_id)
    assert item["status"] == "REGISTERED" and item["enabled"] is True
    assert item["device"]["id"] == device["id"] and item["sensor_type"]["code"] == "BME280"
    assert {channel["key"] for channel in item["channels"]} == {"temperature", "humidity", "pressure"}
    assert {channel["key"]: channel["unit"] for channel in item["channels"]} == {"temperature": "°C", "humidity": "%", "pressure": "hPa"}
    assert item["current_configuration"]["config_version"] == 1
    assert item["current_configuration"]["status"] == "PENDING"
    assert item["current_configuration"]["is_current"] is True


def test_ds18b20_generates_exactly_one_channel(client: TestClient) -> None:
    headers = auth_headers(client)
    seed_sensor_types()
    site = create_site(client, headers)
    device = create_device(client, headers, site["id"])
    response = client.post(
        f"/api/v1/devices/{device['id']}/sensors",
        headers=headers,
        json={
            **sensor_payload(sensor_type_id("DS18B20"), "TEMP-001"),
            "configuration": {"gpio_pin": 4, "sample_interval_seconds": 10},
        },
    )
    assert response.status_code == 201
    item = response.json()
    assert [(channel["key"], channel["unit"]) for channel in item["channels"]] == [("temperature", "°C")]


def test_sensor_uid_unique_per_device_but_reusable_across_devices(client: TestClient) -> None:
    headers = auth_headers(client)
    first, type_id = setup_device(client, headers)
    second = create_device(client, headers, first["site"]["id"], "DEVICE-B")
    create_sensor(client, headers, first["id"], type_id)
    duplicate = client.post(f"/api/v1/devices/{first['id']}/sensors", headers=headers, json=sensor_payload(type_id))
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "SENSOR_UID_EXISTS"
    assert client.post(f"/api/v1/devices/{second['id']}/sensors", headers=headers, json=sensor_payload(type_id)).status_code == 201


@pytest.mark.parametrize("case", ["inactive_device", "inactive_type", "empty_type", "invalid_configuration"])
def test_creation_readiness_and_validation_are_transactional(client: TestClient, case: str) -> None:
    headers = auth_headers(client)
    device, type_id = setup_device(client, headers)
    payload = sensor_payload(type_id)
    if case == "inactive_device":
        client.patch(f"/api/v1/devices/{device['id']}/status", headers=headers, json={"is_active": False})
        expected = "DEVICE_INACTIVE"
    elif case == "inactive_type":
        client.patch(f"/api/v1/sensor-types/{type_id}/status", headers=headers, json={"is_active": False})
        expected = "SENSOR_TYPE_NOT_READY"
    elif case == "empty_type":
        created = client.post("/api/v1/sensor-types", headers=headers, json={"name": "Empty", "code": "EMPTY", "manufacturer": None, "model": None, "interface_type": "GPIO", "driver_key": "empty", "configuration_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}).json()
        payload["sensor_type_id"] = created["id"]
        expected = "SENSOR_TYPE_NOT_READY"
    else:
        payload["configuration"] = {"sample_interval_seconds": 0, "unexpected": True}
        expected = "SENSOR_CONFIGURATION_INVALID"
    response = client.post(f"/api/v1/devices/{device['id']}/sensors", headers=headers, json=payload)
    assert response.status_code in (409, 422) and response.json()["error"]["code"] == expected
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Sensor)) == 0
        assert session.scalar(select(func.count()).select_from(SensorChannel)) == 0
        assert session.scalar(select(func.count()).select_from(SensorConfiguration)) == 0
    engine.dispose()


def test_configuration_versioning_preserves_history(client: TestClient) -> None:
    headers = auth_headers(client)
    device, type_id = setup_device(client, headers)
    item = create_sensor(client, headers, device["id"], type_id)
    response = client.put(f"/api/v1/sensors/{item['id']}/configuration", headers=headers, json={"configuration": {"i2c_address": "0x76", "sample_interval_seconds": 30}})
    assert response.status_code == 200 and response.json()["config_version"] == 2
    history = client.get(f"/api/v1/sensors/{item['id']}/configurations", headers=headers).json()
    assert [(value["config_version"], value["status"], value["is_current"]) for value in history] == [(2, "PENDING", True), (1, "SUPERSEDED", False)]
    assert history[1]["configuration"]["sample_interval_seconds"] == 10
    assert sum(configuration["is_current"] for configuration in history) == 1
    invalid = client.put(f"/api/v1/sensors/{item['id']}/configuration", headers=headers, json={"configuration": {"sample_interval_seconds": -1}})
    assert invalid.status_code == 422
    assert len(client.get(f"/api/v1/sensors/{item['id']}/configurations", headers=headers).json()) == 2


def test_sensor_channel_and_sensor_updates(client: TestClient) -> None:
    headers = auth_headers(client)
    device, type_id = setup_device(client, headers)
    item = create_sensor(client, headers, device["id"], type_id)
    channel = item["channels"][0]
    update = client.put(f"/api/v1/sensors/{item['id']}/channels/{channel['id']}", headers=headers, json={"name": "Motor Temperature", "unit": "°C", "enabled": False})
    assert update.status_code == 200 and update.json()["name"] == "Motor Temperature" and update.json()["enabled"] is False
    forbidden_field = client.put(f"/api/v1/sensors/{item['id']}/channels/{channel['id']}", headers=headers, json={"name": "Changed", "unit": None, "enabled": True, "measurement_definition_id": str(uuid.uuid4())})
    assert forbidden_field.status_code == 422
    edited = client.put(f"/api/v1/sensors/{item['id']}", headers=headers, json={"name": "Edited Sensor", "description": "Edited", "enabled": False}).json()
    assert edited["name"] == "Edited Sensor" and edited["status"] == "DISABLED"


def test_sensor_lists_search_filters_and_device_empty_state(client: TestClient) -> None:
    headers = auth_headers(client)
    device, type_id = setup_device(client, headers)
    empty = create_device(client, headers, device["site"]["id"], "EMPTY-DEVICE")
    item = create_sensor(client, headers, device["id"], type_id)
    assert client.get(f"/api/v1/devices/{empty['id']}/sensors", headers=headers).json()["items"] == []
    filters = [f"device_id={device['id']}", f"site_id={device['site']['id']}", f"sensor_type_id={type_id}", "status=REGISTERED", "enabled=true", "search=Environment", "search=ENV-001"]
    for query in filters:
        result = client.get(f"/api/v1/sensors?{query}&page=1&page_size=1", headers=headers).json()
        assert result["pagination"]["total_items"] == 1 and result["items"][0]["id"] == item["id"]
    assert client.get(f"/api/v1/devices/{device['id']}/sensors?search=ENV", headers=headers).json()["pagination"]["total_items"] == 1


@pytest.mark.parametrize(("role", "email", "can_write"), [(UserRole.ADMIN, "admin@aqress.dev", True), (UserRole.USER, "user@aqress.dev", True), (UserRole.VIEWER, "viewer@aqress.dev", False)])
def test_sensor_authorization(client: TestClient, role: UserRole, email: str, can_write: bool) -> None:
    headers = auth_headers(client, role, email)
    admin = headers if role == UserRole.ADMIN else auth_headers(client, UserRole.ADMIN, "setup-admin@aqress.dev")
    device, type_id = setup_device(client, admin)
    response = client.post(f"/api/v1/devices/{device['id']}/sensors", headers=headers, json=sensor_payload(type_id))
    assert response.status_code == (201 if can_write else 403)
    assert client.get("/api/v1/sensors", headers=headers).status_code == 200
    assert client.get("/api/v1/sensors").status_code == 401
    catalogue_write = client.post("/api/v1/sensor-types", headers=headers, json={"name": "Nope", "code": "NOPE", "manufacturer": None, "model": None, "interface_type": "GPIO", "driver_key": "nope", "configuration_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}})
    assert catalogue_write.status_code == (201 if role == UserRole.ADMIN else 403)
