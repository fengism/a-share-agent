"""在线量化策略编排 Tool 注册。"""

from __future__ import annotations

from typing import Any

from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.tools.application import get_application_tool_handlers
from app.agentic.tools.contracts import Tool, ToolPolicy
from app.agentic.tools.packs.quant.finance import FINANCIAL_PARAMETERS, calculate_financial_metric

_QUANT_MUTATION_POLICY = ToolPolicy(
    cost="high",
    cache_ttl_seconds=0,
    deduplicate_in_batch=False,
    freshness="realtime",
    scope="user",
    timeout_seconds=180,
    max_parallel_calls=1,
    max_result_characters=20_000,
)


async def _list_quant_dsl_capabilities() -> Any:
    return await get_application_tool_handlers().list_quant_dsl_capabilities()


async def _generate_quant_strategy_draft(prompt: str) -> Any:
    return await get_application_tool_handlers().generate_quant_strategy_draft(prompt=prompt)


async def _validate_quant_strategy_draft(draft_id: str) -> Any:
    return await get_application_tool_handlers().validate_quant_strategy_draft(draft_id=draft_id)


async def _backtest_quant_strategy_draft(
    draft_id: str,
    codes: list[str],
    start_date: str,
    end_date: str,
    benchmark: str = "000300",
    minimum_trade_count: int = 1,
    maximum_drawdown_pct: float = 80,
    minimum_sharpe_ratio: float | None = None,
    minimum_holdout_trade_count: int | None = None,
    maximum_holdout_drawdown_pct: float | None = None,
    minimum_holdout_sharpe_ratio: float | None = None,
) -> Any:
    return await get_application_tool_handlers().backtest_quant_strategy_draft(
        draft_id=draft_id,
        codes=codes,
        start_date=start_date,
        end_date=end_date,
        benchmark=benchmark,
        minimum_trade_count=minimum_trade_count,
        maximum_drawdown_pct=maximum_drawdown_pct,
        minimum_sharpe_ratio=minimum_sharpe_ratio,
        minimum_holdout_trade_count=minimum_holdout_trade_count,
        maximum_holdout_drawdown_pct=maximum_holdout_drawdown_pct,
        minimum_holdout_sharpe_ratio=minimum_holdout_sharpe_ratio,
    )


async def _publish_quant_strategy_draft(
    draft_id: str,
    expected_definition_hash: str,
) -> Any:
    return await get_application_tool_handlers().publish_quant_strategy_draft(
        draft_id=draft_id,
        expected_definition_hash=expected_definition_hash,
    )


