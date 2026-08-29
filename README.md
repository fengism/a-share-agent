# A 股智能选股助手

基于 AI 的 A 股多维度智能分析平台，覆盖市场概览、今日主线、热点榜单、涨停复盘、龙虎榜、板块资金、条件选股、每日复盘、个股行情、基本面、技术面、情绪面和 AI 综合分析。内置 AI 选股助手，对话式获取实时数据并智能分析。

## 功能特性

- **全局股票搜索**：支持 6 位股票代码和名称模糊搜索，跳转到个股分析页。
- **市场概览**：展示主要指数、成交量、自选栏和今日主线（财联社主线题材、板块涨跌、龙头股与风格判断）。
- **市场数据**：指数分时/K线、涨停天梯、历史涨跌停与风向标复盘、北向资金、融资融券余额与融资净买入历史、行业资金排行。
- **交易日历**：A 股交易日历热力视图，每个交易日按上证指数当日涨跌着色，支持月份切换与今日交易状态。
- **板块下钻**：行业排行按开盘红板块代码一键查看历史成分股明细（涨跌幅、主力净额、连板与龙虎榜标签）。
- **条件选股**：按市场板块（主板/创业板/科创板/北交所）、行业、价格、市值、估值等条件筛选，支持估值百分位过滤与可选风控过滤（ST/次新/低流动性）；策略选股按信号新鲜度排序。
- **每日潜力股**：收盘后自动挖掘潜力标的——按成交额构建候选池（剔除 ST/次新/低流动性），7 个量化策略信号加权融合评分，前端榜单展示命中策略与信号日期，支持历史回看。
- **24小时资讯**：聚合多源快讯和新闻，AI 智能摘要提炼关键信息并附带引用链接，自动刷新。
- **产业链分析**：输入产业关键词，AI 自动搜索研报数据并生成完整产业链分析报告，支持历史记录和推送。
- **宏观经济**：物价、景气、货币、利率、增速、外贸六大类宏观指标一览，含图表趋势。
- **每日复盘**：聚合市场、热点、新闻和 LLM 结论，生成结构化复盘。
- **个股分析**：展示分时、K 线、基本面、营收与毛利构成、估值（含机构一致预期）、技术指标、情绪数据和 AI 结论。营收与毛利构成来自新浪最新披露的产品/业务/地区口径，独立缓存 24 小时；上游不提供报告期与币种声明，各维度或条目可能重叠，因此不做跨维度汇总。该构成数据也会作为有界、可选证据进入 AI 财务分析。三张报表使用最新共同报告期生成汇总指标，并保持稳定 raw key；前端中文列名由后端统一字段字典生成，避免新浪与东方财富字段映射漂移。
- **AI 综合分析**：LLM 输出评分、评级、目标价格区间和买入/持有/卖出信号，融合机构一致预期数据。
- **个股研究**：统一入口承载分析执行、历史记录、基本面、估值、技术面、情绪面和资金流向，“投资研究”作为默认分析维度展示信息完备度、盈利引擎、护城河反证、管理层、行业位置、风险、三情景估值和条件化行动。带股票代码的 `/investment-research/:code` 保留为专注报告阅读与 PDF 导出地址，无代码旧入口会跳转到 `/analysis`。
- **量化研究**：YAML DSL 声明式策略热加载（支持跟踪止损等持仓路径依赖条件）、确定性回测引擎（T-1 信号次日开盘成交、涨跌停不成交、费用模型、未平仓敞口标记）、在线 LLM 草稿工作台与发布门禁；回测历史分页加载。
- **资讯去重**：多源市场资讯按归一化标题跨源去重。
- **可恢复长任务**：个股分析和产业链分析由 SQLite 持久化 Workflow 执行，支持进度续传、断线重连和远程取消；切换到其他页面后任务继续运行，顶部“运行中”入口可返回任务或直接停止。
- **AI 选股助手**：对话式智能选股，支持自然语言提问，自动调用工具获取实时数据并分析；专业 Agent 可回答主线、板块资金与历史成分股等问题。同一浏览器标签页内切换页面不会中断当前对话生成，顶部任务入口和对话输入区均可停止；刷新或关闭标签页后的续传暂不支持。
- **飞书推送**：将分析结果和每日复盘推送到飞书文档，自动按类型分目录，支持权限授权。聊天结果可推送飞书卡片。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 18 + TypeScript + Vite + Ant Design 6（多主题） |
| 状态与请求 | Zustand + TanStack Query + SSE |
| 图表 | Lightweight Charts + ECharts |
| 后端 | FastAPI + Python 3.11+ + Pydantic v2 |
| 数据源 | 国家统计局 + 交易所官方名录 + akshare/东方财富/新浪/同花顺/问财/财联社/开盘红/百度/腾讯/巨潮资讯/Twitter 等 fallback |
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

