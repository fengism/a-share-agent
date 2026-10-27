"""Agent 调研、LLM 生成预算、并发保护与渲染队列配置分组。"""

from __future__ import annotations

from pydantic import Field

from app.configuration.groups.base import ConfigGroup


class ResearchGroup(ConfigGroup):
    """调研/分析/聊天预算、并发上限、PDF 渲染与 provider 熔断。"""

    PREFIX = ""

    agent_research_timeout_seconds: float = Field(default=1200.0, gt=0)
    # 产业链调研预算独立于交互式 Chat/通用 Agent；针对当前产业链全链路分析复杂度升级
    industry_chain_tool_calls_total: int = Field(default=160, ge=8, le=300)
    industry_chain_repair_tool_calls_total: int = Field(default=80, ge=4, le=160)
    industry_chain_max_rounds: int = Field(default=10, ge=2, le=24)
    industry_chain_repair_max_rounds: int = Field(default=5, ge=1, le=12)
    industry_chain_research_timeout_seconds: float = Field(default=2400.0, gt=0)
    # 产业链定向补证分为独立的取证与报告重写时限；任一阶段超时都保留初稿并标记 degraded。
    industry_chain_repair_research_timeout_seconds: float = Field(default=1200.0, gt=0)
    industry_chain_repair_synthesis_timeout_seconds: float = Field(default=900.0, gt=0)
    # Long report generation: one deadline shared by streaming and schema repair.
    analysis_llm_timeout_seconds: float = Field(default=1200.0, gt=0)
    analysis_llm_max_completion_tokens: int = Field(default=32768, ge=1)
    # 每日复盘的确定性校验：情绪周期与量化锚点冲突时按锚点修正、关键点位/情景预案
    # 必须含可验证数字。关闭后完全按模型输出（回退到旧行为）。
    daily_review_grounding_enabled: bool = True

    # Deployment-only; deliberately absent from private/persisted editable keys.
    pdf_max_concurrency: int = Field(default=1, ge=1, le=4)
    pdf_max_waiters: int = Field(default=4, ge=0, le=32)
    pdf_render_timeout_seconds: float = Field(default=120.0, gt=0, le=240.0)
    python_sandbox_url: str = ""
    python_sandbox_token: str = Field(default="", repr=False)

    max_concurrent_chat_per_user: int = 2
    max_concurrent_chat_total: int = 8
    max_concurrent_llm_requests: int = 6
    # 每用户 LLM 触发频率上限（滑动窗口）。LLM 端点会有「用户 Key → 全局 Key」
    # 回退，且共享 max_concurrent_llm_requests 全局槽位：没有频率上限时单个账号
    # 反复触发长任务既烧掉管理员的额度，也会把其他用户挤进排队。
    user_llm_rate_limit_requests: int = Field(default=20, ge=1, le=1000)
    user_llm_rate_limit_window: int = Field(default=60, ge=1, le=3600)
    blocking_thread_pool_workers: int = 20
    chat_max_completion_tokens: int = 4096
    chat_total_timeout_seconds: int = 300
    chat_heartbeat_seconds: int = 15
    chat_tool_timeout_seconds: int = 45
    # Maximum new calls in an execution batch, not a hard cap on one model turn.
    chat_max_tool_calls_per_round: int = Field(default=16, ge=1, le=32)
    chat_max_tool_calls_total: int = Field(default=32, ge=1, le=128)
    chat_max_tool_context_characters: int = Field(default=60_000, ge=4_096, le=500_000)
    # 首轮工具数上限。首轮工具 schema 是 prompt 的最大单项（14 个工具约 8.8k 字符），
    # 而 chat_max_initial_active_skills 限的是 Skill 数不是工具数：3 个 Skill 的
    # core_tools 相加可能是 14 个。0 表示不限制；被截掉的工具仍可通过 load_skill 获得。
    chat_max_initial_tools: int = Field(default=0, ge=0, le=64)
    # 历史回灌预算；大上下文模型可调高，0 不合法（必须保留最起码的连续性）。
    chat_max_history_characters: int = Field(default=40_000, ge=4_000, le=200_000)
    # 整轮 prompt 的字符总预算，用于反推「工具结果」与「子任务前置分析」还能占多少。
    # 注意：它不是硬上限——system prompt、Skill 规则与历史各自受自己的配置约束；
    # 这里只把工具结果上下文与依赖上下文压到剩余额度内。0=不启用，保持旧行为。
    chat_max_prompt_characters: int = Field(default=0, ge=0, le=1_000_000)
    # 跨请求复用 public + daily/static 工具结果（按 ToolPolicy.cache_ttl_seconds）。
    chat_tool_process_cache_enabled: bool = True
    chat_max_synthesis_characters: int = Field(default=60_000, ge=4_096, le=500_000)
    # 通用 Agent 的 Skill 渐进披露：-1=完整 rules（回滚），0=仅目录+load_skill，N=目录+前 N 个详细规则。
    chat_skill_instruction_top_n: int = Field(default=0, ge=-1, le=10)
    # 允许 load_skill 激活未命中关键词的 Skill，并动态加入其工具。
    chat_skill_dynamic_activation_enabled: bool = True
    # load_skill 使用独立预算，不占用数据工具额度。
    chat_max_skill_loads_total: int = Field(default=3, ge=0, le=20)
    # 初始工具集只加载得分最高的 N 个 active Skill；-1=全部，0=只给 load_skill。
    chat_max_initial_active_skills: int = Field(default=3, ge=-1, le=10)
    # 专业 Agent 是否注入其 profile.skill_names 对应的 Skill 规则。
    chat_agent_skill_instructions_enabled: bool = True
    # 初始工具集是否只暴露 Skill 的 core_tools；false 回退为全部 tools。
    chat_skill_core_tools_enabled: bool = True

    provider_gateway_max_attempts: int = 2
    provider_failure_threshold: int = 3
    provider_circuit_open_seconds: float = 30.0
    provider_retry_base_seconds: float = 0.2
    provider_retry_budget_seconds: float = 5.0
    provider_retry_jitter_seconds: float = 0.1
