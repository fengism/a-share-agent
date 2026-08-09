SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_HOST ?= 127.0.0.1
FRONTEND_PORT ?= 5173
STARTUP_TIMEOUT ?= 90

RUN_ENV = BACKEND_HOST="$(BACKEND_HOST)" BACKEND_PORT="$(BACKEND_PORT)" FRONTEND_HOST="$(FRONTEND_HOST)" FRONTEND_PORT="$(FRONTEND_PORT)" STARTUP_TIMEOUT="$(STARTUP_TIMEOUT)"

.PHONY: help setup start stop restart status logs dev prod pack check test \
	backend-sync backend-dev backend-lint backend-test backend-db-init backend-reset-accounts \
	frontend-install frontend-dev frontend-test frontend-build frontend-lint \
	export-industry-mapping docker-up docker-down docker-restart docker-build docker-logs docker-status

help: ## 显示可用命令
	@awk 'BEGIN {FS = ":.*## "; printf "用法: make <target>\n\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## 安装前后端依赖
	./setup.sh

start: dev ## 启动开发环境

dev: ## 启动开发环境（热重载）
	$(RUN_ENV) ./start.sh dev

prod: ## 构建并启动本地生产模式
	$(RUN_ENV) ./start.sh prod

stop: ## 安全停止当前项目服务
	$(RUN_ENV) ./stop.sh

restart: ## 重启开发环境
	$(RUN_ENV) ./stop.sh
	$(RUN_ENV) ./start.sh dev

status: ## 查看前后端端口状态
	@printf "后端 (:$(BACKEND_PORT))\n"; lsof -nP -iTCP:$(BACKEND_PORT) -sTCP:LISTEN || printf "  未运行\n"
	@printf "\n前端 (:$(FRONTEND_PORT))\n"; lsof -nP -iTCP:$(FRONTEND_PORT) -sTCP:LISTEN || printf "  未运行\n"

logs: ## 持续查看前后端日志
	@mkdir -p logs && touch logs/backend.log logs/frontend.log
	tail -n 100 -f logs/backend.log logs/frontend.log

test: backend-test frontend-test ## 运行前后端测试

check: backend-lint backend-test frontend-test frontend-lint frontend-build ## 运行完整质量检查

pack: ## 打包源码（排除密钥、依赖、数据库和日志）
	tar czf stock-agent.tar.gz \
		--exclude='stock-agent.tar.gz' \
		--exclude='.git' \
		--exclude='.env' \
		--exclude='.env.local' \
		--exclude='.env.*.local' \
		--exclude='.claude' \
		--exclude='.agents' \
		--exclude='.codex' \
		--exclude='.harness_local' \
		--exclude='AGENTS.local.md' \
		--exclude='backend/.venv' \
		--exclude='backend/data' \
		--exclude='backend/tests' \
		--exclude='frontend/node_modules' \
		--exclude='frontend/dist' \
		--exclude='docs/superpowers' \
		--exclude='note' \
		--exclude='logs' \
		--exclude='data' \
		--exclude='__pycache__' \
		--exclude='.pytest_cache' \
		--exclude='.ruff_cache' \
		--exclude='*.db' \
		--exclude='*.db-wal' \
		--exclude='*.db-shm' \
		.
	@echo "打包完成: stock-agent.tar.gz ($$(du -h stock-agent.tar.gz | cut -f1))"

backend-sync: ## 同步后端锁定依赖
	cd backend && uv sync --frozen

backend-dev: ## 单独启动后端
	cd backend && uv run --frozen uvicorn app.main:app --reload --host "$(BACKEND_HOST)" --port "$(BACKEND_PORT)"

backend-lint: ## 检查后端代码规范
	cd backend && uvx --from ruff==0.12.11 ruff check --config pyproject.toml app tests

backend-test: ## 运行后端测试
	cd backend && uv run --frozen pytest -q

backend-db-init: ## 初始化双数据库并应用结构迁移
	cd backend && uv run --frozen python -c 'from app.infrastructure.persistence import init_db; init_db(); print("database initialization complete")'

backend-reset-accounts: ## 重置本地账号数据
	cd backend && uv run --frozen python -m app.scripts.reset_accounts

frontend-install: ## 按 lockfile 安装前端依赖
	cd frontend && npm ci

frontend-dev: ## 单独启动前端
	cd frontend && VITE_API_PROXY_TARGET="http://127.0.0.1:$(BACKEND_PORT)" npm run dev -- --host "$(FRONTEND_HOST)" --port "$(FRONTEND_PORT)" --strictPort

frontend-test: ## 运行前端测试
	cd frontend && npm test

frontend-build: ## 构建前端
	cd frontend && npm run build

frontend-lint: ## 运行前端 lint
	cd frontend && npm run lint

export-industry-mapping: ## 更新行业映射文件
	cd backend && uv run --frozen python -c 'from app.modules.screener.industry.service import update_industry_mapping_sw_second_file; update_industry_mapping_sw_second_file()'

docker-up: ## 启动 Docker 服务
	docker compose up -d

docker-down: ## 停止 Docker 服务
	docker compose down

docker-restart: ## 重启 Docker 服务
	docker compose down
	docker compose up -d

docker-build: ## 重新构建 Docker 镜像
	docker compose build

docker-logs: ## 持续查看 Docker 日志
	docker compose logs -f

docker-status: ## 查看 Docker 服务状态
	docker compose ps
