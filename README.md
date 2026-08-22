# AQRESS Pulse

AQRESS Pulse is a configurable IoT sensor and device management platform. This repository contains the **V0.1.1 Phase 6 Device Communication and Simulator** application, built on the foundations delivered in Phases 1–5.

Devices authenticate to EMQX with individually provisioned credentials and broker-enforced per-Device topic ACLs. The MQTT control worker tracks heartbeat presence and configuration acknowledgments, while the optional simulator exercises the complete control-plane lifecycle. Telemetry ingestion, readings, dashboards, deployment, and cloud infrastructure are intentionally not implemented yet.

## Prerequisites

- Docker Desktop with Docker Compose v2
- Git (recommended)
- Optional for running outside Docker: Python 3.12+ and Node.js 22+

## Quick start

1. Create a local environment file:

   ```bash
   cp .env.example .env
   ```

2. Change all local-only passwords, `JWT_SECRET_KEY`, and `EMQX_NODE_COOKIE` in `.env`.

3. Build and start the core services:

   ```bash
   docker compose up --build
   ```

   To run in the background, add `-d`.

4. Open the services:

   - React frontend: <http://localhost:5173>
   - FastAPI health: <http://localhost:8000/api/v1/health>
   - FastAPI Swagger UI: <http://localhost:8000/docs>
   - EMQX dashboard: <http://localhost:18083>
   - MQTT: `localhost:1883`
   - PostgreSQL: `localhost:5433`

The expected API health response is:

```json
{"status":"healthy"}
```

The backend applies pending Alembic migrations before starting. Seed the local administrator after the stack is healthy:

```bash
docker compose run --rm backend python -m app.scripts.seed_admin
```

The seed reads `AQRESS_PULSE_ADMIN_*` values from `.env` and is idempotent.

Open <http://localhost:5173> and sign in with the configured development admin email and password. The frontend restores sessions through `/auth/me`, rotates expired access tokens through `/auth/refresh`, and logs out when refresh is no longer valid.

