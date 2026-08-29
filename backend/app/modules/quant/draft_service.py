"""在线量化策略草稿应用服务。"""

from __future__ import annotations

import logging
import math
from pathlib import Path

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore, misc_semaphore
from app.infrastructure.llm.prompting import PromptExecutionError, run_structured_prompt
from app.modules.quant.draft_prompts import QUANT_STRATEGY_DRAFT_PROMPT
from app.modules.quant.persistence import drafts as draft_store
from app.modules.quant.persistence import runs as run_store
from app.modules.quant.schemas import (
    QuantBacktestCreate,
    QuantBacktestRun,
    QuantStrategyConfig,
    QuantStrategyDraft,
    QuantStrategyDraftBacktestRequest,
    QuantStrategyDraftGenerateRequest,
    QuantStrategyDraftQualityGate,
    QuantStrategyDraftUpdateRequest,
    QuantStrategyDraftValidationReport,
)
from app.modules.quant.service import create_backtest_with_snapshot
from app.modules.quant.strategies.contracts import StrategyDefinition, StrategySnapshot
from app.modules.quant.strategies.loader import canonical_definition_hash
from app.modules.quant.strategies.registry import StrategyRegistry, get_strategy_registry

logger = logging.getLogger(__name__)


class StrategyDraftNotFoundError(LookupError):
    pass


class StrategyDraftConflictError(RuntimeError):
    pass


class StrategyDraftGenerationError(RuntimeError):
    pass


def validate_strategy_definition(
    definition: StrategyDefinition,
    *,
    registry: StrategyRegistry | None = None,
) -> tuple[QuantStrategyDraftValidationReport, StrategySnapshot]:
    active_registry = registry or get_strategy_registry()
    snapshot = active_registry.validate_definition_for_publication(definition)
    warnings = []
    if not definition.constraints:
        warnings.append("策略未声明跨参数约束")
    return (
        QuantStrategyDraftValidationReport(
            valid=True,
            definition_hash=snapshot.definition_hash,
            warnings=warnings,
        ),
        snapshot,
    )


