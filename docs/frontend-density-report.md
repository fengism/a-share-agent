# 前端布局密度测量报告

> 范围：P2「布局密度优化」的前置测量（只测量，不改代码）。
> 数据来源：86 个真实 e2e 场景（每个用例使用各自已验证的接口 mock），桌面 50 个 / 移动 36 个。
> 样本：465 个 antd Card（small 290）、77 个 antd Table（small 52 / medium 25）。

## 结论摘要

1. **全站整体并不「过松」**：桌面 small 表格 69% 已是 8px、按钮 63% 为 24px，比 antd 默认更紧。
2. **真正的问题是密度不统一**：同一组件存在 4~6 种间距变体，视觉节奏不稳定，也无法用单一 token 统一调优。
3. 最集中的不一致来自三处：**默认 Card 的 24px（antd 默认）与项目 `--c-pad-card`（20/24）并存**、**Form 项距 24/14/8/0 混用**、**Tabs 下距 16/18/12/20/8 混用**。
4. 移动端的 5 种表格 padding 主要是**全局 `!important` 与页面级 `!important` 相互覆盖**的结果，属已知的承重规则，不在本次统一范围内。

## 测量方法

- 夹具：`frontend/e2e/base.ts` 统一挂载 `frontend/e2e/instrument/density.ts`（仅当 `DENSITY_OUT` 存在时落盘），在每个 e2e 用例结束时采集：
  - 页面 `scrollHeight`
  - Card：数量、small 数量、`.ant-card-body` 的 padding 分布（small / 默认分开）
  - Table：数量与 `small / medium / default` 分布、`.ant-table-cell` padding 分布（按尺寸分开）、行高中位数
  - Form / Descriptions / Tabs / Button / Input / Space 的间距分布
- 分析：`frontend/scripts/density-report.mjs <dumpDir>`

```bash
# 复现（在 frontend/ 下，无需修改 spec）
DENSITY_OUT=/tmp/density npx playwright test --reporter=line
node scripts/density-report.mjs /tmp/density
```

## 桌面现状（50 场景）

| 维度 | 分布（按元素计） | 判定 |
| :--- | :--- | :--- |
| 默认 Card body | `24px` 36% · `20/24` 24% · `0` 15% · `10/16/14/16` 8% · `10/14/8/14` 5% | ❌ 6 种变体 |
| small Card body | `12px` 63% · `16px` 10% · `16/20` 9% · `12/14` 6% · `8/16` 3% | ⚠️ 主值明确，长尾多 |
| small Table cell | `8/8` 69% · `7/6` 23% · `4/6` 6% · `6/8` 2% | ✅ 主值明确；`7/6` 为热榜有意收紧 |
| medium Table cell | `12/8` 100% | ✅ 一致（antd medium token） |
| Form item 间距 | `24px` 35% · `0` 27% · `14px` 22% · `8px` 16% | ❌ 4 种变体 |
| Descriptions cell | `8/16` 86% · `0` 14% | ✅ 基本一致 |
| Tabs nav 下距 | `16px` 29% · `18px` 26% · `12px` 26% · `20px` 9% · `8px` 6% | ❌ 5 种变体 |
| 按钮 height | `24px` 63% · `32px` 14% · `48px` 8% · `38px` 6% · `36px` 5% | ⚠️ 以 24px 为主（偏紧） |
| 输入框 padding | `0` 47% · `4.5/11` 43% · `0.5/7` 8% | ⚠️ 0 多为紧凑控件，需确认非缺陷 |
| Space gap | `8px` 54% · `6px` 32% · 其余 2/4/16 | ⚠️ 8 为主值，`6` 应为 `size="small"` 的误用 |

桌面页面高度 Top 8（`scrollHeight`）：

| 高度 | 路由 | 卡片（small） | 默认卡 padding | 表格（small/medium） | 行高中位 |
| ---: | :--- | :--- | :--- | :--- | ---: |
| 4395 | `/stock/600519?tab=valuation` | 10 (5) | `24px` | 1 (1/0) | - |
| 3968 | `/`（1280） | 7 (5) | `24px` | 5 (4/1) | 65 |
| 3916 | `/quant?panel=result` | 21 (21) | - | 0 | - |
| 3740 | `/industry-chain/AI算力` | 1 (0) | `24px` | 2 (2/0) | 64 |
| 3611 | `/settings?section=data-sources` | 12 (0) | `20/24` | 0 | - |
| 3117 | `/stock/600519?tab=fund-flow` | 7 (2) | `24px` | 1 (1/0) | 39 |
| 3052 | `/`（1512） | 7 (5) | `24px` | 5 (4/1) | 49 |
| 2761 | `/national-team?tab=all` | 17 (9) | `10/14/8/14` | 2 (2/0) | 29 |

仍使用 **antd 默认 24px 卡片内边距**的桌面路由共 11 个：`/`、`/stock/600519`（valuation / fund-flow）、`/industry-chain/*`、`/analysis/600519`（report / research）、`/daily-review`、`/quant?view=authoring`、`/market?tab=limit-up`。

## 移动现状（36 场景）

