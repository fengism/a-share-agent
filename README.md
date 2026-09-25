# 智能投研平台

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
- **产业链分析**：输入产业关键词，AI 自动搜索研报数据并生成完整产业链分析报告，支持历史记录和推送。 支持行业研究模板、原文片段核验、关系传导图、公司业务相关度对比、同口径指标修订及按维度刷新公共数据；资料完整度不代表投资评分，原文匹配不等于事实核实。详见 [研究质量与跟踪说明](docs/industry-chain-research-quality.md)。
- **港股与全球品种**：港股实时行情、搜索与日 K；SGE 黄金全品种行情、大宗商品期货连续/主力合约报价（非现货或基差）、美元指数与中美国债收益率/利差、央行政策利率与全国海关进出口月度总量；商品与公司映射为静态参考，不含细分商品量价序列。
- **宏观经济**：物价、景气、货币、利率、增速、外贸六大类宏观指标一览，含图表趋势。
- **每日复盘**：聚合市场、热点、新闻和 LLM 结论，生成结构化复盘。
- **个股行情**：分时、K 线、MACD、RSI、KDJ 与筹码分布统一在个股页查看。K 线提供缠论开关，按当前周期与复权数据叠加笔、中枢及买卖点；不足 10 根 K 线时显示提示。
- **个股分析**：聚焦分析执行、历史记录和 AI 研究结论，移除技术面面板与技术面分项评分；估值快照、五种估值方法、DCF 情景与敏感性、机构一致预期和同行对比统一在个股资料的「估值」Tab 查看（旧估值链接自动跳转），基本面摘要、营收与毛利构成及关键财务指标统一在个股资料的「财务」Tab 查看，散户评论并入「资讯」Tab，资金流向作为与财务、资讯并列的独立 Tab，移除独立情绪面面板（完整 PDF 仍保留基本面与估值资料），复用个股页的基础资料与分时行情缓存，不重复展示或加载 K 线及技术指标图表；行情与技术指标仍在个股资料页查看。营收与毛利构成来自新浪最新披露的产品/业务/地区口径，独立缓存 24 小时；上游不提供报告期与币种声明，各维度或条目可能重叠，因此不做跨维度汇总。该构成数据也会作为有界、可选证据进入 AI 财务分析。三张报表使用最新共同报告期生成汇总指标，并保持稳定 raw key；前端中文列名由后端统一字段字典生成，避免新浪与东方财富字段映射漂移。
- **个股资金流备选**：百度、东方财富均失败或返回空数据后，尝试 tdxhub 的最近 60 个交易日分笔估算（含超大/大/中/小单及主力净流入）。页面通过 `/fund-flow-pages` 每批加载 20 日，点击「加载更多」再读取下一批，最多 60 日；游标固定数据源和交易日期，不跨源拼接，后续批次失败保留已显示数据。首批仅取得 60 日日 K 日期清单并聚合最新 20 日 `capital_flow`，不额外拉取滚动指标的 19 日预热分笔；完整历史单日结果独立进程内缓存 24 小时（当天不缓存，失败不写入，重启后清空），后续批次及重试可复用已完成日期。游标缓存有效 1 小时，重启或淘汰后需重新加载。原 `/fund-flow` 完整查询接口保持兼容。使用独立连接、并发 1、单次尝试；`TDXHUB_FUND_FLOW_TIMEOUT_SECONDS=60` 控制总 I/O 预算（最大 90 秒）。返回带 `source=tdxhub_stock_fund_flow_estimate`，页面提示估算口径；不与其他源拼接或补零，缺失/超时则沿用最近成功缓存并标为过期。日志区分日 K/历史分笔阶段、失败日期、已完成天数及实际耗时；SDK 0.3.0 的 deadline 内部接口仅封装在 tdxhub 适配器，升级 SDK 时需运行对应契约测试。
- **AI 综合分析**：LLM 输出评分、评级、目标价格区间和买入/持有/卖出信号，融合机构一致预期数据。
- **个股研究**：统一入口承载分析执行、历史记录和研究结论，独立的研究结论区展示信息完备度、盈利引擎、护城河反证、管理层、行业位置、风险、三情景估值和条件化行动。带股票代码的 `/investment-research/:code` 保留为专注报告阅读与 PDF 导出地址，无代码旧入口会跳转到 `/analysis`。
- **量化研究**：YAML DSL 声明式策略热加载（支持跟踪止损等持仓路径依赖条件）、确定性回测引擎（T-1 信号次日开盘成交、涨跌停不成交、费用模型、未平仓敞口标记）、在线 LLM 草稿工作台与发布门禁；回测历史分页加载。
- **资讯去重**：多源市场资讯按归一化标题跨源去重。
- **可恢复长任务**：个股分析和产业链分析由 SQLite 持久化 Workflow 执行，支持进度续传、断线重连和远程取消；切换到其他页面后任务继续运行，顶部“运行中”入口可返回任务或直接停止。
- **AI 选股助手**：对话式智能选股，支持自然语言提问，自动调用工具获取实时数据并分析；专业 Agent 可回答主线、板块资金与历史成分股等问题，并可通过 `compare_stocks` 工具完成多只股票横向对比。Web 端不再提供独立股票对比页面，历史 `/compare` 地址会跳转到条件选股页。同一浏览器标签页内切换页面不会中断当前对话生成，顶部任务入口和对话输入区均可停止；刷新或关闭标签页后的续传暂不支持。
- **主数据管理**：管理端维护个股资料、个股概念与申万行业分类——支持 Excel/CSV 批量导入（内容无变化的行自动跳过）、CSV 导出（导出文件可直接改后再导入）、联网补充（库中已有主营资料则跳过上游请求）与交易所官方名录同步；港股代码统一 5 位口径。
- **飞书推送**：将分析结果和每日复盘推送到飞书文档，自动按类型分目录，支持权限授权。聊天结果可推送飞书卡片。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 18 + TypeScript + Vite + Ant Design 6（多主题） |
| 状态与请求 | Zustand + TanStack Query + SSE |
| 图表 | Lightweight Charts + ECharts |
| 后端 | FastAPI + Python 3.11+ + Pydantic v2 |
| 数据源 | 统一 Provider Gateway 架构（内置熔断、限流与降级）：tdxhub / akshare / 东方财富 / 新浪 / 交易所官方名录 / 国家统计局 / 同花顺 / 问财 / 财联社 / 开盘红 / SGE / Twitter 等 |
| AI 引擎 | OpenAI-compatible SDK + LiteLLM，可配置 DeepSeek、通义千问、OpenAI、Claude、Gemini、Azure、Ollama 等 |
| 包管理 | uv + npm |
| 部署 | Docker + Docker Compose + Nginx |

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

