# 国家队监测（宽基 ETF 代理口径）

> 页面：`/national-team`　接口：`GET /api/market/national-team-etf-holdings?days=30..365&include_etf_points=true`
> 后端：`backend/app/financial_data/market/quotes/national_team.py`（采集 / 持久化 / 对外服务）
> 　　`.../national_team_aggregation.py`（纯聚合计算）、`.../national_team_definitions.py`（静态名单与画像）
> 前端：`frontend/src/pages/NationalTeam/`

## 1. 口径：为什么叫「代理指标」

中央汇金、证金、社保的真实持仓只在定期报告里披露，且滞后一个季度以上。本页面测的是
**核心宽基 ETF 的份额变化**，把它当作国家队资金行为的代理信号：

```
单只 ETF 某日净申购(亿元) = (当日份额 - 前一交易日份额) / 1e8 × 当日 ETF 收盘价
某宽基 某日净申购(亿元)   = 该宽基下所有 ETF 当日净申购之和
```

因此 ETF 份额变动**不等于**中央汇金持仓变动：申购赎回可能来自公募、私募、保险、
券商自营或个人投资者。页面顶部与底部均展示 `disclaimer` 与 `methodology`，删掉它们
会让用户误读数据，不要为了版面删。

## 2. 数据来源与刷新

| 数据 | 来源 | 说明 |
| --- | --- | --- |
| 上交所 ETF 份额历史 | 上交所官方接口 | 逐日回填，单次最多补 4 个交易日 |
| 深交所 ETF 份额历史 | 深交所官方接口 | 按 ≤7 自然日窗口回填，单次最多 8 个窗口 |
| 当日份额快照 | 深交所直连 → 东方财富备选 | 无业务日期，只作为 `observations` 观察值 |
| ETF / 指数日 K | 腾讯财经 → `get_kline` / `get_index_kline` | 收盘价与成交额 |
| 交易日历 | 内部交易日历服务 | 失败时置 `calendar_degraded=True` |

落库位置：`market_data.db` 的 `national_team_etf_shares`、`national_team_etf_backfill_state`、
`national_team_etf_observations`（见 `app/infrastructure/persistence/national_team_etf_store.py`）。

缓存分三层：

1. `_source_cache`：单次上游响应，TTL 60s，按 `scope:key` 隔离；
2. `market_cache`：完整响应，`partial` 时 60s、否则 900s，键含 `days` 与交易日窗口；
3. `_stale_responses`：最近一次成功响应，TTL 1h，用于「旧数据 + 后台刷新」返回。

前端另有 React Query 层：`staleTime` 10 分钟，`partial`/`refreshing` 时 60s 轮询，
切换时间窗使用 `keepPreviousData` 保留上一份结果（不闪骨架屏）。

启动预热任务：`national_team_price_prewarm`（`app/runtime/lifecycle.py`），只预热行情
日 K，成功与否不影响启动。

### 2.1 收盘后自动刷新

`national_team_snapshot_refresh`（`app/runtime/background_tasks.py`）每 5 分钟轮询一次，
但**只在 16:00–18:00 窗口内、交易日、且当日尚未完成时**才真正采集：

- 轮询本身几乎零成本（与 `/ready` 同级的常数检查），真正的上游请求次数与「用户恰好
  在收盘后打开页面」时一致，但把冷启动成本从首个访客挤到了后台；
- 判定「完成」看的是 `as_of_date == 当日 且 not partial`。交易所份额发布常晚于 16:00，
  若只看「跑过一次」就标记完成，当天永远不会再补；
- 18:00 后不再尝试，避免非交易日/节假日全天反复请求上游；
- `leader_election=True`：多副本只让 leader 刷，不会 N 倍打上游。
- **不接入 readiness**：它挂了不影响 HTTP 请求，接了会让一次行情抖动摘掉流量。

### 2.2 Prometheus 指标

`national_team_snapshot()`（`app/runtime/health.py` → `application_metrics["national_team"]`
→ `app/core/prometheus.py`）导出：

