# 架构与边界

本文记录后端的稳定分层约定、依赖环基线，以及两条最核心的分析链路。改动涉及跨层
依赖、公共契约或后台任务时，请先读这里。

## 分层

| 层 | 目录 | 允许依赖 | 说明 |
|---|---|---|---|
| 内层 | `app/core`、`app/domain` | 仅互相依赖 + 标准库 | 时间、代码规范化、缓存、领域模型 |
| 基础设施 | `app/infrastructure` | `core`、`domain`、`constants`、`configuration` | provider、持久化、HTTP、LLM 适配 |
| 数据层 | `app/financial_data` | 内层 + 基础设施 | 行情、财报、估值、宏观等对外数据能力 |
| 业务模块 | `app/modules/*` | 内层 + 基础设施 + `financial_data` + 共享内核 | 分析、量化、选股、潜力股、推送等 |
| Agent 核心 | `app/agentic` | 内层 + `app.domain` | 可独立抽取的 Agent 执行、编排、预算与证据契约 |
| Agent 集成 | `app/agentic_integration` | 任意（宿主适配） | 工具包、业务 Agent、默认 Research Runtime |
| 上层 | `app/api`、`app/runtime`、`app/main.py` | 任意 | HTTP 适配、后台任务、组合根 |

共享内核：`app/modules/code_normalization.py`、`import_limits.py`、
`master_data_revision.py`，允许被数据层直接引用，不视为跨层违规。

### 门禁

```bash
cd backend
python -m scripts.check_import_boundaries   # 分层 / 私有名 / 反向依赖
pytest tests/test_module_cycles.py          # 包级依赖环
```

`check_import_boundaries.py` 的 `LAYER_FORBIDDEN` 是硬规则；`KNOWN_EXCEPTIONS` 是
历史债务基线，**只减不增**。新增例外必须在评审中说明理由。

## 依赖环基线

`test_module_cycles.py` 用 AST 计算包级强连通分量，当前允许三个环：

1. `{api, runtime}`：版本解析与认证 cookie 分居两侧；
2. `{core, domain}`：内层互相引用；
3. 数据层/基础设施/若干业务模块组成的大环（本地落库仓储被数据层直接读取）。

新增环会让测试失败。数据层读取本地落库快照的历史债务当前**冻结存量、只减不增**，
不做端口化或仓储下沉。后续如果出现同一能力多数据源运行时切换等真实需求，再单独评估
数据访问架构。

每消除一条，就从 `KNOWN_EXCEPTIONS` 与 `tests/test_module_cycles.py::BASELINE`
中同步删除对应条目。

## 估值链路（`app/financial_data/stock/valuation`）

```
orchestrator（取数：目标行定位 / 同行 / 前瞻 PE）
  → profile（画像：金融 / 周期 / 成长 / 稳定 / 亏损）
  → bases（TTM、正常化盈利、现金流）
  → methods（PE / PB / PS / PEG / DCF）
  → blending（相对重估、质量调整、共识惩罚、区间与分歧）
  → detail（快照缓存、结果组装）
```

- 同行倍数按 ROE/净利率做质量调整，龙头对标同行上四分位；
- 同一股票的方法估值按当前倍数相对重估，避免财务口径混用；
- 金融/周期画像剔除不适用方法（DCF/PEG/PS）；
- `helpers.py` 中的同行质量、TTM 桥接、归一化盈利是纯函数，优先单测。

## 潜力股链路（`app/modules/potential`）

```
constants   可调参数（单一事实来源）
common      共享小工具
screening   三层候选池 + 行业统计
signals     策略族信号 + 技术质量/风险画像
themes      热门题材/行业映射与加分
fundamentals 前 60 名财务基本面重排
regime      指数趋势 + 市场情绪
service     编排：取数 → 评估 → 分散 → 持久化 → 事件
performance 5/10/20 日前瞻复盘
```

后台任务每日收盘后在 leader 节点执行；手动触发返回后台任务状态，前端轮询
`/potential/run/status`，同一交易日由 singleflight 合并，避免重复全量扫描。

`periodic_wal_checkpoint` 同时执行文件保留：扁平快照
（`potential_stocks` / `potential_performance` / `valuation_snapshots`）按 mtime 删除；
`analyses` / `industry_chains` 以「目录」为删除单位，删除后重建各自历史索引，
保证索引与文件一致。


## Agentic 边界（`app/agentic`）

