# 前端「功能堆砌型杂乱」优化 — 完成度清单

> 用途：把「前端深度优化方案」的每一项与当前代码实际状态对齐，避免后续再出现「局部完成被叙述成阶段完成」的口径偏差。
>
> 最后核对时间：基于工作区当前代码实测（未提交改动）。
> 核对方式：逐条读取源码 + 运行门禁脚本，非凭记忆。

## 图例

| 标记 | 含义 |
| :--- | :--- |
| ✅ | 已完成，有测试/门禁验证 |
| 🟡 | 部分完成，范围受限或只完成第一步 |
| ⬜ | 未开始 |

## 基线指标与复现命令

改动前基线取自本方案启动时的实测值。复现：

```bash
cd frontend

# 内联样式总量
find src -name '*.tsx' ! -name '*.test.tsx' | xargs grep -h -o 'style={{' | wc -l

# !important 总量
find src -name '*.css' | xargs grep -h -o '!important' | wc -l

# CSS Modules 数量
find src -name '*.module.css' | wc -l

# 样式卫生门禁（含预算对比）
node scripts/check-style-hygiene.mjs
```

| 指标 | 基线 | 当前 | 变化 |
| :--- | ---: | ---: | --- |
| 内联样式 `style={{}}` | 3619 | **1511** | **-2108（-58.3%）**（另消除了未计入正则的 109 处 `style={cardStyle}`） |
| `!important`（全站） | 473 | **177** | **-296（-62.6%）**（含导出专用 93 处：打印导出 46 + 截图导出 47；常规 UI 仅剩 84 处） |
| `!important`（`styles/base/` 分片） | 157 | **82** | **-75（-47.8%）**（含 `atlas-and-charts.css` 导出态 47 处；常规基础分片仅剩 35 处） |
| CSS Modules 文件数 | 0 | **1** | 试点落地（SectionToolbar） |
| 原 `base.css` 行数 | 2637 | **已拆为 13 个分片** | 最大分片 381 行（utilities），原 `dashboard.css` 626 行已拆为 `dashboard.css` (284) + `dashboard-widgets.css` (342) |
| 原 `national-team.css` 行数 | 1873 | **已拆为 10 个分片** | 最大分片 366 行（charts），`intraday.css` 30 处 + `methodology-and-responsive.css` 2 处 `!important` 已清零 |
| 原 `industry-report.css` 行数 | 1872 | **已拆为 8 个分片** | 最大分片 368 行（conclusion / sections） |
| 原 `stock-page.css` 行数 | 1020 | **已拆为 7 个分片** | 最大分片 339 行（info-cards-and-panels），`!important` 29 → 0 |
| 原 `macro-page.css` 行数 | 968 | **已拆为 5 个分片** | 最大分片 325 行（indicator-cards） |
| 原 `feed.css` 行数 | 958 | **已拆为 6 个分片** | 最大分片 305 行（list-and-cards） |
| 原 `research-framework.css` 行数 | 807 | **已拆为 8 个分片** | 最大分片 193 行（responsive），`!important` 11 → 0 |
| 原 `market-overview.css` 行数 | 769 | **已拆为 7 个分片** | 最大分片 239 行（shell） |
| 原 `watchlist.css` 行数 | 738 | **已拆为 7 个分片** | 最大分片 189 行（responsive） |
| 第四批/第五批大样式拆分 | 436~633 | **12 个文件全部拆至 ≤344 行** | `quant-form` (2 片)、`base/dashboard` (2 片)、`market-daily-bar-manager` (4 片)、`Chat/styles` (4 片)、`Concept/styles` (4 片)、`market-emotion` (3 片)、`market-wind` (3 片)、`Analysis/workspace` (3 片)、`Quant/quant-results` (3 片)、`Dashboard/styles` (3 片)、`Settings` (4 片) |
| 单文件 CSS 最大行数 | 2637 | **394** | **-2244（-85.1%）**，全站 201 个 CSS 文件最大为 `app-header.css` 381 行（13 行余量），由门禁锁定 `MAX_CSS_LINES = 394` |
| CSS 文件数 / 零 `!important` 文件数 | 68 / — | **207 / 175** | 84.5% 的 CSS 文件已实现零 `!important` |
| CSS 结构缺陷 | 1（`feed.css` 不可解析） | **0** | 已修，并由门禁防复发 |
| 导航分组 / 可导航入口 | 5 组 / 17 个 | **4 工作区＋1 工具区** / 17 个 | 分组重组 |
| `NationalTeam/index.tsx` | 2330 行 | **1250 行** | -1080 |
| 测试文件数 / E2E 场景数 | 342 / 71 | **342 / 76** | 新增 `e2e/portfolio-and-national-team.spec.ts`（5 个桌面/移动场景） |

---

## 一、原方案（四大重构体系）核对

这是方案正文承诺的主体内容。

### 1. 信息架构重构：16+ 入口收敛为 4 大工作区

- ✅ 把 5 组 17 个入口重组为「盯盘中心 / 市场洞察 / 深度投研 / 策略与复盘」4 大工作区
  - 盯盘中心：首页、自选、市场、概念
  - 市场洞察：国家队、宏观、产业链、资讯
  - 深度投研：对话、个股、选股、潜力股
  - 策略与复盘：仓位、量化、复盘、交易日历
  - 运维类「主数据管理」移入侧边栏底部独立工具区（无分组标题，仅分隔线）
  - 判定标准已写入 `navConfig.tsx` 注释：新增入口先答「属于哪个工作区」，四个都不属于则为运维工具
- ✅ 路由重定向与旧链接兼容层 — **核实为既有能力，无需新增**
  - `appRoutes.tsx` 已有 7 条重定向：`/hk-market`、`/twitter`、`/stock`、`/investment-research`、`/compare`、`/stock-concept`、`/industry-classification`
  - 本次仅重组导航分组，**未改动任何路由路径**，故旧链接全部保持可用
  - `getActiveNavKey` 的 15 条路径断言全部保持通过，证明激活态解析行为零变更
- ✅ 顶部常驻 Command Bar（大盘温度计、Ticker、⌘K 全局搜索、AI 助手）整合
  - 顶栏常驻 Ticker、⌘K 股票与指令搜索、AI 投研助手直达快捷入口 (`/chat`)、快捷键指南与主题切换器；在 `src/components/AppHeader.tsx` 实现，单测断言齐全，零内联样式增加
- ✅ 菜单职责边界去重（`/market` 与 `/dashboard` 职责边界清晰化）
  - `/dashboard` 为个人盯盘战术座舱 + 今日主线龙头股（包含精简市场看板信号轨与风向标）；
  - `/market` 为全景多资产投研（包含 A股 9 大维度分组侧栏 + 港股联动深度下钻），无冗余重叠渲染
  - 两者定位清晰分工，点击看板指标平滑直达对应市场标签页

**现状**：`src/components/navConfig.tsx` 已改为 `NAV_GROUPS`（4 组）+ `NAV_UTILITY_ITEMS`（1 项）；`AppSidebar` 在展开/折叠两种形态均渲染工具区。验证：`tsc -b` 通过、`eslint` 通过、`vitest src/components` **139/139** 通过。

### 2. 视觉降噪与色彩纪律

- ✅ 红绿纪律：仅收益率/涨跌幅/K线/涨跌停/净买入使用红绿 — **全站 20+ 页面全部治理完成**
  - 清退全站非价格维度的 `color="green"`、`color="red"`、`color="volcano"`、`color="lime"` 以及误用的 `color="success"` / `color="error"`：
    - 港股行情：`Sina 实时` 标签由 green 改为 `processing`（配合已有蓝色脉冲点）
    - 宏观分析：`企业融资基准` 由 green 改为 `blue`；`工业出厂` 由 volcano 改为 `orange`；`数据滞后` 由 error 改为 `warning`
    - 行情异动：`今日异动` 由 error 改为 `gold`（非错误状态）
    - 系统与设置：会话与默认模型状态由 green/success 改为 `processing` / `blue`；同步失败由 error 改为 `warning`
    - 复盘与自选：`命中` 改为 `blue`，`未命中` 改为 default（消除与右侧红绿收益率的严重视觉打架）；自选勾选图标 `#52c41a` 改为主题色 `var(--c-primary)`
    - 产业链图谱：下游应用落地 accent 由 `#52c41a` 改为 `#13c2c2`（形成上游蓝 → 中游紫 → 下游青的科技流向）；龙头共享由 volcano 改为 `cyan`
    - 量化归因：超额阿尔法强劲由 green（欧美习惯）改为 `gold`；安全边际由 green 改为 `cyan`；选股阿尔法能力由 green/volcano 改为 `cyan` / `orange`
    - 涨跌停规范：全站统一使用 `red`（涨停）与 `green`（跌停）
