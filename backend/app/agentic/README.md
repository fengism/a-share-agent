# Agentic 模块边界

目标：核心执行链路可以在不修改业务代码的前提下抽取为独立包；宿主只提供
LLM 传输、配置、指标、工具实现和业务 Agent/Tool Pack。

## Core（可独立，`app/agentic`）

- `contracts.py` / `protocol.py` / `events.py` / `messages.py` / `semantics.py`
- `agents/contracts.py` / `agents/executor.py`
- `orchestration/*`
- `runtime/*`
- `skills/contracts.py`
- `tools/{application,cache,calls,contracts,document_output,serialization,validation}.py`
- `catalog.py` / `public.py`

约束（由 `tests/test_agentic_core_boundary.py` 强制）：

- 只能依赖标准库、`pydantic`、`app.agentic.*`、`app.domain.*`
- 不得导入 `app.configuration` / `app.core` / `app.infrastructure` /
  `app.modules` / `app.api` / `app.runtime`
- 不得导入 `app.agentic_integration.*`

## Integration（宿主相关，`app/agentic_integration`）

- `tools/packs/**`、`skills/definitions/**`
- `agents/profiles/**`、`agents/prompts.py`、`agents/catalog.py`、`agents/service.py`
- `tools/registration.py`、`skills/catalog.py`、`bootstrap.py`
- `adapters/**`
- `public.py`：默认 Research Runtime 与 web-search 兼容入口

这些文件可以导入宿主业务、数据源、浏览器和配置；抽取独立包时由宿主保留。


## 文件化 Skill（Phase 1）

内置 Skill 现在由 `app/agentic_integration/skills/definitions/<name>/SKILL.md`
加载，运行时仍构造同一个 `Skill` dataclass。

```text
app/agentic_integration/skills/
├── loader.py
├── catalog.py
└── definitions/
    └── stock_analysis/
        └── SKILL.md
```

`SKILL.md` 结构：

```markdown
---
name: stock_analysis
description: 个股识别、查询与分析
triggers:
  - 股票名称或代码
activation_keywords:
  - 股票
  - 估值
tools:
  - get_stock_info
priority: 30
exclusions:
  - 不要重复调用组合工具
examples:
  - 查询茅台估值 ➔ get_stock_valuation_detail('600519')
---

## Rules

- 先确认股票代码。
- 单一维度使用对应工具。
```

约束：

- frontmatter 必填：`name` / `description` / `triggers` / `activation_keywords` / `tools`
- 可选：`priority`（默认 100）、`exclusions`、`examples`
- 正文必须且只能有一个 `## Rules`，每条规则用 `- ` 列表项
- 目录名必须与 `name` 一致
- 非法定义在启动期直接失败，并带文件路径
- `SKILL.md` 是唯一事实来源；Phase 1 的 Python packs 已移除

### 按需加载（Phase 2b）

- 通用 Agent 默认只注入 Skill 目录（description + triggers）
- 需要详细规则时调用 `load_skill(name)` 工具
- `load_skill` 的 `ToolPolicy.evidence=False`，返回的是指令，不计入数据证据
- `chat_skill_instruction_top_n` 控制自动注入：
  - `-1`：完整 rules（旧行为，回滚用）
  - `0`：仅目录 + `load_skill`（默认）
  - `N`：目录 + 前 N 个 Skill 的详细规则

### 动态激活（P2）

- 默认允许 `load_skill` 加载当前请求所有 enabled Skill，而不仅是关键词命中的 Skill
- 加载成功后，该 Skill 的工具从**下一轮**起加入 `state.tool_definitions`
- 同一轮中如果同时调用 `load_skill` 和数据工具，会先执行 `load_skill` 并扩展工具，
  再执行剩余数据工具；最终结果仍按原始调用顺序返回
- 动态加入的工具必须存在于 registry，且属于 `enabled_tool_names`
- 初始工具集仍只包含 active Skill 的工具 + `load_skill`
- `chat_skill_dynamic_activation_enabled=false` 可回退到 Phase 2b 的 active-only 行为
- `load_skill` 返回 `tools_available_next_turn=true`，并提示指令不是数据证据
- 目录对关键词命中的 active Skill 标记 `[推荐]`
- `load_skill` 使用独立预算 `chat_max_skill_loads_total`（默认 3），不占数据工具额度
- `chat_max_initial_active_skills` 控制初始工具集（默认 3）：
  - `-1`：所有 active Skill 的工具
  - `0`：不预加载数据工具，只给 `load_skill`
  - `N`：前 N 个 active Skill 的工具
- active Skill 按 `match_score` 排序；股票代码/名称、URL、Twitter 会获得高优先级
- `enabled_tool_names` 仍覆盖全部 enabled Skill，供 `load_skill` 动态扩展
- `SKILL.md` 的 `core_tools` 声明首轮工具；未声明的工具在 `load_skill` 后从下一轮起可用
  （`chat_skill_core_tools_enabled=false` 回退为全部 `tools`）
- core 漏工具观测：运行时记录 `skill_core_tool_missed:<tool>`、`skill_load_after_initial:<skill>`；
  用 `python -m scripts.analyze_skill_core_misses <metrics.json>` 按真实调用排序并给出提升建议
- 专业 Agent（technical/fundamental/news/risk/macro）按 `profile.skill_names` 注入 Skill 规则；
  `chat_agent_skill_instructions_enabled=false` 可关闭

未来打成 wheel 时需要把 `definitions/**/SKILL.md` 加入 package-data；当前
Docker/源码运行会直接复制整个 `app` 目录。

## 组合根需要注入的端口

| 端口 | 配置入口 |
| --- | --- |
| LLM 传输 | `app.agentic.runtime.llm.configure_llm_transport()` |
| 默认 Settings | `app.agentic.runtime.settings.configure_default_settings()` |
| 指标 | `app.agentic.runtime.metrics.configure_metrics()` |
| 请求上下文 | `app.agentic.runtime.context.configure_request_context_provider()` |
| 工具实现 | `app.agentic.tools.application.configure_application_tool_handlers()` |

当前宿主在 `app/agentic_integration/agents/service.py`、
`app/agentic_integration/adapters/research.py` 和
`app/runtime/agentic_tools.py` 完成注入。

## 后续抽取步骤

1. 将 `app/agentic` 复制为独立包，保留 `app.domain` 中的共享契约（或一起抽为
   `agentic-domain`）。
2. 宿主实现上述端口，并提供自己的 `public` 入口。
3. 将 `app/agentic_integration` 留在宿主，按需注册 Tool/Skill/Agent。
4. 注意：本仓库 `app/__init__.py` 有宿主机启动副作用；独立包不应复制该行为。
