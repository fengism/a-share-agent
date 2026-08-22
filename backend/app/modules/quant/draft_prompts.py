"""在线量化策略生成 Prompt。"""

from app.infrastructure.llm.prompting import PromptSpec, prompt_registry
from app.modules.quant.strategies.contracts import StrategyDefinition

SYSTEM_PROMPT = """你是 A 股量化策略 DSL 设计器。你只能生成 quant.strategy/v1 的声明式策略定义。

安全与正确性规则：
- 禁止 Python、SQL、Shell、导入、回调、自定义 YAML Tag 或任何可执行代码。
- 只能使用 open/high/low/close/volume 数据字段。
- 指标只能使用 sma、ema、rsi、rolling_max、rolling_min。
- 信号只能使用 greater_than、greater_or_equal、less_than、less_or_equal、cross_above、cross_below、and、or、not。
- 所有周期必须通过有明确 minimum/maximum 的整数参数声明，默认值应适合日线回测。
- 参数之间存在大小关系时必须声明 constraints。
- 信号按当日收盘数据计算，系统在下一交易日执行；不得假设未来数据。
- key 使用简洁英文 snake_case；新策略默认 version=1.0.0、enabled=true。
- 描述必须准确说明入场和退出逻辑，不承诺收益。
- 输出必须是完整、自洽、可编译的 StrategyDefinition JSON。
"""


def _build_user_prompt(context) -> str:
    return f"""请把以下管理员需求转换为受限量化策略定义：

{context['prompt']}

只使用系统允许的 DSL 能力。如果需求包含 DSL 不支持的止损、仓位权重、分钟线或外部因子，请用最接近且保守的日线二元持仓逻辑表达，不得虚构操作符。"""


QUANT_STRATEGY_DRAFT_PROMPT = prompt_registry.register(
    PromptSpec(
        id="quant_strategy_draft",
        version="1.0.0",
        system_prompt=SYSTEM_PROMPT,
        user_builder=_build_user_prompt,
        output_model=StrategyDefinition,
        temperature=0.1,
        repair_attempts=1,
    )
)