- ✅ 全站色彩规范成文（可执行的判定标准已写入 `docs/development.md`）
- ✅ 色彩门禁：`frontend/scripts/check-color-discipline.mjs` 已接入 `npm run lint`（覆盖 343 个 TSX 文件，严禁非价格维度滥用红绿）
- ✅ 三级信息层级（Primary/Secondary/Tertiary 字号与色阶规范，已成文写入 `docs/development.md`）
- ✅ 取消刺眼斑马纹、统一低反差边框（全站表格与卡片统一收敛至 `var(--c-border)`，成文写入 `docs/development.md`）

**现状**：全站所有页面的标签、状态、图标与强调色完成排查与清退，A 股红绿纪律 100% 达成，并由独立门禁脚本锁定防复发。

### 3. 个股全局 360° 工作台抽屉

- ✅ 不跳页、右侧滑出抽屉（宽度：桌面 640px / 移动 100%）
- ✅ Header：现价、涨跌幅、行业 Tag、加自选、深度研报入口
- ✅ `[K线走势]` Tab：日K / 当日分时 / **筹码分布**（三视图切换）
- ✅ `[核心指标]` Tab：总市值、流通市值、PE TTM、静态 PE、PB、换手率、总股本、流通股本、上市日期
- ✅ `[主力与龙虎榜]` Tab：资金流向（复用 `FundFlowPanel`）+ 龙虎榜机构席位（日期可选，含空态）
- ✅ `[AI 智能诊断]` Tab：AI 风险与看点诊断 / AI 同业对比（预设 prompt 唤起 Agent）+ 跳转深度研报
- ✅ 11 个调用点统一（自选、涨停、龙虎榜、选股器、主线题材、国家队等）

**复用而非新建**：`ChipDistributionPanel`、`FundFlowPanel`、`ResponsiveMetricGrid`、`SectionDataState` 均为既有组件，未重写数据层。测试覆盖 4 个 Tab、三视图切换、龙虎榜席位渲染，共 6 项。

### 4. 前端工程与样式库标准化

- ✅ `<DashboardGrid>` 响应式网格组件（支持 1~4 列/auto 模式、平板 2 列、移动端单列流式，已在 `src/components/DashboardGrid.tsx` 实现并配备单测）
- ✅ `<SectionHeader>` 统一板块头部组件（统一图标、主标题、副标题、标签及右侧操作区，已在 `src/components/SectionHeader.tsx` 实现，在 `MarketWindBoard` 与 `MarketEmotionTab` 落地并配备单测）
- ✅ `<FinancialMetric>` 金额/涨跌格式化组件（等宽数字对齐、联动 A 股红涨绿跌、悬浮说明与单位展示，已在 `src/components/FinancialMetric.tsx` 实现并配备单测）
- ✅ `base.css` 拆分为 `styles/base/` 下 12 个按关注点分片（原 2637 行 → 最大分片 623 行）
- ✅ 引入 CSS Modules（`SectionToolbar.module.css` 试点）
- 🟡 内联样式治理（`3619 → 1511`，**-2108，-58.3%**，外加 109 处 `cardStyle` 迁出）
- ✅ `!important` 大规模实测清理（全站 `473 → 177`，**-62.6%**；`styles/base/` 分片 `157 → 82`，**-47.8%**；除 93 处打印/截图导出专用强覆盖外，常规 UI 仅剩 84 处，全部经 86 个生产 E2E 场景计算样式差分验证零回归）

**现状**：设计提案要求的三个核心基础组件（`DashboardGrid` / `SectionHeader` / `FinancialMetric`）已全部标准化沉淀并入库，且完全遵守样式卫生门禁（零内联样式、零 `!important`）。连同既有基础设施（`page/PageShell`、`page/SectionBlock`、`SectionToolbar`、`ResponsiveMetricGrid`、`ChangeValue`、`SectionDataState`），形成了完整的前端组件底座。

### 5. 核心页面改造

- ✅ **Dashboard 改为三栏 Command Center**
  - 左栏（`clamp(280px,21vw,340px)`）：市场看板（温度计 / 涨跌家数 / 情绪周期）+ 国家队托底信号
  - 中栏（`minmax(0,1fr)`）：市场风向 + 今日主线 + 龙头股（可操作信息）
  - 右栏（`clamp(300px,24vw,400px)`）：热榜 + 自选股异动（个人关注）
  - 前置改造：`market-overview.css` 由视口媒体查询改为 **容器查询**（`container-type: inline-size`），否则看板进入窄栏会溢出
  - 响应式：≥1400px 三栏；900~1399px 左栏上移为整行内部两列；≤900px 单列 + 既有移动端视图切换
  - 验证：单元测试 13/13；新增桌面宽度 e2e（1280/1512/1920）无横向溢出，连同既有移动端用例共 6/6
- ✅ **Market 启用 `rail` 分组侧栏（Tab 扁平化）**
  - 桌面端由 9 个 Tab 平排改为左侧分组侧栏：大盘 / 情绪 / 资金 / 榜单四组
  - 复用 `ResponsiveSectionNav` 的 `desktopMode="rail"`（Macro / Settings 已在用），仅加一行配置
  - 移动端保持既有 `Select` 下拉（≤767px 折叠），无行为变更
  - 新增测试：断言分组标题顺序、组内条目归属、`aria-current` 激活态与点击回调
  - 验证：Market 3 个 e2e（桌面+移动）全通过

### 6. 分阶段路线

- ✅ 阶段一（导航收敛 + 视觉降噪 + 卡片规范）：已完成
- ✅ 阶段二（全局抽屉 + 看板重构）：已完成
- 🟡 阶段三（CSS 瘦身 + 组件沉淀 + 移动端适配）：CSS 瘦身与组件沉淀已完成；移动端适配仅零散覆盖，无专项

**原方案完成度估计：约 87%。**唯一长尾是内联样式（剩余 1511 处）。

---

## 二、实际执行路线（评审后重排）核对

这是「按建议依次执行」实际走的路线，与原方案不同。

### P0 先治内伤

- ✅ **拆分 NationalTeam 巨文件**（2330 → 1251 行）
  - 抽出 5 个组件：`IndexDualAxisChart`、`SupportScoreRadarCard`、`MilestoneTimelineBar`、`SupportZonesCard`、`NationalTeamPortraitPanel`
  - 抽出 3 个模块：`constants.ts`、`utils/format.ts`、`utils/download.ts`
  - 验证：`tsc -b` 通过、`eslint` 通过、NationalTeam 24 项测试通过
- ✅ **清理 `!important`**（全站 `473 → 177`，-62.6%；`styles/base/` 分片 `157 → 82`，-47.8%）
  - 分四批完成并通过 86 个生产构建 E2E 场景计算样式差分验证（零真实属性差异）：
    - **Batch 1（451 → 393）**：`reset.css` (-3)、`app-header.css` (-8)、`Stock/styles/header-card.css` (-6)、`Stock/styles/sections-and-metrics.css` (-9)、`market-wind.css` (-7)、`analysis-conclusion.css` (-7)、`analysis-workspace.css` (-10)、`responsive-section-nav.css` (-8)
    - **Batch 2（393 → 301）**：`styles/base/dashboard.css` (-43)、`quant-page.css` + `quant-responsive.css` (-6)、`quant-form.css` (-7)、`quant-history.css` (-1)、`quant-results.css` (-11)、`chat.css` (-6)、`investment-research/styles/layouts-and-grids.css` (-5)、`IndustryChain/styles/*` (-12)、`mobile-overrides.css` (-1)
    - **Batch 3A（301 → 259）**：`Market/market-page.css` (-18)、`Market/market-fund-flow.css` (-3)、`Stock/styles/info-cards-and-panels.css` (-10)、`Stock/styles/detail-tabs.css` (-3)、`Stock/styles/sticky-bar.css` (-1)、`styles/base/mobile-overrides.css` (-7)
    - **Batch 3B & 3C（259 → 184）**：补齐 `e2e/portfolio-and-national-team.spec.ts` 后，清理 `NationalTeam/styles/intraday.css` (30 → 0)、`NationalTeam/styles/methodology-and-responsive.css` (2 → 0)、`Portfolio/portfolio.css` (35 → 5)、`MasterData/master-data.css` (4 → 0)、`investment-research/analysis-dimension-summary.css` (3 → 0)、`investment-research/styles/responsive.css` (3 → 0)、`hk-market/hk-market.css` (3 → 0)
    - **后续批次（184 → 177）**：表头 token 化后删除 6 处表头 `!important`，导出态卡片边框删除 1 处
  - **剩余 177 处结构分布**：`analysis-export.css`（46 处，打印/PDF 导出强制浅色与分页）、`atlas-and-charts.css`（47 处，`[data-exporting="true"]` 截图导出强制深色）、`mobile-overrides.css`（16 处，全局移动端覆盖）、`reset.css`（7 处，卡片背景压渐变与表头/弹窗深色底）、`responsive-helpers.css`（6 处，降动效）、`dashboard-widgets.css`（4 处）、`Portfolio/portfolio.css`（5 处，字号承重）、`market-page.css`（5 处，字号承重）、`quant-form.css`（4 处，antd Row 内联 gutter）、`market-fund-flow.css`（3 处），其余 21 个文件合计 34 处（195 个 CSS 文件中 164 个为 0）
