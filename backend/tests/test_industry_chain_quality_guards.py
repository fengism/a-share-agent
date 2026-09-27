"""产业链生成质量与降级可见性的守卫测试。"""


from app.configuration.schema import PERSISTED_GLOBAL_KEYS, Settings
from app.modules.bot.commands.chain import _format_chain_reply
from app.modules.industry_chain.models import IndustryChainResult
from app.modules.industry_chain.prompts import SYSTEM_PROMPT as INDUSTRY_CHAIN_SYSTEM_PROMPT
from app.modules.industry_chain.verification_repair import _repair_timeout_seconds


def test_repair_timeout_defaults_and_reads_settings():
    assert _repair_timeout_seconds(Settings()) == 600.0

    tight = Settings(industry_chain_repair_timeout_seconds=180.0)
    assert _repair_timeout_seconds(tight) == 180.0

    # 非法值回退默认，且不允许非正数
    broken = Settings.model_construct(industry_chain_repair_timeout_seconds="bad")
    assert _repair_timeout_seconds(broken) == 600.0
    broken2 = Settings.model_construct(industry_chain_repair_timeout_seconds=-5)
    assert _repair_timeout_seconds(broken2) == 600.0


def test_repair_timeout_is_admin_persistable():
    assert "industry_chain_repair_timeout_seconds" in PERSISTED_GLOBAL_KEYS


def test_settings_config_schemas_stay_consistent():
    # 导入即触发三向一致性守卫：ConfigResponse / ConfigUpdateRequest / PERSISTED_GLOBAL_KEYS。
    # 新增可持久化配置时漏改任一侧会在应用启动时报错，这里提前到测试期暴露。
    from app.modules.settings import schemas as settings_schemas

    budget_keys = {
        "industry_chain_repair_timeout_seconds",
        "industry_chain_tool_calls_total",
        "industry_chain_repair_tool_calls_total",
        "analysis_llm_timeout_seconds",
        "agent_research_timeout_seconds",
        "chat_max_tool_calls_total",
    }
    assert budget_keys <= settings_schemas.CONFIG_VALUE_FIELDS
    assert budget_keys <= PERSISTED_GLOBAL_KEYS
    # 模型上下文长度是 per-user 私有配置
    assert "llm_context_length_tokens" in settings_schemas.CONFIG_VALUE_FIELDS


def test_chat_history_trim_respects_model_context_length():
    from app.agentic.messages import build_messages
    from app.agentic.protocol import AgentMessage

    history = [
        AgentMessage(role="user" if i % 2 == 0 else "assistant", content="长" * 3000)
        for i in range(20)
    ]
    system_prompt = "系统提示词"

    # 未设置上下文长度：沿用 40k 字符预算（20 × 3000 = 60k 只装得下一部分）
    default_messages = build_messages("当前问题", history, 20, system_prompt)
    default_history_chars = sum(len(m["content"]) for m in default_messages[1:-1])

    # 设置 16k tokens：历史预算压到 16k - 6k = 10k 字符
    tight_messages = build_messages("当前问题", history, 20, system_prompt, context_length_tokens=16_000)
    tight_history_chars = sum(len(m["content"]) for m in tight_messages[1:-1])
    assert tight_history_chars <= 10_000
    assert tight_history_chars < default_history_chars

    # 大上下文模型不受影响（预算封顶 40k）
    roomy_messages = build_messages("当前问题", history, 20, system_prompt, context_length_tokens=131_072)
    roomy_chars = sum(len(m["content"]) for m in roomy_messages[1:-1])
    assert roomy_chars == default_history_chars

    # 消息结构完整：system 在首、当前问题在尾
    assert tight_messages[0]["role"] == "system"
    assert tight_messages[-1]["role"] == "user" and tight_messages[-1]["content"] == "当前问题"


def test_prompt_requires_tier_density_and_allows_structure_exceptions():
    assert "上中下游每层输出 5-10 个环节节点" in INDUSTRY_CHAIN_SYSTEM_PROMPT
    assert "环节覆盖不全比证据缺口更严重" in INDUSTRY_CHAIN_SYSTEM_PROMPT
    assert "禁止用三四个粗环节概括大型产业链" in INDUSTRY_CHAIN_SYSTEM_PROMPT
    # 判断类内容仍然保持"宁可少输出"的防幻觉约束
    assert "除上中下游结构节点外" in INDUSTRY_CHAIN_SYSTEM_PROMPT
    # 旧的全局上限表述不应残留
    assert "上中下游各最多 6 条" not in INDUSTRY_CHAIN_SYSTEM_PROMPT


def test_research_guidance_phases_breadth_before_deep_reads():
    from app.modules.industry_chain.research import render_research_planning_guidance

    text = render_research_planning_guidance(
        search_total_limit=16, search_burst_limit=4, reserved_tool_calls=20, total_calls=72,
    )
    assert "结构发现广度优先" in text
    assert "累计建议≥8次" in text
    assert "搜索组累计最多16次" in text
    assert "工具上限72次" in text
    assert "必然产出粗环节链条" in text


def test_format_chain_reply_surfaces_degraded_and_tier_counts():
    from app.modules.industry_chain.models import IndustryChainNode

    result = IndustryChainResult(
        name="AI 算力",
        quality_status="degraded",
        upstream=[IndustryChainNode(name="GPU"), IndustryChainNode(name="HBM")],
        midstream=[IndustryChainNode(name="服务器")],
        downstream=[],
        key_stocks=[IndustryChainNode(name="中际旭创"), IndustryChainNode(name="海光信息")],
    )
    text = _format_chain_reply(result)
    assert "⚠️ 本次为降级稿" in text
    assert "上游 2 / 中游 1 / 下游 0" in text
    assert "关键公司 2 家" in text

    healthy = IndustryChainResult(name="光模块")
    assert "降级稿" not in _format_chain_reply(healthy)


def test_llm_output_coercion_tolerates_string_lists_and_claim_type_aliases():
    from app.modules.industry_chain.models import IndustryChainMetric, IndustryChainThesis

    thesis = IndustryChainThesis(
        title="算力需求外溢",
        conditions="AI资本开支持续、库存回补延续。",
        tracking_metrics="云厂商资本开支",
        claim_type="forecast",
    )
    assert thesis.conditions == ["AI资本开支持续、库存回补延续。"]
    assert thesis.tracking_metrics == ["云厂商资本开支"]
    # LLM 把 evidence_basis 的枚举词误填进 claim_type，映射到最接近的合法值
    assert thesis.claim_type == "inference"

    metric = IndustryChainMetric(label="资本开支", value="+50%", claim_type="预测")
    assert metric.claim_type == "inference"

    # 正常列表与合法枚举不受影响
    ok = IndustryChainThesis(title="t", conditions=["a", "b"], claim_type="fact")
    assert ok.conditions == ["a", "b"]
    assert ok.claim_type == "fact"


def test_push_industry_chain_surfaces_degraded_warning():
    from app.modules.push.content import _build_industry_chain

    degraded = IndustryChainResult(
        name="AI 算力",
        quality_status="degraded",
        schema_version=1,
        summary="初稿摘要",
        llm_review="",
    )
    blocks = _build_industry_chain(degraded)
    assert any("降级稿" in block.text for block in blocks if block.text)

    healthy = IndustryChainResult(name="光模块", schema_version=1, llm_review="", summary="ok")
    assert not any("降级稿" in block.text for block in _build_industry_chain(healthy) if block.text)