### 后端日志

本地后端日志位于 `logs/backend.log`。默认 `LOG_LEVEL=INFO`，每个普通 HTTP 请求只保留中间件的一条结构化日志（含 `request_id`、路径、状态码、耗时及用户 ID），不再额外输出 Uvicorn 的原始访问日志；Uvicorn 的启动、关闭和错误日志不受影响。

- `GET /api/workflows/active` 是全局任务状态轮询：有任务时每 2 秒一次，空闲时每 10 秒一次，不代表任务卡住。
- 该轮询成功且耗时小于 1 秒时只记 DEBUG；耗时达到 1 秒记 WARNING。所有请求的 4xx 记 WARNING，5xx 或未处理异常记 ERROR。长连接 SSE 不按轮询耗时告警。
- 降噪不影响请求指标统计或 `X-Request-ID` 响应头。需要排查每次轮询及原始访问记录时，可用 `LOG_LEVEL=DEBUG ./start.sh` 启动后端；已有进程需要重启后生效。

### Docker 部署

环境要求：Docker 20.10+、Docker Compose v2+

```bash
# 1. 配置环境变量
cp .env.example .env
# Docker Compose 不会自动生成 CONFIG_ENCRYPTION_KEY；请编辑 .env 填入 LLM_API_KEY，
# 并执行以下命令生成密钥后写入 CONFIG_ENCRYPTION_KEY：
openssl rand -base64 32 | tr '+/' '-_' | tr -d '\n'; echo

# 2. 准备数据目录并启动
# Linux 若当前用户不是 UID/GID 1000，可先执行：
# export APP_UID=$(id -u) APP_GID=$(id -g)
mkdir -p data logs
docker compose up -d
# 或者使用 Makefile: make docker-up

# 3. 查看状态和首次启动生成的管理员临时密码
docker compose ps
docker compose logs backend

# 4. 停止
docker compose down
# 或者使用 Makefile: make docker-down
```

Docker Compose 只会从 `.env` 读取 `CONFIG_ENCRYPTION_KEY`，不会在首次启动或容器重建时自动生成。将密钥生成命令的输出填入 `.env` 的 `CONFIG_ENCRYPTION_KEY`，并妥善备份该值；后续容器重建、迁移或数据恢复时必须继续使用同一个密钥，否则已加密的用户私密配置无法解密。未配置密钥时，空数据库仍可启动，但无法保存 API Key、Token 等敏感配置；如果数据库中已经存在敏感配置，后端就绪检查将失败。

启动后访问 `http://localhost:8080`。

#### 服务拓扑结构