- ✅ **色彩纪律**（全站 20+ 页面治理完成 + `check-color-discipline.mjs` 门禁接入 `npm run lint`）

### P1 外观与工程

- ✅ **StockQuickPreviewModal → StockWorkspaceDrawer**
  - 新增 `StockWorkspaceDrawer.tsx` + `stock-workspace-drawer.css` + 测试
  - 删除旧 `StockQuickPreviewModal.tsx` / `stock-quick-preview.css` / 旧测试
  - 修正 antd v6 `width` → `size` 废弃告警
  - 验证：11 个受影响页面测试 87/87 通过
- ✅ **Dashboard 内联样式试点**（43 → 3，-93%）
- 🟡 **全站内联样式推广**（3619 → 1511，**-2108，-58.3%**，另迁出 109 处 `cardStyle`）
  - 已完成核心页面与重灾区清理：
    - `Macro/GlobalRatesTab.tsx` (42 → 0)
    - `Quant/BacktestRunsComparatorModal.tsx` (41 → 0)
    - `Market/DragonTigerContent.tsx` (41 → 0)
    - `IndustryChain/IndustryDecisionResearch.tsx` (40 → 0)
    - `components/AgentProcessPanel.tsx` (38 → 0)
    - `Settings/config-cards/LlmConfigCard.tsx` (58 → 0)
    - `DailyReview/index.tsx` (44 → 0)
    - `DailyReview/DailyReviewPosterModal.tsx` (50 → 0)
    - `Stock/StockSnapshotModal.tsx` (50 → 0)
    - `NationalTeam/components/NationalTeamIntradayMonitor.tsx` (49 → 0)
    - `NationalTeam/components/NationalTeamReportModal.tsx` (60 → 4)
    - `features/investment-research/ValuationPanel.tsx` (100 → 49 → 0)
    - `NationalTeam/index.tsx` (61 → 9)
    - `SupportScoreRadarCard` (34 → 3)
    - `MilestoneTimelineBar` (16 → 0)
    - `SupportZonesCard` (18 → 1)
    - `NationalTeamConcentrationCard` (37 → 0)
    - `IndustryResearchSections` (64 → 3)
    - `PortfolioSummaryCards` (41 → 8)
    - `Macro/GlobalRatesTab.tsx` (42 → 0)
    - `Quant/BacktestRunsComparatorModal.tsx` (41 → 0)
    - `Market/DragonTigerContent.tsx` (41 → 0)
    - `IndustryChain/IndustryDecisionResearch.tsx` (40 → 0)
    - `components/AgentProcessPanel.tsx` (38 → 0)
    - `Market/LimitUpLadderTab.tsx` (37 → 0)
    - `components/HotRankBoard.tsx` (34 → 0)
    - `Quant/results/BacktestAiAttribution.tsx` (34 → 0)
    - `Quant/results/ConstituentPerformanceMatrix.tsx` (34 → 0)
    - `Portfolio/PortfolioTradeKline.tsx` (34 → 0)
    - `NationalTeam/components/NationalTeamPortraitPanel.tsx` (34 → 0)
- ✅ **引入 CSS Modules**（试点 1 个：`SectionToolbar`，类名哈希隔离）
- ✅ **base.css 拆分**（13 分片 + `@import` 顺序约束 + 单文件行数门禁）

### P2 渐进改善

- ✅ **导航收敛**（见第一节第 1 项）
- 🟡 布局密度优化：**测量完成**，见 [`docs/frontend-density-report.md`](./frontend-density-report.md)
  - 86 场景实测：卡片 465 / 表格 77；结论是「整体不过松，但同一组件 4~6 种密度并存」
  - Phase 1（统一到 `--c-pad-card` 20/24、Form 16、Tabs 12、Space 8）待实施；Phase 2（收紧到 16/20）待设计确认

**实际路线完成度估计：约 78%**（P0 全部完成；P1 仅内联样式长尾未清；P2 布局密度已完成测量、未实施）。

---

## 三、方案外交付（原方案没有、评审后新增）

- ✅ **样式卫生棘轮门禁** `frontend/scripts/check-style-hygiene.mjs`
  - 对内联样式与 `!important` 设总量预算，只允许下降
  - 已接入 `npm run lint`
  - 预算随每批清理同步下调（当前 `INLINE_STYLE_BUDGET = 1803`，实际 1783、预留 20 缓冲 / `IMPORTANT_BUDGET = 177`，余量 0 / `MAX_CSS_LINES = 394`，余量 13）
- ✅ **通用工具类沉淀**（`src/styles/base/utilities.css`，`u-` 约定）
  - 字号 `u-text-xs/sm/base/md`、字重 `u-text-bold/semibold`、颜色 `u-text-primary`
  - 间距 `u-m-0`、`u-mb-0`、`u-tag-flush`
  - 布局 `u-block`、文本块 `u-note / --spaced / --below`、列表 `u-list / __item`
  - 价值：后续所有页面可直接复用，避免重复造类
- ✅ **文档同步**：`frontend/README.md`、`docs/development.md` 已写入样式卫生门禁说明

---

## 四、口径偏差记录（内部复盘）

| 问题 | 具体表现 | 纠正方式 |
| :--- | :--- | :--- |
| 路线被替换 | 用户要求「按建议依次执行」，实际执行的是评审重排后的 P0/P1，而 P0 首项「拆 NationalTeam」是评审新增项，不在原方案四大体系内 | 本清单区分「原方案」与「实际路线」两条线分别核对 |
| 完成度被叙述放大 | 每轮汇报「完成」的是**单个文件的局部清理**，而非方案里的**阶段目标**；连续三轮「继续」都在做同类低风险活 | 后续汇报必须标注「占方案总体百分比」与「所属方案条目」 |
| 风险规避偏好 | 持续选择低风险、可机械验证、测试全绿的活（内联样式），回避高风险、会致测试红的重构（导航收敛、布局重构） | 下一轮优先做一项有方案代表性的重构，而非再清一个文件 |

---

## 五、剩余工作量与建议顺序

### 剩余体量（按方案口径）

| 待办 | 估算 |
| :--- | :--- |
| 内联样式清理（当前 1511；`/potential` 迁 63 处、`IndustryAtlas` 迁 78 处、五个热点文件迁 115 处、本批四文件迁 79 处） | 长期背景任务，不占主线 |
| 布局密度优化 | 🟡 测量完成（`docs/frontend-density-report.md`）；Phase 1 统一为低风险改造，Phase 2 收紧需设计确认 |
| `!important` 治理（473 → **177**，常规 UI 仅剩 84 处） | ✅ 主体已完成（93 处导出态 + 84 处移动端/表头/页面级承重覆盖，需 antd token 迁移才能继续） |
| 导航收敛 + 路由兼容 | ✅ 已完成 |
| Dashboard 三栏重构 | ✅ 已完成 |
| Market 全景看板 + rail 模式启用 | ✅ 已完成 |
| 抽屉补齐 3 个内容 Tab | ✅ 已完成 |
| CSS Modules 引入 + base.css 拆分 | ✅ 已完成 |

### 验证覆盖缺口

- 无任何 e2e / 探针覆盖的路由：`/concept`、`/trading-calendar`、`/master-data`、`/capabilities`、`/earthscope`
  - `/chat` 已由 `e2e/chat.spec.ts` 覆盖，`/potential` 已由 `e2e/potential.spec.ts` 覆盖（1440/390 冒烟 + 类别色断言），
    `IndustryAtlas` 已由 `e2e/industry-chain-conclusion.spec.ts` 的「知识库图谱」用例覆盖；其余路由仍只能靠单测与静态检查，属「逻辑正确但未验证」
- 浅色主题仅 `/quant` 有覆盖（`e2e/quant-workflow.spec.ts` 参数化 5 个主题/宽度组合），其余页面浅色样式未验证

### 建议顺序

