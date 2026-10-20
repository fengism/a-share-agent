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
- `chat_max_initial_tools` 限制首轮工具**数量**（默认 0=不限制），被截掉的工具仍可通过
  `load_skill` 获得
- `chat_max_initial_active_skills` 控制初始工具集（默认 3）：
  - `-1`：所有 active Skill 的工具
  - `0`：不预加载数据工具，只给 `load_skill`
  - `N`：前 N 个 active Skill 的工具
- 首轮工具清单**跟随 Skill 的相关度顺序**（`_selected_skills` 保留调用方顺序）；集合输入
  退回注册顺序以保证确定性（prompt 前缀缓存依赖顺序稳定）。顺序错了会被上限放大成事故：
  按错误顺序截断会先把 `web_search` 截掉
- 首轮工具 schema 是 prompt 的最大单项（14 个工具约 8.8k 字符），`chat_max_initial_tools=8`
  可压到 2.7k（−69%）；`chat_max_initial_active_skills` 限的是 Skill 数，不是工具数
- active Skill 按 `match_score` 排序；股票代码/名称、URL、Twitter 会获得高优先级
- `enabled_tool_names` 仍覆盖全部 enabled Skill，供 `load_skill` 动态扩展
- `SKILL.md` 的 `core_tools` 声明首轮工具；未声明的工具在 `load_skill` 后从下一轮起可用
  （`chat_skill_core_tools_enabled=false` 回退为全部 `tools`）
- core 漏工具观测：运行时记录 `skill_core_tool_missed:<tool>`、`skill_load_after_initial:<skill>`、
  `tool_called:<tool>`；用 `python -m scripts.analyze_skill_core_misses <metrics.json>`
  同时给出提升（miss 多）与降级（core 但从未被调用）建议
- 专业 Agent（technical/fundamental/news/risk/macro）按 `profile.skill_names` 注入 Skill 规则；
  `chat_agent_skill_instructions_enabled=false` 可关闭

#### 标的消歧（Layer C）

能看出在问某只股票、却看不出是哪只（"这票怎么样"）。两条路径都会投递消歧指令：

| 路径 | 投递方式 |
| --- | --- |
| 通用 Agent | `STOCK_RESOLUTION_INSTRUCTION` 前置到 `tool_selection_prompt` |
| 专业 Agent（编排） | `Orchestrator._task_instruction` 按 `allowed_tools` 精确投递 |

投递只在任务真的能调用 `search_stocks` 时发生——`stock_analysis` 规则里写着
「仅有名称或代码不完整时先调用一次 search_stocks」，而**所有个股域 profile
（technical/fundamental/news/risk）必须带这个工具**，否则模型被要求调用一个它没有的工具
（`tests/agentic/test_sub_agent_resolution.py` 锁住这条）。宏观 Agent 不针对个股，不带它。
指令文案在 `app/modules/chat/general_agent.py` 单点定义，两条路径复用。

未来打成 wheel 时需要把 `definitions/**/SKILL.md` 加入 package-data；当前
Docker/源码运行会直接复制整个 `app` 目录。

## Prompt 前缀与预算

多轮 Agent 每轮重发同一前缀，供应商的 prompt/KV 缓存只看最长公共前缀，因此有两条不变量：

1. **静态在前、动态在后**：system prompt 里 `system_prompt` → Skill/工具规则 → 运行时时钟
   （`## 运行时日期与时间`）必须最后。时钟放在中间会让它之后的每一个 token 都不可缓存。
   `app/agentic/research.py` 的 `build_research_system_prompt()` 同样把时钟放最后。
2. **轮内只追加**：`state.messages` 只允许在尾部增长。研究节奏提示（search guidance）改为
   内容变化时追加新消息，而不是原地改写早期消息（原地改写会让它之后的全部历史失效）。

预算分三层，避免“每个上限都不超，总和却失控”：

| 配置 | 管什么 | 默认 |
| --- | --- | --- |
| `chat_max_history_characters` | 回灌历史总量（单条上限同此值，`AgentMessage` 协议上限 100k） | 40000（上限 200000） |
| `chat_max_tool_context_characters` | 工具结果 | 60000 |
| `chat_max_prompt_characters` | system+历史+工具结果总和 | 0（不启用） |

`chat_max_prompt_characters>0` 时，`_bound_tool_context_for_prompt_budget()` 用
「总上限 − 已占用 prompt 字符」反推工具结果还能用多少，并保留下限 4096 字符；
触发时记录 `agent_prompt_budget_reduced` / `agent_prompt_budget_exceeded`。

## 热路径 JSON 预算

一次请求里每条工具结果会被解析多次：上下文截断要 `json.loads` 整包，紧接着证据判定又要
再解析同一份内容。`serialize_context_results_detailed()` 把截断时那次 decode 的结果复用出去
（`_has_meaningful_value(envelope)`，纯内存遍历），`EvidenceState.from_content(acquired=...)`
因此不再二次解析。

实测（8 工具 × 5 轮、每条结果 46k 字符的合成请求，cProfile）：

