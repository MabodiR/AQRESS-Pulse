# AQRESS SenseGrid

AQRESS SenseGrid is a configurable IoT sensor and device management platform. This repository currently contains the **V0.1.1 Phase 1 project foundation only**: PostgreSQL, EMQX, a FastAPI API skeleton, and a React/TypeScript/Vite frontend.

Domain tables, authentication, device and sensor management, telemetry ingestion, simulation, dashboards, and deployment are intentionally not implemented yet.

## Prerequisites

- Docker Desktop with Docker Compose v2
- Git (recommended)
- Optional for running outside Docker: Python 3.12+ and Node.js 22+

## Quick start

1. Create a local environment file:

   ```bash
   cp .env.example .env
   ```

2. Change the local-only passwords in `.env`.

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

## Verify the stack

```bash
docker compose ps
curl --fail http://localhost:8000/api/v1/health
curl --fail http://localhost:5173
docker compose exec postgres pg_isready -U sensegrid -d sensegrid
docker compose exec emqx emqx ctl status
```

Run all Phase 1 checks:

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

## Common commands

```bash
make up       # build and start services in the foreground
make ps       # show service and health state
make logs     # follow logs
make down     # stop services without deleting data
```

To stop services and remove local PostgreSQL/EMQX data volumes:

```bash
docker compose down --volumes
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
  app/core/              Environment-backed configuration
  app/schemas/           Pydantic API schemas
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
- PostgreSQL is available but has no AQRESS domain schema or Alembic migrations in Phase 1.
- Application source is copied into the Phase 1 images rather than bind-mounted, which avoids Docker Desktop file-sharing requirements for the XAMPP workspace. Rebuild after code changes with `docker compose up --build`; use the optional direct-host commands for hot reload.

## Phase boundary

Phase 1 proves that the local development platform starts and that the frontend can reach the FastAPI health endpoint. Do not proceed to Phase 2 without an explicit instruction.
