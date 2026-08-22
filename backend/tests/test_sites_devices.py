import uuid

import pytest
from fastapi.testclient import TestClient

from app.models.user import UserRole
from tests.helpers import create_test_user, login


def auth_headers(client: TestClient, *, role: UserRole = UserRole.ADMIN, email: str = "admin@aqress.dev") -> dict[str, str]:
    create_test_user(email=email, role=role)
    token = login(client, email)["access_token"]
    return {"Authorization": f"Bearer {token}"}


def site_payload(name: str = "AQRESS IoT Lab") -> dict[str, object]:
    return {"name": name, "description": "Pulse development laboratory", "latitude": -26.2041, "longitude": 28.0473}


def create_site(client: TestClient, headers: dict[str, str], name: str = "AQRESS IoT Lab") -> dict[str, object]:
    response = client.post("/api/v1/sites", json=site_payload(name), headers=headers)
    assert response.status_code == 201
    return response.json()


def device_payload(site_id: str, uid: str = "ESP32-A8C339") -> dict[str, object]:
    return {"site_id": site_id, "device_uid": uid, "name": "Lab ESP32 Controller", "description": "Development IoT controller", "device_type": "ESP32", "manufacturer": "Espressif", "model": "ESP32", "firmware_version": "0.1.0", "connection_type": "WIFI"}


def create_device(client: TestClient, headers: dict[str, str], site_id: str, uid: str = "ESP32-A8C339") -> dict[str, object]:
    response = client.post("/api/v1/devices", json=device_payload(site_id, uid), headers=headers)
    assert response.status_code == 201
    return response.json()


def test_site_create_retrieve_update_list_search_and_deactivate(client: TestClient) -> None:
    headers = auth_headers(client)
    created = create_site(client, headers)
    assert created["created_by_user_id"]
    assert client.get(f"/api/v1/sites/{created['id']}", headers=headers).json()["name"] == "AQRESS IoT Lab"
    update = site_payload("AQRESS Main Lab")
    assert client.put(f"/api/v1/sites/{created['id']}", json=update, headers=headers).json()["name"] == "AQRESS Main Lab"
    listing = client.get("/api/v1/sites?search=Main&page=1&page_size=1", headers=headers).json()
    assert listing["pagination"] == {"page": 1, "page_size": 1, "total_items": 1, "total_pages": 1}
    assert listing["items"][0]["id"] == created["id"]
    deactivated = client.patch(f"/api/v1/sites/{created['id']}/status", json={"is_active": False}, headers=headers).json()
    assert deactivated["is_active"] is False


@pytest.mark.parametrize(("field", "value"), [("latitude", -91), ("latitude", 91), ("longitude", -181), ("longitude", 181)])
def test_site_rejects_invalid_coordinates(client: TestClient, field: str, value: int) -> None:
    headers = auth_headers(client)
    payload = site_payload()
    payload[field] = value
    assert client.post("/api/v1/sites", json=payload, headers=headers).status_code == 422


def test_sites_require_authentication_and_viewer_is_read_only(client: TestClient) -> None:
    assert client.get("/api/v1/sites").status_code == 401
    headers = auth_headers(client, role=UserRole.VIEWER, email="viewer@aqress.dev")
    assert client.get("/api/v1/sites", headers=headers).status_code == 200
    response = client.post("/api/v1/sites", json=site_payload(), headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_device_create_detail_update_filters_search_duplicate_and_deactivate(client: TestClient) -> None:
    headers = auth_headers(client)
    site = create_site(client, headers)
    device = create_device(client, headers, site["id"])
    assert device["status"] == "PROVISIONING"
    assert device["last_seen_at"] is None
    assert device["site"]["name"] == "AQRESS IoT Lab"
    assert client.get(f"/api/v1/devices/{device['id']}", headers=headers).status_code == 200
    updated = device_payload(site["id"])
    updated["name"] = "Updated Controller"
    assert client.put(f"/api/v1/devices/{device['id']}", json=updated, headers=headers).json()["name"] == "Updated Controller"
    for query in (f"site_id={site['id']}", "status=PROVISIONING", "search=Updated", "search=ESP32-A8C339"):
        assert client.get(f"/api/v1/devices?{query}", headers=headers).json()["pagination"]["total_items"] == 1
    assert client.get(f"/api/v1/sites/{site['id']}/devices", headers=headers).json()["items"][0]["id"] == device["id"]
    duplicate = client.post("/api/v1/devices", json=device_payload(site["id"]), headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DEVICE_UID_EXISTS"
    disabled = client.patch(f"/api/v1/devices/{device['id']}/status", json={"is_active": False}, headers=headers).json()
    assert disabled["is_active"] is False
    assert disabled["status"] == "DISABLED"


def test_device_invalid_site_auth_and_viewer_rules(client: TestClient) -> None:
    assert client.get("/api/v1/devices").status_code == 401
    admin = auth_headers(client)
    invalid = client.post("/api/v1/devices", json=device_payload(str(uuid.uuid4())), headers=admin)
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "INVALID_SITE"
    site = create_site(client, admin)
    viewer = auth_headers(client, role=UserRole.VIEWER, email="viewer@aqress.dev")
    assert client.get("/api/v1/devices", headers=viewer).status_code == 200
    response = client.post("/api/v1/devices", json=device_payload(site["id"]), headers=viewer)
    assert response.status_code == 403


def test_site_with_device_has_no_delete_endpoint(client: TestClient) -> None:
    headers = auth_headers(client)
    site = create_site(client, headers)
    create_device(client, headers, site["id"])
    assert client.delete(f"/api/v1/sites/{site['id']}", headers=headers).status_code == 405
