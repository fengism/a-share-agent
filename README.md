# A 股智能选股助手

基于 AI 的 A 股多维度智能分析平台，覆盖市场概览、热点榜单、龙虎榜、条件选股、每日复盘、个股行情、基本面、技术面、情绪面和 AI 综合分析。内置 AI 选股助手，对话式获取实时数据并智能分析。

## 功能特性

- **全局股票搜索**：支持 6 位股票代码和名称模糊搜索，跳转到个股分析页。
- **市场概览**：展示主要指数、成交量、热点入口和市场状态。
- **热点榜单**：支持热股榜、概念榜、行业榜。
- **龙虎榜**：按日期查看龙虎榜明细，并支持详情弹窗。
- **条件选股**：按行业、价格、市值、估值等条件筛选，并支持估值百分位过滤。
- **24小时资讯**：聚合多源快讯和新闻，AI 智能摘要提炼关键信息并附带引用链接，自动刷新。
- **产业链分析**：输入产业关键词，AI 自动搜索研报数据并生成完整产业链分析报告，支持历史记录和推送。
- **宏观经济**：物价、景气、货币、利率、增速、外贸六大类宏观指标一览，含图表趋势。
- **每日复盘**：聚合市场、热点、新闻和 LLM 结论，生成结构化复盘。
- **个股分析**：展示分时、K 线、基本面、估值（含机构一致预期）、技术指标、情绪数据和 AI 结论。
- **AI 综合分析**：LLM 输出评分、评级、目标价格区间和买入/持有/卖出信号，融合机构一致预期数据。
- **AI 选股助手**：对话式智能选股，支持自然语言提问，自动调用工具获取实时数据并分析。
- **飞书推送**：将分析结果和每日复盘推送到飞书文档，自动按类型分目录，支持权限授权。聊天结果可推送飞书卡片。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 (Dark Theme) |
| 状态与请求 | Zustand + TanStack Query + SSE |
| 图表 | Lightweight Charts + ECharts |
| 后端 | FastAPI + Python 3.11+ + Pydantic v2 |
| 数据源 | akshare + 东方财富/新浪/同花顺/问财/Twitter 等 fallback |
| AI 引擎 | OpenAI-compatible SDK + litellm，可配置 DeepSeek/通义千问/OpenAI/Claude/智谱 |
| 包管理 | uv + npm |
| 部署 | Docker + Nginx |

## 快速开始

### 一键安装启动

```bash
# 1. 安装依赖（首次运行）
./setup.sh

# 2. 配置 API Key
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 3. 启动服务
./start.sh         # 开发模式（热重载）
./start.sh prod    # 生产模式

# 4. 停止服务
./stop.sh
```

启动后访问 `http://localhost:5173`。也可以通过 Makefile 运行：`make setup`、`make start`、`make stop`。

### Docker 部署

环境要求：Docker 20.10+、Docker Compose v2+

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 2. 构建并启动
docker compose up -d

# 3. 查看日志
docker compose logs -f

# 4. 停止
docker compose down
```

启动后访问 `http://localhost`。`data/` 和 `logs/` 通过卷挂载持久化，容器重建后数据不丢失。代码更新后重新构建：

```bash
docker compose up -d --build
```

### 手动安装

环境要求：Python 3.11+、Node.js 18+、uv、npm

### 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

不配置 API Key 仍可浏览行情和数据页面，AI 分析能力不可用。

所有配置也可在前端设置页面（`/settings`）动态修改，无需重启服务。

### 网页抓取增强（可选）

AI 聊天助手支持抓取任意 URL 并总结内容。基础抓取开箱即用，如需反爬绕过和 JS 渲染支持（如抓取需要 JavaScript 加载的 SPA 页面），可安装增强依赖：

```bash
cd backend

# 1. 安装 Scrapling + 浏览器指纹库（一键安装可选依赖）
uv pip install -e ".[web-fetch]"

# 2. 安装 Playwright 浏览器（stealth/dynamic 模式需要）
uv run playwright install chromium
uv run playwright install-deps chromium   # 需要 sudo 权限
```

| 模式 | 命令 | 依赖 | 适用场景 |
|------|------|------|---------|
| `http` | 默认 | 仅 scrapling | 公开网页，自带反爬指纹 |
| `stealth` | `--mode stealth` | + playwright + chromium | 反爬严格的网站 |
| `dynamic` | `--mode dynamic` | + playwright + chromium | JS 渲染的 SPA 页面 |

> 不安装增强依赖时，系统自动降级为纯 HTTP 抓取（`requests` + BeautifulSoup），功能不受影响。

### 问财数据源配置

如需使用问财智能搜索和查询功能，在 `.env` 中配置：