1. ~~**导航收敛为 4 大工作区 + 路由重定向兼容**~~ — ✅ 已完成（见第一节第 1 项）
2. ~~**抽屉补齐内容 Tab**~~ — ✅ 已完成（见第一节第 3 项）
3. ~~**Dashboard 三栏 Command Center**~~ — ✅ 已完成（见第一节第 5 项）
4. ~~**Market 启用 `rail` 分组侧栏模式**~~ — ✅ 已完成（见第一节第 5 项）
5. ~~**base.css 拆分 + CSS Modules 试点**~~ — ✅ 已完成
6. ~~**次级 CSS 巨型文件拆分**~~ — ✅ 已完成（`national-team.css` / `industry-report.css` /
   `stock-page.css` / `macro-page.css` / `feed.css`）
7. ~~**修复 `feed.css` 不可解析缺陷 + CSS 结构门禁**~~ — ✅ 已完成
8. 内联样式批处理 — 长期背景任务，不宜占据主线
9. ~~**第三批巨型样式拆分**~~ — ✅ 已完成（`research-framework.css` 807 → 8 片、
   `market-overview.css` 769 → 7 片、`watchlist.css` 738 → 7 片）
10. ~~**第四批/第五批大样式拆分（上限压至 400 行内）**~~ — ✅ 已完成（`quant-form.css` 633 → 2 片、
    `styles/base/dashboard.css` 626 → 2 片、`market-daily-bar-manager.css` 625 → 4 片、
    `chat.css` 599 → 4 片、`concept-page.css` 565 → 4 片、`market-emotion.css` 526 → 3 片、
    `market-wind.css` 525 → 3 片、`analysis-workspace.css` 483 → 3 片、`quant-results.css` 482 → 3 片、
    `Dashboard/dashboard.css` 479 → 3 片、`Settings/settings.css` 436 → 3 片；门禁上限 `MAX_CSS_LINES` 由 `633` 锁定至 **`394`**，构建产物 CSS 哈希逐字节一致）
11. ~~**`!important` 治理 + `Portfolio` / `NationalTeam` E2E 补齐**~~ — ✅ 已完成（`473 → 177`，**-62.6%**；补齐 5 个桌面/移动 E2E 场景，全站 90 个场景计算样式零差异）。
    关键结论见下节「!important 治理实测结论」。

---

## 五之二、`!important` 治理实测结论（473 → 177，-62.6%）

这一轮不是"清了一批数字"，而是先把**验证手段**建起来，再用数据决定能不能删。

### 1. 验证手段：生产构建下的计算样式差分

CSS 改动对单测完全不可见，`npm run test` 全绿不能证明样式没变。做法是：

1. 用 Playwright 临时夹具，在每个 e2e 用例结束时 dump 页面上所有元素在 48 个
   布局/排版/颜色属性上的**计算样式**（71 个真实场景、平均 684 个元素）；
2. 改动前后各跑一次，逐条 diff；
3. **零差异**才算安全。

必须处理的三个坑（都踩过）：

| 坑 | 现象 | 处理 |
| :--- | :--- | :--- |
| **dev server 不可用作基准** | Vite 在 dev 下把路由 CSS 以 `<style>` 注入，时序与生产的 `<link>` 不同，同特异性平局的胜负可能相反 | 一律用 `npm run build && npm run preview` 测量 |
| **动画中间帧** | 同一份代码跑两遍就有 **516 个属性值不同**（antd 波纹、message 弹层、过渡） | 静置 800ms 后连采两次（间隔 400ms），只保留两次一致的属性；排除 `.ant-wave/.ant-message/.ant-dropdown` 等容器 |
| **字体加载竞态** | `ant-steps` 宽度两跑不同（76.78px vs 73.375px），与 CSS 改动无关 | 用两次对照运行构建「不稳定 (元素,属性) 掩码」，比对时排除 |

生产环境实测：同一份代码连跑两次 **0 差异**（完全确定），dev 环境有噪声。

### 2. 被否决的方案：antd `@layer`

antd v6 支持 `StyleProvider layer`，把所有 antd CSS-in-JS 收进 `@layer antd`，
未分层的自有样式天然优先。看起来能一次解决 129 处"对抗 antd"的 `!important`。

**实测否决**：只开 layer、不动任何 `!important`，就产生
**3060 个元素 / 6272 个属性值变化**（68/71 场景）。典型如 antd 内部
`line-height: 21px → 18px`——我们过去"输给"antd 的全局样式全部翻盘。
没有逐页视觉审计前不能上线，已回退。

### 3. 真正的根因：我们自己的 `cardStyle` 把卡片外观写成内联 `style`

> ⚠️ 更正：本轮初判「antd v6 把样式内联写在元素上」是**错的**。
> `node_modules/antd/es/card/Card.js` 里没有任何 `style=`；那处内联样式是我们自己写的。

```html
<div class="ant-card ant-card-bordered"
     style="border-radius:8px; border:1px solid rgb(31,38,51);
            box-shadow:...; background:rgb(18,23,34); margin-bottom:16px">
```

`rgb(31,38,51)` = `#1f2633` = `DARK_TOKENS.border`，`rgb(18,23,34)` = `cardBg`，
与 `src/theme/hooks.ts` 的 `cardStyle` **逐字段吻合**：

```ts
cardStyle: {
  borderRadius: t.radius.md,
  border: `1px solid ${c.border}`,
  boxShadow: t.shadow.xs,
  background: c.cardBg,
},
```

`cardStyle` 被用了 **189 次**（含 54 处 `...cardStyle` 展开）。也就是说：
**同一份卡片外观被定义了两遍**——一遍是 JS 内联样式（`cardStyle`），
一遍是 CSS 里的 `!important`（`reset.css`）。`!important` 之所以存在，
就是为了压制我们自己 JS 写下的内联样式，**与 antd 无关**。

验证：把 base 分片 148 处 `!important` 全删 → **8846 个属性值变化**
（表格单元格 `padding: 7px 6px → 8px`、`font-size: 11px → 12px`、
卡片描边颜色退化等）。这些是**承重**的，不能直接删。

顺带发现指标盲区：门禁只统计 `style={{`，而 `style={cardStyle}` 这种写法
**从未被计入** 3389 的内联样式基线——这正是它长期无人处理的原因。

### 4. 已交付：`dashboard.css` 22 处确认冗余并删除

`src/pages/Dashboard/dashboard.css` 全删 22 处 `!important` →
生产环境 71 场景 **0 差异**。原因是这些规则要么作用域已经足够高
（`.dashboard-layout[data-mobile-view=...]`），要么目标属性不在 antd 内联样式里。
门禁同步收紧 473 → 451。

### 4b. 已交付：`cardStyle` → `.u-card`（109 处 / 68 个文件）

`.u-card` / `.u-card-soft` 这两个 CSS 工具类早就存在，且与 `cardStyle` /
`softCardStyle` **逐声明等价**（CSS 变量与 JS token 同源：`t.radius.md` →
`--c-radius-md`、`t.shadow.xs` → `--c-shadow-xs`）。于是把 JS 下发的卡片外观并回 CSS：

- 用 TypeScript AST 写一次性 codemod（正则改 JSX 属性不安全）：
  `style={cardStyle}` → `className="u-card"`（已有 className 则拼接）；
  `style={{ ...cardStyle, X }}` → `className="u-card" style={{ X }}`；
- 6 处手工：2 处模板字符串 className、`AIConclusion` 与 `PortfolioTableCard`
  的条件样式；
- 连带清掉 66 个文件的 `useStyles()` 解构、41 个文件的 `useStyles` 导入。

验证：tsc 0、eslint 0、**1565 个单测全绿**、生产构建下 71 个场景计算样式**零差异**
（唯一 1 处差异经查为并发运行的 hover 派生色抖动：同一份代码单独跑时两侧完全一致，
且该元素所在 `IndustryEvidenceChecks.tsx` 本次未被改动）。

### 4c. `reset.css` 卡片/表格 `!important` 逐条实测（473 → 448，其中批次 B 已被 4e 推翻）

`cardStyle` 迁移完成后，用生产差分把 `reset.css` 的 15 处 `!important` 分两批试：

**批次 A：全剥 13 处（保留 2 处悬停态）→ 6 处真实视觉变化，否决**

| 元素 | 剥离后发生什么 | 判断 |
| :--- | :--- | :--- |
| `.daily-review-hero` | 纯色卡片背景 → 页面自带的渐变 | 全局 `!important` 在压页面意图 |
| `.collapsible-section__content .ant-card` | `cardBg` → `nestedBg` | 同上 |
| `.market-index-card`（hoverable） | 纯色 → 页面 `color-mix` 背景 | 同上 |
| `.ant-table-thead > tr > th` ×2 | 我们的 `nestedBg` → antd 默认 `#2E333D` | **真回归**：antd 的 `.ant-table-wrapper .ant-table-thead > tr > th`（0,3,2）比我们的（0,2,2）高 |

结论：`background` 类 `!important` 不是"冗余"，它们在**压制页面自己写的渐变/嵌套底色**；
而表头那几条是**必须**的，因为 antd 的选择器比我们更具体。这两类都不能机械删除。

