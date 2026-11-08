# 行业韭菜指数 (Industry Leek Index) 设计与量化规范

## 1. 概述与核心哲学

**A 股行业韭菜指数（Retail Crowding & Bagholder Risk Index）** 是一个介于 $0 \sim 100$ 的反向情绪与见顶风险预警指标（Contrarian Risk Indicator）。

在行为金融学中，散户（“韭菜”）的典型行为特征包括：
1. **追高接盘**：在股价/行业涨幅末期受舆论情绪驱动集中涌入；
2. **筹码背离**：主力（机构/大单）坚决出逃，中小散户蜂拥买入承接；
3. **被动深套**：高位滞涨放量、冲高回落，套牢盘沉重且越跌越补。

指数区间定义：
- **$75 \sim 100$ (🔥 极度接盘区 / Extreme)**：散户极度狂热、主力大幅流出、见顶回调概率极高；
- **$60 \sim 75$ (⚠️ 散户过热区 / Fever)**：跟风炒作加速、板块成交拥挤度走高；
- **$35 \sim 60$ (⚖️ 筹码均衡区 / Normal)**：多空博弈平稳、散户主力参与比例正常；
- **$0 \sim 35$ (💎 筹码出清区 / Safe)**：散户割肉离场、市场无人问津，常为左侧配置黄金坑。

---

## 2. 四维量化因子模型

$$I_{\text{leek}} = 0.30 \times S_{\text{flow}} + 0.25 \times S_{\text{guba}} + 0.25 \times S_{\text{crowd}} + 0.20 \times S_{\text{trap}}$$

### 2.1 资金博弈剪刀差 ($S_{\text{flow}}$, 权重 30%)
- **原理**：统计散户小单净买入与主力超大单流出的剪刀差：
  $$\text{Divergence} = \text{small\_net} - \text{main\_net}$$
- **数据源**：东财行业级资金流向 (`call_industry_data("industry_fund_flow")`)，覆盖 128 个申万二级行业并聚合至 31 个申万一级行业。
- **涨跌幅惩罚/奖励**：
  - 若板块涨幅 $> 1\%$ 但主力坚决撤退且散户狂买，得分追加 $+12$ 分（诱多出货特征）；
  - 若板块深跌 $> -1.5\%$ 但主力逆势吸筹且散户割肉出逃，得分扣减 $-15$ 分（黄金坑特征）。

### 2.2 东财股吧热度与异动 ($S_{\text{guba}}$, 权重 25%)
- **原理**：统计行业成分股在东财股吧热搜人气榜（`ak.stock_hot_rank_em`）与飙升榜（`ak.stock_hot_up_em`）中的上榜密度。
- **龙头锁定**：提取每个申万一级行业人气排名前 3 的代表个股，作为跟风龙头标的。

### 2.3 成交与交易拥挤度 ($S_{\text{crowd}}$, 权重 25%)
- **原理**：板块成交额占全市场总成交额的历史分位数，衡量追涨流动性是否进入过热极值。

### 2.4 高位滞涨与套牢盘风险 ($S_{\text{trap}}$, 权重 20%)
- **原理**：监测行业高换手滞涨与冲高回落幅度，识别上方密集套牢筹码的阻力压迫。

---

## 3. 架构分层与数据存储

```mermaid
flowchart TD
    DS[多源数据: 东财资金流 + 股吧人气榜 + 行情] --> Factor[四维因子计算 app/modules/sentiment/factors/]
    Factor --> Engine[综合打分服务 LeekIndexService]
    Engine --> Cache[(盘中 30s 内存 TTL 缓存)]
    Engine --> Persist[(每日收盘 JSON 归档: data/sentiment/leek_index/{date}.json)]
    Engine --> Metrics[Prometheus /metrics 导出]
    Engine --> AgentTool[Agentic 工具: get_industry_leek_index]
    Engine --> API[REST API: /api/sentiment/leek-index/]
    API --> UI[前端看板 /leek-index + 首页监控胶囊]
```

### 3.1 极简持久化策略
- **每日单文件存储**：每日收盘（15:35）自动归档单个 `{date}.json` 文件，单日存储仅约 27KB，一整年累计不超过 7MB。
- **历史回填工具**：提供 `backend/scripts/backfill_leek_index_history.py`，支持基于交易日历快速回填 15~30 天历史基线，开箱即用。

---

## 4. API 接口契约

### 4.1 全行业概览
- **路径**：`GET /api/sentiment/leek-index/overview`
- **参数**：`force_refresh: bool`（可选，默认 `false`）
- **返回**：包含 `summary`（全市场中位数、极度接盘数、过热数、出清数、整体情绪标签）以及 31 个申万一级行业的详细特征、跟风龙头与申万二级细分赛道列表。

### 4.2 单行业历史轨迹
- **路径**：`GET /api/sentiment/leek-index/history`
- **参数**：`industry_name: str`, `days: int` (默认 30)
- **返回**：该行业近 N 天的时间序列点（日期、韭菜指数、风险级别、子项拆解、行业涨跌幅），供前端绘制双轴对比曲线。

---

## 5. Agentic AI 智能体赋能

系统已注册内置工具：`get_industry_leek_index`
- **功能**：当用户在自然语言聊天中询问“哪个行业散户在接盘”、“高危追高板块”、“板块情绪过热”时，AI 自动调用该工具。
- **能力**：
  - 支持全市场宏观扫盘（自动提取 Top 5 接盘行业与 Top 3 出清行业）；
  - 支持指定行业二级细分赛道下钻（如电子 $\rightarrow$ 半导体、消费电子、光学光电子）。

---

## 6. 前端交互与设计系统规范

- **独立路由**：`/leek-index`，在导航“市场洞察”分组下。
- **跟风龙头联动**：点击代表龙头股票 Tag，直接同屏滑出 `StockWorkspaceDrawer`，快速查阅分时图与日 K 线。
- **首页监控集成**：在首页 `Dashboard` 左侧仪表栏展示 `DashboardLeekCard` 环形温度计，支持一键直达详情看板。
- **设计规范纪律**：完全遵循全站 CSS 样式卫生与 A 股红绿色彩纪律门禁（零非法内联样式）。
