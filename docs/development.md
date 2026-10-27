# 本地开发指南

面向需要改代码、跑测试、发版的开发者。部署与使用说明见 [README](../README.md)。

## 一、环境要求

| 项目 | 版本 | 说明 |
| :--- | :--- | :--- |
| Python | 3.11+ | 后端运行时；开发依赖由 `uv` 管理 |
| uv | 最新 | `backend/pyproject.toml` + `uv.lock` 锁定依赖 |
| Node.js | 22 | 前端构建与测试 |
| npm | 10+ | 与 Node 22 自带版本一致 |
| 可选：Docker | 20.10+ | 只在需要容器化验证时使用 |

> [!NOTE]
> 后端**必须**用 `uv run` 执行（`cd backend && uv run pytest`）。系统自带的 `python3` 通常缺少
> pydantic / fastapi 等运行时依赖，直接调用会得到误导性的 import 错误。

## 二、首次初始化

```bash
./setup.sh                 # 安装前后端依赖与基础运行库
cp .env.example .env       # 配置环境变量（至少生成 CONFIG_ENCRYPTION_KEY）
cd backend && uv run python -c 'from app.infrastructure.persistence import init_db; init_db(); print("db ok")'
```

`init_db()` 会创建四个 SQLite 库并应用结构迁移，空行业库自动从 `backend/seeds/` 播种。

需要以下两项可选能力时再单独安装浏览器内核（下载量较大）：

```bash
make backend-browser-install                  # 后端网页抓取（patchright + Chromium）
cd frontend && npx playwright install chromium  # 前端 E2E 与 README 配图脚本
```

## 三、常用命令

### 运行与调试

| 命令 | 作用 |
| :--- | :--- |
| `make dev` / `./start.sh dev` | 启动前后端（热重载） |
| `make stop` / `make restart` | 停止 / 重启本地服务 |
| `make status` | 查看 `8000` / `5173` 端口监听状态 |
| `make logs` | 持续跟踪 `logs/backend.log`、`logs/frontend.log` |
| `make backend-dev` / `make frontend-dev` | 单独启动后端 / 前端 |
| `make prod` | 本地生产模式（构建前端产物） |

### 质量门禁

| 命令 | 内容 |
| :--- | :--- |
| `make check` | **提交前必跑**：后端 lint → 模块边界 → 类型 → 覆盖率 → OpenAPI 同步 → 前端测试 → 前端 lint → 前端构建 |
| `make backend-lint` | `ruff check app scripts tests` |
| `make backend-boundaries` | 分层/私有名/反向依赖门禁（规则见 [架构与边界](architecture.md)） |
| `make backend-type` | `mypy`（严格模式，全量源文件） |
| `make backend-test` | `pytest -q` |
| `make backend-coverage` | 覆盖率下限 44%，可用 `COVERAGE_MIN=50 make backend-coverage` 覆盖 |
| `make frontend-test` | `vitest run` |
| `make frontend-lint` | `eslint .` + 页面边界检查 + 时区门禁（见下一节「硬约束」） |
| `make frontend-e2e` | Playwright 浏览器 smoke 测试（首次需 `cd frontend && npx playwright install chromium`） |
| `make frontend-api-check` | 校验 OpenAPI 生成产物是否与后端一致 |

### 数据与发布

| 命令 | 作用 |
| :--- | :--- |
| `make backend-db-init` | 初始化数据库结构 |
| `make backend-export-seeds` | 从运行库导出种子到 `backend/seeds/*.csv.gz` |
| `make backend-seeds-drift` | 对比运行库与种子快照差异（只读） |
| `make backend-seed-hot-stocks TOP=100` | 为热门股票补抓经营资料 |
| `make backend-reset-admin ADMIN=admin PASS=xxx` | 无损重置管理员密码 |
| `make backend-reset-accounts` | 重置本地全部账号数据 |
| `make pack` | 打包源码（排除密钥、数据、日志与依赖） |
| `make release V=v0.8.0` | 打 tag 并推送，触发镜像构建与发版 |

## 四、质量门禁的硬约束

1. **模块边界**：`app/core`、`app/domain`、`app/infrastructure`、`app/financial_data` 不得反向依赖
   `app/modules` / `app/api` / `app/runtime`；跨模块引用不得使用下划线私有名。规则实现见
   `backend/scripts/check_import_boundaries.py`，背景见 [架构与边界](architecture.md)。
