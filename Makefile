.PHONY: up down build logs ps backend-test backend-lint frontend-lint frontend-typecheck frontend-build check

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

backend-test:
	docker compose run --rm backend pytest

backend-lint:
	docker compose run --rm backend ruff check .

frontend-lint:
	docker compose run --rm frontend npm run lint

frontend-typecheck:
	docker compose run --rm frontend npm run typecheck

frontend-build:
	docker compose run --rm frontend npm run build

check: backend-lint backend-test frontend-lint frontend-typecheck frontend-build