The optional Device simulator is started separately after an administrator provisions its one-time MQTT password; see [Device communication and simulator](#device-communication-and-simulator).

## Database migrations

Apply all migrations:

```bash
docker compose run --rm backend alembic upgrade head
```

Show the current revision or history:

```bash
docker compose run --rm backend alembic current
docker compose run --rm backend alembic history
```

Downgrade one revision, then restore it:

```bash
docker compose run --rm backend alembic downgrade -1
docker compose run --rm backend alembic upgrade head
```

All schema changes must be implemented through Alembic. Do not create application tables manually.

## Authentication API

Authentication endpoints are under `/api/v1/auth`:

- `POST /login` accepts JSON `{"email":"...","password":"..."}`.
- `GET /me` requires `Authorization: Bearer <access_token>`.
- `POST /refresh` accepts JSON `{"refresh_token":"..."}` and rotates the token.
- `POST /logout` accepts JSON `{"refresh_token":"..."}` and records revocation server-side.

Example login after seeding:

```bash
curl --fail --request POST http://localhost:8000/api/v1/auth/login \
  --header 'Content-Type: application/json' \
  --data '{"email":"admin@aqress.dev","password":"YOUR_LOCAL_ADMIN_PASSWORD"}'
```

Access tokens live for 15 minutes and refresh tokens for 7 days by default. Both lifetimes are configurable. Refresh tokens rotate on use; the used token is revoked and cannot be reused. PostgreSQL stores only SHA-256 hashes of refresh tokens. Passwords are hashed with Argon2id.

## Site and Device API

All endpoints require authentication. `ADMIN` and `USER` roles can read and write; `VIEWER` is read-only and receives `403 Forbidden` for write operations.

- Sites: `GET/POST /api/v1/sites`, `GET/PUT /api/v1/sites/{id}`, `PATCH /api/v1/sites/{id}/status`, and `GET /api/v1/sites/{id}/devices`.
- Devices: `GET/POST /api/v1/devices`, `GET/PUT /api/v1/devices/{id}`, and `PATCH /api/v1/devices/{id}/status`.

Collections accept `page` and `page_size` (defaults `1` and `25`, maximum `100`). Sites support `search` and `is_active`; devices support `search`, `site_id`, `status`, and `is_active`. Results use `items` plus a `pagination` object.

Example site and device requests, using an access token in `TOKEN`:

```bash
curl --request POST http://localhost:8000/api/v1/sites \
  --header "Authorization: Bearer $TOKEN" --header 'Content-Type: application/json' \
  --data '{"name":"AQRESS IoT Lab","description":"Pulse development laboratory","latitude":-26.2041,"longitude":28.0473}'

curl --request POST http://localhost:8000/api/v1/devices \
  --header "Authorization: Bearer $TOKEN" --header 'Content-Type: application/json' \
  --data '{"site_id":"SITE_UUID","device_uid":"ESP32-A8C339","name":"Lab ESP32 Controller","description":"Development IoT controller","device_type":"ESP32","manufacturer":"Espressif","model":"ESP32","firmware_version":"0.1.0","connection_type":"WIFI"}'
```

New devices always start as `PROVISIONING`; Phase 3 never marks a device online automatically. Normal application flows use soft activation/deactivation and provide no physical delete endpoints.

## Sensor Type framework

A Sensor Type is a global reusable catalogue definition, not a physical Sensor attached to a Device. It defines a stable `code`, firmware-facing `driver_key`, controlled interface type, configuration contract, and one or more Measurement Definitions. Measurement keys are unique within their Sensor Type, so both BME280 and DS18B20 can legitimately expose `temperature`.

Sensor Type endpoints are under `/api/v1/sensor-types`:

- `GET/POST /sensor-types`
- `GET/PUT /sensor-types/{id}`
- `PATCH /sensor-types/{id}/status`
- `GET/POST /sensor-types/{id}/measurements`
- `PUT /sensor-types/{id}/measurements/{measurement_id}`

All authenticated roles may read the catalogue. Only `ADMIN` may create, update, deactivate, or manage Measurement Definitions. The catalogue list supports standard page pagination, search across name/code/manufacturer/model, and `interface_type` and `is_active` filters.

`configuration_schema` is PostgreSQL JSONB containing a documented subset of JSON Schema Draft 2020-12. Supported root keywords are `type`, `properties`, `required`, `title`, `description`, and `additionalProperties`. Supported field keywords are `type`, `title`, `description`, `default`, `minimum`, `maximum`, and `enum`. Field values may be `string`, `integer`, `number`, or `boolean`; nested objects are not supported in V0.1, and `additionalProperties` must be `false`.

The backend uses the `jsonschema` library to validate both catalogue schemas and future configuration payloads through a reusable configuration validation service.

Seed the development catalogue after migrations:

```bash
docker compose run --rm backend python -m app.scripts.seed_sensor_types
# or
make seed-sensor-types
```

The idempotent seed provides:

- DS18B20 Temperature Sensor
- BME280 Environmental Sensor with temperature, humidity, and pressure
- Generic Digital Input
- Generic Analog Input

Open <http://localhost:5173/sensor-types> after login to browse the catalogue. Administrators can create/edit Sensor Types and add Measurement Definitions through the UI.

## Physical Sensors and configuration

A Sensor is a physical instance attached to one Device and backed by one Sensor Type. Its `sensor_uid` identifies it only within that Device: the database enforces `UNIQUE(device_id, sensor_uid)`, so two Devices may each have an `ENV-001`, while one Device may not have it twice.

Creating a Sensor is atomic. AQRESS Pulse validates the active Device, the active and ready Sensor Type, and the submitted values against the Phase 4 JSON Schema contract. It then creates exactly one Sensor Channel for each Measurement Definition and configuration version 1. Channels preserve the catalogue definition present at registration time; later catalogue changes are not automatically reconciled with existing Sensors in Phase 5.

Configuration edits never overwrite history. They supersede the previous desired version and create the next version as `PENDING`, with a PostgreSQL partial unique index ensuring only one `is_current = true` record per Sensor. “Current” means the latest desired state in AQRESS Pulse. Phase 6 can publish that state to the Device, then record its `APPLIED` or `FAILED` acknowledgment.

To add a Sensor, open an active Device, choose **Add Sensor**, select a ready Sensor Type, enter its identity, complete the dynamically generated configuration form, review, and save. The generic renderer supports the Phase 4 schema subset: string, integer, number, boolean, enum, title, description, defaults, minimum/maximum, and required fields.

Sensor endpoints are under `/api/v1`:

- `GET /sensors` with Device, Site, Sensor Type, status, enabled, search, and pagination filters.
- `GET/POST /devices/{device_id}/sensors` for Device-scoped listing and atomic registration.
- `GET/PUT /sensors/{sensor_id}` and `PATCH /sensors/{sensor_id}/status`.
- `GET /sensors/{sensor_id}/configuration`, `GET /sensors/{sensor_id}/configurations`, and `PUT /sensors/{sensor_id}/configuration`.
- `PUT /sensors/{sensor_id}/channels/{channel_id}` for display name, unit, and enabled state only.

`ADMIN` and `USER` may manage Sensor instances, Channels, and configuration versions. `VIEWER` is read-only. Sensor Type catalogue writes remain restricted to `ADMIN`.

## Device communication and simulator

Each Device has a stable MQTT username (`device:<device_uid>`) and a random password that is shown only when provisioned or rotated. AQRESS Pulse stores only its Argon2id hash. Provision, rotate, and revoke are administrator-only operations on Device Detail. Rotation immediately invalidates the prior password on the next connection; revocation prevents authentication entirely.

EMQX delegates password authentication to the internal-only `mqtt-auth` service. Its successful response contains an exact per-Device ACL, and the broker applies default-deny authorization. A Device may publish only its own heartbeat, configuration acknowledgment, and reserved telemetry topic, and may subscribe only to its own configuration and reserved command topic. The separate platform identity can publish Device configurations and subscribe to heartbeat and acknowledgment topics. `mqtt-auth` has no host port and does not expose API documentation.

The Phase 6 topic namespace is:

```text
aqress/pulse/v1/devices/{device_uid}/status
aqress/pulse/v1/devices/{device_uid}/config
aqress/pulse/v1/devices/{device_uid}/config/ack
aqress/pulse/v1/devices/{device_uid}/telemetry   # reserved; not consumed
aqress/pulse/v1/devices/{device_uid}/command     # reserved; not published
aqress/pulse/v1/devices/{device_uid}/command/ack # reserved; not consumed
```

Configuration snapshots use QoS 1 and retained delivery. The worker subscribes only to `status` and `config/ack`; it deliberately does not subscribe to telemetry. Valid heartbeats set the Device `ONLINE` and update `last_seen` with server receive time. An `ONLINE` Device becomes `OFFLINE` after `DEVICE_OFFLINE_TIMEOUT_SECONDS` without a heartbeat. Disabled Devices are not brought online and are excluded from offline transitions.

A heartbeat has this shape (the first four fields are required):

```json
{
  "device_uid": "ESP32-A8C339",
  "timestamp": "2026-08-22T14:30:00Z",
  "status": "ONLINE",
  "uptime_seconds": 120,
  "firmware_version": "0.1.0",
  "wifi_rssi": -61,
  "free_memory": 183240
}
```

A Device configuration is one snapshot containing stable external identifiers, each current desired version, its configuration, and its Channels:

```json
{
  "message_id": "a UUID",
  "device_uid": "ESP32-A8C339",
  "generated_at": "2026-08-22T14:35:00Z",
  "sensors": [{
    "sensor_uid": "ENV-001",
    "driver_key": "bme280",
    "enabled": true,
    "configuration_version": 2,
    "configuration": {"i2c_address": "0x76", "sample_interval_seconds": 30},
    "channels": [{"key": "temperature", "enabled": true, "unit": "°C"}]
  }]
}
```

The acknowledgment echoes the snapshot `message_id` and reports `APPLIED` or `FAILED` for each Sensor version:

```json
{
  "message_id": "the snapshot UUID",
  "device_uid": "ESP32-A8C339",
  "timestamp": "2026-08-22T14:35:02Z",
  "results": [{
    "sensor_uid": "ENV-001",
    "configuration_version": 2,
    "status": "APPLIED",
    "error": null
  }]
}
```

Configuration statuses have these meanings:

- `PENDING`: desired version exists but has not been successfully published.
- `PUBLISHED`: the retained snapshot was accepted by EMQX and is awaiting the Device.
- `APPLIED`: the Device acknowledged that exact current Sensor version successfully.
- `FAILED`: the Device rejected that exact current Sensor version.
- `SUPERSEDED`: a newer desired version replaced it.

Duplicate acknowledgments are idempotent and stale-version acknowledgments are ignored. Publishing an already applied current version does not create a new version or regress its status. A broker publish failure leaves the database state unchanged.

To run the simulator:

1. Sign in as an administrator, open a Device, and choose **Provision Credentials** (or **Rotate Credentials**).
2. Copy the one-time username and password into the `SIMULATOR_*` values in your ignored `.env`.
3. Start the simulator profile:

   ```bash
   docker compose --profile simulator up --build simulator
   ```

The simulator publishes heartbeats, receives retained configuration snapshots, keeps supported configuration in memory, and publishes acknowledgments. It never generates telemetry in Phase 6. Set `SIMULATOR_FORCE_CONFIG_FAILURE=true` to test a deterministic `FAILED` acknowledgment. Stop it and wait for the configured timeout to verify the `OFFLINE` transition.

Device communication endpoints are under `/api/v1/devices/{device_id}`:

- `GET /mqtt-credentials/status` for credential metadata (all authenticated roles).
- `POST /mqtt-credentials`, `/mqtt-credentials/rotate`, and `/mqtt-credentials/revoke` (`ADMIN` only).
- `POST /sync-configuration` (`ADMIN` and `USER`).

To verify credentials and ACLs directly against the live broker, run the built-in probe from the backend network after provisioning:

```bash
docker compose exec backend python -m app.scripts.mqtt_acl_probe \
  --username 'device:ESP32-A8C339' \
  --password 'ONE_TIME_PASSWORD' \
  --device-uid ESP32-A8C339
```

The probe requires valid authentication, tests status/ACK publishing and config subscription, and verifies that cross-Device operations are denied. Add `--expect-rejected` when checking an old or revoked password.

## Verify the stack

```bash
docker compose ps
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:5173
docker compose exec postgres pg_isready -U aqress_pulse -d aqress_pulse
docker compose exec emqx emqx ctl status
```

Run all Phase 1–6 checks:

```bash
make check
```

Or run checks separately:

```bash
docker compose run --rm backend ruff check .
docker compose run --rm backend pytest
docker compose --profile simulator run --rm simulator ruff check .
docker compose --profile simulator run --rm simulator pytest
docker compose run --rm frontend npm run lint
docker compose run --rm frontend npm run typecheck
docker compose run --rm frontend npm run build
```

Backend tests create and drop dedicated `aqress_pulse_test` and `aqress_pulse_migration_test` databases. They do not truncate or mutate the normal `aqress_pulse` development database.

## Common commands

```bash
make up       # build and start services in the foreground
make ps       # show service and health state
make logs     # follow logs
make down     # stop services without deleting data
make migrate  # apply Alembic migrations
make seed-admin # create the configured local admin if absent
make seed-sensor-types # create the reusable Sensor Type catalogue idempotently
```

To reset the complete local environment, including PostgreSQL and EMQX data:

```bash
docker compose down --volumes
docker compose up --build -d
docker compose run --rm backend python -m app.scripts.seed_admin
```

This permanently deletes local development data.

## Run outside Docker (optional)

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Frontend, in a separate terminal:

```bash
cd frontend
npm ci
npm run dev
```

PostgreSQL and EMQX can remain in Docker:

```bash
docker compose up postgres emqx
```

## Repository structure

```text
backend/                 FastAPI application and tests
  app/api/v1/            Versioned API routes
  app/core/              Configuration, security, and API errors
  app/db/                SQLAlchemy base and async sessions
  app/models/            User, Site, Device, Sensor Type, and physical Sensor models
  app/repositories/      Database access
  app/schemas/           Pydantic API schemas
  app/services/          Authentication and domain business rules
  alembic/               Versioned PostgreSQL migrations
frontend/                React + TypeScript + Vite application
simulator/               Phase 6 authenticated Device simulator and tests
emqx/                    Pinned EMQX image and broker auth/ACL configuration
Doc/                     Product and engineering source documents
docker-compose.yml       Local service orchestration
.env.example             Safe local configuration template
Makefile                 Common development commands
```

The MQTT control worker lives under `backend/app/mqtt`. No ingestion or firmware implementation exists in Phase 6.

## Local configuration notes

- `.env` is ignored by Git; `.env.example` contains placeholders only.
- Compose has local fallback values so the stack can start before `.env` is copied. Change them before using the environment beyond isolated local development.
- Set a long random `EMQX_NODE_COOKIE` in `.env`; it protects Erlang node communication and must match across broker nodes if clustering is introduced later.
- PostgreSQL uses host port `5433` by default to avoid collisions with an existing local PostgreSQL installation; it remains on port `5432` inside Compose.
- EMQX dashboard credentials are independent of Device MQTT credentials. Device and platform access is authenticated through the internal service and authorized by broker-enforced ACLs.
- PostgreSQL contains the Phase 1–5 tables plus `device_mqtt_credentials`. It intentionally does not contain `sensor_readings`.
- Application source is copied into the local images rather than bind-mounted, which avoids Docker Desktop file-sharing requirements for the XAMPP workspace. Rebuild after code changes with `docker compose up --build`; use the optional direct-host commands for hot reload.
- All database/API timestamps are timezone-aware and stored in UTC using PostgreSQL `TIMESTAMPTZ`.
- Local development defaults are intentionally not production credentials. Replace them in `.env`; never commit that file.

## Phase boundary

Phase 6 implements secure per-Device MQTT identities, broker-enforced isolation, heartbeat presence, desired-configuration publish/acknowledgment, and a control-plane simulator. It does **not** ingest telemetry, create readings, produce simulated measurements, build dashboards, deploy infrastructure, or implement any Phase 7+ work.