| 维度 | 分布 | 判定 |
| :--- | :--- | :--- |
| 默认 Card body | `12/10` 55% · `20/24` 22% · `0` 17% | 移动端有全局 12/10 覆盖 |
| small Card body | `8px` 22% · `12px` 22% · `11/9/9/9` 17% · `10px` 9% | ❌ 5 种变体 |
| small Table cell | `7/6` 52% · `6/8` 21% · `7/8` 12% · `6/6` 9% · `4/6` 6% | ⚠️ 全局 `!important` 承重，见 §归因 |
| medium Table cell | `7/6` 53% · `6/6` 21% · `7/8` 15% · `8/8` 12% | ⚠️ 同上 |
| Form item 间距 | `14px` 52% · `24px` 29% · `8px` 19% | ❌ 3 种变体 |
| Tabs nav 下距 | `16px` 50% · `18px` 20% · `12px` 10% · `8px` 10% | ❌ 4 种变体 |

## 归因

| 值 | 来源 | 处理建议 |
| :--- | :--- | :--- |
| Card `24px` | antd 默认 `bodyPadding` | Phase 1 统一到 `--c-pad-card`（20/24） |
| Card `12px` | antd small Card 默认 | 保留为 small 卡标准 |
| Table `8/8` | antd small Table token | 保留（桌面数据表标准） |
| Table `12/8` | antd medium Table token | 保留（阅读型表标准） |
| Table `7/6` | `.hot-rank-horizontal-scroll .ant-table-cell`（桌面）、`mobile-overrides.css`（移动） | 有意紧凑，保留 |
| Table `6/8` `6/6` `4/6` `7/8` | NationalTeam / investment-research / Stock / Feed 等页面级响应式覆盖 | 移动端承重规则，**不动**（探针无法验证移动 `!important` 的移除） |
| Form `24px` | antd 默认 `itemMarginBottom` | Phase 1 统一到 16px |
| Form `14px` | 页面级自定义 | 统一到 16px |
| Form `0` | 紧凑内联表单（可接受） | 保留 |
| Tabs `16/18/20` | 页面级自定义 | 统一到 12px |
| Space `6px` | 自定义 `size={6}` 或 CSS gap | 统一到 8px（`--c-space-2`） |

## 建议目标值

### Phase 1：统一到现有 token（不改设计尺度，低风险）

| 维度 | 现状 | 目标 | 实现方式 |
| :--- | :--- | :--- | :--- |
| 默认 Card body | 24 / 20,24 / 10,16,14,16 | `20px 24px`（`--c-pad-card`） | antd `components.Card.bodyPadding = 20`；保留 `styles={{ body }}` 的特例 |
| Form item 间距 | 24 / 14 / 8 | `16px`（`--c-space-4`） | antd `components.Form.itemMarginBottom = 16`；页面级 14 → 删除覆盖 |
| Tabs nav 下距 | 16 / 18 / 12 / 20 / 8 | `12px`（`--c-space-3`） | 全局 `.ant-tabs-nav` 规则统一；删除页面级 18/20 |
| Space gap | 6 / 8 | `8px`（`--c-space-2`） | 把 `size={6}` / `gap: 6px` 的用法收敛 |
| small Card | 12 / 16 / 16,20 / 12,14 | `12px` | 删除 small 卡的自定义 body padding |
| small Table | `8/8` 与 `7/6` | 保留双档 | 热榜/仪表盘用 7/6，数据页用 8/8 |

预期：桌面默认卡 6 种变体 → 2 种（20/24 与特例 0），Form 4 → 2，Tabs 5 → 1；**字号/行高/颜色零变化**。

### Phase 2：真正收紧（需设计确认）

| 维度 | 现状 → 建议 | 单卡/单页收益 |
| :--- | :--- | :--- |
| 默认 Card body | `20/24` → `16/20` | 每卡省 8px 垂直 |
| Form item 间距 | `16` → `12` | 每项省 4px |
| 页面高度 | `/stock` 4395 / `/` 3968 / `/quant` 3916 | 预计 **-3% ~ -6%**，首屏多 1~2 行 |

## 实施与验证方案

1. **改一处、测一处**：先只加 Card `bodyPadding` token，跑密度测量对比分布；再依次 Form / Tabs / Space。
2. 每次改动后跑 `scripts/density-report.mjs`，断言目标维度的分布**收敛到 1~2 个值**。
3. 同时跑生产计算样式探针（86 场景），确认差异只出现在 `padding*` / `height`，**无 font-size / color / width 变化**。
4. 背书：`npm run lint`（inline 1848 / `!important` 177 不变）、`npx playwright test`（86/86）。
5. 若某项 token 未真正落到元素（历史上 Table `headerBg` 曾经出现「配置了但没生效」），以计算样式实测为准，不以 token 配置为证据。

## 不纳入本次的事项

- 移动端页面级表格 `!important` 变体（承重规则，静态探针无法验证）。
- 按钮高度体系（24px 占 63%，需单独评估触控可用性，属交互设计而非间距）。
- 字号 / 行高 / 字重（属排版层级，已在 `docs/development.md` 固化）。
- `/chat`、`/potential` 等无覆盖或无权限改动的页面（`/chat` 已有覆盖，其余见清单缺口）。
