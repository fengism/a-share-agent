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
# Frontend: http://localhost:8080 (override with DOCKER_FRONTEND_PORT)

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

- Frontend: React 18 + TypeScript + Vite + Ant Design 6 + TanStack Query + Zustand (Node.js 22)
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
├── /feed            → Feed (24小时资讯：快讯 + 新闻 + AI 摘要面板)
├── /chat            → Chat (AI 选股助手，对话式交互)
├── /analysis        → AnalysisEntry (分析入口)
├── /analysis/:code  → Analysis (分时 + K线 + 基本面 + 估值 + 技术面 + 情绪面 + AI结论)
├── /industry-chain  → IndustryChain (AI 产业链分析，支持名称参数)
├── /macro           → Macro (宏观经济指标：物价/景气/货币/利率/增速/外贸)
├── /compare         → Compare (多股票关键指标横向对比)
├── /portfolio       → Portfolio (用户持仓、收益与实时估值)
├── /capabilities    → Capabilities (Chat Skill 与 Tool 能力目录)
└── /settings        → Settings (系统配置：大模型/飞书/问财/Notion/Twitter)
```

Dark theme is applied globally via Ant Design `darkAlgorithm` + custom token overrides. All colors are defined in `frontend/src/styles/ui.ts`.

Global search accepts 6-digit stock codes and fuzzy stock names, then navigates to `/analysis/:code`.

### API Endpoints

| Prefix | Router | Responsibility |
| --- | --- | --- |
| `/api/stock` | `modules/stock/*_router.py` | search, info, intraday, kline, financial, valuation, news, indicators |
| `/api/market` | `modules/market/router.py` | indices, volume, hot rank, dragon tiger, sentiment, market news and AI news summary |
| `/api/analysis` | `modules/analysis/router.py` | trigger analysis, fetch result, stream progress with SSE |
| `/api/screener` | `modules/screener/router.py` | screen stocks, industries, valuation percentile |
| `/api/daily-review` | `modules/daily_review/router.py` | generate, fetch and store daily review |
| `/api/industry-chain` | `modules/industry_chain/router.py` | generate, stream and archive industry-chain analysis |
| `/api/portfolio` | `modules/portfolio/router.py` | manage positions and portfolio summaries |
| `/api/push` | `modules/push/router.py` | push analysis/daily-review/chat to Feishu or Notion |
| `/api/chat` | `modules/chat/router.py` | streaming chat with AI agent (SSE) |
| `/api/auth` | `modules/auth/router.py` | authentication, invitations and password reset |
| `/api/config` | `modules/settings/router.py` | read/update runtime configuration |
| `/api/health` | `api/system.py` | liveness, readiness and metrics endpoints |

## Backend Module Boundaries

- `backend/app/modules/`: vertical business modules. Each module owns its routers, schemas, application logic, prompts and storage orchestration.
- `backend/app/modules/stock/`: stock HTTP adaptation and product use cases such as typed multi-stock comparison; raw stock data capabilities do not live here.
- `backend/app/market_data/`: provider-backed market and stock capabilities. Each domain exposes supported calls through `public.py`; callers must not deep-import its implementation packages.
- `backend/app/market_data/stock/`: stock search/profile, quotes, K-line, technical indicators, financials, valuation, news, sentiment and risk data.
- `backend/app/modules/market/`: indices, volume, hot rank, dragon tiger, market news, news AI summary (with citation refs) and statistics.
- `backend/app/modules/screener/`: industry mapping, screening and percentiles.
- `backend/app/modules/industry_chain/`: industry chain analysis pipeline, prompts, storage and chart generation.
- `backend/app/modules/analysis/`: stock AI analysis pipeline, prompts, parser and domain-specific analysis inputs. Pipeline fetches institution forecasts from THS and injects them into the LLM prompt.
- `backend/app/modules/daily_review/`: daily review pipeline, prompts, formatter and storage.
- `backend/app/modules/chat/`: Chat product entry and routing. `agent.py` selects general or multi-Agent execution, while `orchestrator.py` plans professional Agent runs and synthesis.
- `backend/app/agentic/`: framework-neutral Agent profiles, orchestration primitives, Tool/Skill catalog and execution engine. Business-backed Tool handlers are declared as application ports and bound by Runtime.
- `backend/app/api/`: FastAPI assembly helpers, global error translation and system endpoints.
- `backend/app/configuration/`: environment settings, provider defaults, runtime updates and sensitive-config encryption.
- `backend/app/contracts/`: small cross-module data contracts; business-specific schemas stay inside their owning module.
- `backend/app/infrastructure/providers/`: provider adapters for Akshare, EastMoney, Sina, THS, Iwencai, Baidu, CLS, RSS, Tencent and Twitter.
- `backend/app/infrastructure/persistence/`: database stores, file snapshots, history indexes and reusable persistence primitives.
- `backend/app/infrastructure/llm/`: config-keyed, reference-counted LLM client/runtime pools, prompt execution and factories.
- `backend/app/infrastructure/integrations/`: Feishu and Notion integrations.
- `backend/app/core/`: shared cache, concurrency, DataFrame, symbol, security, metrics and request-context helpers.
- `backend/app/runtime/`: application lifecycle, middleware, background scheduling and cross-module dependency composition, including Agent application-handler binding.

Dependency direction is `api/modules -> market_data/agentic -> infrastructure -> core/contracts`. `runtime` is the composition root and may depend on multiple business modules. `agentic` must not import product modules or Provider implementations; modules consume other domains only through `public.py`.

## Frontend Module Boundaries

- `frontend/src/pages/`: route-level pages.
- `frontend/src/components/`: reusable layout and UI components.
- `frontend/src/charts/`: chart components.
- `frontend/src/api/`: API client, query hooks and SSE helper.
- `frontend/src/store/`: Zustand state.
- `frontend/src/types/`: TypeScript domain types.
- `frontend/src/styles/`: shared UI style constants (dark theme palette in `ui.ts`).

## Key Patterns

**Stock Code Normalization:** use `backend/app/core/market.py` for raw, upper-prefix and lower-prefix symbol formats. Do not duplicate symbol conversion logic.

**Async Data Fetching:** akshare and direct `requests` calls are synchronous. Run blocking work through `app.core.concurrency.call_blocking` with the appropriate semaphore, preserve provider rate limiting, and keep business functions async.

**Provider Fallbacks:** external data sources can fail under network restrictions. Preserve provider-chain behavior and return useful partial data where the existing service contract allows it.

**Provider Retry Budget:** Provider Gateway retries are bounded by both `PROVIDER_GATEWAY_MAX_ATTEMPTS` and `PROVIDER_RETRY_BUDGET_SECONDS`. Keep exponential backoff, `PROVIDER_RETRY_JITTER_SECONDS`, `Retry-After` handling and cancellation propagation centralized in `app.infrastructure.providers.provider_gateway`.

**Provider Lazy Loading:** use `get_provider("name")` from `app.infrastructure.providers` to access provider singletons. Do not import provider instances directly (e.g. `from app.infrastructure.providers.eastmoney import eastmoney_provider`). The registry defers module import until first use, avoiding circular imports and startup overhead.

**Authenticated APIs:** all business routers registered in `backend/app/main.py` require `require_active_user`. Only `/api/auth/*` and `/api/health` are public. New business routers must be registered with the same dependency; frontend route guards are not a security boundary.

**Global Settings Persistence:** administrator-updated instance settings are stored in `user_data.db.global_config` and loaded after database initialization, before background tasks start. Persisted values override the environment baseline. Global secrets use the same AES-GCM keyring as user secrets with reserved scope id `0`; masked values must never be written back.

**User-Scoped Analysis:** pass `user_id` explicitly from analysis, aggregate and push routers into analysis stream/pipeline/storage functions. New analysis files live under `data/analyses/users/{user_id}/{code}/{date}.json`; reads may fall back to legacy `data/analyses/{code}/{date}.json`, but must never inspect another user's directory. Cache and in-flight keys must include `user_id`.

**User-Scoped AI Artifacts:** daily reviews live under `data/daily_reviews/users/{user_id}/` and industry-chain archives under `data/industry_chains/users/{user_id}/`. Reads may merge legacy global records, with the current user's record winning. Market-news source data stays shared, but its LLM summary cache, content hash and SingleFlight key must include `user_id`. Routers, chat tools, pipelines, storage and push code pass `user_id` explicitly.

**LLM Runtime Pool:** `create_llm_client()` returns a proxy that borrows a config-keyed sync client per `chat()` call. Chat SSE flows must use `borrow_async_openai_chat_runtime()` across the complete generator lifetime. The pools keep at most 16 idle/config resources, never evict active leases, and are closed through `close_llm_pools()` after lifespan tasks stop.

**Frontend Bundle Splitting:** route pages and `AppLayout` must stay dynamically imported. Do not force all `antd` or `@ant-design/icons` modules into one manual Chunk; let Rollup split them by route. Keep ECharts and zrender in separate route-only vendor Chunks, and preserve on-demand imports for `html2canvas` and `jspdf`. Production builds should keep initial static JS and every individual JS Chunk below 500 KB.

**Frontend User Scope:** `authStore` must call `setActiveUserScope()` whenever the authenticated user changes. Keep the shared TanStack client in `frontend/src/api/queryClient.ts`; user changes clear it before exposing the next account. Chat history keys are `chat-sessions:user:{userId}` and pending writes retain their original user ID. Route-only stores register handlers through `userScope.ts`; do not statically import Chat or Analysis stores from the auth path, because that would break route-level code splitting. User changes must abort active Chat/Analysis work and reset account-owned memory state.

**EastMoney Mixins:** each module under `backend/app/infrastructure/providers/eastmoney/` must explicitly import every constant and utility it uses. Imports in `base.py` are not visible in sibling mixin module globals.

**Public Market Aggregation:** `get_market_statistics()` loads sector rankings, price distribution and limit pools concurrently while preserving partial-result fallback and deterministic source priority. Market statistics, basic macro and full macro cache misses must pass through module-level `AsyncSingleFlight` keyed by the complete cache key. Do not bypass existing provider semaphores or merge the two macro response keys.

**Spot Snapshot Lifecycle:** full-market snapshot cache misses must pass through the module-level `AsyncSingleFlight`. Preserve the memory → file with background refresh → Sina → EastMoney → Akshare order. File reads and writes must use `call_blocking(..., semaphore=misc_semaphore)`, and background refresh must pass a coroutine factory to `BaseFileSnapshotService.start_refresh()` rather than creating a coroutine eagerly. Never cache or persist an empty provider result.

**Stock Name Map Lifecycle:** stock-name cache misses must pass through the module-level `AsyncSingleFlight`. Preserve snapshot-over-standalone-file merge priority and Baidu → EastMoney → Sina provider order. Local snapshot/name reads, freshness checks and atomic writes must use `call_blocking(..., semaphore=misc_semaphore)`. Every provider result must meet `_STOCK_NAME_MAP_MIN_SIZE`; do not cache or persist partial mappings. Startup refresh must stay inside the lifespan-owned `build_stock_name_map()` task rather than spawning a nested task.

**Frontend Request Lifecycle:** API helpers combine the caller's `AbortSignal` with an internal timeout signal. TanStack Query functions must pass their `signal` to API helpers. Use `API_TIMEOUTS.EXTERNAL` for provider/push refreshes and `API_TIMEOUTS.LONG_RUNNING` for AI generation; do not restore a single short timeout for every request. HTTP failures must remain `ApiError` instances with status/path. Query retries use `shouldRetryQuery`: never retry 4xx, timeout or abort; retry network and 5xx failures at most once.

**History I/O and Pagination:** analysis, daily-review and industry-chain route/pipeline file calls must run through `call_blocking(..., semaphore=misc_semaphore)`. History storage functions select, deduplicate, sort and paginate paths before reading JSON. HTTP list endpoints default to `limit=100`, cap it at 200 and accept non-negative `offset`; current-user records continue to override legacy global records.

**Frontend History Pagination:** Analysis, DailyReview and IndustryChain use their `useInfinite*History` hooks with 50-item pages and explicit load-more controls. IndustryChain history filtering is debounced by 300ms and remains synchronized with route-driven industry names. Keep page flattening outside presentational history components.

**Frontend Search State:** stock search UIs use `useStockSearchController` so controlled inputs update immediately while only a debounced normalized value reaches `useStockSearch`. Before navigating from a name result, `resolveStockSearchCode` must verify that the result query still matches the current input; six-digit codes may navigate immediately. Apply caller-specific filtering, such as Compare's selected-code exclusion, after the controller publishes current results.

**Frontend Page Boundaries:** Settings keeps configuration state/save coordination in `pages/Settings/index.tsx`, keys form initialization by `user.id` and renders explicit card components. Feed keeps list rendering and pagination in dedicated components. Analysis keeps route/SSE/PDF/push coordination in its page while header, state, charts and business panels remain presentational components; non-default panels stay dynamically imported and PDF export preloads them first. Market keeps its default A-index tab synchronous and non-default tabs dynamic. IndustryChain keeps SSE/archive/push coordination in its page and report/history/Markdown parsing in dedicated modules. Preserve route-level dynamic imports when adding components.

**Analysis Render Subscriptions:** `pages/Analysis/index.tsx` must use field-level `useAnalysisStore` selectors rather than subscribing to the complete store. `AnalysisStateSection` owns `analysisStages` and `currentStageIndex`; SSE stage events must not rerender `AnalysisChartsSection` or unrelated panels. Keep the chart section memoized unless its effective inputs change.

**Feed Refresh Rendering:** use React Query `dataUpdatedAt` as the successful refresh timestamp. Relative-time ticks belong in a small label component and should align to minute boundaries; do not keep a periodic tick in `TwitterTab` that rerenders `PaginatedList`.

**Lightweight Chart Lifecycle:** Kline and intraday charts separate Chart creation, Series data updates and theme updates. Callers provide a stable `viewKey` that changes with stock/index, period and adjustment; preserve the visible logical range for updates within the same view and call `fitContent()` only for a new view or explicit reset. ResizeObserver callbacks must not reset the viewport. Indicator charts may replace Series when the indicator changes but keep the Chart and observer alive.

**Responsive Financial Tables:** at widths up to 768px, wide financial tables expose core scanning columns and keep secondary fields in `ResponsiveMetricGrid` details. Screener, Dragon Tiger, hot stock/sector rankings, industry rankings, stock fund flow and valuation forecast/peer tables use expandable rows; Compare uses complete per-stock cards and keeps the matrix desktop-only. Do not remove data solely to make a table fit on mobile.

**Frontend Section Data States:** data sections with first-load, request failure and empty-result states use `SectionDataState`. Preserve the priority `loading -> error -> empty -> content`, fixed-height Skeletons and contextual retry actions. Combine parallel Query states at the panel boundary and retry every Query needed to rebuild that panel. Analysis, DailyReview and IndustryChain history panels must keep successful rows visible when a background refresh fails; their first-load states and route/Tab Suspense fallbacks use fixed-height Skeletons rather than indeterminate page-level Spin.

**Frontend Workflow Actions:** DailyReview and Analysis header action groups use a two-column grid below 768px and compact max-content columns on desktop. Keep the DailyReview date picker full-width on mobile and disabled while generation is pending; keep Analysis primary/cancel actions full-width below the secondary actions.

**Frontend Lazy Chart Placeholders:** IndustryChain charts remain IntersectionObserver-driven and must not eagerly download ECharts. Use fixed-size Skeletons both before viewport activation and while the lazy module loads. Icon-only chart actions require a descriptive accessible name.

**Frontend Workflow Reliability:** IndustryChain Feishu receiver input is controlled state and must be passed explicitly as `feishu_receiver`; do not read it through a DOM id or leave it as presentation-only `defaultValue`. Archive loads expose the pending item and prevent overlapping selections. DailyReview PDF export owns a dedicated pending flag, catches all lazy-import/render failures and disables actions that could change the captured report.

**Frontend List Error States:** reusable list components accept Query errors and retry actions instead of treating failures as empty results. If successful rows already exist, keep them visible when a background refresh fails. Feed pagination stays compact on narrow screens and must not overflow its card.

**Mobile Control Layout:** multi-control Card headers must move controls into the body or wrap them below 640px. Inline admin forms switch to vertical full-width fields on narrow screens. Chat message content may use up to 94% width on mobile and should use dynamic viewport units to avoid browser-toolbar clipping.

**Frontend Change Semantics:** directional percentage values use `ChangeValue` with raw percentage units. Keep formatting, theme colors, optional direction icons and Chinese `aria-label` generation in the shared component and format helpers; amount values and ratios with different units keep their dedicated formatters.

**Screener and Compare State:** Screener keeps placeholder results during filter, page and sort transitions; only replace the table with an error state when no successful result exists. Industry-list failures stay non-blocking. Compare URL parsing and UI additions cap the list at five unique six-digit codes. Keep comparison change percentages numeric until render, use `ChangeValue`, and mark the metric column as row headers.

**Background Refresh Feedback:** query-key changes and polling should preserve successful rows when that does not mislabel the data, and use `DataRefreshIndicator` for non-blocking fetches. Bind Table `loading` to first-load state, not background `isFetching`; use fixed-height Skeletons for chart placeholders.

**Frontend Layout and Query Boundaries:** `AppLayout.tsx` only coordinates breakpoints, sidebar state and the outlet. Keep navigation/theme behavior in `AppSidebar.tsx` and stock search/user actions in `AppHeader.tsx`. Query hooks live under `frontend/src/api/queryHooks/` by stock, market, workflows, screener and settings domain; preserve `frontend/src/api/queries.ts` as the compatibility barrel and do not change query keys, TTLs, abort signals or timeouts during moves.

**Frontend URL State:** shareable page state uses validated URL search parameters. Market, Macro and Feed tabs, Feed search, Compare codes and applied Screener filters must recover on refresh and browser navigation. Omit defaults, use replace for high-frequency inputs, reject invalid enum/number values and keep draft Screener edits separate from applied URL filters.

**Industry Chain Rendering:** report charts mount through `LazyIndustryChart` when they approach the viewport and reserve their final height before mounting. `IndustryChart.tsx` owns all ECharts imports so the chart runtime is downloaded only after intersection or modal open. Use CSS viewport/container sizing instead of reading `window.innerWidth` or `window.innerHeight` during render; keep report/history layout single-column below 1024px.

**Chat Stream Rendering:** text and reasoning deltas pass through `createStreamDeltaBatcher` and flush at most once per animation frame. Flush before tool, error, done, stop, session switch and unmount events. Streaming assistant content stays plain pre-wrapped text; parse Markdown only after finalization.

**Chat History Rendering:** `ChatMessageList` initially renders the latest 60 messages and reveals 40 older messages per request. Preserve scroll-height compensation when prepending history, reset the visible window on session changes and keep `content-visibility` on message blocks. Do not change persisted session data when tuning rendering.

**Chat Render Subscriptions:** `ChatPage` owns SSE, input, stop/clear and push coordination but must not subscribe to `messages` or `sessions`. `ChatConversation` owns the high-frequency message subscription and scroll anchor; `ChatSessionSidebar` owns session-list subscriptions. Keep Zustand selectors narrow so stream deltas do not rerender the page shell.

**Chat Persistence:** user-scoped keys and persisted structures are owned by `frontend/src/store/chatPersistence.ts`. Preserve `chat-sessions:user:{userId}` and its `-data` companion. Parse metadata and session data independently, report read/write failures with context, and run deterministic size compaction before localStorage writes. Never mutate the live in-memory session while compacting persisted copies.

**CI Quality Gate:** `.github/workflows/ci.yml` runs backend pytest under Python 3.12 and frontend test/build/lint under Node.js 22. Ruff runs from `backend/` and only receives changed backend Python paths so first-party import classification stays correct and the existing repository-wide baseline is not mixed into feature changes.

**Async SingleFlight:** use `app.core.concurrency.singleflight.AsyncSingleFlight` instead of module-local inflight task dictionaries. Keys may be any `Hashable`. Waiting is cancellation-isolated: cancelling one request must not cancel the shared loader or other waiters. Loader completion callbacks own registry cleanup and exception observation, including when no waiters remain. `clear()` drops references for tests/reset but does not cancel running loaders.

**Startup Prewarm:** `backend/app/main.py` starts industry mapping refresh and stock name map prewarm in lifespan tasks. First startup can be slow.

**Deployment Concurrency Boundary:** the supported backend deployment is one Uvicorn process. TTL caches, SingleFlight registries, chat concurrency counters, active SSE task maps, provider semaphores and LLM pools are process-local. Multi-worker or multi-replica deployment requires shared locks, caches and rate limiting and is not currently supported.

**LLM Output:** analysis output must remain structured JSON and be validated by Pydantic models. Parser changes must keep validation strict.

**SSE Progress:** analysis progress streams through frontend SSE helpers. Keep event formats stable unless updating both backend and frontend.

**Feishu Push:** docs are created via two-step API (create empty doc → write block children). `folder_token` must go in request body JSON, not query params. Block types: 2=text, 3=heading1, 4=heading2, 5=heading3, 12=bullet, 22=divider. Push auto-grants edit permission to receiver and routes to type-specific folders (daily_review vs analysis). Chat push sends card only, no document creation.

**Chat Agent Skills:** `backend/app/agentic/skills/` maps enabled Skills to ordered Tool allowlists, and `backend/app/agentic/agents/` owns professional Agent profiles plus the shared multi-round executor. Per-user `disabled_chat_skills` removes Skill prompt sections and tools not covered by another enabled Skill. Per-user `disabled_chat_agents` removes profiles from classification and execution planning, with an all-disabled fallback to the general Agent. The Settings page persists both lists, while `/api/chat/capabilities` exposes read-only Skill, Agent and Tool metadata without system prompts.

**Market News AI Summary:** `backend/app/modules/market/news_analysis.py` calls LLM to produce structured analysis with citation refs. `_resolve_refs` maps LLM ref numbers back to `{title, url}` for each item. Frontend renders these as clickable citation chips in `NewsAnalysisPanel`. News data auto-refreshes every 5 minutes (frontend `refetchInterval` + backend 300s cache TTL); AI summary cache keys are user-scoped.

**Industry Chain Analysis:** the `/industry-chain` page uses SSE streaming for progress updates. History records are always visible in the right sidebar. Cache, active SSE tasks, archives and push lookup are user-scoped; legacy global archives remain read-only fallback.

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

Provider resilience configuration:

- `PROVIDER_GATEWAY_MAX_ATTEMPTS`: maximum calls including the first attempt
- `PROVIDER_RETRY_BASE_SECONDS`: exponential-backoff base delay
- `PROVIDER_RETRY_BUDGET_SECONDS`: maximum elapsed retry budget per Provider call
- `PROVIDER_RETRY_JITTER_SECONDS`: random jitter added to each retry delay

## Testing Guidance

Backend tests live under `backend/tests/` and mirror the current boundaries (`architecture/`, `configuration/`, `core/`, `infrastructure/`, `modules/`, `runtime/`). Run them from `backend/` with `uv run pytest`. Static gates are `uv run ruff check app tests` and the scoped `uv run mypy` configuration in `backend/pyproject.toml`.

Frontend verification uses:

```bash
cd frontend
npm run build
npm run lint
npm run test
```

Use Node.js 22 for the complete frontend test suite. Older Node 20 releases can fail to load the current Ant Design dependency graph in Vitest even when the production build succeeds.

Some backend tests or data calls may depend on live external data sources. When a failure occurs, distinguish code failures from network/data-provider failures and report the exact command and error.
