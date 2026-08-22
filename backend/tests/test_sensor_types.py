import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.models.sensor_type import SensorType
from app.models.user import UserRole
from app.scripts.seed_sensor_types import seed_sensor_types
from app.services.configuration_validation_service import (
    ConfigurationValidationService,
)
from tests.helpers import create_test_user, login

VALID_SCHEMA = {"type": "object", "properties": {"pin": {"type": "integer", "title": "Pin", "minimum": 0}, "mode": {"type": "string", "enum": ["A", "B"]}}, "required": ["pin"], "additionalProperties": False}


def headers(client: TestClient, role: UserRole = UserRole.ADMIN, email: str = "admin@aqress.dev") -> dict[str, str]:
    create_test_user(email=email, role=role)
    return {"Authorization": f"Bearer {login(client, email)['access_token']}"}


def sensor_payload(code: str = "TEST_SENSOR", driver: str = "test_sensor") -> dict[str, object]:
    return {"name": "Test Sensor", "code": code, "manufacturer": "AQRESS", "model": "V1", "interface_type": "GPIO", "driver_key": driver, "configuration_schema": VALID_SCHEMA}


def create_sensor_type(client: TestClient, auth: dict[str, str], code: str = "TEST_SENSOR", driver: str = "test_sensor") -> dict[str, object]:
    response = client.post("/api/v1/sensor-types", headers=auth, json=sensor_payload(code, driver))
    assert response.status_code == 201
    return response.json()


def measurement_payload(key: str = "value") -> dict[str, object]:
    return {"key": key, "name": key.title(), "description": "Measured value", "value_type": "NUMERIC", "default_unit": "V"}


def test_configuration_schema_and_configuration_validation() -> None:
    ConfigurationValidationService.validate_schema(VALID_SCHEMA)
    ConfigurationValidationService.validate_configuration(VALID_SCHEMA, {"pin": 0, "mode": "A"})
    for invalid in ({"type": "string"}, {**VALID_SCHEMA, "additionalProperties": True}, {**VALID_SCHEMA, "properties": {"pin": {"type": "array"}}}):
        with pytest.raises(AppError) as error:
            ConfigurationValidationService.validate_schema(invalid)
        assert error.value.code == "INVALID_CONFIGURATION_SCHEMA"
    for configuration in ({}, {"pin": -1}, {"pin": 1, "mode": "C"}, {"pin": 1, "extra": True}):
        with pytest.raises(AppError) as error:
            ConfigurationValidationService.validate_configuration(VALID_SCHEMA, configuration)
        assert error.value.code == "INVALID_SENSOR_CONFIGURATION"


def test_admin_catalogue_crud_filters_pagination_and_measurements(client: TestClient) -> None:
    auth = headers(client)
    item = create_sensor_type(client, auth)
    assert item["code"] == "TEST_SENSOR"
    assert client.get(f"/api/v1/sensor-types/{item['id']}", headers=auth).status_code == 200
    for query in ("search=AQRESS", "search=TEST_SENSOR", "interface_type=GPIO", "is_active=true"):
        result = client.get(f"/api/v1/sensor-types?{query}&page=1&page_size=1", headers=auth).json()
        assert result["pagination"] == {"page": 1, "page_size": 1, "total_items": 1, "total_pages": 1}
    updated = sensor_payload()
    updated["name"] = "Updated Test Sensor"
    assert client.put(f"/api/v1/sensor-types/{item['id']}", headers=auth, json=updated).json()["name"] == "Updated Test Sensor"
    measurement = client.post(f"/api/v1/sensor-types/{item['id']}/measurements", headers=auth, json=measurement_payload()).json()
    assert measurement["key"] == "value"
    assert len(client.get(f"/api/v1/sensor-types/{item['id']}", headers=auth).json()["measurements"]) == 1
    changed = measurement_payload("voltage")
    assert client.put(f"/api/v1/sensor-types/{item['id']}/measurements/{measurement['id']}", headers=auth, json=changed).json()["key"] == "voltage"
    assert client.patch(f"/api/v1/sensor-types/{item['id']}/status", headers=auth, json={"is_active": False}).json()["is_active"] is False


def test_uniqueness_rules_and_scoped_measurement_keys(client: TestClient) -> None:
    auth = headers(client)
    first = create_sensor_type(client, auth)
    duplicate_code = client.post("/api/v1/sensor-types", headers=auth, json=sensor_payload("TEST_SENSOR", "another_driver"))
    assert duplicate_code.status_code == 409 and duplicate_code.json()["error"]["code"] == "SENSOR_TYPE_CODE_EXISTS"
    duplicate_driver = client.post("/api/v1/sensor-types", headers=auth, json=sensor_payload("ANOTHER_SENSOR", "test_sensor"))
    assert duplicate_driver.status_code == 409 and duplicate_driver.json()["error"]["code"] == "DRIVER_KEY_EXISTS"
    second = create_sensor_type(client, auth, "SECOND_SENSOR", "second_sensor")
    for item in (first, second):
        assert client.post(f"/api/v1/sensor-types/{item['id']}/measurements", headers=auth, json=measurement_payload("temperature")).status_code == 201
    duplicate = client.post(f"/api/v1/sensor-types/{first['id']}/measurements", headers=auth, json=measurement_payload("temperature"))
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "MEASUREMENT_KEY_EXISTS"


@pytest.mark.parametrize(("role", "email"), [(UserRole.USER, "user@aqress.dev"), (UserRole.VIEWER, "viewer@aqress.dev")])
def test_catalogue_roles_are_read_only(client: TestClient, role: UserRole, email: str) -> None:
    auth = headers(client, role, email)
    assert client.get("/api/v1/sensor-types", headers=auth).status_code == 200
    response = client.post("/api/v1/sensor-types", headers=auth, json=sensor_payload())
    assert response.status_code == 403 and response.json()["error"]["code"] == "FORBIDDEN"


def test_sensor_type_invalid_schema_and_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/sensor-types").status_code == 401
    auth = headers(client)
    payload = sensor_payload()
    payload["configuration_schema"] = {"type": "string"}
    response = client.post("/api/v1/sensor-types", headers=auth, json=payload)
    assert response.status_code == 422 and response.json()["error"]["code"] == "INVALID_CONFIGURATION_SCHEMA"


def test_seed_is_idempotent_and_bme280_is_complete() -> None:
    assert seed_sensor_types() == (4, 6)
    assert seed_sensor_types() == (0, 0)
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        items = session.scalars(select(SensorType).options(selectinload(SensorType.measurements))).all()
        assert len(items) == 4
        bme280 = next(item for item in items if item.code == "BME280")
        assert {item.key for item in bme280.measurements} == {"temperature", "humidity", "pressure"}
        assert bme280.created_at.tzinfo is not None
        assert all(item.created_at.tzinfo is not None for item in bme280.measurements)
    engine.dispose()
