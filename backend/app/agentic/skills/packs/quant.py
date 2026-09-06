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
            "只有用户明确说出发布意图时才调用 publish_quant_strategy_draft；必须提交用户确认过的 expected_definition_hash。",
        ),
        exclusions=("普通策略讨论或收益分析不得创建、回测或发布草稿",),
        examples=(
            "根据双均线金叉生成量化策略草稿 ➔ generate_quant_strategy_draft(prompt='基于MA5与MA20金叉做多')",
            "回测当前策略草稿历史表现 ➔ backtest_quant_strategy_draft(draft_id='...', codes=['600519'], start_date='2024-01-01', end_date='2024-12-31')",
        ),
        priority=45,
    ),
    Skill(
        name="python_code_interpreter",
        description="Python 代码计算沙盒，用于复合增速、DCF模型、财务比率计算与统计矩阵分析",
        triggers=("复杂数值计算", "CAGR 复合增长率测算", "现金流折现 DCF 计算", "敏感性分析与统计测算"),
        activation_keywords=("计算", "测算", "cagr", "复合增长率", "dcf", "贴现", "折现", "敏感性", "方差", "夏普比率", "python"),
        tool_names=("python_interpreter",),
        rules=(
            "当需要进行精确数学公式计算、DCF 折现、CAGR 复合增速推算时调用 python_interpreter。",
            "代码中必须包含 print(...) 输出最终结果。",
        ),
        exclusions=(),
        examples=(
            "测算2024到2030年规模从10亿到80亿的CAGR ➔ python_interpreter(code='print(((80/10)**(1/6)-1)*100)')",
        ),
        priority=40,
    ),
)
