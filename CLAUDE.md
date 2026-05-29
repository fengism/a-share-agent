# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Build, Run, and Verify

```bash
# One-click install + start
./setup.sh          # First time: check deps, install packages, create .env
./start.sh          # Start both servers (dev mode with hot reload)
./start.sh prod     # Production mode
./stop.sh           # Stop all services

# Or via Makefile
make setup / make start / make stop / make dev / make prod

# Docker deployment
docker compose up -d          # Build and start
docker compose up -d --build  # Rebuild after code changes
docker compose logs -f        # Follow logs
docker compose down           # Stop and remove containers

# Individual commands
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
cd backend && uv run pytest
cd frontend && npm install && npm run dev
cd frontend && npm run build && npm run lint
```

Both servers must run simultaneously. The frontend dev server proxies `/api` to the backend.

## Architecture

A 股智能分析助手：用户输入股票或进入市场页面后，系统采集行情、财务、估值、新闻、情绪和市场数据，并用 LLM 生成结构化分析、评级、目标价格区间和交易信号。

### Tech Stack

- Frontend: React 18 + TypeScript + Vite + Ant Design + TanStack Query + Zustand
- Charts: Lightweight Charts for K-line/intraday, ECharts for other visualizations
- Backend: FastAPI + Python 3.11+ + uv + Pydantic v2
- Data: akshare plus direct fallback providers for EastMoney, Sina, THS, Baidu, RSS, CLS, Tencent
- LLM: configurable via `.env`; OpenAI-compatible providers use `openai`, Claude uses `litellm`
- Deployment: Docker Compose (backend uvicorn + frontend nginx)

### Page Structure & Routes

```text
AppLayout (sticky header: logo + nav menu + global search box, dark theme)
├── /                → Dashboard (市场指数概览 + 功能入口 + 搜索)
├── /market          → Market (指数/热点榜单/龙虎榜相关 Tab)
├── /screener        → Screener (FilterPanel + ResultsTable + 估值百分位)
├── /daily-review    → DailyReview (每日市场复盘)
├── /chat            → Chat (AI 选股助手，对话式交互)
├── /analysis        → AnalysisEntry (分析入口)
├── /analysis/:code  → Analysis (分时 + K线 + 基本面 + 估值 + 技术面 + 情绪面 + AI结论)
└── /settings        → Settings (系统配置：大模型/飞书/问财/Notion)
```

Dark theme is applied globally via Ant Design `darkAlgorithm` + custom token overrides. All colors are defined in `frontend/src/styles/ui.ts`.

Global search accepts 6-digit stock codes and fuzzy stock names, then navigates to `/analysis/:code`.

### API Endpoints

| Prefix | Router | Responsibility |
| --- | --- | --- |
| `/api/stock` | `routers/stock.py` | search, info, intraday, kline, financial, valuation, news, indicators |
| `/api/market` | `routers/market.py` | indices, volume, hot rank, dragon tiger, sentiment and market news |
| `/api/analysis` | `routers/analysis.py` | trigger analysis, fetch result, stream progress with SSE |
| `/api/screener` | `routers/screener.py` | screen stocks, industries, valuation percentile |
| `/api/daily-review` | `routers/daily_review.py` | generate, fetch and store daily review |
| `/api/push` | `routers/push.py` | push analysis/daily-review/chat to Feishu or Notion |
| `/api/chat` | `routers/chat.py` | streaming chat with AI agent (SSE) |
| `/api/config` | `routers/config.py` | read/update runtime configuration |
| `/api/health` | `main.py` | health check |

## Backend Module Boundaries

- `backend/app/routers/`: HTTP API layer. Keep request parsing and response shaping here.
- `backend/app/models/`: Pydantic models shared by routers and services.
- `backend/app/adapters/`: external system adapters — Feishu (doc creation, card messaging, permissions) and Notion (page creation).
- `backend/app/services/stock/`: stock basic info, intraday, kline, financials, valuation (including institution forecasts from THS) and search.
- `backend/app/services/market/`: indices, volume, hot rank, dragon tiger, market news and statistics.
- `backend/app/services/screener/`: industry mapping, spot snapshots, screening and percentiles.
- `backend/app/services/analysis/`: stock AI analysis pipeline, prompts, parser and domain-specific analysis inputs. Pipeline fetches institution forecasts from THS and injects into LLM prompt.
- `backend/app/services/daily_review/`: daily review pipeline, prompts, formatter and storage.
- `backend/app/services/providers/`: provider adapters for akshare, EastMoney (including research report stats), Sina, THS (including EPS/net-profit forecasts), Iwencai (semantic search and structured query), Baidu, CLS, RSS and Tencent.
- `backend/app/services/base/`: provider chain, file snapshots and reusable data-provider primitives.
- `backend/app/services/chat/`: AI chat agent with extensible skill system. `agent.py` runs multi-round tool-calling loop, `skills/` contains the SkillRegistry + per-domain skill modules, `prompts.py` holds the system prompt.
- `backend/app/services/llm/`: LLM client factory.
- `backend/app/utils/`: symbol conversion, cache, rate limiting and utility functions.