def evaluate_quality_gate(
    run: run_store.QuantRunRow,
    *,
    expected_definition_hash: str,
    minimum_trade_count: int,
    maximum_drawdown_pct: float,
    minimum_sharpe_ratio: float | None = None,
    minimum_holdout_trade_count: int | None = None,
    maximum_holdout_drawdown_pct: float | None = None,
    minimum_holdout_sharpe_ratio: float | None = None,
) -> QuantStrategyDraftQualityGate:
    snapshot = run.request.get("strategy_snapshot")
    actual_hash = snapshot.get("definition_hash") if isinstance(snapshot, dict) else None
    errors: list[str] = []
    if actual_hash != expected_definition_hash:
        errors.append("回测策略快照与当前草稿不一致")
    metrics = run.result.get("metrics") if isinstance(run.result, dict) else None
    trade_count = metrics.get("trade_count") if isinstance(metrics, dict) else None
    max_drawdown = metrics.get("max_drawdown") if isinstance(metrics, dict) else None
    sharpe_ratio = metrics.get("sharpe_ratio") if isinstance(metrics, dict) else None
    holdout = run.result.get("holdout_validation") if isinstance(run.result, dict) else None
    holdout_metrics = holdout.get("metrics") if isinstance(holdout, dict) else None
    holdout_trade_count = (
        holdout_metrics.get("trade_count") if isinstance(holdout_metrics, dict) else None
    )
    holdout_max_drawdown = (
        holdout_metrics.get("max_drawdown") if isinstance(holdout_metrics, dict) else None
    )
    holdout_sharpe_ratio = (
        holdout_metrics.get("sharpe_ratio") if isinstance(holdout_metrics, dict) else None
    )
    valid_trade_count = type(trade_count) is int and trade_count >= 0
    valid_holdout_trade_count = type(holdout_trade_count) is int and holdout_trade_count >= 0

    def finite_number(value: object) -> bool:
        return type(value) in (int, float) and math.isfinite(float(value))

    valid_max_drawdown = finite_number(max_drawdown) and float(max_drawdown) <= 0
    valid_sharpe = finite_number(sharpe_ratio)
    valid_holdout_max_drawdown = (
        finite_number(holdout_max_drawdown) and float(holdout_max_drawdown) <= 0
    )
    valid_holdout_sharpe = finite_number(holdout_sharpe_ratio)
    if run.status != "succeeded":
        errors.append(f"回测未成功完成: {run.status}")
    elif not valid_trade_count or trade_count < minimum_trade_count:
        actual_trades = trade_count if valid_trade_count else 0
        errors.append(f"交易次数 {actual_trades} 少于最低要求 {minimum_trade_count}")
    if run.status == "succeeded" and (
        not valid_max_drawdown
        or float(max_drawdown) < -maximum_drawdown_pct
    ):
        errors.append(
            f"最大回撤超过 {maximum_drawdown_pct:g}%"
            if valid_max_drawdown
            else "最大回撤指标无效"
        )
    if run.status == "succeeded" and minimum_sharpe_ratio is not None and (
        not valid_sharpe or float(sharpe_ratio) < minimum_sharpe_ratio
    ):
        errors.append(
            f"夏普比率低于 {minimum_sharpe_ratio:g}"
            if valid_sharpe
            else "夏普比率指标无效"
        )
    holdout_required = any(
        value is not None
        for value in (
            minimum_holdout_trade_count,
            maximum_holdout_drawdown_pct,
            minimum_holdout_sharpe_ratio,
        )
    )
    if run.status == "succeeded" and holdout_required and not isinstance(holdout_metrics, dict):
        errors.append("回测区间不足，未生成后段样本验证")
    elif run.status == "succeeded" and isinstance(holdout_metrics, dict):
        if minimum_holdout_trade_count is not None and (
            not valid_holdout_trade_count
            or holdout_trade_count < minimum_holdout_trade_count
        ):
            actual_trades = holdout_trade_count if valid_holdout_trade_count else 0
            errors.append(
                f"后段样本交易次数 {actual_trades} 少于最低要求 {minimum_holdout_trade_count}"
            )
        if maximum_holdout_drawdown_pct is not None and (
            not valid_holdout_max_drawdown
            or float(holdout_max_drawdown) < -maximum_holdout_drawdown_pct
        ):
            errors.append(
                f"后段样本最大回撤超过 {maximum_holdout_drawdown_pct:g}%"
                if valid_holdout_max_drawdown
                else "后段样本最大回撤指标无效"
            )
        if minimum_holdout_sharpe_ratio is not None and (
            not valid_holdout_sharpe
            or float(holdout_sharpe_ratio) < minimum_holdout_sharpe_ratio
        ):
            errors.append(
                f"后段样本夏普比率低于 {minimum_holdout_sharpe_ratio:g}"
                if valid_holdout_sharpe
                else "后段样本夏普比率指标无效"
            )
    if run.status == "succeeded":
        metric_groups = (
            (
                metrics,
                "",
            ),
            (
                holdout_metrics,
                "后段样本",
            ),
        )
        for metric_group, label_prefix in metric_groups:
            if not isinstance(metric_group, dict):
                continue
            for key, label in (
                ("downside_volatility", "下行波动率"),
                ("sharpe_ratio", "夏普比率"),
                ("sortino_ratio", "索提诺比率"),
                ("calmar_ratio", "卡玛比率"),
                ("tracking_error", "跟踪误差"),
                ("information_ratio", "信息比率"),
            ):
                value = metric_group.get(key)
                error = f"{label_prefix}{label}指标无效"
                if value is not None and not finite_number(value) and error not in errors:
                    errors.append(error)
    return QuantStrategyDraftQualityGate(
        passed=not errors,
        run_status=run.status,
        definition_hash=expected_definition_hash,
        minimum_trade_count=minimum_trade_count,
        maximum_drawdown_pct=maximum_drawdown_pct,
        minimum_sharpe_ratio=minimum_sharpe_ratio,
        minimum_holdout_trade_count=minimum_holdout_trade_count,
        maximum_holdout_drawdown_pct=maximum_holdout_drawdown_pct,
        minimum_holdout_sharpe_ratio=minimum_holdout_sharpe_ratio,
        trade_count=trade_count if valid_trade_count else None,
        max_drawdown=float(max_drawdown) if valid_max_drawdown else None,
        sharpe_ratio=float(sharpe_ratio) if valid_sharpe else None,
        holdout_trade_count=holdout_trade_count if valid_holdout_trade_count else None,
        holdout_max_drawdown=(
            float(holdout_max_drawdown) if valid_holdout_max_drawdown else None
        ),
        holdout_sharpe_ratio=(
            float(holdout_sharpe_ratio) if valid_holdout_sharpe else None
        ),
        errors=errors,
    )


