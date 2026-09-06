SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_HOST ?= 127.0.0.1
FRONTEND_PORT ?= 5173
STARTUP_TIMEOUT ?= 90

RUN_ENV = BACKEND_HOST="$(BACKEND_HOST)" BACKEND_PORT="$(BACKEND_PORT)" FRONTEND_HOST="$(FRONTEND_HOST)" FRONTEND_PORT="$(FRONTEND_PORT)" STARTUP_TIMEOUT="$(STARTUP_TIMEOUT)"

.PHONY: help setup start stop restart status logs dev prod pack check test \
	backend-sync backend-browser-install backend-dev backend-lint backend-type backend-test backend-db-init backend-reset-accounts \
	frontend-install frontend-dev frontend-api-check frontend-test frontend-e2e frontend-build frontend-lint \
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

check: backend-lint backend-type backend-test frontend-api-check frontend-test frontend-lint frontend-build ## 运行完整质量检查

pack: ## 打包源码（排除密钥、依赖、运行时数据库和日志，使用仓库种子初始化行业库）
	tar czf stock-agent.tar.gz \
		--exclude='stock-agent.tar*' \
		--exclude='.git' \
		--exclude='.env' \
		--exclude='.env.local' \
		--exclude='.env.*.local' \
		--exclude='.claude' \
		--exclude='.agents' \
		--exclude='.codex' \
		--exclude='.harness_local' \
		--exclude='.agy-staff' \
		--exclude='output' \
		--exclude='tmp' \
		--exclude='session-logs' \
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

backend-browser-install: ## 安装主进程浏览器抓取所需 Chromium
	cd backend && uv run --frozen patchright install chromium

backend-dev: ## 单独启动后端
	cd backend && uv run --frozen uvicorn app.main:app --reload --host "$(BACKEND_HOST)" --port "$(BACKEND_PORT)"

backend-lint: ## 检查后端代码规范
	cd backend && uv run --frozen ruff check --config pyproject.toml app tests

backend-type: ## 检查后端静态类型
	cd backend && uv run --frozen mypy

backend-test: ## 运行后端测试
	cd backend && uv run --frozen pytest -q

backend-db-init: ## 初始化双数据库并应用结构迁移（空行业库自动播种）
	cd backend && uv run --frozen python -c 'from app.infrastructure.persistence import init_db; init_db(); print("database initialization complete")'

backend-export-seeds: ## 从行业库导出种子数据（backend/seeds/*.csv.gz）
	cd backend && uv run --frozen python -m app.scripts.export_industry_seeds

backend-seeds-drift: ## 对比运行行业库与种子快照差异（只读）
	cd backend && uv run --frozen python -m app.scripts.seeds_drift

backend-seed-hot-stocks: ## 为热门股票抓取经营信息入库（make backend-seed-hot-stocks TOP=100）
	cd backend && uv run --frozen python -m app.scripts.seed_hot_stock_business --top $${TOP:-50}

backend-reset-accounts: ## 重置本地账号数据
	cd backend && uv run --frozen python -m app.scripts.reset_accounts

frontend-install: ## 按 lockfile 安装前端依赖
	cd frontend && npm ci

frontend-dev: ## 单独启动前端
	cd frontend && VITE_API_PROXY_TARGET="http://127.0.0.1:$(BACKEND_PORT)" npm run dev -- --host "$(FRONTEND_HOST)" --port "$(FRONTEND_PORT)" --strictPort

frontend-api-check: ## 校验 OpenAPI 生成产物
	cd frontend && npm run api:check

frontend-test: ## 运行前端测试
	cd frontend && npm test

frontend-e2e: ## 运行前端浏览器 smoke 测试
	cd frontend && npm run test:e2e

frontend-build: ## 构建前端
	cd frontend && npm run build

frontend-lint: ## 运行前端 lint
	cd frontend && npm run lint

export-industry-mapping: ## 更新行业映射文件
	cd backend && uv run --frozen python -c 'from app.financial_data.stock.public import update_industry_mapping_sw_files; update_industry_mapping_sw_files()'

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