## Frontend Module Boundaries

- `frontend/src/pages/`: route-level pages.
- `frontend/src/components/`: reusable layout and UI components.
- `frontend/src/charts/`: chart components.
- `frontend/src/api/`: API client, query hooks and SSE helper.
- `frontend/src/store/`: Zustand state.
- `frontend/src/types/`: TypeScript domain types.
- `frontend/src/styles/`: shared UI style constants (dark theme palette in `ui.ts`).

## Key Patterns

**Stock Code Normalization:** use `backend/app/utils/symbol_utils.py` for raw, upper-prefix and lower-prefix symbol formats. Do not duplicate symbol conversion logic.

**Async Data Fetching:** akshare and direct `requests` calls are synchronous. Wrap blocking work with `asyncio.to_thread`, preserve rate limiting, and keep business functions async.

**Provider Fallbacks:** external data sources can fail under network restrictions. Preserve provider-chain behavior and return useful partial data where the existing service contract allows it.

**Startup Prewarm:** `backend/app/main.py` starts industry mapping refresh and stock name map prewarm in lifespan tasks. First startup can be slow.

**LLM Output:** analysis output must remain structured JSON and be validated by Pydantic models. Parser changes must keep validation strict.

**SSE Progress:** analysis progress streams through frontend SSE helpers. Keep event formats stable unless updating both backend and frontend.

**Feishu Push:** docs are created via two-step API (create empty doc → write block children). `folder_token` must go in request body JSON, not query params. Block types: 2=text, 3=heading1, 4=heading2, 5=heading3, 12=bullet, 22=divider. Push auto-grants edit permission to receiver and routes to type-specific folders (daily_review vs analysis). Chat push sends card only, no document creation.

**Chat Agent Skills:** the skill system in `backend/app/services/chat/skills/` uses a registry pattern. Each skill auto-converts to an OpenAI function-calling tool definition. To add a new skill, create a .py file in `skills/`, call `registry.register(Skill(...))`, and add the registration call in `__init__.py`. No changes to `agent.py` are needed. Composite skills use `asyncio.gather` for parallel data fetching.

## Configuration

Copy `.env.example` to `.env` and set `LLM_API_KEY` when AI features are needed. All configuration can also be changed at runtime via the Settings page (`/settings`) without restarting.

Default provider values:

- DeepSeek: `base_url=https://api.deepseek.com`, `model=deepseek-v4-flash`
- Qwen: `base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`, `model=qwen-plus`
- OpenAI: configurable OpenAI-compatible endpoint
- Claude: via `litellm`, model name should use the `anthropic/...` format
- Zhipu: OpenAI-compatible endpoint

Notion export is manual-only. Configure `NOTION_ENABLED=true`, `NOTION_API_TOKEN`, and either `NOTION_DATABASE_ID` or `NOTION_PARENT_PAGE_ID` in `.env`. Never expose Notion tokens to frontend code.

Feishu push configuration:

- `FEISHU_ENABLED`: master switch (default true)
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`: app credentials for tenant_access_token
- `FEISHU_FOLDER_TOKEN`: default folder for created docs (fallback when type-specific folder is empty)
- `FEISHU_WIKI_SPACE_ID`: when set, docs are created in Wiki space instead of Drive folder (takes priority over folder_token)
- `FEISHU_WIKI_DAILY_REVIEW_PARENT`: Wiki parent node token for daily review docs
- `FEISHU_WIKI_ANALYSIS_PARENT`: Wiki parent node token for stock analysis docs
- `FEISHU_DAILY_REVIEW_FOLDER`: folder token for daily review docs
- `FEISHU_ANALYSIS_FOLDER`: folder token for stock analysis docs
- `FEISHU_DEFAULT_RECEIVER`: default open_id or chat_id when caller omits receiver

Iwencai data source configuration:

- `IWENCAI_ENABLED`: master switch (default false)
- `IWENCAI_BASE_URL`: API endpoint (default `https://openapi.iwencai.com`)
- `IWENCAI_API_KEY`: authentication key for iwencai API

## Testing Guidance

Backend tests live under `backend/tests/` organized by module (`adapters/`, `providers/`, `services/`). Run them from `backend/` with `uv run pytest`.

Frontend verification uses:

```bash
cd frontend
npm run build
npm run lint
```

Some backend tests or data calls may depend on live external data sources. When a failure occurs, distinguish code failures from network/data-provider failures and report the exact command and error.