2. **类型**：`mypy` 全量通过，不新增 `# type: ignore` 作为常规手段。
3. **覆盖率**：总体不低于 44%（当前约 52%），新增模块应自带测试而不是拉低均值。
4. **契约同步**：改了后端 Pydantic 模型必须重新生成前端产物，否则 `make frontend-api-check` 失败：

   ```bash
   cd frontend && npm run api:generate   # 重新生成 src/api/generated/*
   ```

另外三条由脚本守住的单点约定（都挂在 `make check` 上）：

- **后端时间戳**：`app/` 内不要直接 `datetime.now()` / `date.today()`，一律用
  `app/domain/timezones.py` 的 `market_now()` / `market_today()`，保证落库值恒为北京时间；
  `tests/test_timezone_guard.py` 会扫描越界写法。
- **时间戳展示**：后端时间戳是「北京时间墙上时钟 + 无时区后缀」，前端一律用
  `src/utils/marketTime.ts`（`parseMarketTime` / `formatMarketDateTime` / `formatMarketClock` …）解析与渲染。
  直接 `new Date(后端时间串)` 会让非 UTC+8 用户看到整体偏移的行情时间，
  `frontend/scripts/check-market-time.mjs` 会拦住这类写法（分时图等用 `getUTC*` 自洽的地方在允许名单里）。
- **CSV 导出**：导出单元格一律经 `app/core/csv_export.py` 的 `csv_safe_row` 处理，
  阻断 `=cmd|…` 这类公式注入；新增导出接口时不要裸用 `writer.writerow([...])`。

另外两条账号域约定（靠 code review + 测试保证，尚未脚本化）：

- **管理员写操作必须留痕**：新增/修改涉及「改别人的账号或全局配置」的接口时，在同一处调用
  `app/infrastructure/persistence/admin_audit_store.py` 的 `record_admin_action(...)`，
  记录 `action` / `target_label` / `details`（只放字段名与布尔值，**绝不写密码、Token、密钥**）。
  前端「设置 → 安全审计 → 管理员操作」直接读这张表。清理期限由 `ADMIN_AUDIT_RETENTION_DAYS` 控制。
- **草稿/会话类个人资源按 owner 过滤**：量化策略草稿（`quant_strategy_drafts.created_by`）、登录设备（`auth_sessions.user_id`）、
  「我的登录记录」（`login_audit_logs.user_id`）都必须用「登录态 user_id」过滤，越权访问统一返回 404（不要 403，
  否则会泄露资源是否存在）。新增这类「个人资源」接口时，管理员分支（看全量）要显式判断 `is_admin`，不要靠前端隐藏按钮。
- **私密配置的"空串=删除覆盖"**：写接口里私密字段传空串表示删除该用户的个人覆盖
  （`user_config_store.delete_user_config_keys`），掩码值表示"未修改"。新增"一键回退默认/继承"这类按钮时，
  必须显式把密钥字段写成空串提交（`buildCardPatch` 默认会跳过空密钥，容易"看着生效其实没清掉"）；
  `Literal` 类字段（如 `llm_api_mode`）传空串会被请求校验 422，要写回该字段的默认语义值。
  回归测试：`tests/test_llm_config_inheritance.py`、`frontend/src/pages/Settings/useSettingsForm.llmClear.test.tsx`。
- **有继承语义的卡片要声明 `skipUnchanged`**：字段留空=沿用全局的卡片（如 LLM）必须在 `cardSpecs.ts`
  里标 `skipUnchanged: true`，让 `buildCardPatch` 只提交与生效配置不同的字段；否则"用户只改了无关项却把
  继承值钉成个人覆盖"这类问题会以"管理员改了配置某些人跟不动"的形式出现，很难排查。
- **凭据只跟着端点走**：全局（管理员）配置里的密钥，只有在**端点与全局一致**时才允许被继承复用。
  判定落在两处：`app/configuration/effective.py::overlay_private`（生效配置）与
  `app/infrastructure/llm/spec.py::_shares_global_endpoint`（真正构建出网客户端处，兜底）。
  新增"用户可自定义地址"的凭据类配置（数据源、推送通道、LLM）时，必须同时实现这两层，
  否则会出现"管理员 Key 被发到用户指定地址"的凭据泄漏。
