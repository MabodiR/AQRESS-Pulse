# AQRESS SenseGrid Codex Build Prompt

**Version:** V0.1.1  
**Status:** Authoritative / Current  
**Supersedes:** All earlier AQRESS SenseGrid Codex Markdown prompts. Do not use older prompt copies.

# 1. Role and Objective

- Act as a senior full-stack software architect and developer building AQRESS SenseGrid, a configurable IoT sensor and device management platform.

- The first milestone must run entirely on a local development machine. Do not implement cloud deployment yet.

- Target flow: React + TypeScript → FastAPI/Python → PostgreSQL → EMQX/MQTT → Python device simulator/ESP32.

# 2. Core Product Scope

- Users can create sites, register devices, define supported sensor types, add sensor instances, dynamically configure them, publish configuration, receive acknowledgement, ingest readings and view latest/history data.

- The platform must support sensors with one or many measurement channels and must not hard-code temperature/humidity/pressure tables.

- Core model: Site → Device → Sensor → Sensor Configuration; Sensor Type → Measurement Definition; Sensor → Sensor Channel → Sensor Reading.

# 3. Technology Baseline

- Frontend: React, TypeScript, Vite, React Router, TanStack Query, React Hook Form, Zod, Tailwind CSS, shadcn/ui, Recharts.

- Backend: Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, Alembic, PostgreSQL driver, JWT authentication, password hashing, pytest.

- Messaging: EMQX MQTT. Infrastructure: Docker + Docker Compose. Separate user-facing API from telemetry ingestion worker.

# 4. Corrected Data Model

- users: id, first_name, last_name, email UNIQUE, password_hash, role (ADMIN/USER/VIEWER), is_active, created_at, updated_at.

- refresh_tokens: id, user_id, token_hash, expires_at, revoked_at, created_at. Store only the token hash.

- devices.device_uid is globally UNIQUE.

- sensors: UNIQUE(device_id, sensor_uid). sensor_uid is not globally unique.

- measurement_definitions: UNIQUE(sensor_type_id, key).

- sensor_channels: UNIQUE(sensor_id, measurement_definition_id).

- sensor_configurations: UNIQUE(sensor_id, config_version); published configurations are immutable and edits create new versions.

- sensor_readings reference sensor_channel_id, sensor_id and device_id and support numeric/text/boolean typed values plus raw_payload JSONB.

# 5. Configuration Schema Standard

- sensor_types.configuration_schema must use a documented subset of JSON Schema stored as PostgreSQL JSONB.

- React uses this schema to generate dynamic forms; Python performs authoritative validation against the same contract.

- Do not create a proprietary ad-hoc schema format.

# 6. Time Standard

- Use PostgreSQL TIMESTAMPTZ for all timestamps and persist all server-side times in UTC.

- Use ISO 8601 in APIs. recorded_at is device-recorded time; received_at is server-received time.

- React localises timestamps for display without changing stored UTC values.

# 7. Pagination Standard

- Inventory endpoints such as sites/devices/sensors use page and page_size with bounded defaults (for example 25).

- Historical readings use time range + limit + cursor continuation. Do not return unbounded telemetry arrays.

# 8. MQTT Contract and Authorization

- Topics: sensegrid/{device_uid}/telemetry, /status, /config, /config/ack, /command, /command/ack.

- Each device has its own identity/credentials. Broker ACLs allow publish only telemetry/status/config-ack/command-ack and subscribe only config/command for that same device UID.

- A device must never access another device namespace. Local username/password is acceptable; prepare for TLS/certificates later.

# 9. Local Definition of Done

- User logs in; creates site; registers device; simulator connects; device becomes online; user adds/configures supported sensor; JSON Schema form validates; configuration is published and acknowledged; telemetry is ingested to PostgreSQL; latest and historical readings render in React; multi-measurement sensors work; device goes offline when heartbeats stop.

# 10. Implementation Phases

| **Phase**                     | **Implement**                                                                                                                | **Stop condition**                                                                                                    |
|-------------------------------|------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| 1 — Project Foundation        | Monorepo structure, Docker Compose, PostgreSQL, EMQX, FastAPI skeleton, React skeleton, .env.example, health checks, README. | docker compose up starts local services and GET /api/v1/health returns healthy. Do not create domain schema/auth yet. |
| 2 — Database & Authentication | SQLAlchemy/Alembic, corrected tables/constraints, UTC TIMESTAMPTZ, users.role, hashed refresh tokens, JWT auth, admin seed.  | Database recreates from zero; auth tests pass. Stop before Sites/Devices UI.                                          |
| 3 — Sites & Devices           | Site/device CRUD, device detail, pagination.                                                                                 | Create/view/edit sites and devices locally; tests pass.                                                               |
| 4 — Sensor Type Framework     | Sensor types, JSON Schema subset, measurement definitions, validation, seed DS18B20/BME280/Digital/Analog types.             | Dynamic schemas validate correctly; tests pass.                                                                       |
| 5 — Sensor Management UI      | Add Sensor wizard, sensor channels, enable/disable, immutable configuration versions and edit flow.                          | A sensor can be created/configured from React without firmware editing.                                               |
| 6 — MQTT Device Simulator     | Python simulator heartbeat, subscribe config, acknowledge config, realistic DS18B20/BME280/Digital readings.                 | Simulator connects to local EMQX and follows the device contract.                                                     |
| 7 — Telemetry Ingestion       | Separate ingestion worker, validation, raw payload, DB inserts, heartbeat and config ack processing.                         | Valid telemetry persists; invalid device/sensor/channel/type is rejected and tested.                                  |
| 8 — Readings & Dashboard      | Latest/history APIs, bounded/cursor telemetry, charts, online/offline, dashboard, SSE/WebSocket.                             | Live/latest/history values appear correctly in React.                                                                 |
| 9 — Local Integration Testing | Execute complete local flow end to end and fix failures.                                                                     | Site → Device → Sensor → Config → MQTT → PostgreSQL → React passes reliably.                                          |
| 10 — Local MVP Hardening      | Security, validation, logging, indexes, typing, tests, responsive UI, empty/loading/offline states, README.                  | Produce local MVP readiness report. Deployment remains out of scope.                                                  |

# 11. Codex Execution Rules

- Inspect the repository before changing files and preserve existing working functionality.

- Implement only the requested phase. Never begin the next phase automatically.

- At the end of each phase run tests, lint/type checks and the application where applicable; fix failures before reporting completion.

- Update README and .env.example whenever setup/configuration changes.

- Do not introduce AI, predictive maintenance, billing, mobile apps, LoRaWAN, SMS/WhatsApp, remote industrial control, Kubernetes or cloud deployment in V0.1.

- Do not put business logic in FastAPI route handlers; use service/repository layers. Do not expose SQLAlchemy models directly.

- Use Python typing and TypeScript types throughout. Do not silently swallow errors or log plaintext credentials/secrets.

# 12. Prompt to Start Phase 1

*Start with Phase 1 only. Build the AQRESS SenseGrid local project foundation. Verify docker compose up, PostgreSQL, EMQX, FastAPI and React are healthy; implement GET /api/v1/health; update README; run checks; fix errors; then stop. Do not implement database domain tables, authentication, sensor logic or deployment yet. At completion report files changed, commands run, checks/results, exact local test commands and known limitations.*