默认拓扑包含 4 个协同容器：
- `backend`：FastAPI 后端主服务（运行 HTTP 接口、后台调度、量化与 Workflow 任务），仅在内部网络暴露，由 Nginx 反代；
- `frontend`：Nginx 静态资源托管与反向代理，对外映射 `8080` 端口；
- `docker-socket-proxy`：隔离的 Docker Socket 代理（仅开放容器生命周期必要只读与重启接口，不直接暴露宿主机 socket 给业务容器）；
- `updater`：在线版本更新执行器，轮询管理员触发的更新请求，按需拉取新镜像并平滑重建 `backend`/`frontend`。

可选服务（通过 Compose Profile 启用）：
- `python-runner`（profile: `python-sandbox`）：隔离 Python 代码执行控制面；
- `python-sandbox-image`（profile: `python-sandbox-build`）：无网络受限沙箱工作镜像构建目标。
启用沙箱可执行：`make docker-sandbox-up` 或 `docker compose --profile python-sandbox up -d`。

通达信数据由后端内置的统一 `tdxhub` 提供商（基于 `tdxhub-sdk`）直连获取，无独立 sidecar，全面整合行情、指数 K 线与 F10 资料。如端口冲突，可在 `.env` 中设置 `DOCKER_FRONTEND_PORT=8081`，再访问对应端口。

#### Docker Hub 自动发布

仓库内置 GitHub Actions 工作流 [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml)：push 到 `main`、推送 `v*` 版本标签或手动触发时，自动构建并发布镜像到 Docker Hub（PR 只构建验证、不推送）。

- 产物镜像（默认命名空间 `fengliu1989`）：
  - `fengliu1989/a-share-backend`
  - `fengliu1989/a-share-frontend`
  - `fengliu1989/a-share-python-runner`
  - `fengliu1989/a-share-python-sandbox`
- 标签策略：`main` 分支发布 `:main` 与 `:sha-xxxxxxx`；语义版本发布 `:vX.Y.Z`、`:release-vX.Y.Z-sha-xxxxxxx`。
- 启用前在 GitHub 仓库 Settings → Secrets and variables → Actions 配置 `DOCKERHUB_USERNAME`（Docker Hub 用户名）与 `DOCKERHUB_TOKEN`（Hub 访问令牌）。
- 镜像构建 `linux/amd64`；服务器可直接 `docker compose up -d` 自动拉取已发布镜像启动，也可以执行 `docker compose up -d --build` 进行本地源码构建。

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

`backend` 和 `frontend` 默认使用只读根文件系统、删除 Linux capabilities 并启用 `no-new-privileges`，Nginx 以非 root 用户运行；`data/` 和 `logs/` 是后端显式可写卷，临时文件写入受限 `tmpfs`。容器重建后持久化数据不会丢失，服务异常退出后会自动重启，日志按单文件 10 MB、最多 3 个文件轮转。当前不支持多 Uvicorn Worker 或多 Backend 副本；这需要先将进程内缓存、限流和任务所有权迁移到共享基础设施。代码更新后重新构建，BuildKit 会复用 uv 和 npm 下载缓存：

```bash
docker compose up -d --build
```

#### Docker 数据备份与恢复

后端默认每天使用 SQLite 在线备份 API 将三个数据库（market/user/industry）备份到 `data/backups/`，写入后执行 `quick_check` 并生成 SHA-256 校验文件，每个数据库保留最近 7 份。可通过 `DATABASE_BACKUP_ENABLED`、`DATABASE_BACKUP_INTERVAL_SECONDS` 和 `DATABASE_BACKUP_RETENTION_COUNT` 调整。生产环境可设置 `DATABASE_BACKUP_DIR` 使用独立备份盘，并设置 `DATABASE_BACKUP_MIRROR_DIR` 将验证通过的备份同步到另一个已挂载的可写目录；使用 Compose 时需在 override 文件中显式挂载这两个目录。

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
docker compose run --rm --no-deps backend \
  python -m app.scripts.restore_database_backup industry \
  /app/data/backups/industry-YYYYMMDDTHHMMSSZ.sqlite3 \
  --confirm-backend-stopped
