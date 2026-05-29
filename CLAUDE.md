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

## Development Constraints

- Prefer small, incremental changes over broad rewrites.
- Do not introduce `go.mod replace`-style local dependency hacks in any future Go-related work.
- Do not skip hooks or tests to force a green result.
- Do not delete `data/`, `logs/`, screenshots or local notes without explicit user confirmation.
- Safe generated artifacts to remove include `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `*.pyc`, `*.pyo`, and `frontend/dist/`; do not remove `backend/.venv/`, `node_modules/`, runtime data, logs, or local env files.
- Do not edit the superpowers managed block between its begin/end markers.
- Keep README user-facing and CLAUDE.md development-facing; avoid duplicating long implementation details in README.

<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（20 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录，每个 skill 有独立的 `SKILL.md` 文件。

- **brainstorming**: 在任何创造性工作之前必须使用此技能——创建功能、构建组件、添加功能或修改行为。在实现之前先探索用户意图、需求和设计。
- **chinese-code-review**: 中文 review 沟通参考——话术模板、分级标注（必须修复/建议修改/仅供参考）、国内团队常见反模式应对。仅在用户显式 /chinese-code-review 时调用，不要根据上下文自动触发。
- **chinese-commit-conventions**: 中文 commit 与 changelog 配置参考——Conventional Commits 中文适配、commitlint/husky/commitizen 中文模板、conventional-changelog 中文配置。仅在用户显式 /chinese-commit-conventions 时调用，不要根据上下文自动触发。
- **chinese-documentation**: 中文文档排版参考——中英文空格、全半角标点、术语保留、链接格式、中文文案排版指北约定。仅在用户显式 /chinese-documentation 时调用，不要根据上下文自动触发。
- **chinese-git-workflow**: 国内 Git 平台配置参考——Gitee、Coding.net、极狐 GitLab、CNB 的 SSH/HTTPS/凭据/CI 接入差异与镜像同步配置。仅在用户显式 /chinese-git-workflow 时调用，不要根据上下文自动触发。
- **dispatching-parallel-agents**: 当面对 2 个以上可以独立进行、无共享状态或顺序依赖的任务时使用
- **executing-plans**: 当你有一份书面实现计划需要在单独的会话中执行，并设有审查检查点时使用
- **finishing-a-development-branch**: 当实现完成、所有测试通过、需要决定如何集成工作时使用——通过提供合并、PR 或清理等结构化选项来引导开发工作的收尾
- **mcp-builder**: MCP 服务器构建方法论 — 系统化构建生产级 MCP 工具，让 AI 助手连接外部能力
- **receiving-code-review**: 收到代码审查反馈后、实施建议之前使用，尤其当反馈不明确或技术上有疑问时——需要技术严谨性和验证，而非敷衍附和或盲目执行
- **requesting-code-review**: 完成任务、实现重要功能或合并前使用，用于验证工作成果是否符合要求
- **subagent-driven-development**: 当在当前会话中执行包含独立任务的实现计划时使用
- **systematic-debugging**: 遇到任何 bug、测试失败或异常行为时使用，在提出修复方案之前执行
- **test-driven-development**: 在实现任何功能或修复 bug 时使用，在编写实现代码之前
- **using-git-worktrees**: 当需要开始与当前工作区隔离的功能开发或执行实现计划之前使用——创建具有智能目录选择和安全验证的隔离 git 工作树
- **using-superpowers**: 在开始任何对话时使用——确立如何查找和使用技能，要求在任何响应（包括澄清性问题）之前调用 Skill 工具
- **verification-before-completion**: 在宣称工作完成、已修复或测试通过之前使用，在提交或创建 PR 之前——必须运行验证命令并确认输出后才能声称成功；始终用证据支撑断言
- **workflow-runner**: 在 Claude Code / OpenClaw / Cursor 中直接运行 agency-orchestrator YAML 工作流——无需 API key，使用当前会话的 LLM 作为执行引擎。当用户提供 .yaml 工作流文件或要求多角色协作完成任务时触发。
- **writing-plans**: 当你有规格说明或需求用于多步骤任务时使用，在动手写代码之前
- **writing-skills**: 当创建新技能、编辑现有技能或在部署前验证技能是否有效时使用

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->