| 指标 | 含义 |
| --- | --- |
| `a_share_national_team_refresh_attempts_total` | 采集次数（含定时/请求触发） |
| `a_share_national_team_refresh_failures_total` | 采集失败次数（取消不计） |
| `a_share_national_team_refresh_duration_milliseconds` | 最近一次采集耗时 |
| `a_share_national_team_coverage_ratio` | 最近一次成功的 ETF 覆盖率 |
| `a_share_national_team_partial` / `_stale` | 最近一次结果是否不完整 / 陈旧 |
| `a_share_national_team_covered_etfs` / `_total_etfs` | 覆盖数 / 池内总数 |
| `a_share_national_team_last_success_timestamp_seconds` | 最近一次成功时间 |
| `a_share_national_team_refresh_by_trigger_{attempts,failures}_total{trigger}` | 按触发源（`request`/`scheduled`）拆分 |
| `a_share_national_team_source_failures_total{scope}` | 按数据源（`sse`/`szse_history`/…）拆分的失败数 |

`last_error` 只存**异常类名**，不带消息：上游报错文本里常有 URL 与请求参数，
不能进 `/metrics`。

告警示例：

```promql
# 覆盖率持续偏低：多数 ETF 份额没抓到，页面结论会失真
(a_share_national_team_coverage_ratio < 0.8)
  and on() (a_share_national_team_refresh_attempts_total > 0)

# 持续刷新失败
increase(a_share_national_team_refresh_failures_total[30m]) > 3

# 某个数据源变砖（与 provider 指标一起吃，能定位到具体源）
increase(a_share_national_team_source_failures_total{scope="szse_history"}[1h]) > 5
```

**注意**：定时刷新失败**不会**体现在
`a_share_background_task_consecutive_errors{task="national_team_snapshot_refresh"}` 上。
轮询循环刻意不抛异常（否则一次上游抖动就会被 supervisor 重启），因此任务健康度
恒为健康，真正的失败信号只在上面这三个国家队专属计数里。

## 3. 覆盖率与「部分数据」

份额缺失是常态（某只 ETF 当日未披露、深交所窗口未回填完、新 ETF 首日无前值）。
早期实现用「全交集 + 全有或全无」聚合，一只 ETF 缺一天就会让整条指数当天消失、
所有 KPI 变成 `-`。现在的规则：

### 3.1 指数序列（`_build_index_series`）

- 按**当日实际有数据的成员**聚合，不再取所有成员的日期交集；
- 每个点位带 `covered_etf_count` / `total_etf_count` / `coverage_ratio`；
- 覆盖率低于 `_INDEX_MIN_COVERAGE`（0.5）时不生成该日点位，避免用一两只 ETF
  冒充整条指数；
- `change_5d_100m` / `change_20d_100m` 由**逐日份额变化累加**得到
  （`_index_period_change`），不是「期末总份额 − 期初总份额」——后者会把新 ETF
  上市带来的成员扩容误算成资金流入。

### 3.2 汇总（`build_national_team_response`）

- 各项 KPI 用 `_sum_or_none` 对**可用值**求和，单个缺失不再把整体拖成 `None`；
- `NationalTeamSummary.coverage_ratio` = 截至日有份额数据的 ETF 数 / 池内 ETF 总数；
- `NationalTeamSummary.quality`：`complete`（全覆盖）/ `partial`（部分）/ `insufficient`（无数据），
  前端在「ETF 总份额」卡片上以 `数据完整 / 部分覆盖 / 数据不足` 展示。

> **保持诚实**：覆盖率只描述「截至日有份额的 ETF 比例」，不逐项追踪每个 KPI 自己的
> 样本完整度。某个 KPI 仍可能是 `-`（例如窗口内缺基线日），此时 `-` 表示「无法计算」，
> **不代表零变化**。

### 3.3 响应级标志