docker compose up -d
```

### 行业数据库与种子

`backend/data/db/industry_data.db` 是运行时可写的行业库（申万行业分类、个股概念映射、个股基础资料），**不提交进 git**。仓库在 `backend/seeds/` 携带一份可 diff 的压缩 CSV 种子（约 0.5 MB），首次启动 `init_db()` 时对空表自动播种；种子陈旧不影响线上数据——行业映射在"从未在线刷新成功"的库上自动走在线优先，小时级刷新成功后回到纯库路径。

```bash
make backend-db-init        # 初始化数据库并应用结构迁移（空行业库自动播种）
make backend-seeds-drift    # 只读对比运行库与种子快照的差异
make backend-export-seeds   # 将当前库状态固化为新种子（提交前执行）
make backend-seed-hot-stocks  # 为成交额前 50 的热门股抓取经营信息入库（TOP=100 可调）
```

热门股经营信息是仓库内置的起始种子：`backend-seed-hot-stocks` 复用潜力股候选池口径（剔除 ST/退市/次新/低成交后按成交额取头部），逐只从同花顺/东方财富抓取主营业务、经营范围、产品与公司工商信息入库，使新部署的空库天然带有头部公司的经营画像。

种子应视为资料库的"存档点"：批量导入或人工整理后，确认无误再执行 `backend-export-seeds` 并提交。程序不会自动更新种子，避免运行时数据灌入提交历史。

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
# 单次网络读写等待上限；总生成时限另行控制
LLM_TIMEOUT_SECONDS=300
# 普通结构化生成/资讯解读总时限，包含排队、退避和 JSON 修复
LLM_GENERATION_TIMEOUT_SECONDS=1200
LLM_GENERATION_MAX_COMPLETION_TOKENS=8192
# 含首次请求，最多 3 次；SDK 重试关闭，由共用调用层控制
LLM_MAX_ATTEMPTS=2
# 可选：按实际模型/网关限制设置输出上限（含推理 token），未设置时不猜测
# LLM_MODEL_MAX_COMPLETION_TOKENS=4096
# 不支持这些可选参数的网关可显式关闭；不会自动重放请求来探测协议
LLM_STREAM_INCLUDE_USAGE=true
LLM_JSON_MODE_ENABLED=true
# 按网关/具体模型覆盖兼容能力，规则示例见下文
LLM_COMPATIBILITY_OVERRIDES=[]
# 个股/产业链报告总生成时限（含 JSON 修复）与输出预算
ANALYSIS_LLM_TIMEOUT_SECONDS=1200
ANALYSIS_LLM_MAX_COMPLETION_TOKENS=32768
# 前置 Agent 调研独立总时限，覆盖所有轮次、追问和工具等待
AGENT_RESEARCH_TIMEOUT_SECONDS=1200

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

### LLM 调用链治理

- 个股/产业链报告、每日复盘、量化策略生成、新闻/Twitter 解读默认使用异步流式收集；Chat/Agent 共用同一限流、参数适配、重试与指标层。Agent 调研优先流式；工具协议不支持流式的模型及已有非流式调用仍受共用总时限约束。
- `LLM_MAX_ATTEMPTS` 是传输尝试总数，默认 2。仅对临时连接失败、408/409/429/5xx 在**尚未收到流式帧**时重试；收到角色、推理或正文任一帧后不再自动重放。超时、鉴权/参数错误不自动重试。OpenAI/LiteLLM SDK 隐式重试均关闭。
- 排队、退避和 JSON 修复计入生成总预算；超时/取消会关闭活动流、释放并发槽位（有界连接清理可能带来少量额外耗时）。报告要求正常结束且通过结构校验，不把截断内容存成成功报告。Chat 可保留部分正文并提示不完整。
- Reviewer 不再因已耗尽的模型调用错误重跑 Agent；持久化 Workflow 遇到模型错误直接终止，避免多层重试相乘。业务/工具证据补齐与其他非模型故障保留原有有界重试。各阶段预算独立，1200 秒报告预算**不等于**包含前置取数和调研的整条工作流时限。
- 参数适配使用下述网关/模型兼容策略；Agent 工具决策、流式/非流式调用、同步兼容客户端共用同一份解析结果。不同模型/网关的输出容量与协议并不相同，不能仅换模型名称就假设全部能力兼容。
- 为兼容外部调用方保留显式同步客户端注入；这条 legacy 路径的 Python 工作线程无法强制中止，不属于默认业务生成路径。

不配置 API Key 仍可浏览行情和数据页面，AI 分析能力不可用。

模型、密钥及页面列出的集成配置可在前端设置页面（`/settings`）动态修改。上述超时、重试、输出上限和协议开关属于部署配置，修改 `.env` 后需重启后端。每个账号还可在「Skill 与 Agent」卡片中独立关闭 Chat Skill 或专业 Agent；关闭 Skill 会同步限制关联工具，关闭 Agent 后它不再参与多 Agent 路由。新能力默认启用。

### 按模型和网关配置兼容策略

`LLM_COMPATIBILITY_OVERRIDES` 是部署级 JSON 数组（默认 `[]`），不通过个人设置页编辑。修改 `.env` 后重启后端生效；不会更换模型、改写请求地址、自动探测或失败后偷偷切模型。

**匹配与优先级**：

1. 以实际路由的 `provider` + `base_url` 为必选条件；可选 `model`、`api_mode`、`api_version` 必须精确匹配。`api_mode` 匹配 `auto` 解析后的 `openai` / `litellm`。省略 `model` 表示该网关默认规则，不支持通配符。
2. URL 只规范化协议/主机大小写、默认端口、末尾 `/`；路径大小写、路径、查询串均参与匹配。不会把 `api.example.com.evil` 当作 `api.example.com`，也不会把不同租户路径或查询串当作同一网关。URL 不能包含用户密码或片段；配置中不要放密钥。
3. **内置默认 → 网关规则 → 具体模型规则**，逐字段覆盖。模型规则优先于网关规则；同一层中指定更多 `api_mode` / `api_version` 的规则优先；同等精度按数组中靠后的规则覆盖。省略或 `null` 字段表示继承。
4. 全局 `LLM_JSON_MODE_ENABLED=false` / `LLM_STREAM_INCLUDE_USAGE=false` 仍是硬关闭；输出预算取业务请求、目标规则 `max_completion_tokens`、全局 `LLM_MODEL_MAX_COMPLETION_TOKENS` 中已配置值的最小值。目标规则不能放宽部署安全上限。
5. 客户端缓存键包含不可变的最终能力快照；改变生效策略会使用不同客户端，无关规则不会造成缓存分裂。已创建的客户端不允许通过请求参数切换到另一个模型；需要为新目标创建客户端，避免复用旧策略。
6. 两种 token 字段同时传入时始终取较小值；显式 `null` 不会取消默认预算，只有未提供任何有效预算时才使用业务默认值。非正整数（包括布尔值、字符串、小数）在发请求前报配置错误，不静默修正。
7. `extra_body` 仅用于厂商扩展字段，不能覆盖 `model`、`messages`、`stream`、两种 token 参数、temperature、JSON / usage / 工具参数。这些字段必须放在顶层接受统一治理；否则请求在本地失败，不会进入 SDK 重试。其他厂商扩展字段保持原样，不代表应用已验证其能力。
8. 网关地址拒绝控制字符、内部空白、反斜杠和片段，避免 URL 解析器静默清洗后误命中策略。配置校验异常的文本不展示输入值；客户端规格的 `repr` 不展示 API Key 和网关地址。结构化异常仍应按日志安全规范处理，不直接记录原始配置。

例如，网关不接受 usage 参数，但其中某个**已确认实际能力**的别名只接受 `max_tokens`，可在 `.env` 中写单行 JSON：

```dotenv
LLM_COMPATIBILITY_OVERRIDES='[{"provider":"custom","base_url":"https://gateway.example.com/team-a/v1","stream_include_usage":false},{"provider":"custom","base_url":"https://gateway.example.com/team-a/v1","api_mode":"openai","model":"my-model-alias","token_parameter":"max_tokens","supports_temperature":true,"json_mode":false,"max_completion_tokens":4096,"streaming_tool_calls":false}]'
```

这里 `4096` 仅为示例部署限制，不是任意模型的容量声明。换网关、路径、别名后不会继承这条模型规则；必须按该目标实际支持情况配置。

| 策略字段 | 行为 |
| --- | --- |
| `token_parameter` / `max_completion_tokens` | 选择 `max_tokens` 或 `max_completion_tokens`，只发送一个字段并限制输出预算 |
| `supports_temperature` | 为 `false` 时不发送 temperature |
| `json_mode` | 为 `false` 时不发送 `json_object` response_format；提示词和本地 JSON/结构校验仍保留 |
| `supports_strict_json_schema` | 默认不声明支持；请求严格 schema 而目标不支持时明确报配置错误，不静默弱化 |
| `stream_include_usage` | 为 `false` 时不发送 stream_options；非流式调用也不发送该字段 |
| `native_tool_calling` / `streaming_tool_calls` | 控制原生工具和流式工具能力；Agent 在请求前选择非流式工具轮次，绕过 Agent 强行发送不支持的协议会明确报错 |
| `parallel_tool_calls` | 控制工具并行能力；禁用时移除同名请求参数并串行执行本地工具 |
| `supports_tool_choice_none` / `supports_tool_choice_required` | 不支持 none 时直接移除工具；不支持 required 时用 auto，业务层仍校验工具证据 |
| `supports_named_tool_choice` | 不支持强制指定工具时明确报错，不静默改成可能调用其他工具的 auto |
| `replay_tool_reasoning` | 仅为需要此协议的目标启用；Agent 工具轮次在后续上下文原样回传模型返回的 reasoning_content，默认关闭，不添加额外日志或持久化 |

**内置策略的边界**：

- 保留现有 `o1` / `o3` / `o4` / `gpt-5` 名称前缀的参数提示：`max_completion_tokens`、不发送 temperature；这是向后兼容的默认提示，不是对任意代理别名的能力保证，可以用具体规则反向覆盖。官方字段定义见 [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。
- DeepSeek 官方目录地址 `https://api.deepseek.com`、OpenAI 模式下的精确名称 `deepseek-flash` / `deepseek-v4-pro` 按当前[思考模式文档](https://api-docs.deepseek.com/guides/thinking_mode)和[接口文档](https://api-docs.deepseek.com/api/create-chat-completion)处理：不发送 temperature、不使用 required / named 强制工具选择、工具轮次回传 reasoning_content，使用 `max_tokens`。这不代表其他旧别名、镜像站、`/v1` 路由或第三方部署具有相同能力；未确认目标请显式配置，也不会因此修改现有默认模型。
- 只有精确命中内置 Provider 目录地址与 API 模式才沿用其高级工具默认值；未知/代理网关默认关闭流式工具、并行工具与强制工具选择。基础原生工具、JSON、usage 保留既有尝试行为，**不代表已验证支持**，可通过规则关闭。没有从模型名称猜测输出容量。
- 验收覆盖 OpenAI SDK MockTransport、LiteLLM Mock、Agent 多轮、规则隔离和连接池刷新，不等于已经对某个付费模型/真实网关做过在线认证。

