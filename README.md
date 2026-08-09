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
| 前端 | React 18 + TypeScript + Vite + Ant Design 6（多主题） |
| 状态与请求 | Zustand + TanStack Query + SSE |
| 图表 | Lightweight Charts + ECharts |
| 后端 | FastAPI + Python 3.11+ + Pydantic v2 |
| 数据源 | akshare + 东方财富/新浪/同花顺/问财/Twitter 等 fallback |
| AI 引擎 | OpenAI-compatible SDK + LiteLLM，可配置 DeepSeek、通义千问、OpenAI、Claude、Gemini、Azure、Ollama 等 |
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

启动后访问 `http://localhost:5173`。脚本使用 PID 文件管理当前项目进程；若端口被其他项目占用，会明确报错而不会直接终止外部进程。也可以运行 `make help` 查看统一命令入口。

端口可按需覆盖，例如：

```bash
BACKEND_PORT=8100 FRONTEND_PORT=5174 make dev
```

### Docker 部署

环境要求：Docker 20.10+、Docker Compose v2+

```bash
# 1. 配置环境变量
cp .env.example .env
# Docker Compose 不会自动生成 CONFIG_ENCRYPTION_KEY；请编辑 .env 填入 LLM_API_KEY，
# 并执行以下命令生成密钥后写入 CONFIG_ENCRYPTION_KEY：
openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'; echo

# 2. 构建并启动
# Linux 若当前用户不是 UID/GID 1000，可先执行：
# export APP_UID=$(id -u) APP_GID=$(id -g)
docker compose up -d

# 3. 查看状态和首次启动生成的管理员临时密码
docker compose ps
docker compose logs backend

# 4. 停止
docker compose down
```

Docker Compose 只会从 `.env` 读取 `CONFIG_ENCRYPTION_KEY`，不会在首次启动或容器重建时自动生成。将密钥生成命令的输出填入 `.env` 的 `CONFIG_ENCRYPTION_KEY`，并妥善备份该值；后续容器重建、迁移或数据恢复时必须继续使用同一个密钥，否则已加密的用户私密配置无法解密。未配置密钥时，空数据库仍可启动，但无法保存 API Key、Token 等敏感配置；如果数据库中已经存在敏感配置，后端就绪检查将失败。

启动后访问 `http://localhost:8080`。如端口冲突，可在 `.env` 中设置 `DOCKER_FRONTEND_PORT=8081`，再访问对应端口。`data/` 和 `logs/` 通过卷挂载持久化，容器重建后数据不丢失。服务异常退出后会自动重启，容器日志按单文件 10 MB、最多 3 个文件轮转。代码更新后重新构建，BuildKit 会复用 uv 和 npm 下载缓存：

```bash
docker compose up -d --build
```

#### Docker 数据备份与恢复

备份前暂停后端，确保 SQLite 主文件及 `-wal`、`-shm` 文件状态一致；归档同时包含 `.env` 中的加密密钥，请安全保存：

```bash
docker compose stop backend
tar -czf ../a-share-agent-backup.tar.gz data .env
docker compose start backend
```

恢复时会覆盖当前 `data/` 和 `.env`，应先停止容器并确认当前数据已另行保留：

```bash
docker compose down
tar -xzf ../a-share-agent-backup.tar.gz
docker compose up -d
```

### 手动安装

环境要求：Python 3.11+、Node.js 22、uv、npm

### 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`：

```env
LLM_PROVIDER=deepseek
LLM_API_MODE=auto
LLM_API_VERSION=
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=180

# Chat 成本与稳定性保护
MAX_CONCURRENT_CHAT_PER_USER=2
MAX_CONCURRENT_CHAT_TOTAL=8
MAX_CONCURRENT_LLM_REQUESTS=6
CHAT_MAX_COMPLETION_TOKENS=4096
CHAT_TOTAL_TIMEOUT_SECONDS=300
CHAT_HEARTBEAT_SECONDS=15
CHAT_TOOL_TIMEOUT_SECONDS=45
```

`LLM_API_MODE` 支持 `auto`、`openai`、`litellm`；推荐使用 `auto` 跟随 Provider。Azure 等接口可通过 `LLM_API_VERSION` 指定版本，本地 Ollama 可不配置 API Key。

不配置 API Key 仍可浏览行情和数据页面，AI 分析能力不可用。

所有配置也可在前端设置页面（`/settings`）动态修改，无需重启服务。每个账号还可在「Skill 与 Agent」卡片中独立关闭 Chat Skill 或专业 Agent；关闭 Skill 会同步限制关联工具，关闭 Agent 后它不再参与多 Agent 路由。新能力默认启用。

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

| 模式 | 触发方式 | 依赖 | 适用场景 |
|------|---------|------|---------|
| `http` | 自动降级 | 仅 scrapling | 公开网页，自带反爬指纹 |
| `stealth` | HTTP 模式失败后自动尝试 | + playwright + chromium | 反爬严格的网站 |
| `dynamic` | 启用动态抓取后自动尝试 | + playwright + chromium | JS 渲染的 SPA 页面 |

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

