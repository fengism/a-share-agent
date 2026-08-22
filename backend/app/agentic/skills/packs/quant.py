from app.agentic.skills.contracts import Skill

SKILLS = (
    Skill(
        name="quant_strategy_authoring",
        description="在线生成、校验、回测与发布受限量化策略",
        triggers=("管理员要求新增或在线生成量化策略", "校验、试跑或发布策略草稿"),
        activation_keywords=(
            "量化策略",
            "策略草稿",
            "策略dsl",
            "在线策略",
            "生成策略",
            "发布策略",
            "quant strategy",
        ),
        tool_names=(
            "list_quant_dsl_capabilities",
            "generate_quant_strategy_draft",
            "validate_quant_strategy_draft",
            "backtest_quant_strategy_draft",
            "publish_quant_strategy_draft",
        ),
        rules=(
            "先调用 list_quant_dsl_capabilities 确认可表达能力，再生成草稿；不得生成 Python、Shell 或任意可执行代码。",
            "生成后先展示草稿定义与哈希，按需校验并使用当前快照回测，不得跳过质量门禁。",
            "只有用户明确说出发布意图时才调用 publish_quant_strategy_draft；必须提交用户确认过的 definition_hash。",
        ),
        exclusions=("普通策略讨论或收益分析不得创建、回测或发布草稿",),
        priority=45,
    ),
)