def _to_api(row: draft_store.StrategyDraftRow) -> QuantStrategyDraft:
    return QuantStrategyDraft(
        id=row.id,
        created_by=row.created_by,
        prompt=row.prompt,
        definition=StrategyDefinition.model_validate(row.definition),
        definition_hash=row.definition_hash,
        status=row.status,
        validation=row.validation,
        backtest_run_id=row.backtest_run_id,
        quality_gate=row.quality_gate,
        published_path=row.published_path,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        published_at=row.published_at,
    )


async def _require_draft(draft_id: str) -> draft_store.StrategyDraftRow:
    row = await call_blocking(draft_store.get_draft, draft_id, semaphore=database_semaphore)
    if row is None:
        raise StrategyDraftNotFoundError("策略草稿不存在")
    return row


async def _sync_draft(row: draft_store.StrategyDraftRow) -> draft_store.StrategyDraftRow:
    if row.status != "testing" or not row.backtest_run_id or row.quality_gate is None:
        return row
    run = await call_blocking(
        run_store.get_run,
        row.created_by,
        row.backtest_run_id,
        semaphore=database_semaphore,
    )
    if run is None or run.status in {"pending", "running"}:
        return row
    minimum_trade_count = int(row.quality_gate.get("minimum_trade_count", 1))
    maximum_drawdown_pct = float(row.quality_gate.get("maximum_drawdown_pct", 80))
    minimum_sharpe_ratio = row.quality_gate.get("minimum_sharpe_ratio")
    minimum_holdout_trade_count = row.quality_gate.get("minimum_holdout_trade_count")
    maximum_holdout_drawdown_pct = row.quality_gate.get("maximum_holdout_drawdown_pct")
    minimum_holdout_sharpe_ratio = row.quality_gate.get("minimum_holdout_sharpe_ratio")
    report = evaluate_quality_gate(
        run,
        expected_definition_hash=row.definition_hash,
        minimum_trade_count=minimum_trade_count,
        maximum_drawdown_pct=maximum_drawdown_pct,
        minimum_sharpe_ratio=minimum_sharpe_ratio,
        minimum_holdout_trade_count=minimum_holdout_trade_count,
        maximum_holdout_drawdown_pct=maximum_holdout_drawdown_pct,
        minimum_holdout_sharpe_ratio=minimum_holdout_sharpe_ratio,
    )
    try:
        return await call_blocking(
            draft_store.record_quality,
            row.id,
            report.model_dump(mode="json"),
            expected_definition_hash=row.definition_hash,
            expected_run_id=row.backtest_run_id,
            status="backtested" if report.passed else "validated",
            error=None if report.passed else "; ".join(report.errors),
            semaphore=database_semaphore,
        )
    except KeyError:
        return await _require_draft(row.id)


