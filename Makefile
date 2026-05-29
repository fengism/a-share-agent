.PHONY: setup start stop dev prod pack backend-sync backend-dev backend-test frontend-install frontend-dev frontend-build frontend-lint export-industry-mapping docker-up docker-down docker-build docker-logs

# 一键命令
setup:
	./setup.sh

start:
	./start.sh dev

stop:
	./stop.sh

dev:
	./start.sh dev

prod:
	./start.sh prod

# 打包
pack:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	tar czf stock-agent.tar.gz \
		--exclude='backend/.venv' \
		--exclude='backend/__pycache__' \
		--exclude='backend/tests' \
		--exclude='frontend/node_modules' \
		--exclude='logs' \
		--exclude='data' \
		--exclude='.git' \
		--exclude='.claude' \
		--exclude='docs/superpowers' \
		--exclude='note' \
		.
	@echo "打包完成: stock-agent.tar.gz ($$(du -h stock-agent.tar.gz | cut -f1))"

# 单独运行
backend-sync:
	cd backend && uv sync

backend-dev:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

backend-test:
	cd backend && uv run pytest

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npm run lint

export-industry-mapping:
	cd backend && uv run python -m app.services.screener.industry

# Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f