### 多 Agent 执行与降级

- 下游分析只使用有效的前置结果；前置任务失败时，不会把错误文案当作已完成分析继续执行。
- Reviewer 最多追加一轮重试，同时重算受影响的全部下游，保留未受影响的有效前置上下文。
- 任一计划维度缺失、失败或部分完成时，最终回答会明确提示覆盖限制，并标记为 `partial`；没有有效分析时标记为 `failed`。
- 工具结果重放保留原始 JSON，统一遵循 `SharedToolCache` 的有效期；过期或 `cache_ttl_seconds=0` 时不跨轮次重放，失败结果允许后续重试。空结果不视为有效证据；结构化结论仅在解析、校验成功后移除，无效块保留原文。
- 同批去重以「工具名 + 规范化 JSON 参数」为键，并受 `deduplicate_in_batch` 策略控制；允许合并的调用共享首次真实结果（包括空结果、失败和预算拒绝），保留各自调用 ID，且不重复占用预算。策略创建、发布、Python 执行等有副作用的工具禁用同批合并和跨轮缓存，逐次执行并计入预算。
- 工具上下文预算在同批结果间分配，优先完整保留短结果，避免大结果挤掉后续小结果；证据被截断或省略时明确告警并标记为 `partial`。证据要求以实际提供给模型的内容为准，未提供的原始结果不能满足证据要求；没有有效可见证据时标记为 `failed`。
- 综合输入的字符预算包含结构化结论指引、覆盖限制、用户问题和专业分析；截断时优先保留高风险否决约束。
- 单 Agent 与综合阶段统一判断结束原因：有正文但长度截断、内容过滤、流中断或其他显式异常结束时标记为 `partial`；单 Agent 无有效正文时标记为 `failed`。综合输出为空或仅含空白时回退到各维度原始分析，综合阶段告警优先于来源告警展示。
- Agent 执行和综合阶段会显式关闭模型响应流；正常结束、异常、取消、提前关闭及重试前均尝试释放 Provider 连接，清理失败不覆盖原始请求错误。外层 Chat、编排器与 Agent 包装流逐层显式关闭子流，在释放模型运行时和并发额度之前等待下层任务清理，覆盖事件队列背压时的取消。