```env
IWENCAI_ENABLED=true
IWENCAI_BASE_URL=https://openapi.iwencai.com
IWENCAI_API_KEY=your_iwencai_api_key
```

### 飞书推送配置

如需将分析结果或每日复盘推送到飞书文档，在 `.env` 中配置：

```env
FEISHU_ENABLED=True
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx
FEISHU_FOLDER_TOKEN=fldcnXXXX                    # 默认云盘文档目录
FEISHU_WIKI_SPACE_ID=                            # Wiki 空间 ID；填写后优先推送到知识库
FEISHU_WIKI_DAILY_REVIEW_PARENT=wikcnXXXX        # 每日复盘 Wiki 父节点 Token（可选）
FEISHU_WIKI_ANALYSIS_PARENT=wikcnXXXX            # 股票分析 Wiki 父节点 Token（可选）
FEISHU_DAILY_REVIEW_FOLDER=fldcnXXXX             # 复盘云盘目录（可选）
FEISHU_ANALYSIS_FOLDER=fldcnXXXX                 # 分析云盘目录（可选）
FEISHU_DEFAULT_RECEIVER=ou_xxxxx                 # 默认推送接收人 open_id / chat_id
```

配置说明：

- `FEISHU_WIKI_SPACE_ID` 非空时，分析和复盘会优先推送到飞书知识库；为空时推送到云盘文档目录。
- `FEISHU_WIKI_DAILY_REVIEW_PARENT` 和 `FEISHU_WIKI_ANALYSIS_PARENT` 用于将每日复盘、股票分析分别挂载到不同 Wiki 父节点下；不填则挂载到 Wiki 空间根目录。
- 云盘模式下优先使用 `FEISHU_DAILY_REVIEW_FOLDER` / `FEISHU_ANALYSIS_FOLDER`，为空时回退到 `FEISHU_FOLDER_TOKEN`。
- Wiki 模式下系统会创建临时源文档用于挂载，内容写入知识库实际文档后会清理临时源文档，避免云盘目录残留副本。

Token 获取方式：

- `folder_token`：打开飞书云文档目标文件夹，URL 中 `folder/` 后的字符串。
- `wiki_space_id`：打开知识库空间主页，URL 中空间标识对应的字符串；也可在知识库管理或开放平台调试中获取。
- `wiki_parent_node_token`：打开目标 Wiki 父节点页面，URL 中 `wiki/` 后的字符串。

### Notion 转存配置

如需使用“转存 Notion”，在 `.env` 中配置：

```env
NOTION_ENABLED=true
NOTION_API_TOKEN=secret_xxx
NOTION_PARENT_PAGE_ID=your_parent_page_id
# 或使用 database
# NOTION_DATABASE_ID=your_database_id
```

Notion token 仅由后端读取，前端不会接触该凭证。

### 手动启动后端

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 手动启动前端

```bash
cd frontend
npm install
npm run dev
```

### 访问应用

打开 `http://localhost:5173`，输入股票代码（如 `600519`）或名称（如 `贵州茅台`）开始分析。

前端会将 `/api` 请求代理到后端 `http://localhost:8000`。

## 账号系统与访问控制

系统内置多用户账号体系：**首个注册的用户自动成为管理员**，其余用户需管理员发放的**邀请码**才能注册。每个账号拥有**独立的私密配置**（各自的 LLM Key、飞书、Notion、问财凭据），互不可见。

### 首次启动与注册

- 首次部署后打开应用会跳转到登录页；点击注册，**第一个注册的账号即管理员**（无需邀请码）。
- 之后的用户注册必须填写邀请码（管理员在「设置 → 邀请码管理」生成）。
- 公开页：`/login`、`/register`、`/reset-password`；其余页面需登录，未登录自动跳转登录页，令牌失效（401）自动登出。

### 邀请码（管理员）

- 在「设置 → 邀请码管理」生成邀请码，可设置有效期（永不过期 / 1 / 7 / 30 天）。
- 每个邀请码**仅可使用一次**；未使用的可随时**撤销**，已使用的保留记录不可撤销。

### 私密配置隔离

| 类型 | 字段 | 作用域 |
| --- | --- | --- |
| 私密（按账号隔离） | LLM Provider / Key / Base URL / Model / Temperature、飞书、Notion、问财 | 仅对当前登录用户生效 |
| 全局（仅管理员可改） | 数据源 Cookie（东方财富 / 百度 / 同花顺）、Twitter 账号、`HTTP_TRUST_ENV` | 实例级，对所有用户生效 |