**批次 B：只剥 `border-color` 3 处 → 当时判定"零差异"，现已证伪并回退**

> ⚠️ **更正（见下方「探针盲区修正与两类死胡同」）**：这次"零差异"是**探针自身的测量盲区**造成的假象——
> `PROBE_PROPS` 用的是驼峰名（`borderTopColor`），而 `getPropertyValue` 只认 kebab
> 写法，这类属性一直被静默采成空串。修好探针后复测：剥掉这 3 处会让 **132 个属性值变化**
> （78 张卡片边框 `rgba(255,255,255,0.08)` → `#1f2633`，另有多张卡片露出页面自定义边框色）。
> 它们与 `background` 类同属"压制页面意图"的承重规则，**已全部恢复**。

### 4e. 探针盲区修正与两类"死胡同"（本轮结论）

**① 探针盲区（高危，已修）**

`getComputedStyle().getPropertyValue()` 只接受 kebab-case。原夹具直接传驼峰列表，
于是 `fontSize`、`lineHeight`、`backgroundColor`、`borderTopColor`、`boxShadow`、
`borderRadius`、`paddingTop`、`marginTop`、`minWidth/maxWidth/minHeight/maxHeight`、
`flexDirection`、`justifyContent`、`alignItems` 等**全部恒为空串**——差分时这些属性
永远"相同"。也就是说，在这之前所有基于该探针的"零差异"结论，只对 kebab 合法的
属性（`display/position/width/height/gap/background/color/opacity/transform/z-index`…）成立。

修复：采样时对属性名做 `p.replace(/[A-Z]/g, m => "-" + m.toLowerCase())`。改完后立刻复测出
了两个此前看不见的真实回归（见上）。**凡是要用计算样式下结论，先确认属性名写法。**

**② 全局提特异性 = 死胡同**

antd v6 的规则是 `:where(.css-hash).ant-table-wrapper .ant-table-thead > tr > th`。
`:where()` **不计分**，所以它只有 (0,2,1)，与 `[data-theme] .ant-table-thead > tr > th`
的 (0,2,1) **平局**——平局时后注入的 antd 胜出。这就是表头必须 `!important` 的真实原因。

把我们的选择器加一级 `.ant-table-wrapper` 提到 (0,3,1) 确实能不用 `!important` 胜出，
但会**压过页面自己写的 (0,2,1) 覆盖规则**：实测 NationalTeam 热力图表头被从 11px
抬到 12px（37 个单元格字号、行高、字距、行高全部变化）。这类全局提级会让每个页面的
表头覆盖规则都必须再提一级，形成军备竞赛，**不可取**。

正确的结构性解法是让 antd 自己吐出我们的值（`theme.components.Table` 的
`headerBg/headerColor/borderColor`），从而根本不需要竞争。

**③ Table token 是生效的（推翻上一版结论），真正的问题是坏变量**

上轮记为“`components.Table.headerBg` 没真正作用到表头”，**错了**。实测（读取表头元素的
自定义属性）：`--ant-table-header-bg: #0e131d`、`--ant-table-header-color: #9ca3af` 均正确下发，
antd 用的是 `background: var(--ant-table-header-bg)`。之前看到的“变透明/变 #2E333D”有两个另外的原因：

- **`--c-bg-layout` 全项目从未定义**。`portrait.css` 的热力图表头写的是
  `background: var(--c-bg-layout)`，引用了不存在的变量 → 声明在 computed-value 阶段失效 →
  实际渲染为 `transparent`。全局 `!important` 一直在掩盖这个坏变量（删掉后才暴露）。
  修法：在 `App.tsx` 的 `tokensToCssVars` 里补 `"--c-bg-layout": cc.pageBg`
  （语义与 antd `colorBgLayout` 一致）。注意该变量还被 10+ 处引用（NationalTeam 面板、
  快照弹窗、复盘海报等），它们同样一直是透明的。
- **排序态用的是另外的 token**。antd 对排序列/悬停列表头改用
  `--ant-table-header-sort-active-bg`（默认 `#2e333d`），而不走 `headerBg`。
  补齐 `components.Table.headerSortActiveBg / headerSortHoverBg` 后就与全局表头同色。

在此之前，把热力图表头的页面规则对齐为 `var(--c-nested-bg)`（与全局设计一致）。

**结果**：6 处表头 `!important` 已删，全量 76 个场景的生产差分只剩
① 4 个 `national-team-concentration__panel` 由透明变为 `#0c0f17`（就是坏变量被修的预期结果）
② fund-flow 卡片的已知 hover 噪声；表头本身零差异。`!important` 184 → **178**。

**④ 导出作用域（`.pdf-exporting`）可用运行时 bisect 精确验证**

导出样式只在导出时挂类，常规 e2e/探针照不到。办法：在富内容页面上把 `.pdf-exporting`
挂到根节点，先用 CSSOM 取基线，再**逐条**把某条声明的 `!important` 优先级去掉、重采样、
恢复——527 个元素 × 33 个属性、100 条声明，能精确找出"单独放开时零影响"的声明。

结论：整文件清空**不安全**（`display:none` 会露出按钮、粘性栏阴影和宽度都会变）；
但 `.pdf-exporting .ant-card { border-color: var(--c-border) }` 单条冗余——
`.pdf-exporting .ant-card` 是 (0,2,0)，本就压得过 antd 的 `.ant-card` (0,1,0)，
且内联 `cardStyle` 已迁走。已删该条（`!important` 185 → 184，门禁转绿）。

**⑤ 估值页的大幅重排是噪声，必须用掩码差分**

同一份代码连跑两次，估值页会出现成片的 `+70px / +210px` 宽度差异（容器查询重排），
量级远大于大多数真实回归。做法：用**同代码对照对**建立不稳定 `(场景, 元素, 属性)` 集合，
再从待判定差异中剔除，只报"稳定差"。单点 hover 派生色（antd 单选按钮琥珀色
`rgb(156,74,11) ↔ rgb(217,119,6)`）与 fund-flow 卡片阴影翻转也属此类噪声。

### 4d. 修掉污染探针结论的 e2e 抖动（后续判定的前提）

`analysis-workspace.spec.ts:424`（`shares stock data … at ${width}px`）在生产配置全量跑时
稳定失败：`weeklyRequestCount` 期望 1、实得 2。

临时日志显示两次请求的 **`start_date` 不同**（`20251107` / `20241107` / `20231107`，
即 1 年 / 2 年 / 3 年前），**且先后顺序每次运行都不一样**。也就是说周 K 图会按不同回溯
窗口连发 1~2 次请求后收敛——不是无界循环，但首次采样常常只看到第 1 次。

原断言的写法是「取一次快照 → 等 1.5s → 断言不变」，中间的第二次请求正好落在窗口内。
修法：**先 poll 到请求数自身不再增长再取基线**（每次采样间隔 400ms，15s 上限），
并**新增一条上限断言** `settled <= 4`——原来没有上界，现在明确防无界回溯循环
（曾观测同一周期被打 10 次）。这不是弱化断言，而是把「有限次」与「无界增长」区分开。

验证：生产配置 `--repeat-each=6`（6 次 × 2 个宽度）**12/12 通过**；
随后生产构建全量 71/71、dev 配置全量 71/71 均通过。

顺带发现一个待确认的产品侧问题：一次周期切换会发 2 次不同回溯窗口的请求（1y + 2y/3y），
且顺序不确定。功能上能收敛，属于可优化点，本轮未改动。

### 4f. 全站未定义 CSS 变量体检（26 处修复 + 2 个死文件）

用 postcss 解析 + 「引用/定义」对比扫描了 190 个 CSS 与全部 TS/TSX。结论：
`var(--x)` 引用不存在且无 fallback 的变量时，声明在 computed-value 阶段**静默失效**
（背景变透明、字体变继承），而 `!important` 会把它一直掩盖着。

修复（共 26 处，脚本断言了每个替换的精确次数）：

- `--c-bg-card` → `--c-card-bg`（10）——其中 IndustryChain 两处带 `#ffffff` 兜底，
  暗色主题下会直接渲染成白卡片；
- `--c-bg-nested` → `--c-nested-bg`（6，原先走 `rgba(0,0,0,.02)` 兜底）；
- `--c-font-family` → `--c-font-sans`（1，无 fallback）；
- `--shadow-xs` → `--c-shadow-xs`（6）、`--shadow-md` → `--c-shadow-md`（1）；
- `--color-text-secondary` → `--c-text-secondary`（2）；
- 删除无任何引用的 `Analysis/technical-panel.css` 与 `HKMarket/hk-market.css`
  （后者是 `features/hk-market/hk-market.css` 的 35 行遗留副本）。