| 字段 | 含义 |
| --- | --- |
| `partial` | 任一 ETF 份额/行情缺失、指数缺失、`stale` 或 `calendar_degraded` |
| `stale` | 份额截至日 < 预期交易日 |
| `refreshing` | 有后台刷新任务在跑 |
| `calendar_degraded` | 交易日历不可用，新鲜度无法确认 |
| `missing_share_etfs` / `missing_price_etfs` / `missing_indices` | 具体缺口 |
| `observations` | 无业务日期的当前份额，**不进**历史与资金估算 |

## 4. 派生指标

### 4.1 托底强度指数（`_calculate_support_score`，0–100）

| 因子 | 满分 | 依据 |
| --- | --- | --- |
| 资金托底 | 40 | 1 日 / 5 日估算净申购分档 |
| 板块扩散 | 30 | 当日为正净申购的战术分类占比 |
| 逆势抗跌 | 30 | 沪深300 当日涨跌 × 净申购方向的组合 |

分档阈值是**固定经验值**，未按牛熊阶段校准。它只适合做横向对比与变化方向提示，
不适合当成绝对「救市力度」读数。要改成滚动分位数需要先攒够至少一年的
`daily_flows` 历史，属于后续工作。

分数旁边还有一个**置信度**（`confidence`，0–1）：

```
confidence = 覆盖率 × 新鲜度 × 日历可用性
           = (populated / ETF_POOL) × (stale ? 0.35 : 1) × (calendar_degraded ? 0.7 : 1)
```

分数本身**不因低置信度打折**（否则同一盘面会随覆盖率忽高忽低），低置信度由前端
用「置信度 xx%」标签与 tooltip 提示。低于 50% 时文案直接写「请勿据此单独决策」。

### 4.1 评分历史

`support_score_history` 用「当天及以前」的切片逐日重跑同一套因子，不额外落库：

- 每天都能看见 5 日资金与沪深300 两日涨跌随时间移动，而不是把今天的分数向前填充；
- 最新一天的历史分必须与实时 `support_score` 完全一致，已有测试卡死；
- 没有任何成员数据、也没有可归因资金流的日子会跳过，避免伪造 0 分；
- 前端在托底雷达卡底部画近 30 个交易日的 sparkline，并显示区间变化。

评分同时带 `percentile_60d`：当前分数在最近 60 个交易日中的分位（0–100）。
只有真正覆盖 60 个交易日时才返回，否则为 null；它**不改评分阈值**，只回答
“这个分数放在近期算高还是低”。

历史分只用于看趋势。要做「信号出现后 5/20 日表现」的后验回测，还需要把每日评分
持久化，否则受 `days` 参数与上游数据回溯修正影响。

### 4.2 评分持久化与后验回测

每次成功采集时，把 `support_score_history` 与当日沪深300 收盘写入
`national_team_support_scores`（`market_data.db`，一个交易日一行）。这样：

- 首次采集就把当前窗口内历史补齐，不用等几个月才开始积累；
- 超出详情接口窗口的评分会继续保留（每个交易日一行，长期累积体积也可忽略）；
- `GET /api/market/national-team/backtest?days=30..1095` 读取落库评分，计算信号后
  第 5 / 20 个有收盘的交易日的沪深300 涨跌、胜率、中位数与极值，并按信号强度分组；
- 置信度低于 50% 或成员覆盖率低于 50% 的评分不会进入回测，响应里的
  `excluded_low_confidence` / `excluded_low_coverage` 会说明剔除了多少样本；
  `first_sample_date` / `last_sample_date` 给出实际参与统计的日期范围；
- 前端在托底雷达卡底部显示「信号后表现 5 日 / 20 日」，样本不足时后端返回说明。

`window_samples` 表示回看的评分快照数量（每个交易日一条），不是自然日；接口参数
仍叫 `days` 以保持兼容。

写入失败只记 warning，不影响采集主流程——历史评分是增强信息，不是页面成败的前提。
写入通过 `asyncio.wait_for(..., timeout=2)` 限时，DB 锁竞争时宁可放弃本次落库，也不
把采集响应一起拖住；落库成功后按 `national_team_backtest:` 前缀失效回测缓存，
新样本不会拖到 TTL 到期才生效。
注意：回测衡量的是「托底信号出现后指数怎么走」，不是「跟着信号交易能赚多少」，
未计交易成本、滑点与仓位。