### 飞书 Bot Command

飞书应用订阅 `im.message.receive_v1` 事件，并将请求地址配置为
`https://<服务域名>/api/bot/feishu`。Bot 使用本地服务账号的模型配置、持仓和分析存储：

```env
BOT_ENABLED=true
BOT_SERVICE_USER_ID=1
BOT_FEISHU_APP_ID=cli_xxxxx
BOT_FEISHU_APP_SECRET=xxxxx
BOT_COMMAND_PREFIX=/
BOT_RATE_LIMIT_REQUESTS=10
BOT_RATE_LIMIT_WINDOW=60
BOT_WEBHOOK_MAX_SKEW_SECONDS=300
BOT_EVENT_DEDUP_TTL_SECONDS=600
BOT_JOB_POLL_SECONDS=1.0
BOT_JOB_LEASE_SECONDS=900
BOT_JOB_MAX_ATTEMPTS=3
BOT_JOB_RETRY_BASE_SECONDS=5.0
BOT_JOB_WORKER_CONCURRENCY=2
BOT_BATCH_CONCURRENCY=2
BOT_BATCH_MAX_STOCKS=10
BOT_ADMIN_USERS=["ou_xxxxx"]
FEISHU_VERIFICATION_TOKEN=xxxxx
FEISHU_ENCRYPT_KEY=xxxxx
```

- 支持 `/help`、`/status`、`/task [任务ID]`、`/analyze <股票代码>`、`/market`、`/batch`。
- 群聊消息需 `@机器人`；私聊可直接发送命令。
- `/batch` 仅允许 `BOT_ADMIN_USERS` 中的飞书用户执行。
- 分析类命令会先回发 8 位任务 ID，可通过 `/task` 查看最近任务或查询指定任务。
- `/batch` 使用受限并发执行，并分阶段回发已完成数量；并发数和最大股票数均可配置。
- 用户命令采用数据库共享滑动窗口限流，多实例部署时共享同一计数结果。
- 启用飞书 Encrypt Key 后，签名请求时间戳默认只允许前后 5 分钟，避免合法请求被重复播放。
- Webhook 会先完成 Token、签名和加密事件校验，将任务持久化后立即确认接收；Worker 支持进程重启恢复、租约接管和失败重试。
- 命令响应会在回发前持久化；飞书发送失败时只重试回发，不会重复执行股票分析。

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

## 账号系统与访问控制

系统内置多用户账号体系：首次启动自动创建管理员，其余用户需管理员发放的**邀请码**才能注册。每个账号拥有**独立的私密配置**（各自的 LLM Key、飞书、Notion、问财凭据），互不可见。

### 首次启动与注册

- **首次启动（空库）时，后端自动创建一个管理员账号**：用户名默认 `admin`（可用 `DEFAULT_ADMIN_USERNAME` 修改），**密码随机生成并打印到后端日志（仅打印一次）**。在日志中查找形如「已创建默认管理员账号」的输出获取临时密码。
- 用该临时密码登录后，系统会**强制要求先修改密码**才能进入应用（首登改密页）。
- 之后的用户注册必须填写邀请码（管理员在「设置 → 邀请码管理」生成）。
- 公开页：`/login`、`/register`、`/reset-password`；其余页面需登录，未登录自动跳转登录页，令牌失效（401）自动登出。
- 若清空账号后重新初始化（见下方「重置账号」），下次启动会再次自动种子一个新的默认管理员。

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
- 个股分析、每日复盘、产业链分析和市场资讯 AI 摘要的运行状态、缓存或历史文件均按用户隔离，不会复用其他用户的 LLM 结果。
- 数据源 Cookie 是实例级全局配置，对所有用户生效。
- **注意**：所有业务 API 均需登录，只有认证接口和健康检查保持公开。

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

命令会先显示各账号表条数并要求输入 `yes` 确认。清空后**重启后端**，后端会**自动种子一个新的默认管理员**（用户名 `admin`，随机密码打印到日志，首次登录强制改密）。

### 相关环境变量

登录失败限流（防暴力破解）可用环境变量调整（可选，均有默认值）：

```env
LOGIN_MAX_FAILURES=5        # 连续失败多少次后锁定（按用户名 + IP 双维度）
LOGIN_WINDOW_SECONDS=300    # 失败计数窗口（秒）
LOGIN_LOCK_SECONDS=300      # 锁定时长（秒）
```

- 首次启动自动创建的默认管理员用户名可用 `DEFAULT_ADMIN_USERNAME` 修改（默认 `admin`；密码随机生成并打印到后端日志，非环境变量，首登强制改密）。
- 若前端部署在与后端不同的域名，用 `CORS_ORIGINS`（逗号分隔）配置允许来源。

## 免责声明

本系统仅供学习和研究使用，不构成任何投资建议。AI 分析结果基于公开数据和模型推理，不保证准确性、完整性或时效性。投资有风险，入市需谨慎。