def register_quant_tools(target_registry: CapabilityCatalog = registry) -> None:
    target_registry.register_tool(
        Tool(
            name="financial_calculator",
            description=(
                "优先用于收益率(return)、CAGR(cagr)、NPV(npv)、永续增长DCF(dcf)、年化波动率(volatility)、"
                "最大回撤(max_drawdown)、财务比率(ratio)。固定公式，不执行代码；返回结果、公式与假设。"
                "参数错误应修正输入，不得转用 Python 绕过。比率使用小数。"
            ),
            parameters=FINANCIAL_PARAMETERS,
            policy=ToolPolicy(cost="low", cache_ttl_seconds=0, scope="user", freshness="static"),
            executor=calculate_financial_metric,
        )
    )
    target_registry.register_tool(
        Tool(
            name="list_quant_dsl_capabilities",
            description="列出在线量化策略支持的数据字段、指标、信号操作符和安全工作流。生成策略前调用。仅管理员可用。",
            parameters={"type": "object", "properties": {}},
            policy=_QUANT_MUTATION_POLICY,
            executor=_list_quant_dsl_capabilities,
        )
    )
    target_registry.register_tool(
        Tool(
            name="generate_quant_strategy_draft",
            description="根据管理员的自然语言需求生成受限 quant.strategy/v1 策略草稿并完成初始校验，不会直接发布。",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "minLength": 10,
                        "maxLength": 4000,
                        "description": "策略目标、入场退出逻辑、参数和风险偏好",
                    },
                },
                "required": ["prompt"],
            },
            policy=_QUANT_MUTATION_POLICY,
            executor=_generate_quant_strategy_draft,
        )
    )
    target_registry.register_tool(
        Tool(
            name="validate_quant_strategy_draft",
            description="重新编译并校验指定策略草稿，返回定义哈希与告警。仅管理员可用。",
            parameters={
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "minLength": 1},
                },
                "required": ["draft_id"],
            },
            policy=_QUANT_MUTATION_POLICY,
            executor=_validate_quant_strategy_draft,
        )
    )
    target_registry.register_tool(
        Tool(
            name="backtest_quant_strategy_draft",
            description="以草稿当前不可变快照创建历史回测，并按收益风险与后段样本表现执行质量门禁。仅管理员可用。",
            parameters={
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "minLength": 1},
                    "codes": {
                        "type": "array",
                        "items": {"type": "string", "pattern": r"^\d{6}$"},
                        "minItems": 1,
                        "maxItems": 10,
                        "uniqueItems": True,
                    },
                    "start_date": {"type": "string", "format": "date"},
                    "end_date": {"type": "string", "format": "date"},
                    "benchmark": {
                        "type": "string",
                        "pattern": r"^\d{6}$",
                        "default": "000300",
                    },
                    "minimum_trade_count": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10000,
                        "default": 1,
                    },
                    "maximum_drawdown_pct": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": 80,
                        "default": 80,
                    },
                    "minimum_sharpe_ratio": {
                        "type": ["number", "null"],
                        "minimum": -20,
                        "maximum": 20,
                        "default": None,
                    },
                    "minimum_holdout_trade_count": {
                        "type": ["integer", "null"],
                        "minimum": 0,
                        "maximum": 10000,
                        "default": None,
                    },
                    "maximum_holdout_drawdown_pct": {
                        "type": ["number", "null"],
                        "exclusiveMinimum": 0,
                        "maximum": 80,
                        "default": None,
                    },
                    "minimum_holdout_sharpe_ratio": {
                        "type": ["number", "null"],
                        "minimum": -20,
                        "maximum": 20,
                        "default": None,
                    },
                },
                "required": ["draft_id", "codes", "start_date", "end_date"],
            },
            policy=_QUANT_MUTATION_POLICY,
            executor=_backtest_quant_strategy_draft,
        )
    )
    target_registry.register_tool(
        Tool(
            name="publish_quant_strategy_draft",
            description="发布已通过当前定义回测质量门禁的策略草稿。只有管理员明确要求发布时才可调用。",
            parameters={
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "minLength": 1},
                    "expected_definition_hash": {
                        "type": "string",
                        "pattern": r"^sha256:[0-9a-f]{64}$",
                    },
                },
                "required": ["draft_id", "expected_definition_hash"],
            },
            policy=_QUANT_MUTATION_POLICY,
            executor=_publish_quant_strategy_draft,
        )
    )
    target_registry.register_tool(
        Tool(
            name="python_interpreter",
            description=(
                "独立隔离 Python 环境，用于固定公式未覆盖的敏感性分析、统计或矩阵运算。"
                "收益率/CAGR/NPV/DCF/波动率/最大回撤/比率优先用 financial_calculator；其参数错误不可转用 Python。"
                "预置 math/datetime/json/re/Decimal/numpy(np)/pandas(pd)，必须 print 输出。"
                "无网络、无业务文件或密钥；所需数据由已授权的数据工具获取后显式放入代码。"
                "仅管理员可用；服务不可用时不得回退到后端本机执行。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 32768,
                        "description": "要执行的 Python 代码脚本，必须通过 print(...) 输出最终计算结果",
                    },
                },
                "required": ["code"],
            },
            policy=ToolPolicy(cost="low", cache_ttl_seconds=0, deduplicate_in_batch=False, scope="user", timeout_seconds=25, max_parallel_calls=2),
            executor=_execute_python_code,
        )
    )


async def _execute_python_code(code: str) -> Any:
    from app.core.request_context import get_current_user

    user = get_current_user()
    if user is None or not bool(user.get("is_admin")):
        raise PermissionError("仅管理员可以使用 Python 计算沙盒")
    from app.agentic.tools.packs.quant.interpreter import execute_python_code

    return await execute_python_code(code=code)