### 4.2 托底点位分布（`_calculate_support_zones`）

对 `csi300` / `sz50` / `csi_a500` 把「当日正净申购」按指数收盘价分箱，输出
`weighted_avg_cost`（按净申购加权的成本中枢）与各价格区间占比。区间**按价格下界升序**
输出（`<X` 在最前，`≥X` 在最后），前端据此从低到高渲染进度条。

### 4.3 静态参考数据

`NATIONAL_TEAM_MILESTONES`（历次救市节点）与 `DEFAULT_NATIONAL_TEAM_PORTRAIT`
（汇金/证金/社保底仓画像）是**人工整理的静态内容**，不随行情更新：

- `portrait.as_of = "2024-12-31"`、`portrait.source` 说明静态整理口径、`portrait.is_static = true`；
- 前端在画像面板顶部渲染「静态参考 · 截至 2024-12-31」徽标与来源；
- 更新时改这两处常量并同步 `as_of`，否则页面上会出现「2024 年的数据看起来像今天的结论」。

## 5. 安全约定

- **CSV 导出**统一走 `plugins/…/utils/csv.ts` 的 `escapeCsvCell` / `downloadCsv`：
  以 `= + - @` 开头的非数值单元格加 `'` 前缀防 Excel 公式注入；负数与带单位金额
  （`-3.25`、`-12.30 亿元`）保持原样，不能为了防注入把负号也转义掉。
- **ECharts tooltip** 是 `formatter` 拼 HTML 字符串，所有动态文本必须过
  `utils/html.ts` 的 `escapeHtml`（序列名、日期、里程碑标题与描述）。

## 6. 前端结构与子 Tab 体系

```
pages/NationalTeam/
  index.tsx                         页面编排：状态、筛选、子 Tab 导航与布局
  components/MacroFlowChart.tsx      全市场宏观资金走势图（净流入+累计双轴 / 成交额双轴 / 板块堆叠）
  components/FlowHeatmapTable.tsx    近一个月宽基 ETF 每日净流入热力矩阵表（日期 × 宽基类别）
  components/NationalTeamIntradayMonitor.tsx 盘中高频分钟量能脉冲、全天累计对比、典型放量日基准对照与百亿护盘日直方
  components/NationalTeamReportModal.tsx 资金监测全景研判简报与高清长图导出
  components/LazyChart.tsx           进入视口才挂载 ECharts（首屏与 Tab 切换性能控制）
  utils/csv.ts                       CSV 转义与下载
  utils/html.ts                      tooltip 文本转义
  national-team.css                  页面样式
```

### 6.1 五大子 Tab 场景架构

为避免单页垂直高度过长造成认知负担，页面拆分为 5 个职责清晰的子 Tab（通过 URL 参数 `tab=` 维护可回退路由）：

1. **📊 资金流向看板 (`tab=flow`，默认)**：
   - 数据质量与状态监控控制台 `NationalTeamDataStatusPanel`（展示数据更新时间、数据源分层、100%覆盖率、延迟与降级状态自检，支持折叠查看计算口径说明）；
   - 异动预警横幅 `NationalTeamAnomalyBanner`（监测 1.8x 异常放量、指数下跌资金净流入背离托底、连续多日净申购等信号）；
   - 附录 A 核心 KPI 卡片（ETF 总份额、样本池总成交额、1日估算净申购、区间累计净申购、份额变化）；
   - 宏观双轴大图 `MacroFlowChart`（净流入+累计走势 / 成交额趋势 / 板块细分堆叠，支持多视角切换、时间轴 DataZoom 滑块拖拽缩放与关键政策时点标注）；
   - 宽基日度资金流向热力矩阵表 `FlowHeatmapTable`（近 20~30 交易日 × 10 大核心宽基，红绿平滑热力单元格，首列冻结，支持点击交易日期**下钻单日宽基与板块明细分析**与 CSV 导出）；
   - 资金集中度与主力持续建仓透视卡 `NationalTeamConcentrationCard`（CR3/CR5 头部聚集度、主力旗舰龙头 ETF 领跑排行、各宽基连续净流入天数与近 20 日胜率）；
   - 资金快报海报模态框 `NationalTeamReportModal`（支持一键导出 PNG 资金长图海报及复制结构化研判文本）；
   - 底部规范化口径说明。