启动后访问 `http://localhost:8080`。默认拓扑只有一个 `backend` 容器：同一 Uvicorn 进程运行 HTTP 服务、周期维护以及 Bot、Quant 和 Analysis/Industry Chain 持久化任务 Worker；此外还有一个 `frontend` 容器和一个 `tdx-api` sidecar，不会额外启动 `backend-worker`。如端口冲突，可在 `.env` 中设置 `DOCKER_FRONTEND_PORT=8081`，再访问对应端口。`tdx-api` 默认仅绑定宿主机 `127.0.0.1:18080`。

#### YAML 量化策略热加载

量化策略使用受限 YAML DSL，默认目录为 `backend/app/modules/quant/strategies/definitions/`。新增 `.yaml` 文件后，后端会按 `QUANT_STRATEGY_RELOAD_SECONDS` 定期扫描；整目录全部校验和编译成功后才原子替换注册表，失败时继续使用上一份有效版本。前端会定期刷新策略描述符，动态渲染数值、布尔、选项参数及跨参数约束。

回测执行会按策略指标图自动计算预热周期，在请求开始日前加载额外行情；完整股票行情输入会随任务保存以支持复现，但 API 展示的行情快照、净值、交易和基准指标只覆盖用户选择的回测区间。预热数据会规范为确定日期顺序并校验实际数量，不足时明确失败；股票与基准统一使用 ISO 交易日期，结果记录真实数据源、市场数据哈希和引擎版本。全组合重平衡只在有限窗口内执行，窗口内无法负担的买单转为逐代码休眠意图，后续满足一手含费资金条件时只补买该代码，不重新调整其他持仓。当前正确语义版本为 `2026-08-24-v8`。

```yaml
api_version: quant.strategy/v1
key: price_above_average
version: 1.0.0
enabled: true
name: 价格均线策略
description: 收盘价高于均线时持仓
scenario: 趋势行情
risk_level: medium
parameters:
  period:
    type: integer
    label: 均线周期
    default: 20
    minimum: 2
    maximum: 250
constraints:
  - operator: greater_or_equal
    left: $period
    right: 10
    message: 均线周期不能小于 10
indicators:
  average:
    operator: sma
    input: close
    period: $period
signals:
  entry: { operator: greater_than, left: close, right: average }
  exit: { operator: less_or_equal, left: close, right: average }
position: { mode: binary }
```

DSL v1 支持 `sma`、`ema`、`rsi`、`rolling_max`、`rolling_min`、`rolling_std`、`obv`、`shift` 指标，以及 `add` / `subtract` / `multiply` / `divide` 指标序列运算；信号支持比较、交叉和 `and` / `or` / `not` 组合。`shift` 将输入序列滞后指定周期，可表达 ROC 动量、连续上涨和跳空缺口等形态。`rsi` 使用简单滚动平均涨跌幅的 Cutler RSI；`obv` 从评估日前固定 250 个交易 bar 的历史锚点起累计，并除以 `10_000`，阈值和派生指标均使用该缩放口径。依赖运行时持仓序列的算术指标不支持 `offset`。YAML 只通过 `safe_load` 解析，不支持 Python 导入、自定义 Tag 或任意代码执行。