- `/settings` 页仅对管理员显示全局项卡片；普通用户只能配置自己的私密项。
- 请求按登录用户作用域读取私密配置：你在对话 / 分析里用的是**你自己的 LLM Key**（消耗你自己的额度）。
- 数据源 Cookie 维持实例级全局：它们鉴权的是所有用户共享且全局缓存的公开行情数据，按用户隔离无隐私收益。
- **注意**：启用账号系统后 `/api/config` 需登录后访问。

### 修改密码与会话

- 「设置 → 账号安全」可修改密码（需验证原密码）；**修改成功后，除当前设备外的其它会话会被强制退出**。
- 会话采用不透明令牌（数据库只存 SHA-256 摘要），默认有效期 14 天，**滑动续期**：活跃访问会自动延长有效期，闲置超期自动失效。

### 密码找回（管理员签发重置链接，无需邮件）

用户忘记密码时：

1. 管理员在「设置 → 用户密码重置」输入用户名，生成**一次性重置链接**（可设有效期，默认 24 小时）。链接**仅显示一次**，复制后线下发给该用户。
2. 用户打开链接（`/reset-password?token=…`）自行设置新密码。
3. 重置成功后该用户**所有会话失效**，需用新密码重新登录。

重置令牌只存哈希、单次使用、可过期；重置端点按 IP 限流。

### 重置账号（忘记管理员 / 重新开始）

忘记唯一管理员的凭据，或想清空全部账号重新初始化时，可一键重置（**仅清空账号相关表，不影响行情缓存等其它数据**）：

```bash
make backend-reset-accounts
# 或：cd backend && uv run python -m app.scripts.reset_accounts
#   跳过确认：加 --yes      只看统计不删除：加 --stats
# Docker：docker compose exec backend python -m app.scripts.reset_accounts --yes
```

命令会先显示各账号表条数并要求输入 `yes` 确认。清空后**重启后端**，打开注册页即可**免邀请码注册新的首个管理员**。

### 相关环境变量

登录失败限流（防暴力破解）可用环境变量调整（可选，均有默认值）：

```env
LOGIN_MAX_FAILURES=5        # 连续失败多少次后锁定（按用户名 + IP 双维度）
LOGIN_WINDOW_SECONDS=300    # 失败计数窗口（秒）
LOGIN_LOCK_SECONDS=300      # 锁定时长（秒）
```

- 会话有效期与滑动续期阈值为内置常量（`backend/app/utils/auth.py` 中的 `SESSION_TTL_DAYS`、`SESSION_RENEW_THRESHOLD_DAYS`），如需调整改代码即可。
- 若前端部署在与后端不同的域名，用 `CORS_ORIGINS`（逗号分隔）配置允许来源。

### 数据表

账号系统在 SQLite 中新增 5 张表：`users`、`auth_sessions`、`invites`、`user_config`、`password_resets`。均在启动时自动创建（`CREATE TABLE IF NOT EXISTS`，纯增量），**现有数据库无需手动迁移**。

## 常用命令