| 阶段 | 每条结果 `json.loads` | per-run CPU |
| --- | --- | --- |
| 优化前 | 3 次（内容 ×2 + 上下文 ×1） | 11.4 ms |
| 优化后 | 2 次（内容 ×1 + 上下文 ×1） | 7.3 ms（−36%） |

输出逐字节不变（`test_tool_context_serialization.py` 里 `serialize_context_results` 与
detailed 版本的等价断言）。剩下两次解析都是必要的：一次是真正的截断，一次是对**已截断**
（更小的）上下文字符串判可见性。

## 跨请求工具缓存

`SharedToolCache` 只在单个 `AgentExecutionContext` 内去重，所以 `ToolPolicy.cache_ttl_seconds`
以前只对一次请求生效。`app/agentic/tools/process_cache.py` 把它扩展到进程级，但准入很窄：

| 条件 | 原因 |
| --- | --- |
| `scope == "public"` | `scope="user"` 结果依赖用户私有配置，绝不能共用户共享 |
| `freshness in {daily, static}` | 实时/准实时数据不跨请求复用 |
| `cache_ttl_seconds > 0` | 显式选择不复用 |
| `deduplicate_in_batch` | 批内都不能合并的副作用调用，更不能跨请求抬回来 |
| 非 error、≤24k 字符 | 一次上游抖动不能被缓存成普遍故障；缓存不能变成内存放大器 |

TTL 取 `min(policy.cache_ttl_seconds, 900s)`：`freshness="static"` 可以声明 1 小时，
但错误声明在单请求去重时只影响一次对话，跨请求后会变成全局陈旧，用 15 分钟钉住炸开半径。
上限 512 条 + LRU，默认开关 `CHAT_TOOL_PROCESS_CACHE_ENABLED=true`。
无执行上下文（单测/抽取使用）时整体禁用。

## 调研循环的两层结构

```
research.py  run_agentic_research    外层：按证据需求清单决定是否再跑一轮
   ↓ AgentResearchSession.run
agentic_integration/adapters/research.py
   ↓ agent_executor.run
agents/executor.py                   内层：按「模型不再要工具」结束
```

两层管的是**不同**的停止条件，因此不合并；重复的是横切逻辑，已抽出：

| 纯决策 | 位置 | 说明 |
| --- | --- | --- |
| `missing_requirements()` | `research_policy.py` | 哪些证据维度还没满足 |
| `select_gap_tools()` | 同上 | 缺口轮下发哪些工具（正文缺口会带上发现类工具） |
| `should_continue()` | 同上 | 新增证据≠缺口缩小；没缩小就停，避免空转 |
| `followup_reserve()` | 同上 | 首轮预留 8 次给补查，后续轮释放 |
| `build_gap_message()` | 同上 | 缺口轮消息 |
| `normalize_round_result()` | 同上 | 致命原因抛出；失败/提前收尾清空摘要 |

`research_policy.py` 无 I/O 无事件，覆盖 100%；`research.py` 只剩编排（89%）。

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

## 抽取现状（已由测试锁住）

| 事实 | 验证方式 |
| --- | --- |
| 核心 36 个模块的传递依赖只到 `app.domain.*`（`agent_llm`/`agent_protocol`/`async_utils`/`errors`/`llm`） | `test_core_transitive_domain_dependencies_stay_inside_the_contract` |
| 运行时拉进的宿主模块为**零**（allowlist 为空集） | `test_core_runtime_import_surface_has_no_new_host_leaks`（子进程探针） |
| 三方依赖只有 `pydantic`（其余全部 stdlib） | 同上（静态扫描） |

已知阻塞项：**无**。

已修复的两个障碍：

1. `app/__init__.py` 曾经在包导入时 `import app.infrastructure.javascript_runtime` 并注册
   py-mini-racer 的 atexit 兜底 guard —— 任何 `import app.*` 都被拖进 `app.infrastructure`。
   该 guard 现在挂在真正 `import akshare` 的两个数据源包上
   （`app.infrastructure.providers.akshare` / `providers.sina.hk`），覆盖面不变；
   `app/__init__.py` 已清空。子进程探针的 `KNOWN_HOST_LEAKS` 现在是**空集**。
   顺带剔除了一个隐形开销：旧 guard 在解释器退出时无条件 `import py_mini_racer`
   （V8 二进制，实测 **+72ms/进程**），现在先查 `sys.modules`，从未用过 AkShare 的
   进程退出时零成本。
2. `app/domain/industry_chain.py` 曾经 `import app.core.market`（domain -> core
   反向依赖）。`market_today()` 与上海时区常量已下沉到 `app.domain.timezones`，domain
   不再依赖任何其它 `app.*` 层；包级依赖环 `{core, domain}` 因此消失
   （`tests/test_domain_layer_boundary.py` + `tests/test_module_cycles.py` 锁住）。

## 后续抽取步骤

1. 将 `app/agentic` 复制为独立包，保留 `app.domain` 中的共享契约（或一起抽为
   `agentic-domain`）。
2. 宿主实现上述端口，并提供自己的 `public` 入口。
3. 将 `app/agentic_integration` 留在宿主，按需注册 Tool/Skill/Agent。
4. `app/__init__.py` 已无副作用，抽取时不需要为它做任何处理。