### 聊天中的思考与执行过程

- 回答上方展示可折叠的过程面板：包含规划步骤、实时进度、工具调用及服务端提供的结构化调研轮次（目标、证据缺口、工具选择依据、新增证据、判断依据、阶段结论、下一步）。独立的「模型推理」区域展示模型接口实际返回的 `reasoning_content`；接口未返回时不展示、不补造，也不尝试提取接口未提供的内部内容。
- 生成时默认展开，完成后默认收起；手动展开或收起后尊重用户选择。停止、失败和部分完成分别提示，避免把异常显示为成功。
- 推理增量实时追加；流式与非流式输出都按独立片段展示来源、模型轮次和重试次数，并关联任务标识；不同调用不会拼成同一段。最后一轮的完成快照不会覆盖之前各轮推理；仅在未收到增量时作为兜底。推理以纯文本渲染，不执行其中的 HTML；报告/调研接口仍默认过滤推理。
- 模型推理和公开进度随聊天会话保存，可在历史消息中展开回看，不进入下一轮模型对话上下文。相邻重复进度合并，每条消息最多保留最近 60 条过程记录；本地或远端快照超出预算时优先裁剪推理与过程记录，尽量保留答案，不修改当前页面的完整内容。推理分段使用文本偏移量保存，避免重复存储正文。
- 流式响应必须收到模型结束标记才算完整；正常 EOF 但缺少结束标记时标记为不完整，保留已返回正文，不执行残缺流中的工具调用。
- 会话同步失败会保留按账号隔离的本地快照和待同步标记。刷新时，远端版本未变化会重试；发生版本冲突则保留本地与远端两份内容、显示「本地缓存模式」，不自动覆盖任一版本（暂不自动合并冲突）。