目标：核心执行链路可在不改业务代码的前提下抽取为独立包。详细清单见
`backend/app/agentic/README.md`。

- **Core**：`agents/executor.py`、`orchestration/*`、`runtime/*`、工具/技能契约、
  `contracts.py` / `events.py` / `protocol.py` 等。只允许依赖标准库、`pydantic`、
  `app.agentic.*`、`app.domain.*`。
- **Integration**：`app/agentic_integration`（`tools/packs/**`、`skills/definitions/**`、
  `agents/profiles/**`、`agents/service.py`、`adapters/**`、`bootstrap.py`、注册入口）。
  可以依赖宿主业务、数据源、浏览器和配置。Skill 已支持 `SKILL.md` 文件化定义，
  `SKILL.md` 是 Skill 的唯一事实来源；通用 Agent 默认只注入 Skill 目录，
  通过 `load_skill(name)` 按需加载详细规则（指令不计入数据证据）。
  专业 Agent 按其 `profile.skill_names` 直接注入详细规则（可用
  `chat_agent_skill_instructions_enabled=false` 关闭）。
  默认允许动态激活 enabled Skill，并从下一轮起把其工具加入执行工具集，
  受 `enabled_tool_names` 白名单限制；同一轮内的 `load_skill` 会先执行并扩展工具，
  再执行剩余数据工具。`load_skill` 使用独立预算，不占数据工具额度。初始工具集只加载
  得分最高的 N 个 active Skill（`chat_max_initial_active_skills`，默认 3），且每个 Skill
  只暴露 `SKILL.md` 声明的 `core_tools`；其余工具在 `load_skill` 后从下一轮起可用
  （`chat_skill_core_tools_enabled=false` 可回退为全部 `tools`）。
  core 漏工具通过 `skill_core_tool_missed:<tool>` 与 `skill_load_after_initial:<skill>`
  指标观测，可用 `scripts/analyze_skill_core_misses.py` 分析 metrics 快照。
- **Ports**：宿主在组合根注入 LLM 传输、默认 Settings、指标、请求上下文和工具实现：
  `app.agentic.runtime.llm.configure_llm_transport()`、
  `app.agentic.runtime.settings.configure_default_settings()`、
  `app.agentic.runtime.metrics.configure_metrics()`、
  `app.agentic.runtime.context.configure_request_context_provider()`、
  `app.agentic.tools.application.configure_application_tool_handlers()`。

门禁：`pytest tests/test_agentic_core_boundary.py` 会检查 Core 文件没有导入
`app.configuration` / `app.core` / `app.infrastructure` / `app.modules` /
`app.api` / `app.runtime` / `app.agentic_integration`。新增 Core 文件时不要绕过该测试。

## 股票标的识别（Chat 路由）

`app/financial_data/stock/profile/short_names.py` 从完整股票名映射自动派生简称与拼音
首字母索引，新增股票/改名会自动跟随；词缀候选按“2 字前后缀 + 3-4 字高频前缀”自动
统计，不再维护股票简称表。`name_map.mentions_stock_target()` 分三级判断：

- 完整名 / A-B 归一 / 拼音首字母：高置信，直接视为股票标的
- 自动派生简称（如 茅台、海康、工行）：仅当消息同时包含股票语境词
  （股价 / 估值 / 新闻 / 公告 / 怎么样…）才判定，避免“友好往来”误命中
- 地名 / 行业 / 常见词不会进入简称索引

该结果同时用于 Skill 激活（`stock_analysis`）和专业 Agent 路由（`classify_message`）。
港股名称走同一机制：`app/financial_data/hk/name_reference.py` 从
`data/hk_stock_search_index.json` 派生完整名与简称，`app/modules/chat/stock_reference.py`
合并 A 股与港股判断。

## 质量门禁

`make check` 覆盖：版本一致性、ruff、模块边界、mypy、覆盖率（≥44%）、OpenAPI 产物
同步、前端测试/构建。新增 Python 文件若属于核心链路，应同步加入 `pyproject.toml`
的 mypy `files` 清单。命令明细与调试方式见 [本地开发指南](development.md)。

## 延伸阅读

- [本地开发指南](development.md) — 环境、命令、测试约定
- [配置系统开发指南](configuration.md) — 配置来源与作用域
- [数据源与降级机制](data-sources.md) — Provider 层与容错策略
- [故障排查手册](troubleshooting.md)