### 后端

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
```

### 前端

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

### 根目录 Makefile

```bash
make setup            # 一键安装
make start / make dev # 启动（开发模式）
make prod             # 启动（生产模式）
make stop             # 停止服务
make backend-sync     # 安装后端依赖
make backend-dev      # 启动后端
make backend-test     # 运行后端测试
make frontend-install # 安装前端依赖
make frontend-dev     # 启动前端
make frontend-build   # 构建前端
make frontend-lint    # 前端 lint
```

## 页面路由

| 路径 | 页面 | 说明 |
| --- | --- | --- |
| `/` | Dashboard | 市场指数概览、功能入口和搜索 |
| `/market` | Market | 热点榜单、龙虎榜、指数相关信息 |
| `/screener` | Screener | 条件选股和估值百分位 |
| `/daily-review` | DailyReview | 每日市场复盘 |
| `/feed` | Feed | 24小时资讯：快讯 + 新闻 + AI 智能摘要 |
| `/chat` | Chat | AI 选股助手（对话式） |
| `/analysis` | AnalysisEntry | 分析入口 |
| `/analysis/:code` | Analysis | 个股分析详情 |
| `/industry-chain` | IndustryChain | AI 产业链分析（支持名称参数） |
| `/macro` | Macro | 宏观经济指标（物价/景气/货币/利率/增速/外贸） |
| `/settings` | Settings | 系统配置（大模型/飞书/问财/Notion/Twitter）、账号安全（改密）、管理员邀请码与密码重置 |
| `/login` | Login | 登录（公开） |
| `/register` | Register | 注册；首个用户即管理员，其余需邀请码（公开） |
| `/reset-password` | ResetPassword | 通过管理员签发的链接重置密码（公开） |

## API 概览

| Prefix | 说明 |
| --- | --- |
| `/api/stock` | 股票搜索、基础信息、分时、K 线、财务、估值（含机构预测）、新闻、技术指标 |
| `/api/market` | 指数、成交量、热点榜单、龙虎榜、市场情绪、资讯 AI 摘要 |
| `/api/analysis` | AI 分析触发、结果查询、SSE 进度流 |
| `/api/screener` | 条件选股、行业列表、估值百分位 |
| `/api/daily-review` | 每日复盘生成、查询和存储 |
| `/api/push` | 推送分析/复盘/聊天到飞书文档或 Notion |
| `/api/chat` | AI 选股助手对话（SSE 流式） |
| `/api/auth` | 账号注册/登录/登出/会话、修改密码、邀请码管理、管理员密码重置链接 |
| `/api/config` | 运行时配置读取/更新（需登录，按用户作用域） |
| `/api/health` | 健康检查 |

## 项目结构

```text
stock-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口和 lifespan 预热任务
│   │   ├── config.py               # 环境变量配置
│   │   ├── adapters/               # 飞书/Notion 外部系统适配
│   │   ├── models/                 # Pydantic 数据模型
│   │   ├── routers/                # HTTP API 路由
│   │   ├── services/
│   │   │   ├── analysis/           # 个股 AI 分析流水线
│   │   │   ├── base/               # provider chain、文件快照、通用接口
│   │   │   ├── chat/               # AI 选股助手（agent + skills 注册中心 + prompts）
│   │   │   ├── daily_review/       # 每日复盘流水线
│   │   │   ├── llm/                # LLM 客户端工厂
│   │   │   ├── market/             # 指数、热点、龙虎榜、资讯、AI 摘要
│   │   │   ├── providers/          # akshare、东方财富、同花顺、问财、百度、RSS、Twitter 等数据源适配
│   │   │   ├── screener/           # 条件选股、行业映射、估值百分位
│   │   │   ├── industry_chain/     # 产业链分析流水线
│   │   │   ├── search/             # 新闻和评论搜索
│   │   │   ├── stock/              # 个股行情、财务、估值、搜索
│   │   │   └── technical.py        # 技术指标计算
│   │   └── utils/                  # 股票代码、缓存、限流等工具
│   ├── tests/                       # 测试（按 adapters/providers/services 组织）
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/
│   ├── src/
│   │   ├── api/                    # API client、query hooks、SSE
│   │   ├── charts/                 # 分时和 K 线图表
│   │   ├── components/             # 通用组件和布局
│   │   ├── pages/                  # Dashboard、Market、Screener、DailyReview、Analysis、Macro
│   │   ├── store/                  # Zustand 状态
│   │   ├── styles/                 # UI 样式常量
│   │   └── types/                  # TypeScript 类型
│   └── package.json
├── docs/
├── data/                           # 本地运行数据
├── logs/                           # 本地日志
├── Makefile
├── .env.example
├── CLAUDE.md
└── README.md
```

## 核心数据流

1. 用户在前端搜索股票并进入 `/analysis/:code`。
2. 前端通过 TanStack Query 请求 `/api/stock/*` 获取行情、财务、估值、新闻和技术指标。
3. 用户触发智能分析后，后端 `/api/analysis` 聚合多维数据并调用 LLM。
4. 分析进度通过 SSE 返回，最终结果经过 Pydantic 校验后展示。
5. 市场、选股和每日复盘页面复用 market、screener、daily-review 相关服务。
6. AI 选股助手（`/chat`）通过多轮 tool-calling 循环自动调用 skills 获取实时数据，SSE 流式返回。
7. 24小时资讯（`/feed`）聚合多源快讯和新闻，AI 自动分析归类并附带引用链接，前端每 5 分钟自动刷新。
8. 产业链分析（`/industry-chain`）通过 SSE 流式输出进度，分析结果存档后可从历史记录回看或推送到飞书/Notion。

## 数据源与启动说明

- akshare 是同步库，后端服务通过异步包装和限流调用。
- 网络环境可能影响东方财富、同花顺、新浪等数据源，服务内置多级 fallback。
- 启动时会预热行业映射和股票名称映射，首次启动可能较慢。
- 使用 `./setup.sh` 一键安装，`./start.sh` 一键启动，`./stop.sh` 停止服务。
- `data/` 和 `logs/` 为本地运行产物，是否清理取决于本地使用场景。

## 验证

```bash
cd backend && uv run pytest
cd frontend && npm run build
cd frontend && npm run lint
```

如果测试依赖实时行情或外部网络，失败时需要区分代码问题和数据源/网络问题。

## 免责声明

本系统仅供学习和研究使用，不构成任何投资建议。AI 分析结果基于公开数据和模型推理，不保证准确性、完整性或时效性。投资有风险，入市需谨慎。