运行时序列 `entry_price`、`holding_bars`、`highest_since_entry` 和 `lowest_since_entry` 只在信号持仓状态下有值。`entry_price` 是入场信号 bar 的收盘价，不是组合回测在下一可交易日开盘并计入滑点和费用后的实际成交价；`holding_bars` 在信号入场 bar 为 1，最高价和最低价序列包含该 bar。

内置预制策略包括：双均线趋势、均线金叉、动量突破、放量突破、RSI 均值回归、EXPMA 交叉、MACD 金叉死叉、布林带反转、KDJ 低位金叉、海龟唐安奇突破、BIAS 乖离率反转、量价配合、OBV 能量潮趋势、多头趋势、缩量回踩、底部放量、一阳夹三阴和箱体震荡共 18 个。

智能选股页还提供多头趋势、均线金叉、放量突破、缩量回踩、底部放量、一阳夹三阴和箱体震荡 7 个历史信号策略。策略可扫描当前分页中的候选，或当前筛选条件下前 200 只候选，并使用与量化回测完全相同的 YAML snapshot 和前复权日线计算最新目标仓位。扫描任务通过持久化 Workflow 执行，支持进度展示、断线续传和取消；结果会展示最近一次入场信号日期，并完整列出扫描范围内的命中股票，自动勾选前 10 只以便继续批量分析或回测。部分行情失败会明确提示且不会写入结果缓存，全部行情失败时任务会自动重试。

- 同一 `key + version` 的内容不可修改；版本哈希账本持久化在 `APP_DATA_DIR/quant-strategy-hashes.json`，服务重启后仍会拒绝同版本篡改。交易逻辑或参数定义变化时必须提升版本号。
- 新任务会把规范化定义、参数、版本和 SHA-256 写入任务快照，已排队和历史回测不受后续热加载影响。
- 管理员可访问 `GET /api/quant/strategy-registry` 查看当前目录、账本、generation、最后加载/尝试时间、最近错误和 last-good 策略版本。
- 管理员登录后可在“量化研究”页使用在线策略工作台：自然语言生成受限 DSL 草稿，编辑 JSON，编译校验，以当前定义快照发起回测，并在交易次数与最大回撤门禁通过后显式确认发布。
- 量化回测前端按“配置回测 / 任务记录 / 结果分析”三个独立视图组织；创建任务后自动进入任务记录，当前视图和任务 ID 会保留在 URL 中，刷新或分享链接后可恢复上下文。
- 配置页默认只展示当前策略摘要，预制策略目录按需展开；在任务记录中打开已完成回测会直接进入对应结果，减少重复切换。
- 当前策略摘要会同步显示实际参数并标记修改状态；低频的策略配置管理默认收起，结果页补充任务上下文和返回入口，移动端提供吸附的回测提交操作。
- 草稿更新必须携带当前定义哈希并通过 SQLite Compare-And-Swap，过期页面不会覆盖其他管理员的修改；回测中和已通过门禁的定义保持冻结，重复试跑使用同一不可变快照。
- 最大允许回撤只能从默认 80% 向下收紧；非有限数值、正回撤、负交易次数或陈旧快照都会直接使质量门禁失败。并发试跑未能绑定草稿时会自动撤销并清理孤儿任务。
- 在线草稿和状态持久化在 SQLite；发布文件原子写入 `APP_DATA_DIR/quant-strategies-published`，随后与只读策略目录一起全量校验并热加载。生成、回测或 LLM 失败都不会修改 last-good 注册表。
- Chat 中的 `quant_strategy_authoring` Skill 只向管理员开放受限策略工具；只有用户明确要求发布且提供当前定义哈希时，Agent 才能调用发布工具。
- 本地开发可通过 `QUANT_STRATEGY_DIR` 指向外部目录。
- Docker Compose 默认将 `QUANT_STRATEGY_HOST_DIR` 只读挂载到容器；首次更换宿主机目录需要重建容器，之后修改 YAML 无需重启。
- 热加载协议见 `docs/design/202608160039-quant-yaml-strategy-hot-reload.md`；在线生成、质量门禁和发布流程见 `docs/design/202608161016-quant-online-strategy-authoring.md`。

