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