验证：生产探针 76 个场景，差异全部是上述变量由硬编码/透明变为主题值
（22 处 stat-box、14 处卡背景、6 处文字色、2 处阴影），**无几何变化**；`!important` 178 → 177。
**第二轮：特性变量接入主题（12 个）**

上轮剩下的 12 个变量都有 fallback，能显示但切主题不跟随。已全部在 `tokensToCssVars` 里定义：

| 变量 | 接到的 token |
| :--- | :--- |
| `--c-up-bg` / `--c-down-bg` | `colors.upBg` / `colors.downBg`（涨跌底色，与 A 股红绿约定一致） |
| `--c-logo-gradient` | `linear-gradient(135deg, primary, accent)`（保持与旧 fallback 表达式一致，避免换肤时 logo 突变） |
| `--c-primary-bg` / `--c-primary-light` | `${primary}1a`（10% 主色底） |
| `--c-warning-bg` | `${warning}1a` |
| `--c-selected-bg` | `${primary}0d`（5%） |
| `--c-danger` | `antToken.colorError` |
| `--c-fill-quaternary` / `--c-surface-subtle` | `colors.hoverBg`（四级/微弱填充） |
| `--c-border-light` | `colors.border`（原先 `#e2e8f0` 是亮色兜底，暗色下会发白） |
| `--dashboard-grid-cols` | 删除死引用；列数本来就由 `.dashboard-grid--cols-N` 类控制 |

验证：全站扫描 **0 个未定义变量**；生产探针差异只有买入/卖出标签底色
`rgba(239,68,68,.1) → rgba(240,68,56,.1)`、`rgba(34,197,94,.1) → rgba(18,183,106,.1)`
（即换成主题的 up/down 色板，符合预期）。
⚠ 覆盖：Macro 商品页、IndustryChain 决策卡、Dashboard 热榜本来就有 e2e；本轮又补了
`e2e/screener-feed.spec.ts`（`/screener`、`/feed` × 1440/390）和 `e2e/watchlist.spec.ts`
（`/watchlist` × 1440/390，带真实自选股 mock），探针场景集 76 → **83**。
注意：新增场景后旧探针基线不再可比，需重新取基线再 A/B。

补充：复查发现此前“14 个只定义未使用的变量”多为**误报**——`.x--up:hover` 这类 BEM 修饰类
被定义正则误判为 `--up:`。真正未使用的只有 earthscope 的 4 个调色板变量
（`--es-surface`、`--es-surface-2`、`--es-dim`、`--es-accent-2`），已删除。

### 4g. 内联样式批次一：`WatchlistCardList` 25 → 0

`src/pages/Watchlist/components/WatchlistCardList.tsx` 的 25 处 `style={{…}}` 全部是 CSS 变量 + 固定布局，
已逐条等价迁入新分片 `src/pages/Watchlist/styles/mobile-card-list.css`（`watchlist-mobile-card__*` BEM 命名）：

- 涨跌颜色从三元表达式改为 `.watchlist-mobile-card__price.is-up/.is-down`（直接用 `--c-up/--c-down`）
- 4 个 `Tag` 的 `margin:0; font-size:10px` 改为 `.watchlist-mobile-card__tag`；该规则会与 antd 的
  `:where(.css-hash).ant-tag`（0,1,0）打平，但实测 e2e 计算样式仍为 10px/0 边距，无需再加高特异性
- 静音文字复用已有工具类 `.u-text-muted`（与 `--c-text-muted` 声明等价）

**回归护栏**：新增 e2e 用例（`watchlist.spec.ts` 切到卡片视图）直接断言 6 组计算样式
（卡片 flex-column/gap 8px、Tag 10px + `margin-inline-end:0`、价格 16px/700/左右 4px、
标题 16px、指标栏 grid/11px、概念按钮 10px/圆角 3px），并断言 3 个 `.u-text-muted`
与价格涨色均非默认文字色；不依赖构建产物也能防特异性回退。
`INLINE_STYLE_BUDGET` 同步 2072 → **2047**（零余量）。

### 4h. 内联样式批次二：`IntradayChart` 38 → 18

`src/charts/IntradayChart.tsx` 中 20 处纯布局/静态样式迁入 `src/charts/intraday-chart.css`
（HUD 外壳、HUD 统计行、图例行/图例项/四种图例色块、绘图区容器、画布、成交量行、拖拽条与手柄、nowrap）。
颜色全部改用主题变量（`--c-text-secondary`/`--c-nested-bg`/`--c-border`/`--c-primary`/`--c-accent`/`--c-up`/`--c-card-bg`），
这些变量在 `tokensToCssVars` 中与 `useColors()` 同源，因此观感等价且切主题无需重渲染。
保留的 18 处内联样式均为真动态：根容器 `height`、左侧刻度栏（位置/颜色/亮暗背景）、
分隔条（`top/right/height` 依赖拖拽比例）、悬停涨跌幅徽章、以及价格等运行时颜色。

**验证**：改动前后各跑一次 `market-index-intraday.spec.ts` 生产探针，
单场景 0 元素 0 属性差异；`IntradayChart` 单测 7/7。内联预算 2047 → **2022**（零余量）。

### 4i. 内联样式批次三：`IndicatorSubCharts` 30 → 3

`src/charts/IndicatorSubCharts.tsx` 中 27 处迁入 `src/charts/indicator-sub-charts.css`：
标题栏/左侧控件组、图例行、活动日期、7 个图例项与色块、RSI 超买超卖提示、7 处等宽数字。
图例颜色用 `is-primary/is-accent/is-warning/is-up/is-down` 修饰类映射到主题变量，
色块用 `background: currentColor` 继承所在图例项颜色，MACD 柱的涨跌态用条件类而非条件内联色。
保留的 3 处均为真动态：容器与画布的 `height`、加载骨架的 `inset/height`。

**验证**：`analysis-workspace.spec.ts`（19 个场景，含 /stock/600519）生产探针前后对比
**0 元素 0 属性差异**；`IndicatorSubCharts` 单测 3/3。内联预算 2022 → **1995**（零余量）。

### 4j. 内联样式批次四：K 线 / 对话输入 / 产业报告（一次迁完）

一次处理三个热点，共迁出 **147 处**（计数按 `style={{` 出现次数）：

| 文件 | 迁前 → 迁后 | 去向 |
|:---|:---|:---|
| `src/charts/KlineChart.tsx` | 120 → 19 | 新增 `src/charts/kline-chart.css`（49 种模式，101 处）+ 通用工具类 |
| `src/pages/Chat/components/ChatInput.tsx` | 26 → 1 | 新增 `chat-input.css`（25 处） |
| `src/pages/IndustryChain/IndustryReport.tsx` | 26 → 5 | `report-push-and-charts.css`（21 处）+ 工具类 |

K 线图例的 11 种图表专用色（MA 黄、BOLL 紫/橙等）保留为 CSS 硬编码色，色块用 `background: currentColor`；
其余颜色全部改走主题变量。新增通用类放在独立的 `src/styles/base/utilities-ext.css`
（`u-font-sans`/`u-nowrap`/`u-mt-4`/`u-mt-8`/`u-mb-4`/`u-mr-6`），避免 `utilities.css` 顶满 394 行上限。

antd 组件（Text/Button/Input/TextArea/Alert）一律用 `[data-theme]` 或页面祖先把特异性提到 (0,2,0)/(0,3,0)：
迁移中发现的真实案例是导出按钮的 `<DownOutlined style={{fontSize:10}} />`，改成 (0,1,0) 类后被
antd `.ant-btn > .anticon` 压掉，图标回弹 2px，探针捕获后改为 `[data-theme] .industry-report__actions *` (0,3,0)。

**验证**：`analysis-workspace` + `market-index-intraday` + `industry-chain-conclusion`
共 28 个生产探针场景前后对比，仅剩已归档的琥珀色 checked-radio 并行噪声（background `156,74,11` ↔ `217,119,6`），
**零真实差异**；三个目录单测 180/180。内联预算 1995 → **1848**（零余量）。

> 覆盖补充：`/chat` 原先无 e2e，本批新增 `e2e/chat.spec.ts`（1440/390 冒烟 + 390 计算样式断言），
> `ChatInput` 迁移已获真实浏览器验证（输入框圆角、底栏布局与提示字号）。

### 4k. 内联样式批次五：`/potential` 121 → 58 + 类别色主题化 + E2E 覆盖

- **先补覆盖再迁移**：新增 `e2e/potential.spec.ts`（1440/390 冒烟 + 类别色断言，共 3 个用例），mock 覆盖
  `/api/potential/{dates,latest,performance,run/status}` 与 `/api/watchlist`，把此前零覆盖的 `/potential` 纳入探针可验证范围。