`backend` 和 `frontend` 默认使用只读根文件系统、删除 Linux capabilities 并启用 `no-new-privileges`，Nginx 以非 root 用户运行；`data/` 和 `logs/` 是后端显式可写卷，临时文件写入受限 `tmpfs`。容器重建后持久化数据不会丢失，服务异常退出后会自动重启，日志按单文件 10 MB、最多 3 个文件轮转。当前不支持多 Uvicorn Worker 或多 Backend 副本；这需要先将进程内缓存、限流和任务所有权迁移到共享基础设施。代码更新后重新构建，BuildKit 会复用 uv 和 npm 下载缓存：

```bash
docker compose up -d --build
```

#### Docker 数据备份与恢复

后端默认每天使用 SQLite 在线备份 API 将两个数据库备份到 `data/backups/`，写入后执行 `quick_check` 并生成 SHA-256 校验文件，每个数据库保留最近 7 份。可通过 `DATABASE_BACKUP_ENABLED`、`DATABASE_BACKUP_INTERVAL_SECONDS` 和 `DATABASE_BACKUP_RETENTION_COUNT` 调整。生产环境可设置 `DATABASE_BACKUP_DIR` 使用独立备份盘，并设置 `DATABASE_BACKUP_MIRROR_DIR` 将验证通过的备份同步到另一个已挂载的可写目录；使用 Compose 时需在 override 文件中显式挂载这两个目录。

执行完整离线归档前仍应暂停后端；归档同时包含在线备份、原始数据和 `.env` 中的加密密钥，请安全保存：

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

也可以从单个已校验的在线备份离线恢复数据库。恢复命令会再次校验 SHA-256（存在时）和 SQLite `quick_check`，并在覆盖前保存原数据库以及仍存在的 WAL/SHM 安全副本；任一步失败都会恢复完整文件组：

```bash
docker compose down
docker compose run --rm --no-deps backend \
  python -m app.scripts.restore_database_backup market \
  /app/data/backups/market-YYYYMMDDTHHMMSSZ.sqlite3 \
  --confirm-backend-stopped
docker compose run --rm --no-deps backend \
  python -m app.scripts.restore_database_backup user \
  /app/data/backups/user-YYYYMMDDTHHMMSSZ.sqlite3 \
  --confirm-backend-stopped
docker compose up -d
```

#### Workflow 进度与取消

个股分析和产业链分析先通过 `POST /api/workflows/analysis/{code}` 或 `POST /api/workflows/industry-chain/{name}` 创建持久化任务，再通过 `GET /api/workflows/{job_id}/stream` 接收 SSE 进度。浏览器断线重连时会携带 `Last-Event-ID`，后端从游标之后继续回放事件并去重；取消操作先调用 `DELETE /api/workflows/{job_id}`，再中止本地连接。旧 Analysis/Industry Chain SSE 地址继续作为兼容入口。

队列默认最多并发执行 2 个任务、每个用户同时运行 1 个任务，并限制用户级和全局活动任务数量；终态任务默认保留 30 天。相关参数见 `.env.example` 中的 `WORKFLOW_JOB_*` 配置。

#### Prometheus 指标

`GET /api/health/metrics/prometheus` 以 Prometheus 文本格式输出 Workflow 队列、后台任务重启和备份新鲜度等指标。设置 `METRICS_API_KEY` 后使用 `X-Metrics-Key` 访问；未设置时也可使用管理员 Bearer Token：

```bash
curl -H "X-Metrics-Key: ${METRICS_API_KEY}" \
  http://localhost:8080/api/health/metrics/prometheus
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
CHAT_MAX_TOOL_CALLS_PER_ROUND=8
CHAT_MAX_TOOL_CALLS_TOTAL=32
CHAT_MAX_TOOL_CONTEXT_CHARACTERS=60000
CHAT_MAX_SYNTHESIS_CHARACTERS=60000
```