### 安全网页抓取

AI 聊天助手通过受控 HTTP 传输抓取公开 URL：域名的全部解析结果必须是公网地址，实际连接固定到已校验 IP，并在每一跳重定向时重新解析、校验和固定目标；HTTPS 仍使用原始域名执行 SNI 和证书校验。

DNS 解析在线程池中执行，并与连接及重定向共享同一个请求截止时间。响应体采用流式读取，默认最多保留 20 MiB（可通过 `WEB_FETCH_MAX_RESPONSE_BYTES` 调整，范围 64 KiB ~ 100 MiB），同时检查声明大小和解压后的实际大小。

`web_fetch` / `fetch_urls` 支持 `auto`、`http`、`stealth`、`dynamic` 四种模式。单网页抓取工具已全面规范为 `web_fetch`；批量并发抓取为 `fetch_urls`（前端呈现为「批量网页正文」）。`auto` 先使用固定 IP HTTP，失败或正文不足时依次尝试 stealth 和 dynamic。浏览器运行在后端主进程中并直接联网，以保持与旧版 Scrapling 行为一致；浏览器模式只校验初始 URL 为 HTTP(S)，不会对重定向、iframe、XHR 或子资源执行私网/DNS Rebinding 防护。

首次安装由 `./setup.sh` 自动安装 Patchright Chromium；也可以手动执行：

```bash
make backend-sync
make backend-browser-install
```

浏览器模式由 `WEB_FETCH_BROWSER_ENABLED` 控制，默认总超时 60 秒；dynamic 等待 DOMContentLoaded 后再稳定 5 秒（`WEB_FETCH_BROWSER_SETTLE_SECONDS`），不等待尾部统计资源触发完整 load；stealth/dynamic 在进程内共享并发上限（`WEB_FETCH_BROWSER_MAX_CONCURRENCY`，默认 2）。主进程方案不能隔离 Chromium 漏洞带来的进程权限风险，面向不可信公网长期运行时仍建议使用独立容器。

#### AI 工具执行安全

- `read_pdf` 仅接受 http/https 在线链接或应用数据目录内的本地 `.pdf` 文件（本地路径越界一律拒绝），避免 Agent 被诱导读取服务器任意文件。 在线下载遇到已识别的 JavaScript 访问验证页时，会在启用 `WEB_FETCH_BROWSER_ENABLED` 的前提下使用安全浏览器重试；沿用浏览器并发、DNS 校验和响应大小限制，浏览器阶段使用配置的超时且最多 30 秒（含排队）。验证失败、浏览器未启用或链接未返回 PDF 时会显示对应原因。
- Python 计算沙盒（`python_interpreter`）**仅管理员可用**：代码先经正则黑名单与 AST 白名单双重静态检查（仅允许科学计算模块导入、禁止一切 dunder 访问与 eval/exec/getattr 等逃生舱），再在隔离子进程中以最小环境（不继承 API Key 等机密）、一次性临时目录、内存/CPU/文件写入资源限制和 1 MB 输出上限运行。
- 已知残余风险：预置的 pandas/numpy 本身具备文件读取能力，无法在静态层区分；面向不可信用户长期运行时，与浏览器抓取一样建议容器隔离。

### 统一数据提供商架构（Data Provider Gateway）

系统内所有金融市场数据、宏观数据和外部检索均全面收敛至 `app.infrastructure.providers`，由统一的 `provider_gateway.call(provider, method, *args, **kwargs)` 进行调度，消除了散落各业务模块的直接外部网络请求：

- **统一治理与稳定性**：
  - **并发控制**：各 Provider 配置独立信号量隔离（如 `tdxhub_semaphore`、`eastmoney_semaphore`、`sina_semaphore`、`misc_semaphore`），防止单数据源阻塞冲击全系统。
  - **自适应熔断（Circuit Breaker）**：连续失败触发熔断阈值后自动阻断请求，冷却后发起半开探测，防止上游故障蔓延。
  - **多源平滑降级（Fallback）**：主数据源不可用时自动按优先级切换备选源（例如行情在 东方财富 ↔ 新浪 ↔ TDX 间自动互备）。
  - **运行指标追踪（Metrics）**：请求耗时、成功率、降级频次实时计入监控指标。
