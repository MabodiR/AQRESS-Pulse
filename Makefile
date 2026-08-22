.PHONY: up down build logs ps migrate downgrade seed-admin seed-sensor-types backend-test backend-lint simulator-test simulator-lint frontend-lint frontend-typecheck frontend-build check

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

migrate:
	docker compose run --rm backend alembic upgrade head

downgrade:
	docker compose run --rm backend alembic downgrade -1

seed-admin:
	docker compose run --rm backend python -m app.scripts.seed_admin

seed-sensor-types:
	docker compose run --rm backend python -m app.scripts.seed_sensor_types

backend-test:
	docker compose run --rm backend pytest

backend-lint:
	docker compose run --rm backend ruff check .

simulator-test:
	docker compose --profile simulator run --rm simulator pytest

simulator-lint:
	docker compose --profile simulator run --rm simulator ruff check .

frontend-lint:
	docker compose run --rm frontend npm run lint

frontend-typecheck:
	docker compose run --rm frontend npm run typecheck

frontend-build:
	docker compose run --rm frontend npm run build

check: backend-lint backend-test simulator-lint simulator-test frontend-lint frontend-typecheck frontend-build
