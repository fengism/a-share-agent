"""在线量化策略编排 Tool 注册。"""

from __future__ import annotations

from typing import Any

from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.tools.application import get_application_tool_handlers
from app.agentic.tools.contracts import Tool, ToolPolicy

_QUANT_MUTATION_POLICY = ToolPolicy(
    cost="high",
    cache_ttl_seconds=0,
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
) -> Any:
    return await get_application_tool_handlers().backtest_quant_strategy_draft(
        draft_id=draft_id,
        codes=codes,
        start_date=start_date,
        end_date=end_date,
        benchmark=benchmark,
        minimum_trade_count=minimum_trade_count,
        maximum_drawdown_pct=maximum_drawdown_pct,
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
    target_registry.register_tool(Tool(
        name="list_quant_dsl_capabilities",
        description="列出在线量化策略支持的数据字段、指标、信号操作符和安全工作流。生成策略前调用。仅管理员可用。",
        parameters={"type": "object", "properties": {}},
        policy=_QUANT_MUTATION_POLICY,
        executor=_list_quant_dsl_capabilities,
    ))
    target_registry.register_tool(Tool(
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
    ))
    target_registry.register_tool(Tool(
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
    ))
    target_registry.register_tool(Tool(
        name="backtest_quant_strategy_draft",
        description="以草稿当前不可变快照创建历史回测，并记录交易次数和最大回撤质量门禁。仅管理员可用。",
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
            },
            "required": ["draft_id", "codes", "start_date", "end_date"],
        },
        policy=_QUANT_MUTATION_POLICY,
        executor=_backtest_quant_strategy_draft,
    ))
    target_registry.register_tool(Tool(
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
    ))