2. **⏱️ 盘中分钟观测 (`tab=intraday`)**：
   - 重点宽基 ETF 1分钟成交脉冲柱状图与上证综指分时双轴走势联动（感知盘中主力脉冲时点）；
   - 全天分钟累计成交额实时对比曲线（今日分钟累计 vs 昨日累计 vs 近20日均值走势）；
   - 救市放量日 vs 常态交易日特征对照基准（支持红/蓝基准切换，识别午后 14:00 突发放大特征）；
   - 20 大重点宽基 ETF 当日成交额与涨跌幅排行榜；
   - 历史百亿级放量护盘日（单日净申购 > 100 亿元）vs 近期交易日成交额直方标定图。
3. **🛡️ 托底信号雷达 (`tab=radar`)**：
   - 异动预警横幅 `NationalTeamAnomalyBanner`；
   - 国家队托底强度雷达卡（0-100 评分、置信度、60日分位、近30日历史走势 Sparkline、5/20日后验胜率回测）；
   - 核心指数主力成本中枢与托底点位分布（`SupportZonesCard`）；
   - 关键政策底救市里程碑标尺（`MilestoneTimelineBar`）。
4. **📈 宽基与ETF明细 (`tab=etf`)**：
   - 跨宽基结构轮动相对强弱卡（`RotationCard`，支持 1日/5日/20日 视窗切换）；
   - 10 大核心宽基走势矩阵（`IndexDualAxisChart`，支持全屏大图预览与战术分类切换）；
   - 四大战术分类概览卡 `CategoryOverviewCards`（核心大盘、新质A500、中小成长、红利防御的份额、成交额、净申购及领跑 ETF）；
   - 22 只 ETF 监测明细表格（支持一键预设快捷排序：默认/今日净买入/5日变化/成交活跃/规模份额/异动放量，搜索、宽基筛选、放量标记与 CSV 导出）。
5. **🏛️ 战略底仓全景 (`tab=portrait` 或 `view=portrait`)**：
   - 中央汇金、证金公司、社保基金底层重仓股与行业配置底牌（静态参考）。
6. **📑 全景总览 (`tab=all`)**：
   - 全模块流式展开，便于全屏投屏或综合研判。

约定：

- 图表用 `LazyChart` 包裹，占位高度必须等于真实图表高度，否则懒加载时页面会跳动；
- 未知指数名（后端新增而 `INDEX_ORDER` 未收录）排序到**末尾**，不能用
  `Array.indexOf` 的 `-1` 直接比较；
- 筛选状态（`days` / `tab` / `view` / `category` / `rotation` / `index` / `q`）全部走 URL，
  可分享、可回退；
- 有旧数据时 `refetch` 失败要**保留旧数据 + 顶部 warning**，不能整页替换成错误态。

## 7. 响应体积

单接口默认返回 22 只 ETF × 至多 365 天的完整点位序列 + 10 条指数序列 + 静态画像，
实测 120 天窗口下 JSON 约 **902 KiB**（gzip 后 29 KiB）。其中 ETF 的 `points` 占
约 **65%**：前端表格与 CSV 只用最新一天的标量。

因此接口带 `include_etf_points`（默认 `true`，向后兼容）：

- 传 `false` 时 `etfs[].points` 置空，标量字段（含
  `latest_estimated_net_flow_100m`）全保留；实测降至 **313 KiB**；
- 响应里的 `etf_points_included` 标明本次是否被裁剪，前端可据此自检；
- 裁剪位在 `without_etf_points()`，且在 **所有聚合算完之后**：`summary` /
  `daily_flows` / `support_score` / `support_zones` / 指数序列在两种模式下必须完全
  相同，已有测试卡死这一点；