- **账号域时间戳显式传入**：`users` / `auth_sessions` / `invites` / `password_resets` / `login_audit_logs`
  的 `created_at` 由 INSERT 显式写 `now_ts()`（北京时间的字符串），不要依赖 DDL 的
  `datetime('now','localtime')`——容器里恰好设了 `TZ`，裸机/k8s 没设时会写成 UTC，两者相差 8 小时。
  回归测试见 `tests/test_account_timestamp_timezone.py`。

## 五、依赖维护

| 目标 | 做法 |
| :--- | :--- |
| 升级后端依赖 | `cd backend && uv lock --upgrade-package <pkg>` 后 `uv sync --frozen`，再跑 `make check` |
| 检查后端漏洞 | `cd backend && uv run --with pip-audit pip-audit`（当前基线：无已知漏洞） |
| 检查前端漏洞 | `cd frontend && npm audit --omit=dev`（当前基线：生产依赖 0 漏洞） |
| 前端传递依赖打补丁 | 在 `package.json` 的 `overrides` 里钉版本，别为此升级主依赖 |

`overrides` 里现有 `dompurify`：它由 `jspdf` 传递引入，3.4.14 命中多个 DOM XSS advisory，
而 `jsPDF.html()` 本仓库并未使用。等 `jspdf` 自身的 `dompurify` 依赖 ≥3.4.17 后即可删除该条。
`npm audit` 剩余项都在 vitest/esbuild 工具链上，需要 vitest 5 破坏性升级，暂缓。

## 六、测试约定

- **后端**（`backend/tests/`）：pytest + `anyio`，异步用例标 `pytestmark = pytest.mark.anyio`。
  按被测对象分文件（`test_<模块>.py`），子域可用子目录（如 `tests/agentic/`）。
  **测试必须自洽**：不得依赖 `backend/data` 里的真实运行时文件（快照、名称映射、归档日线），
  这些文件在跑过应用的开发机上一定存在，会让断言环境敏感。需要"文件不存在"的场景请显式
  `monkeypatch` 掉兜底读取路径。
- **前端**（`frontend/src/**/*.test.tsx`）：vitest + Testing Library，按组件就近放置用例。
- **E2E**（`frontend/e2e/`）：Playwright 拦截 `/api/**` 并注入夹具，不依赖真实后端，可在 CI 运行。
- **README 配图**（`frontend/scripts/capture-readme-screenshots.mjs`）：依赖真实运行实例，不进 CI，
  用法见 [README「项目开发与维护」](../README.md#项目开发与维护)。

## 七、本地调试技巧

- **交互式 API 文档**默认关闭（避免未认证访问者拉取全量路由表）。本地需要时：
  `APP_EXPOSE_DOCS=1 make backend-dev`，然后访问 `http://127.0.0.1:8000/docs`。
- **健康检查**：`/api/health/live`、`/api/health/ready`、`/api/health` 无需鉴权；
  `/api/health/metrics` 与 `/api/health/metrics/prometheus` 需要鉴权（Prometheus 抓取请用带凭据的代理）。
- **日志**：本地写 `logs/backend.log`；容器内 `docker compose logs -f backend`。
  访问日志对健康检查/轮询路径已降噪到 DEBUG，排查时把日志级别调回 INFO 以上即可。
- **数据库**：四个 SQLite 库都在 `backend/data/`（容器内 `/app/data`），
  结构与迁移见 `backend/app/infrastructure/persistence/migrations.py`。

## 八、提交与发布约定

- 按仓库 `AGENTS.md`：**修改后先说明改动内容并获得确认，不要自行 `git commit` / `git push`。**
- 发版由 tag 驱动：`make release V=vX.Y.Z` 推送标签后，GitHub Actions 构建并发布镜像。
- 破坏性配置变更必须向后兼容（见 [配置系统开发指南](configuration.md) 第六节）。

## 九、相关文档

- [架构与边界](architecture.md) — 分层、依赖环基线、Agentic/估值/潜力股链路
- [配置系统开发指南](configuration.md) — 配置来源、作用域、新增字段流程
- [数据源与降级机制](data-sources.md) — Provider 清单、熔断、限流、质量校验
- [故障排查手册](troubleshooting.md) — 启动、数据、LLM、推送与前端常见问题
- [自动推送与通知配置](push-notifications.md)