async def generate_strategy_draft(
    request: QuantStrategyDraftGenerateRequest,
    *,
    user_id: int,
) -> QuantStrategyDraft:
    try:
        prompt_run = await run_structured_prompt(
            QUANT_STRATEGY_DRAFT_PROMPT,
            {"prompt": request.prompt},
        )
    except PromptExecutionError as error:
        raise StrategyDraftGenerationError("策略生成失败，请调整描述后重试") from error
    definition = prompt_run.value
    report, snapshot = validate_strategy_definition(definition)
    row = await call_blocking(
        draft_store.create_draft,
        created_by=user_id,
        prompt=request.prompt,
        definition=definition.model_dump(mode="json"),
        definition_hash=snapshot.definition_hash,
        status="validated",
        validation=report.model_dump(mode="json"),
        semaphore=database_semaphore,
    )
    return _to_api(row)


async def list_strategy_drafts(*, limit: int = 100) -> list[QuantStrategyDraft]:
    rows = await call_blocking(draft_store.list_drafts, limit=limit, semaphore=database_semaphore)
    return [_to_api(await _sync_draft(row)) for row in rows]


async def get_strategy_draft(draft_id: str) -> QuantStrategyDraft:
    return _to_api(await _sync_draft(await _require_draft(draft_id)))


async def update_strategy_draft(
    draft_id: str,
    request: QuantStrategyDraftUpdateRequest,
) -> QuantStrategyDraft:
    row = await _require_draft(draft_id)
    if row.definition_hash != request.expected_definition_hash:
        raise StrategyDraftConflictError("草稿已被其他操作更新，请刷新后重试")
    if row.status not in {"draft", "validated"}:
        raise StrategyDraftConflictError("仅待校验或已校验草稿可以修改")
    definition_hash = canonical_definition_hash(request.definition)
    try:
        updated = await call_blocking(
            draft_store.replace_definition,
            draft_id,
            request.definition.model_dump(mode="json"),
            definition_hash,
            expected_definition_hash=request.expected_definition_hash,
            semaphore=database_semaphore,
        )
    except KeyError as error:
        raise StrategyDraftConflictError("草稿已被其他操作更新，请刷新后重试") from error
    return _to_api(updated)


async def validate_strategy_draft(draft_id: str) -> QuantStrategyDraft:
    row = await _require_draft(draft_id)
    if row.status not in {"draft", "validated"}:
        raise StrategyDraftConflictError("仅待校验或已校验草稿可以重新校验")
    definition = StrategyDefinition.model_validate(row.definition)
    try:
        report, _snapshot = validate_strategy_definition(definition)
    except ValueError as error:
        try:
            await call_blocking(
                draft_store.record_error,
                draft_id,
                str(error),
                expected_definition_hash=row.definition_hash,
                status="draft",
                semaphore=database_semaphore,
            )
        except KeyError as conflict:
            raise StrategyDraftConflictError("草稿已被其他操作更新，请刷新后重试") from conflict
        raise
    try:
        updated = await call_blocking(
            draft_store.record_validation,
            draft_id,
            report.model_dump(mode="json"),
            expected_definition_hash=row.definition_hash,
            semaphore=database_semaphore,
        )
    except KeyError as error:
        raise StrategyDraftConflictError("草稿已被其他操作更新，请刷新后重试") from error
    return _to_api(updated)


