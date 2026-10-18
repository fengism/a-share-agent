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

- `tools/packs/**`、`skills/packs/**`
- `agents/profiles/**`、`agents/prompts.py`、`agents/catalog.py`、`agents/service.py`
- `tools/registration.py`、`skills/catalog.py`、`bootstrap.py`
- `adapters/**`
- `public.py`：默认 Research Runtime 与 web-search 兼容入口

这些文件可以导入宿主业务、数据源、浏览器和配置；抽取独立包时由宿主保留。


## 文件化 Skill（Phase 1）

内置 Skill 现在由 `app/agentic_integration/skills/definitions/<name>/SKILL.md`
加载，运行时仍构造同一个 `Skill` dataclass，行为与 Python packs 保持一致。

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
- Phase 1 保留 Python packs 作为 parity/rollback；`list_python_skills()` 与
  `load_builtin_skills()` 的字段必须完全一致

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
