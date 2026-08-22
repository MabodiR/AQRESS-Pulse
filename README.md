# AQRESS Pulse

AQRESS Pulse is a configurable IoT sensor and device management platform. This repository contains the **V0.1.1 Phase 5 Physical Sensor Management** application, built on the Phase 1 infrastructure, Phase 2 authentication, Phase 3 Site and Device Management, and Phase 4 Sensor Type Framework.

Authenticated users can attach physical Sensors to Devices, generate Channels from the reusable Sensor Type catalogue, and maintain immutable desired-configuration history. MQTT device communication, telemetry, simulation, dashboards, and deployment are intentionally not implemented yet.

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

3. Build and start all services:

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

Configuration edits never overwrite history. They supersede the previous desired version and create the next version as `PENDING`, with a PostgreSQL partial unique index ensuring only one `is_current = true` record per Sensor. “Current” means the latest desired state in AQRESS Pulse. It does not mean hardware has received or applied it; `APPLIED` and `applied_at` remain reserved for a later MQTT synchronization phase.

To add a Sensor, open an active Device, choose **Add Sensor**, select a ready Sensor Type, enter its identity, complete the dynamically generated configuration form, review, and save. The generic renderer supports the Phase 4 schema subset: string, integer, number, boolean, enum, title, description, defaults, minimum/maximum, and required fields.

Sensor endpoints are under `/api/v1`:

- `GET /sensors` with Device, Site, Sensor Type, status, enabled, search, and pagination filters.
- `GET/POST /devices/{device_id}/sensors` for Device-scoped listing and atomic registration.
- `GET/PUT /sensors/{sensor_id}` and `PATCH /sensors/{sensor_id}/status`.
- `GET /sensors/{sensor_id}/configuration`, `GET /sensors/{sensor_id}/configurations`, and `PUT /sensors/{sensor_id}/configuration`.
- `PUT /sensors/{sensor_id}/channels/{channel_id}` for display name, unit, and enabled state only.

`ADMIN` and `USER` may manage Sensor instances, Channels, and configuration versions. `VIEWER` is read-only. Sensor Type catalogue writes remain restricted to `ADMIN`.

## Verify the stack

```bash
docker compose ps
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:5173
docker compose exec postgres pg_isready -U aqress_pulse -d aqress_pulse
docker compose exec emqx emqx ctl status
```

Run all Phase 1–5 checks:

```bash
make check
```

Or run checks separately:

```bash
docker compose run --rm backend ruff check .
docker compose run --rm backend pytest
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
Doc/                     Product and engineering source documents
docker-compose.yml       Local service orchestration
.env.example             Safe local configuration template
Makefile                 Common development commands
```

The ingestion worker, simulator, and firmware directories will be added in their assigned phases rather than populated prematurely.

## Local configuration notes

- `.env` is ignored by Git; `.env.example` contains placeholders only.
- Compose has local fallback values so the stack can start before `.env` is copied. Change them before using the environment beyond isolated local development.
- Set a long random `EMQX_NODE_COOKIE` in `.env`; it protects Erlang node communication and must match across broker nodes if clustering is introduced later.
- PostgreSQL uses host port `5433` by default to avoid collisions with an existing local PostgreSQL installation; it remains on port `5432` inside Compose.
- EMQX dashboard credentials are configured separately from future per-device MQTT authentication and ACLs. Device identities and topic isolation belong to later phases.
- PostgreSQL contains `users`, `refresh_tokens`, `sites`, `devices`, `sensor_types`, `measurement_definitions`, `sensors`, `sensor_channels`, `sensor_configurations`, and Alembic version tables. It intentionally does not contain `sensor_readings`.
- Application source is copied into the local images rather than bind-mounted, which avoids Docker Desktop file-sharing requirements for the XAMPP workspace. Rebuild after code changes with `docker compose up --build`; use the optional direct-host commands for hot reload.
- All database/API timestamps are timezone-aware and stored in UTC using PostgreSQL `TIMESTAMPTZ`.
- Local development defaults are intentionally not production credentials. Replace them in `.env`; never commit that file.

## Phase boundary

Phase 5 implements local physical Sensor registration, generated Channels, and immutable desired-configuration versioning. It does not publish or subscribe over MQTT, create broker credentials or ACLs, update Device presence, mark configurations published/applied, ingest telemetry, create readings, simulate hardware, build dashboards, or deploy cloud infrastructure. Do not proceed to Phase 6 without an explicit instruction.