async def backtest_strategy_draft(
    draft_id: str,
    request: QuantStrategyDraftBacktestRequest,
    *,
    user_id: int,
) -> QuantBacktestRun:
    row = await _require_draft(draft_id)
    if row.status not in {"validated", "backtested"}:
        raise StrategyDraftConflictError("仅已校验或已通过门禁的草稿可以发起回测")
    definition = StrategyDefinition.model_validate(row.definition)
    snapshot = get_strategy_registry().validate_definition_for_publication(definition)
    if snapshot.definition_hash != row.definition_hash:
        raise StrategyDraftConflictError("草稿内容已变化，请重新校验")
    backtest_request = QuantBacktestCreate(
        name=request.name or f"{definition.name} 草稿回测",
        universe=request.universe,
        strategy=QuantStrategyConfig(
            type=definition.key,
            version=definition.version,
            parameters=snapshot.parameters,
        ),
        execution=request.execution,
        start_date=request.start_date,
        end_date=request.end_date,
        benchmark=request.benchmark,
    )
    run = await create_backtest_with_snapshot(backtest_request, user_id, snapshot)
    quality_gate = QuantStrategyDraftQualityGate(
        passed=None,
        run_status="pending",
        definition_hash=row.definition_hash,
        minimum_trade_count=request.minimum_trade_count,
        maximum_drawdown_pct=request.maximum_drawdown_pct,
        minimum_sharpe_ratio=request.minimum_sharpe_ratio,
        minimum_holdout_trade_count=request.minimum_holdout_trade_count,
        maximum_holdout_drawdown_pct=request.maximum_holdout_drawdown_pct,
        minimum_holdout_sharpe_ratio=request.minimum_holdout_sharpe_ratio,
    )
    try:
        await call_blocking(
            draft_store.record_backtest,
            draft_id,
            run.id,
            quality_gate.model_dump(mode="json"),
            expected_definition_hash=row.definition_hash,
            semaphore=database_semaphore,
        )
    except KeyError as error:
        await call_blocking(run_store.cancel, user_id, run.id, semaphore=database_semaphore)
        await call_blocking(run_store.delete_run, user_id, run.id, semaphore=database_semaphore)
        raise StrategyDraftConflictError("草稿已被其他操作更新，回测任务已撤销") from error
    return run


async def publish_strategy_draft(
    draft_id: str,
    *,
    expected_definition_hash: str,
) -> QuantStrategyDraft:
    row = await _sync_draft(await _require_draft(draft_id))
    if row.definition_hash != expected_definition_hash:
        raise StrategyDraftConflictError("草稿哈希已变化，请重新确认")
    if row.status == "published":
        if not row.published_path:
            raise StrategyDraftConflictError("草稿发布状态异常，请联系管理员检查发布记录")
        logger.info(
            "复用已完成的量化策略草稿发布: draft_id=%s definition_hash=%s",
            draft_id,
            row.definition_hash,
        )
        return _to_api(row)
    if row.status != "backtested" or not row.quality_gate or not row.quality_gate.get("passed"):
        raise StrategyDraftConflictError("草稿必须通过当前版本回测质量门禁后才能发布")
    definition = StrategyDefinition.model_validate(row.definition)
    published_path: Path = await call_blocking(
        get_strategy_registry().publish_definition,
        definition,
        semaphore=misc_semaphore,
    )
    published_path_text = str(published_path)
    try:
        updated = await call_blocking(
            draft_store.record_publication,
            draft_id,
            published_path_text,
            expected_definition_hash=row.definition_hash,
            semaphore=database_semaphore,
        )
    except KeyError as error:
        current = await _require_draft(draft_id)
        if (
            current.status == "published"
            and current.definition_hash == row.definition_hash
            and current.published_path == published_path_text
        ):
            logger.info(
                "量化策略草稿并发发布已对账: draft_id=%s definition_hash=%s",
                draft_id,
                row.definition_hash,
            )
            return _to_api(current)
        raise StrategyDraftConflictError("草稿发布状态已被其他操作更新，请刷新后确认") from error
    return _to_api(updated)


async def delete_strategy_draft(draft_id: str) -> bool:
    row = await _require_draft(draft_id)
    if row.status not in {"draft", "validated"}:
        raise StrategyDraftConflictError("仅待校验或已校验草稿可以删除")
    return await call_blocking(draft_store.delete_draft, draft_id, semaphore=database_semaphore)
