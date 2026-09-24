.PHONY: up down logs seed test lint format reset health

up:
	docker compose up -d

down:
	docker compose down -v

logs:
	docker compose logs -f

seed:
	docker compose exec backend python seed.py

test:
	docker compose exec backend pytest

lint:
	docker compose exec backend flake8 app tests

format:
	docker compose exec backend black app tests

reset: down up

health:
	curl -s http://localhost:8000/api/v1/health | jq