- 缓存里始终存**完整**响应：若把两种模式分别缓存，容量翻倍且互相抢占。

### 7.1 轻量概览接口

首页信号卡只需要结论，不需要 22 只 ETF 与 10 条指数序列，因此另有：

```
GET /api/market/national-team/overview?days=30..365
```

只返回 `summary`、`support_score`、近 30 日 `support_score_history`、覆盖率与
新鲜度标量（`partial` / `stale` / `calendar_degraded` / `refreshing`）。它复用同一份
完整响应缓存，裁剪发生在 `build_national_team_overview()`，不额外采集数据。
首页 `/` 的「国家队托底信号」卡调用的就是它，详情页仍用完整接口。

### 7.2 指数序列单独获取

详情页首屏请求现在同时传 `include_etf_points=false&include_index_points=false`：

- ETF 点位去掉后约 313 KiB；
- 指数点位（10 条 × N 天）再占大头，两个都去掉后开发样本约 **80 KiB**（−75%）；
- 指数标量（最新份额、1/5/20 日变化、覆盖率）仍保留，表格与托底评分不需要点位；
- 10 张图改由 `GET /api/market/national-team/index-series/{index_key}?days=30..365`
  在图表进入视口后逐图拉取（`LazyChart` 同一套 IntersectionObserver 约定），
  首屏不下载任何指数点位；批量场景仍可用 `/index-series?days=` 一次取全；
- 响应里的 `index_points_included` 标明本次是否被裁剪，缓存仍只存完整一份；
- 前端同时传 `include_flow_breakdown=false`：`daily_flows[].flows_by_index` 与指数
  序列信息重复且前端未使用，关闭后只保留总量与 `flows_by_category`。

## 8. HTTP 缓存

接口返回 `ETag` 与 `Cache-Control`：

- `/national-team-etf-holdings` 的 `ETag` 由 `fetched_at`、`as_of_date`、
  `partial` / `refreshing` / `stale` / `calendar_degraded`、`include_etf_points` /
  `index_points_included` / `flow_breakdown_included` 等影响响应体的标量拼成，
  不 hash 整份 JSON（响应可达数百 KiB，每次请求序列化只为算 ETag 不划算）；
- `/national-team/overview`、`/national-team/index-series`、
  `/national-team/index-series/{index_key}`、`/national-team/backtest` 也返回 `ETag`：
  概览/回测取影响结论的标量与样本数，指数序列取每条序列的最新日期、点位数量与
  最后一个点位的份额/收盘，避免为分段接口重复序列化大响应；
- 请求带 `If-None-Match` 且匹配时返回 **304**，并携带同样的缓存头；
- 主接口 `Cache-Control: private, max-age=60`（partial/refreshing）或 `max-age=300`
  （完整）；概览/指数序列/回测固定 `max-age=300`。前端仍以 React Query 的
  `staleTime` 为主，浏览器缓存作为补充。

## 9. 已知限制 / 后续工作

1. `daily_flows[].flows_by_index` 已可通过 `include_flow_breakdown=false` 关闭，
   前端默认关闭；目前没有按宽基拆分的图表需求。
2. 托底强度指数已有置信度、近 60 日分位、窗口内历史序列与信号后 5/20 日回测，
   但评分阈值仍是固定经验值，没有按牛熊阶段滚动校准；回测也未计交易成本/滑点。
3. 回测以「已落库评分日」为单位，缺采的交易日会被跳过；过滤了低置信度/低覆盖率
   样本后，`first_sample_date` ~ `last_sample_date` 才是实际统计区间。
4. 静态画像仍是人工维护，长期应由定期报告 / 十大股东数据生成。
5. 后端已拆成三个模块：`national_team_definitions`（ETF / 指数池、里程碑、画像）、
   `national_team_aggregation`（纯计算，可用固定输入单测）、`national_team`
   （采集、缓存、落库、对外服务，并重新导出前两者的公开名）。
6. 部署新增 migration 15（`national_team_support_scores`）：先跑迁移再发后端。
   未执行迁移时采集仍能返回，只是评分落库会在 warning 日志里持续报错。
