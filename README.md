<h1 align="center">智能投研平台</h1>

<p align="center">基于 AI 的 A 股多维分析平台：行情、选股、个股研究、宏观资讯、产业链、量化回测与自动推送。</p>

<p align="center"><img src="docs/images/dashboard.png" alt="市场总览"></p>

> [!TIP]
> **第一次部署**看 [快速开始](#快速开始)；只想确认界面效果看 [界面预览](#界面预览)；
> 遇到报错先查 [常见问题](#常见问题) 与 [故障排查手册](docs/troubleshooting.md)。

## 目录

- [核心特性](#核心特性) — 功能总览
- [界面预览](#界面预览) — 界面截图
- [技术架构](#技术架构) — 技术选型
- [快速开始](#快速开始) — Docker 部署 / 本地开发
- [常用配置](#常用配置) — 大模型、搜索、推送、Notion
- [数据与存储](#数据与存储) — 分库、日线归档、备份恢复
- [账号与权限](#账号与权限) — 初始管理员、邀请码、登录审计
- [量化策略](#量化策略) — YAML DSL 与回测引擎
- [开发与维护](#开发与维护) — 常用命令与 CI 约定
- [常见问题](#常见问题) — FAQ
- [延伸文档](#延伸文档) — 文档索引
- [免责声明](#免责声明) — 风险提示
- [许可证](#许可证) — MIT License

## 核心特性

### 行情与复盘
- 市场大盘概览：主要指数分时、成交量分布、自选股与今日题材主线（主线题材、龙头股、市场风格、板块资金排行）。
- 行情与复盘数据：指数分时 / K 线、涨跌停天梯、连板晋级、风向标表现、北向资金与两融数据。
- 交易日历：A 股交易日热力视图，按当日涨跌着色，支持月份切换与休市查询。
- 智能每日复盘：聚合盘面、热点轮动、资金流向与宏观要闻，生成结构化复盘报告并可导出 PDF。

### 选股与潜力挖掘
- 条件与策略选股：主板 / 创业板 / 科创板 / 北交所、行业、市值、估值百分位、流动性多维筛选，内置 7 大量化形态策略。
- 全局股票搜索：支持 6 位 A 股代码、5 位港股代码与名称模糊搜索。
- 每日潜力股：从高流动性龙头、中盘活跃、质量中盘三层候选池出发，融合策略信号、技术 / 估值 / 行业质量、财务二次重排与题材加权，按行业分散输出，支持历史回溯与 5/10/20 日前瞻收益复盘。

### 个股研究与持仓
- 个股全维分析：分时 / K 线 / MACD / RSI / KDJ / 筹码分布 / 缠论笔与中枢；三张报表关键指标、营收毛利构成、DCF 情景测算、五种估值模型与同行对标；投资研究框架（盈利引擎、护城河反证、资本配置、竞争格局、三情景估值与条件化行动指引）。
- 主力资金流向：多源自动降级与高精度分笔估算。
- 仓位管理：按交易流水与手续费 FIFO 核算成本，基于历史收盘价绘制总资产、持仓市值、累计收益率与最大回撤曲线。

### 宏观、资讯与产业链
- 24 小时财经资讯：聚合主流财经媒体快讯与宏观要闻，AI 提炼摘要并标注信源。
- 深度产业链分析：输入产业关键词，自动检索研报与上下游，生成产业链图谱、标的业务相关度对比与研报依据。
- 全球宏观：物价、景气、货币、利率、外贸指标走势；港股行情、SGE 黄金现货、大宗商品期货、美元指数与中美国债利差。

### AI、量化与协同
- AI 对话助手：自然语言问答，自动调用行情、资讯、财务与对比工具完成多股横向推演。
- 声明式量化研究：安全 YAML DSL 策略定义 + 确定性回测引擎，支持移动止损、路径依赖条件与在线生成 / 校验。
- 多端协同与推送：研报与复盘支持导出高清 PDF、转存 Notion；支持收盘后推送到飞书群、钉钉群、企业微信群与微信服务号，具备事件总线解耦、智能防抖与全链路审计（见 [自动推送与通知配置](docs/push-notifications.md)）。

## 界面预览

以下截图取自本地运行实例（真实行情、真实申万行业映射与真实回测结果），非设计稿。

**市场行情** — 指数分时、K 线趋势、涨停梯队与板块资金一屏联动。

![市场行情](docs/images/market.png)

**智能选股** — 按估值、价格、涨跌幅、行业与概念筛选全市场 5000+ 标的，内置场景条件与历史形态信号。

![智能选股](docs/images/screener.png)

**仓位管理** — FIFO 核算持仓成本，绘制总资产、证券市值、累计收益率与最大回撤。

![仓位管理](docs/images/portfolio.png)

**量化研究** — 声明式策略 DSL + 确定性回测引擎，输出核心指标、净值与回撤、交易点位与收益归因。

![量化回测](docs/images/quant.png)

**交易日历** — A 股交易日热力图，按当日上证涨跌着色，支持月份切换与休市查询。

![交易日历](docs/images/trading-calendar.png)

**登录与访问控制** — 多租户登录、邀请码注册与首次登录强制改密。

![登录页](docs/images/login.png)

## 技术架构

| 分层 | 技术选型 | 说明 |
| :--- | :--- | :--- |
| 前端 | React 18 + TypeScript + Vite + Ant Design 6 | 响应式交互与多主题适配 |
| 图表 | Lightweight Charts + ECharts | 金融 K 线与复合数据看板 |
| 状态 / 网络 | Zustand + TanStack Query + SSE | 状态管理、服务端缓存与流式长任务推送 |
| 后端 | FastAPI + Python 3.11+ + Pydantic v2 | 异步 API 服务与长任务 Workflow 编排 |
| 存储 | SQLite 3（WAL） | 按业务分库：用户库、行情库、行业库、历史日线库 |
| 数据源网关 | 统一 Provider Gateway | tdxhub、akshare、东方财富、新浪、交易所名录、开盘红、AnySearch 等，含熔断、限流与平滑降级 |
| AI 引擎 | OpenAI-compatible SDK + LiteLLM | DeepSeek、通义千问、OpenAI、Claude、Gemini、Azure、本地 Ollama 等 |
| 部署 | Docker Compose + Nginx | 容器化部署、自动备份与非 root 安全加固 |

## 快速开始

| 方式 | 适合 | 前置要求 |
| :--- | :--- | :--- |
| Docker 部署（推荐） | 只想用起来 | Docker 20.10+、Compose v2+ |
| 本地开发部署 | 要改代码 | Python 3.11+、uv、Node.js 22、npm |

最短路径：`cp .env.example .env` → 生成并填入 `CONFIG_ENCRYPTION_KEY` → `docker compose up -d`，
首次启动的后端日志会打印初始管理员账号密码。

### 方式一：Docker 部署（推荐）

```bash
# 1. 复制环境变量文件
cp .env.example .env

# 2. 生成配置加密密钥并填入 .env 的 CONFIG_ENCRYPTION_KEY
openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'; echo

# 3. 编辑 .env 配置必需项（如 LLM_API_KEY）
vim .env

# 4. 创建持久化数据目录并启动
mkdir -p data logs
docker compose up -d

# 5. 查看状态与后端日志（首次启动会打印初始管理员账号密码）
docker compose ps
docker compose logs backend
```

启动完成后访问 `http://localhost:8080`。

**服务拓扑**（默认 4 个容器）：

| 服务 | 职责 |
| :--- | :--- |
| `backend` | FastAPI 主服务：API、异步任务调度、持久化任务引擎 |
| `frontend` | Nginx 静态资源托管与反向代理，对外访问入口 |
| `docker-socket-proxy` | 受限安全代理，容器管理接口最小权限访问 |
| `updater` | 在线更新执行器：按后端解析的 release revision 拉取不可变镜像 `<repo>:sha-<rev>`，仅在不可用时回退 `main` 别名 |

镜像只在**发版（tag）或手动触发流水线**时发布，因此更新的可见节奏跟随发版，不随每次代码推送变动
（Actions → *Build & Publish Docker Images* → *Run workflow* 可手动发布）。

可选沙箱服务：`python-runner`（profile `python-sandbox`，隔离的 Python 代码执行环境），用 `make docker-sandbox-up` 启动。

> [!TIP]
> - **权限**：容器默认以 UID/GID `1000:1000` 运行；挂载目录报权限错时执行 `sudo chown -R 1000:1000 data logs`。
> - **端口**：改前端映射端口在 `.env` 设置 `DOCKER_FRONTEND_PORT=8081`。

### 方式二：本地开发部署

```bash
# 1. 安装前后端依赖与基础运行库
./setup.sh

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 配置相关 API Key

# 3. 启动开发环境（热重载）→ http://localhost:5173
./start.sh dev

# 停止服务
./stop.sh
```

环境准备、命令全表与调试技巧见 [本地开发指南](docs/development.md)，或执行 `make help`。

## 常用配置

> [!NOTE]
> 下表只列最常用项，**完整变量清单与注释以 `.env.example` 为准**（约 300 行，按业务分组）。
> 配置的存储位置、作用域与新增流程见 [配置系统开发指南](docs/configuration.md)。

### 大模型（LLM）

支持任意兼容 OpenAI 接口规范的提供商。

```env
LLM_PROVIDER=zhipu
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=GLM-4.7-Flash
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=300
```

管理员可在前端「系统设置」动态修改全局配置；登录用户也可配置自己的 API Key 实现额度与模型隔离。
管理员保存的模型与推送通道配置会自动同步为全局基线，供无用户上下文的常驻后台任务复用。

### AnySearch 聚合搜索

提供 `web_search` 检索工具：

```env
# 支持多个 Key，逗号分隔，后端按请求轮询
ANYSEARCH_API_KEY=key_1,key_2,key_3
```

未配置时自动降级为百度、360 等公共搜索源；可在「系统设置 → 数据源管理」在线更新。

### 飞书推送与 Bot 交互

```env
FEISHU_ENABLED=true
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx
FEISHU_FOLDER_TOKEN=fldcnXXXX                    # 云文档目录 Token
FEISHU_WIKI_SPACE_ID=                            # 知识库 Space ID（配置后优先推送知识库）
FEISHU_DEFAULT_RECEIVER=ou_xxxxx                 # 默认接收人 open_id / chat_id

BOT_ENABLED=true                                 # Bot 复用上面的 APP_ID / APP_SECRET
FEISHU_VERIFICATION_TOKEN=xxxxx
FEISHU_ENCRYPT_KEY=xxxxx
# Bot 使用与文档转存不同的飞书应用时才需单独指定（兼容旧部署）
# BOT_FEISHU_APP_ID=cli_yyyyy
# BOT_FEISHU_APP_SECRET=yyyyy
```

- 支持命令：`/analyze <股票代码>`、`/market`、`/status`、`/task <任务ID>`；群聊 `@机器人` 或私聊即可触发。

### 问财与 Notion

```env
IWENCAI_ENABLED=true                             # 问财自然语言选股
IWENCAI_BASE_URL=https://openapi.iwencai.com
IWENCAI_API_KEY=your_iwencai_api_key

NOTION_ENABLED=true                              # 研报转存 Notion
NOTION_API_TOKEN=secret_xxx
NOTION_PARENT_PAGE_ID=your_parent_page_id
```

## 数据与存储

数据持久化在 `data/` 目录，采用 SQLite 分库 + WAL 模式：

| 数据库 | 内容 | 备注 |
| :--- | :--- | :--- |
| `market_data.db` | 行情基础缓存、指数与自选数据 | 可从数据源重建 |
| `user_data.db` | 账号、授权、研报版本历史、任务队列 | 含账号与历史报告，**需备份** |
| `industry_data.db` | 申万行业分类、概念标签、主营业务资料 | 由种子 + 周期同步维护 |
| `market_daily.sqlite3` | 历史日线与复权因子 | 归档 / 回填产物，重建成本高 |

### 历史日线归档与复权

- 交易日归档：每个交易日收盘后两阶段快照（16:20 预归档、17:00 最终复核），记录 A 股与港股原始未复权 OHLCV。
- 复权因子：由除权除息记录推导前 / 后复权仿射因子，本地可用时优先本地计算，降低外部接口依赖。
- 状态与运维：「系统设置 → 行情归档」可查看归档状态、手动刷新、失败重试与因子健康度检查。
- 历史回填：同一页面可按日期区间创建 A 股回填任务，按 `TDX → 腾讯 → AkShare 新浪 → 东方财富直连 → 新浪直连 → 财联社` 优先级逐股拉取未复权日 K，至少两个独立来源校验日期、OHLC、成交量与成交额后才入库；支持断点续跑、质量评分、取消与「跳过 / 覆盖已有数据」两种写入模式。

### 备份与离线恢复

后端每天用 SQLite 在线备份 API 热备四个数据库：自动 `quick_check` 完整性检查、gzip(level 9) 压缩为
`.sqlite3.gz` 并生成 SHA-256 校验文件。默认在 `data/db/backups/` 保留最近 2 份，可用
`DATABASE_BACKUP_RETENTION_COUNT` 或「系统设置 → 管理员工具 → 数据库在线备份」调整。

```bash
docker compose down

# 恢复指定数据库（支持 .sqlite3 与 .sqlite3.gz）
docker compose run --rm --no-deps backend \
  python -m app.scripts.restore_database_backup market \
  /app/data/db/backups/market-YYYYMMDDTHHMMSSZ.sqlite3.gz \
  --confirm-backend-stopped

docker compose up -d
```

### 行业主数据与种子

`backend/seeds/` 内置行业分类与概念映射种子（约 0.5 MB），新部署首次启动自动播种。

```bash
make backend-db-init          # 初始化数据库结构
make backend-export-seeds     # 将当前运行库导出为新种子
make backend-seed-hot-stocks  # 为热门股票补充经营主营资料（默认 TOP=50）
```

## 账号与权限

- **初始管理员**：首次启动自动创建（默认用户名 `admin`，可用 `DEFAULT_ADMIN_USERNAME` 覆盖）；
  **初始密码随机生成并仅在首次启动的后端日志打印**，首次登录强制改密。
  空库时首个注册者即管理员，若实例在注册前已公网可达，请配置 `ADMIN_SETUP_TOKEN` 防止他人抢先注册。
- **邀请码注册**：普通用户注册必须使用邀请码，管理员在「系统设置 → 邀请码管理」生成并设置有效期。
- **配置隔离**：用户自备的 API Key、自选股与历史研报互相隔离；数据源 Cookie 等全局配置仅管理员可见可改。
- **登录设备与审计**：「系统设置 → 账号与安全」可查看登录设备、让其他设备下线、查看自己的登录记录；
  登录审计与管理员操作留痕分别按 `LOGIN_AUDIT_RETENTION_DAYS`（默认 180 天）、`ADMIN_AUDIT_RETENTION_DAYS`（默认 365 天）清理，记录不含任何密钥。
- **密码策略**：长度 8–128 且同时含字母与数字；拦截高频弱口令、与用户名相同 / 包含用户名、单一字符重复。

忘记管理员密码可在服务器无损重置（不影响业务数据）：

```bash
# 本地运行
make backend-reset-admin ADMIN=admin PASS="YourNewPassword"

# Docker 环境运行
docker compose exec backend python scripts/reset_admin_password.py admin --password "YourNewPassword"
```

## 量化策略

声明式 YAML DSL + 确定性回测引擎，支持历史回测与在线热加载。

```yaml
api_version: quant.strategy/v1
key: price_above_average
version: 1.0.0
name: 均线突破策略
description: 收盘价上穿指定均线买入，下穿时平仓
scenario: 趋势行情
risk_level: medium
parameters:
  period: { type: integer, label: 均线周期, default: 20, minimum: 5, maximum: 120 }
indicators:
  average: { operator: sma, input: close, period: $period }
signals:
  entry: { operator: greater_than, left: close, right: average }
  exit: { operator: less_or_equal, left: close, right: average }
position: { mode: binary }
```

- **内置算子**：`sma`、`ema`、`rsi`、`rolling_max`、`rolling_min`、`rolling_std`、`obv`、`shift` 及算术运算。
- **回测引擎**：次日开盘成交、涨跌停限制校验、佣金与印花税模型；输出净值、年化收益、夏普与最大回撤。
- **预制策略**：双均线、MACD 交叉、布林带反转、海龟唐安奇突破等 18 种经典策略。
- **在线策略**：任何登录用户可用一句话生成受限 DSL 草稿，编辑、编译校验并回测；「发布到全局策略库」需管理员权限，草稿与回测记录按用户隔离。

## 开发与维护

| 场景 | 命令 | 说明 |
| :--- | :--- | :--- |
| 启动 / 停止 | `make dev` / `make stop` | 热重载开发模式 |
| 状态 / 日志 | `make status` / `make logs` | 端口与日志 |
| 测试 | `make test` | 后端 pytest + 前端 vitest |
| 质量门禁 | `make check` | Ruff / Mypy / 模块边界 / 覆盖率 / OpenAPI 同步 / 前端测试与构建 |
| 端到端 | `make frontend-e2e` | Playwright smoke 测试 |
| 打包 | `make pack` | 排除密钥、数据与日志，生成 `stock-agent.tar.gz` |
| 发版 | `make release V=v0.8.0` | 推送 tag，由 GitHub Actions 构建并发布多架构镜像 |

> **CI 成本约定**：镜像构建与发布只在 tag 或手动触发（Actions → *Build & Publish Docker Images* → *Run workflow*）
> 时进行；推送到 `main` 只跑质量门禁与 E2E（约 25 分钟），tag 发布约 67 分钟。这样 30 次日常推送 + 2 次发版
> 约消耗 900 分钟/月。改动 Dockerfile / nginx.conf / 沙箱运行时时，PR 会额外做一次不推送镜像的构建与冒烟。

提交前请先本地跑通 `make check`；详细约定见 [本地开发指南](docs/development.md)。

## 常见问题

**Q：没有大模型 API Key 能用吗？**
行情、选股、潜力股、复盘数据、量化回测**不需要 Key**；AI 研报、对话、每日复盘文字生成需要。
管理员配一套即可全站复用，普通用户留空即继承管理员配置。
为避免管理员 Key 被发到其它地址，**换成自己的端点后必须自备 Key**（本地 Ollama 这类不需要 Key 的服务除外）。

**Q：数据从哪来，需要额外付费吗？**
以公开免费数据源为主（通达信、新浪、腾讯、东方财富、交易所官方名录、财联社、国家统计局等），
全市场数据多源交叉校验后入库；AnySearch、问财、FRED 等为可选增强源（见 [数据源与降级机制](docs/data-sources.md)）。

**Q：首次启动的管理员密码在哪看？**
仅在首次启动的后端日志中打印一次；忘记可用 `make backend-reset-admin ADMIN=admin PASS='新密码'` 无损重置
（容器环境见 [故障排查](docs/troubleshooting.md#二启动与部署)）。

**Q：会不会写坏数据库？**
四个 SQLite 库分工存储（见 [数据与存储](#数据与存储)），WAL 模式 + 在线热备，每天自动备份并校验完整性，支持离线恢复。

**Q：怎么升级到新版本？**
容器部署：`docker compose pull && docker compose up -d`，或用内置 `updater` 一键升级；
本地开发：`git pull` 后 `./setup.sh` 更新依赖，再执行 `make backend-db-init` 应用结构迁移。

**Q：数据会上传到第三方吗？**
除你自己配置的 LLM / 搜索 / 推送服务外，行情与研报数据只保存在本机 SQLite；
API Key 等敏感配置使用 `CONFIG_ENCRYPTION_KEY` 加密后落库。

## 延伸文档

| 文档 | 内容 | 适用场景 |
| :--- | :--- | :--- |
| [本地开发指南](docs/development.md) | 环境准备、命令表、质量门禁、测试与调试约定 | 参与开发 |
| [架构与边界](docs/architecture.md) | 分层与依赖规则、关键链路、设计取舍 | 深入代码 |
| [配置系统开发指南](docs/configuration.md) | 配置来源、作用域、新增配置项流程 | 改配置 / 加字段 |
| [数据源与降级机制](docs/data-sources.md) | Provider 清单、多源降级、熔断限流、质量校验 | 数据异常排查 |
| [故障排查手册](docs/troubleshooting.md) | 按症状组织的排查步骤与处置命令 | 运维排障 |
| [自动推送与通知配置](docs/push-notifications.md) | 飞书 / 钉钉 / 企微 / 微信服务号接入 | 配置推送 |

## 免责声明

1. 本平台仅供金融数据研究、量化模型学习与个人开发测试使用，**不构成任何投资建议、荐股或收益承诺**。
2. 市场有风险，投资需谨慎。AI 推理受限于公开数据与训练假设，可能存在时效滞后或幻觉，请独立判断并自行承担投资风险。
3. 行情与资讯数据版权归各数据源提供方所有，使用时须遵守其服务条款；请勿将本平台用于商业数据分发。

## 许可证

本项目基于 **MIT License** 发布，可自由使用、修改与分发（含商业用途），仅需保留版权与许可声明。
完整条款见 [LICENSE](LICENSE)。