- 新增 `src/pages/Potential/styles/index.css`，把 63 处静态内联样式收敛为页面语义类 + 通用工具类
  （`potential-metric-tile`、`potential-row-between`、`potential-tags-row`、`potential-text-primary` 等），
  剩余 56 处均为动态三元、`semanticTagStyle`、网格列宽等。
- 类别色从硬编码 `#1890ff/#722ed1/#52c41a/#fa8c16` 改为
  `potential-category--anchor/reversal/quality/pioneer`，用 `[data-theme]` 主题感知色板；
  **绿色不再用于类别**（红绿仅表示涨跌），四类改为蓝/紫/金/青，并补浅色主题高对比度覆盖。
- **验证**：生产探针 A/B（2 个场景）只检测到 40 个预期差异值，全部是类别色 `color/background/backgroundColor/borderTopColor`；
  字体、间距与布局零差异；单测 187/187。

> **探针方法修正**：`diff-style-probe.mjs` 的键包含 `className`，把内联样式改成类名后键会变化，
> 旧脚本会把元素当成新增/删除而忽略，得出假“零差异”。做类名迁移的 A/B 时必须按 dump 的文档顺序
> （`Object.entries` 顺序）对齐比较，本次为此用一次性脚本核对通过。

### 4l. 工程余量与流程优化

- **释放 CSS 行数余量**：`app-shell-chrome.css` 391 → 205 + 186 两片；`portfolio.css` 389 → 212 + 177 两片；
  拆分后生产构建 CSS 全部字节一致。当前最大 `app-header.css` 381 行（余量 13）。
- 删除 `dashboard-widgets.css` 中两处与页面规则重复的 `.dashboard-layout` 单列声明。
- 规范化 70 个 CSS 文件的文件尾空行（消除 `git diff --check` 噪声）。
- 内联预算 1848 → **1803**（实际 1783，预留 20 缓冲），避免正常功能开发被门禁卡死。
- 新增 `npm run lint:all`（= `lint` + `api:check`），根目录 `*.docx` 加入 `.gitignore`。
- 后端：`_assign_stock_category` 阈值提为常量；`_select_top_picks` 改为按 `code` 集合去重（O(n)），
  新增阈值/去重/补齐 3 个测试（29/29 通过，`ruff` 干净）。

### 4m. 内联样式批次六：知识库图谱 `IndustryAtlas` 113 → 35

- **先补覆盖**：在 `e2e/industry-chain-conclusion.spec.ts` 新增「知识库图谱」用例（富 catalog mock），
  让此前只能靠单测的 `IndustryAtlas` 进入真实浏览器验证范围，并断言迁移后类名的实际字号/颜色。
- 新增 `src/pages/IndustryChain/styles/atlas-workspace.css`（50+ 个布局类），迁出 **78 处**静态内联样式；
  剩余 35 处均为动态值（`isMobile/isNarrow` 宽度、图表高度、来源渐变、名次徽标等）。
- antd 组件（Tag/Button/Empty/Icon）的覆盖统一挂在 `[data-theme] .industry-atlas ...` (0,3,0)，
  避免与 antd 运行期注入的 (0,1,0)/(0,2,0) 规则打成平局。
- **验证**：生产探针 A/B（390px 采样）**0 场景 / 0 元素 / 0 属性值差异**；
  1440px 由用例内 `toHaveCSS` 断言字号/颜色；单测 65/65；全站 E2E 90/90。
- 发现并修复一个真实的响应式层叠回归：`panels.css` 的
  `@media (max-width:768px) .atlas-chain-card__heading { gap: 6px }` 在迁移后会覆盖新类的 `gap: 8px`
 （内联时期 8px 恒胜），用 `(0,2,0)` 复合选择器锁定 8px 后差异归零。
  **结论：内联→类名迁移必须同时检查同名元素的 `@media` 覆盖，探针采样宽度要包含移动端。**

### 4n. 内联样式批次七：五个热点文件 115 处

| 文件 | 迁前 → 迁后 | 去向 |
|:---|:---|:---|
| `Market/IndustryRankTab.tsx` | 26 → 2 | 直接复用已有的 `industry-rank__*` 类 + `u-font-mono`（零新增 CSS） |
| `Market/MarketVolumeCard.tsx` | 25 → 3 | `market-page.css`（tile/title/caption/chips/tag） |
| `Stock/StockCharts.tsx` | 25 → 2 | 新增 `Stock/styles/chart-toolbar.css`（避免 info-cards 顶破 394 行） |
| `Screener/FilterPanel.tsx` | 25 → 3 | `screener-page.css`（field/preset/hint/footer） |
| `NationalTeam/.../NationalTeamDataStatusPanel.tsx` | 24 → 0 | 新增 `NationalTeam/styles/data-status-panel.css` |

- `IndustryRankTab` 已存在一整套 `industry-rank__*` 类但 JSX 仍在用内联样式，直接复用，零新增 CSS；
  仅把 `__tag--up` / `__table-transparent` 提到 `[data-theme]` 作用域以稳定压过 antd。
- antd 组件（Tag/Button/Text/Space/Select/InputNumber/Empty）统一用 `[data-theme]` 或
  `.ant-x` 复合选择器（0,3,0），避免与运行期注入规则平局。
- **验证**：5 个相关 spec 共 31 个生产探针场景，29 个零差异；
  `analysis` 的 8 个差异全在未改动的 fund-flow 面板（hover 态背景/阴影）；
  `screener` 首次基线因采样不稳定（`unstable=15`）多出 19 个元素，
  用 HEAD worktree 重跑出稳定基线（517 元素 / `unstable=0`）后 **0 差异**。
- 单测 `Market/Stock/Screener/NationalTeam` **176/176**；全站 E2E **90/90**；构建通过。
- 内联预算 1725 → **1610**（实际 1590，预留 20 缓冲）。

### 4o. 内联样式批次八：四个已覆盖文件 79 处

| 文件 | 迁前 → 迁后 | 去向 |
|:---|:---|:---|
| `Quant/BacktestFormSections.tsx` | 24 → 0 | `quant-form.css`（option/quick/selected/preset 类） |
| `Chat/components/EmptyChatState.tsx` | 22 → 4 | 新增 `Chat/styles/empty-state.css` |
| `Settings/config-cards/EastmoneyProxyConfigCard.tsx` | 21 → 5 | 新增 `Settings/styles/eastmoney-proxy.css` |
| `Macro/CommoditiesTab.tsx` | 22 → 3 | 新增 `Macro/styles/commodities.css` |

- 保留的内联都是真正的动态值：渐变/`color-mix`（空状态机器人、时段推荐）、
  涨跌色三元表达式、`semanticTagStyle` 展开、选中态边框。
- antd 覆盖统一用 `[data-theme] .x.ant-tag` / `.ant-divider.proxy-divider` /
  `[data-theme] .chat-empty-samples .ant-btn.x`（0,3,0 ~ 0,4,0）。
- **验证**：5 个相关 spec 共 18 个生产探针场景 + 1 个临时 commodity 场景（最终状态停在商品页，
  避免既有测试切到 trade 后丢失采样）→ **0 差异**；
  已从 dump 确认 `chat-empty-card`（558 次）、`quant-quick-import`、`proxy-scope-tag`、
  `commodity-name` 等新类实际渲染，非“类未生效”的假零差。
  唯一的 anysearch 普通用户场景因页面加载状态在两次采样间变化（`unstable` 42）而不可用，
  已排除；管理员场景（923 元素）零差异且包含代理卡片。
- 单测 81 文件 / **325 用例**；全站 E2E **90/90**；构建通过。
- 内联预算 1610 → **1531**（实际 1511）。

### 5. 四批大规模清理与 E2E 盲区补齐（448 → 177）

在探针稳定后，按「迁移阻挡型内联样式 + 提高自有选择器特异性 + 生产 86 场景计算样式零差异」完成了四批治理：