`LLM_API_MODE` 支持 `auto`、`openai`、`litellm`；推荐使用 `auto` 跟随 Provider。Azure 等接口可通过 `LLM_API_VERSION` 指定版本，本地 Ollama 可不配置 API Key。

不配置 API Key 仍可浏览行情和数据页面，AI 分析能力不可用。

所有配置也可在前端设置页面（`/settings`）动态修改，无需重启服务。每个账号还可在「Skill 与 Agent」卡片中独立关闭 Chat Skill 或专业 Agent；关闭 Skill 会同步限制关联工具，关闭 Agent 后它不再参与多 Agent 路由。新能力默认启用。

### 安全网页抓取

AI 聊天助手通过受控 HTTP 传输抓取公开 URL：域名的全部解析结果必须是公网地址，实际连接固定到已校验 IP，并在每一跳重定向时重新解析、校验和固定目标；HTTPS 仍使用原始域名执行 SNI 和证书校验。

DNS 解析在线程池中执行，并与连接及重定向共享同一个请求截止时间。响应体采用流式读取，默认最多保留 20 MiB（可通过 `WEB_FETCH_MAX_RESPONSE_BYTES` 调整，范围 64 KiB ~ 100 MiB），同时检查声明大小和解压后的实际大小。

`fetch_url` / `fetch_urls` 支持 `auto`、`http`、`stealth`、`dynamic` 四种模式。`auto` 先使用固定 IP HTTP，失败或正文不足时依次尝试 stealth 和 dynamic。浏览器运行在后端主进程中并直接联网，以保持与旧版 Scrapling 行为一致；浏览器模式只校验初始 URL 为 HTTP(S)，不会对重定向、iframe、XHR 或子资源执行私网/DNS Rebinding 防护。

首次安装由 `./setup.sh` 自动安装 Patchright Chromium；也可以手动执行：

```bash
make backend-sync
make backend-browser-install
```

浏览器模式由 `WEB_FETCH_BROWSER_ENABLED` 控制，默认总超时 60 秒；dynamic 等待 DOMContentLoaded 后再稳定 5 秒（`WEB_FETCH_BROWSER_SETTLE_SECONDS`），不等待尾部统计资源触发完整 load；stealth/dynamic 在进程内共享并发上限（`WEB_FETCH_BROWSER_MAX_CONCURRENCY`，默认 2）。主进程方案不能隔离 Chromium 漏洞带来的进程权限风险，面向不可信公网长期运行时仍建议使用独立容器。

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

### 质量验证

```bash
make check          # 后端 Ruff/Mypy/pytest + 前端 API 合同/Vitest/ESLint/Build
make frontend-e2e   # Playwright 登录与 Workflow 重连/取消 smoke 测试
```

完整前端验证使用 Node.js 22。Playwright 首次运行前需在 `frontend/` 执行 `npx playwright install chromium`。

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

## 投资研究框架

个股分析在原有基本面、估值、技术面和情绪面之外，提供结构化长期投资研究：盈利引擎、护城河与反证、管理层与资本配置、行业与价值链、反向风险、估值情景、角色化行动条件以及待核验的数据缺口。

- A/B/C 表示公开信息的完备程度，不是股票或公司质量评级。
- “证据可信度”衡量数据覆盖、时效和一致性；“投资确定性”衡量商业模式与结果区间的可预测性，两者不会合并成一个分数。
- 技术面和情绪面仅作为短期择时参考，不替代长期商业质量判断。
- 旧版历史快照不会被自动补写；重新运行分析后才会产生新版结构化研究。
- 方法设计受 [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire) 的公开投资研究框架启发，本项目采用独立的数据契约和实现。

## 免责声明

本系统仅供学习和研究使用，不构成任何投资建议或收益承诺。AI 分析结果基于公开数据和模型推理，不保证准确性、完整性或时效性；信息完备度与模型置信度也不能消除市场、公司经营和估值假设的不确定性。请独立核验重要事实与假设，投资有风险，入市需谨慎。