- **Provider 合并与标准化**：
  - **通达信统一归一化**：彻底合并原先分散的 `tdx` 与 `tdxhub` 模块，收敛为统一的 `tdxhub` 提供商（`TdxhubDataProvider`，基于 `tdxhub-sdk`），单一入口完整承接实时分笔、日/周/月 K 线、指数历史 K 线（`fetch_index_kline`）与 F10 财务基本面资料。
  - **标准化品种覆盖**：`akshare`（宏观与行业）、`eastmoney`（行情/异动/龙虎榜）、`sina`（行情/期货/财务构成）、`exchange`（沪深北交易所名录）、`exchange_etf`（ETF 份额与资金）、`sge`（上海黄金交易所现货行情）、`web_search`（公开网页搜索）与 `legulegu` 等均注册为标准 Provider。

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

账号 API 测试使用每例独立的临时 SQLite 数据库，禁止对开发/运行数据库清表或重建管理员。新增持久化测试必须先隔离数据库路径及线程连接缓存，再初始化测试数据；密码重置应保留用户 ID 和个人 AI 配置。

完整前端验证使用 Node.js 22。Playwright 首次运行前需在 `frontend/` 执行 `npx playwright install chromium`。

后端固定使用 `tdxhub-sdk==0.3.0`，通过 SDK 原生 `quotes()` 统一获取沪深京实时行情（含北交所 `920` 及原 `43/83/87` 代码段），由 SDK 负责去重与每批最多 80 条的分块请求，不再依赖 `tdxpy` 或应用层北交所协议绕行。数据提供商契约测试与统一网关回归测试：
```bash
cd backend
uv sync --frozen
# 运行 Provider 统一网关与合约单测（无需外网）
uv run --frozen pytest tests/infrastructure/providers/ -q
# 联网冒烟测试（默认跳过，显式启用后直连 TDX 行情服务器，不走降级）
TDXHUB_LIVE=1 uv run --frozen pytest tests/infrastructure/providers/test_tdxhub_live.py -v -s
```

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

### 管理员密码忘记 / 账号救援（无损保留用户与数据）

如果忘记了管理员密码，**无需清空任何用户数据**，直接在服务器或容器中运行密码重置命令行脚本：

```bash
# 宿主机 / 本地开发环境：
make backend-reset-admin                                        # 自动重置并随机生成高强度密码
make backend-reset-admin ADMIN=admin PASS="YourNewPassword123"  # 指定账号与新密码

# 或直接调用 Python 脚本：
cd backend && uv run python scripts/reset_admin_password.py [用户名] [--password "新密码"]

# Docker 容器环境下执行：
docker compose exec backend python scripts/reset_admin_password.py [用户名] [--password "新密码"]
```

> **效果**：
> - 仅更新指定的已有账号（默认 `admin`），**UID 保持不变，AI 配置、聊天记录与业务数据保留**；
> - 账号不存在时直接报错，不创建新账号，也不自动替换为其他管理员；成功后输出原 UID 供核对；
> - 若账号被停用将自动解除禁用恢复正常；
> - 自动注销该管理员的所有历史在线会话，重置后即可立即使用新密码登录。

### 重置全部账号（重置数据库 / 重新开始）

想清空全部账号重新初始化时，可一键重置（**仅清空账号相关表，不影响行情缓存等其它数据**）：

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

个股分析提供结构化长期投资研究：盈利引擎、护城河与反证、管理层与资本配置、行业与价值链、反向风险、估值情景、角色化行动条件以及待核验的数据缺口。

- A/B/C 表示公开信息的完备程度，不是股票或公司质量评级。
- “证据可信度”衡量数据覆盖、时效和一致性；“投资确定性”衡量商业模式与结果区间的可预测性，两者不会合并成一个分数。
- 技术面和情绪面仅作为短期择时参考，不替代长期商业质量判断。
- 旧版历史快照不会被自动补写；重新运行分析后才会产生新版结构化研究。
- 方法设计受 [xbtlin/ai-berkshire](https://github.com/xbtlin/ai-berkshire) 的公开投资研究框架启发，本项目采用独立的数据契约和实现。

## 免责声明

本系统仅供学习和研究使用，不构成任何投资建议或收益承诺。AI 分析结果基于公开数据和模型推理，不保证准确性、完整性或时效性；信息完备度与模型置信度也不能消除市场、公司经营和估值假设的不确定性。请独立核验重要事实与假设，投资有风险，入市需谨慎。