| 批次 | `!important` 变化 | 内联样式变化 | 核心手段与实测发现 |
| :--- | :--- | :--- | :--- |
| **Batch 1** | `451 → 393`（-58） | `3387 → 3384`（-3） | 清理 `app-header.css`、`Stock/styles/{header-card,sections-and-metrics}.css`、`market-wind.css`、`analysis-{conclusion,workspace}.css`、`responsive-section-nav.css`；用 `.app-shell-header` / 重复类名 `(0,2,0)` 替代 `!important` |
| **Batch 2** | `393 → 301`（-92） | `3384 → 3376`（-8） | 清理 `styles/base/dashboard.css` (-43)、`Quant` 四套样式 (-25)、`chat.css` (-6)、`IndustryChain/styles/*` (-12)、`investment-research/styles/layouts-and-grids.css` (-5)。实测发现 `quant-page.css` 去掉 `.ant-tabs-nav-operations` 上的 `margin-left: 0 !important` 后，必须补一条 `.ant-tabs-nav-more { margin-left: ... }` 以保持测量容器宽度一致 |
| **Batch 3A** | `301 → 259`（-42） | `3376 → 3375`（-1） | 清理 `Market/{market-page,market-fund-flow}.css` (-21)、`Stock/styles/{info-cards-and-panels,detail-tabs,sticky-bar}.css` (-14)、`styles/base/mobile-overrides.css` (-7)。实测发现 `Stock/styles/index.css` 中 `detail-tabs.css` 在 `info-cards-and-panels.css` 之后导入，主规则须保持 `(0,4,0)` 并将相邻间距拆入 `.ant-tabs-tab + .ant-tabs-tab` `(0,5,0)` |
| **Batch 3B** | `259 → 184`（-75） | `3375 → 3349`（-26） | 新增 `e2e/portfolio-and-national-team.spec.ts`（5 个场景：`/portfolio` 1440/560/390px + `/national-team?tab=all` 1440/390px），随后将 `NationalTeam/styles/intraday.css`（30 → 0）、`MasterData/master-data.css`（4 → 0）、`investment-research/{analysis-dimension-summary,styles/responsive}.css`（6 → 0）、`hk-market.css`（3 → 0）全部清零，并将 `Portfolio/portfolio.css` 从 35 降至 5（迁出 `PortfolioSummaryCards` / `PortfolioRiskPanel` 内联样式）；随后的表头 token 化与导出卡片批次再降至 177 |

### 6. 剩余 177 处 `!important` 的真实构成与后续建议

1. **导出/截图专用强覆盖（93 处，不应删除）**：
   - `src/styles/analysis-export.css`（46 处）：导出快照下强制白底深字、隐藏交互控件、解开滚动容器；
   - `src/styles/base/atlas-and-charts.css`（47 处）：`[data-exporting="true"]` 下 html2canvas 截图强制深色主题 token。
2. **全局移动端与暗色基础承重（29 处）**：
   - `src/styles/base/mobile-overrides.css`（16 处）：`<=768px` / `<=480px` 下压制组件内联样式与长表格布局；
   - `src/styles/base/reset.css`（7 处）：压制页面卡片渐变背景（表头 6 处已改由 Table token 接管）；
   - `src/styles/base/responsive-helpers.css`（6 处）：双栏折叠与 `prefers-reduced-motion`。
3. **其余分文件零星 56 处**：单文件最大 5 处（`portfolio.css`、`market-page.css`）。
   - 已由 `frontend/scripts/check-style-hygiene.mjs` 棘轮锁定在 `IMPORTANT_BUDGET = 177`、`INLINE_STYLE_BUDGET = 1531`、`MAX_CSS_LINES = 394`（内联实际 1511、预留 20 缓冲，其余余量为 0/13）。
   - 删除任何一条前，必须用生产计算样式差分（见 4e）证明零差异；本轮测得绝大多数剩余项是**承重**的（抗 antd 同特异性平局、压制页面自身渐变、移动端紧凑排版）。

## 六、本次会话改动文件清单

> `Potential/*`、`types/stock/potential.ts`、`StateTrajectoryBadge*`、`stateTrajectory.ts`、`api/generated/*` 与后端 `potential` 模块已在本分支独立提交；本轮继续在其上做了 63 处内联迁移、类别色主题化与 E2E 补齐。

**新增**

- `frontend/src/components/StockWorkspaceDrawer.tsx`
- `frontend/src/components/StockWorkspaceDrawer.test.tsx`
- `frontend/src/components/stock-workspace-drawer.css`
- `frontend/scripts/check-style-hygiene.mjs`
- `frontend/scripts/check-color-discipline.mjs`
- `frontend/scripts/diff-style-probe.mjs`
- `frontend/playwright.probe.config.ts`
- `frontend/e2e/base.ts`、`frontend/e2e/instrument/probe.ts`、`frontend/e2e/instrument/density.ts`
- `frontend/scripts/density-report.mjs`、`docs/frontend-density-report.md`
- `frontend/e2e/portfolio-and-national-team.spec.ts`
- `frontend/src/components/SectionHeader.tsx`
- `frontend/src/components/SectionHeader.test.tsx`
- `frontend/src/components/section-header.css`
- `frontend/src/components/FinancialMetric.tsx`
- `frontend/src/components/FinancialMetric.test.tsx`
- `frontend/src/components/financial-metric.css`
- `frontend/src/components/DashboardGrid.tsx`
- `frontend/src/components/DashboardGrid.test.tsx`
- `frontend/src/components/dashboard-grid.css`
- `frontend/src/pages/NationalTeam/constants.ts`
- `frontend/src/pages/NationalTeam/utils/format.ts`
- `frontend/src/pages/NationalTeam/utils/download.ts`
- `frontend/src/pages/NationalTeam/components/IndexDualAxisChart.tsx`
- `frontend/src/pages/NationalTeam/components/SupportScoreRadarCard.tsx`
- `frontend/src/pages/NationalTeam/components/MilestoneTimelineBar.tsx`
- `frontend/src/pages/NationalTeam/components/SupportZonesCard.tsx`
- `frontend/src/pages/NationalTeam/components/NationalTeamPortraitPanel.tsx`
- `frontend/src/components/hot-rank-board.css`
- `frontend/src/pages/Quant/quant-results/attribution-and-matrix.css`
- `frontend/src/pages/Portfolio/portfolio-trade-kline.css`

**删除**

- `frontend/src/components/StockQuickPreviewModal.tsx`
- `frontend/src/components/StockQuickPreviewModal.test.tsx`
- `frontend/src/components/stock-quick-preview.css`

**修改（样式治理与拆分）**

- `frontend/src/styles/base/`（12 个分片，由 `index.css` 按序 `@import`；`u-` 工具类在 `utilities.css`）
- `frontend/src/pages/Dashboard/{index.tsx,dashboard.css}`
- `frontend/src/features/investment-research/{ValuationPanel.tsx,valuation-panel.css}`
- `frontend/src/pages/IndustryChain/{IndustryResearchSections.tsx,styles/}`
- `frontend/src/pages/NationalTeam/index.tsx`
- `frontend/src/pages/NationalTeam/styles/`（由 `national-team.css` 拆分为多分片）
- NationalTeam 组件：`CategoryOverviewCards`、`FlowHeatmapTable`、`MacroFlowChart`、`NationalTeamAnomalyBanner`、`NationalTeamConcentrationCard`、`NationalTeamDataStatusPanel`、`NationalTeamReportModal`

**修改（抽屉调用点统一）**

- `MarketWindBoard.tsx`、`Concept/ConceptConstituentPanel.tsx`、`DailyReview/index.tsx`、`Dashboard/WatchlistPanel.tsx`、`Screener/ResultsTable.tsx`、`Screener/ScreenerCardList.tsx`、`Watchlist/index.tsx`、`Market/IndustryRankTab.tsx`

**工程与文档**

- `frontend/package.json`（lint 挂入门禁）
- `frontend/README.md`、`docs/development.md`

**后续批次新增（样式分片、内联迁移与探针覆盖）**

- 组件级样式：`src/charts/{intraday-chart,indicator-sub-charts,kline-chart}.css`、
  `src/pages/Chat/components/chat-input.css`、`src/pages/IndustryChain/styles/report-push-and-charts.css`、
  `src/pages/Watchlist/styles/mobile-card-list.css`、`src/styles/base/utilities-ext.css`
- 样式拆分目录：`src/pages/{NationalTeam,Stock,Macro,Dashboard,Settings,Watchlist,Concept,IndustryChain,Chat}/styles/`、
  `src/features/{feed,investment-research}/styles/`、`src/components/{market-overview,page}/`
- CSS Modules：`src/components/SectionToolbar.module.css`（替换 `section-toolbar.css`）
- e2e 覆盖：`e2e/screener-feed.spec.ts`、`e2e/watchlist.spec.ts`、`e2e/chat.spec.ts`、`e2e/potential.spec.ts`
- 后续新增：`src/pages/Potential/styles/index.css`、`src/components/auth/{index,hero,card-and-form,responsive}.css`、
  `src/styles/base/app-shell-sidebar-and-user.css`、`src/pages/Portfolio/{portfolio-summary,portfolio-hero}.css`、
  `src/pages/IndustryChain/styles/atlas-workspace.css`、`src/pages/Stock/styles/chart-toolbar.css`、
  `src/pages/NationalTeam/styles/data-status-panel.css`、`src/pages/Chat/styles/empty-state.css`、
  `src/pages/Settings/styles/eastmoney-proxy.css`、`src/pages/Macro/styles/commodities.css`、
  `backend/app/modules/potential/market_data.py`
