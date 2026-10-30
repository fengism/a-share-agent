"""Portfolio historical equity curve calculation."""

from __future__ import annotations

import asyncio
import logging
import math
import statistics
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.core.market import market_today
from app.financial_data.market.public import get_completed_market_date
from app.financial_data.stock.public import get_kline
from app.modules.portfolio.accounting import LedgerReplay, ReplayedTransaction, parse_trade_time
from app.modules.portfolio.schemas import (
    PortfolioAccountSettings,
    PortfolioEquityCurvePoint,
    PortfolioEquityCurveResponse,
    is_hk_stock_code,
)

_HISTORY_CONCURRENCY = 4


def _money(value: Decimal) -> float:
    return round(float(value), 2)


def _percent(value: Decimal) -> float:
    return round(float(value), 4)


def _risk_metrics(points: list[PortfolioEquityCurvePoint]) -> dict[str, float | int | None]:
    """基于总资产序列计算年化收益、波动、夏普与回撤持续期。"""

    series = [
        (point.date, point.total_assets)
        for point in points
        if point.total_assets is not None and point.total_assets > 0
    ]
    metrics: dict[str, float | int | None] = {
        "annualized_return_pct": None,
        "annualized_volatility_pct": None,
        "sharpe_ratio": None,
        "calmar_ratio": None,
        "win_rate_pct": None,
        "best_day_pct": None,
        "worst_day_pct": None,
        "longest_drawdown_days": None,
    }
    if len(series) < 2:
        return metrics

    first_date, first_value = series[0]
    last_date, last_value = series[-1]
    calendar_days = (last_date - first_date).days
    annualized_return: float | None = None
    if calendar_days > 0 and first_value and first_value > 0:
        annualized_return = (last_value / first_value) ** (365 / calendar_days) - 1
        metrics["annualized_return_pct"] = round(annualized_return * 100, 2)

    returns = [
        last / previous - 1
        for (_, previous), (_, last) in zip(series, series[1:], strict=False)
        if previous and previous > 0
    ]
    if returns:
        metrics["win_rate_pct"] = round(sum(value > 0 for value in returns) / len(returns) * 100, 2)
        metrics["best_day_pct"] = round(max(returns) * 100, 2)
        metrics["worst_day_pct"] = round(min(returns) * 100, 2)
    if len(returns) >= 2:
        volatility = statistics.pstdev(returns) * math.sqrt(252)
        metrics["annualized_volatility_pct"] = round(volatility * 100, 2)
        if volatility > 0 and annualized_return is not None:
            metrics["sharpe_ratio"] = round(annualized_return / volatility, 2)

    peak_value = first_value
    peak_date = first_date
    longest_drawdown = 0
    for current_date, current_value in series[1:]:
        if current_value >= peak_value:
            peak_value = current_value
            peak_date = current_date
        else:
            longest_drawdown = max(longest_drawdown, (current_date - peak_date).days)
    metrics["longest_drawdown_days"] = longest_drawdown

    max_drawdown = min(
        (point.drawdown_pct for point in points if point.drawdown_pct is not None),
        default=None,
    )
    if annualized_return is not None and max_drawdown is not None and max_drawdown < 0:
        metrics["calmar_ratio"] = round(annualized_return * 100 / abs(max_drawdown), 2)
    return metrics


def build_equity_curve(
    replay: LedgerReplay,
    price_history: dict[str, dict[date, float]],
    settings: PortfolioAccountSettings,
    *,
    start_date: date,
    end_date: date,
    sources: list[str] | None = None,
    warnings: list[str] | None = None,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioEquityCurveResponse:
    """Replay cash and share balances, valuing positions at daily unadjusted closes."""
    resolved_fx_rates = {"CNY": 1.0, **(fx_rates or {})}
    transactions_by_date: dict[date, list[ReplayedTransaction]] = defaultdict(list)
    for transaction in replay.transactions:
        transactions_by_date[parse_trade_time(transaction.trade_time).date()].append(transaction)

    prices_by_date: dict[date, dict[str, Decimal]] = defaultdict(dict)
    for code, history in price_history.items():
        for trading_date, close in history.items():
            if start_date <= trading_date <= end_date and close > 0:
                prices_by_date[trading_date][code] = Decimal(str(close))

    curve_dates = {trading_date for trading_date in prices_by_date if start_date <= trading_date <= end_date}
    curve_dates.update(transactions_by_date)
    curve_dates.add(end_date)

    cash_configured = settings.initial_cash is not None
    cash = Decimal(str(settings.initial_cash or 0))
    initial_cash = Decimal(str(settings.initial_cash)) if settings.initial_cash is not None else None
    shares_by_code: dict[str, int] = defaultdict(int)
    last_prices: dict[str, Decimal] = {}
    peak_assets: Decimal | None = initial_cash if initial_cash is not None and initial_cash > 0 else None
    max_drawdown = Decimal("0")
    points: list[PortfolioEquityCurvePoint] = []
    missing_price_codes: set[str] = set()

    for curve_date in sorted(curve_dates):
        prices_today = prices_by_date.get(curve_date, {})
        last_prices.update(prices_today)

        for transaction in transactions_by_date.get(curve_date, []):
            currency = "HKD" if is_hk_stock_code(transaction.stock_code) else "CNY"
            fx_rate = Decimal(str(resolved_fx_rates.get(currency, 1.0)))
            trade_value = transaction.trade_price * transaction.shares * fx_rate
            fee = transaction.fee * fx_rate
            if transaction.side == "buy":
                shares_by_code[transaction.stock_code] += transaction.shares
                if cash_configured:
                    cash -= trade_value + fee
            else:
                shares_by_code[transaction.stock_code] -= transaction.shares
                if cash_configured:
                    cash += trade_value - fee
            if transaction.stock_code not in prices_today:
                last_prices[transaction.stock_code] = transaction.trade_price

        securities_value = Decimal("0")
        unpriced_count = 0
        for code, shares in shares_by_code.items():
            if shares <= 0:
                continue
            price = last_prices.get(code)
            if price is None:
                missing_price_codes.add(code)
                unpriced_count += 1
                continue
            securities_value += (
                price * shares * Decimal(str(resolved_fx_rates.get("HKD" if is_hk_stock_code(code) else "CNY", 1.0)))
            )

        total_assets = cash + securities_value if cash_configured else None
        cumulative_return: Decimal | None = None
        drawdown: Decimal | None = None
        if total_assets is not None:
            if initial_cash is not None and initial_cash > 0:
                cumulative_return = (total_assets / initial_cash - 1) * 100
            if peak_assets is None or total_assets > peak_assets:
                peak_assets = total_assets
            if peak_assets is not None and peak_assets > 0:
                drawdown = (total_assets / peak_assets - 1) * 100
                max_drawdown = min(max_drawdown, drawdown)

        points.append(
            PortfolioEquityCurvePoint(
                date=curve_date,
                cash_balance=_money(cash) if cash_configured else None,
                securities_value=_money(securities_value),
                total_assets=_money(total_assets) if total_assets is not None else None,
                cumulative_return_pct=(_percent(cumulative_return) if cumulative_return is not None else None),
                drawdown_pct=_percent(drawdown) if drawdown is not None else None,
                unpriced_count=unpriced_count,
            )
        )

    resolved_warnings = list(warnings or [])
    if missing_price_codes:
        resolved_warnings.append(
            "以下证券缺少可用历史价格，相关日期资产可能低估：" + "、".join(sorted(missing_price_codes))
        )
    if not cash_configured:
        resolved_warnings.append("未配置初始资金，仅展示证券市值曲线，不计算总资产、收益率和回撤。")
    resolved_warnings.append("曲线按交易流水与不复权收盘价估值，不包含未录入的分红、税费和资金转入转出。")
    if "HKD" not in resolved_fx_rates and any(is_hk_stock_code(item.stock_code) for item in replay.transactions):
        resolved_warnings.append("港元兑人民币汇率不可用，港股相关金额暂按 1:1 折算。")

    last_point = points[-1] if points else None
    metrics = _risk_metrics(points) if cash_configured else {}
    return PortfolioEquityCurveResponse(
        mode="total_assets" if cash_configured else "securities_only",
        start_date=start_date,
        end_date=end_date,
        base_currency="CNY",
        fx_rates=resolved_fx_rates,
        initial_cash=settings.initial_cash,
        current_total_assets=last_point.total_assets if last_point else None,
        current_securities_value=last_point.securities_value if last_point else None,
        total_return_pct=last_point.cumulative_return_pct if last_point else None,
        max_drawdown_pct=_percent(max_drawdown) if cash_configured and points else None,
        annualized_return_pct=metrics.get("annualized_return_pct"),
        annualized_volatility_pct=metrics.get("annualized_volatility_pct"),
        sharpe_ratio=metrics.get("sharpe_ratio"),
        calmar_ratio=metrics.get("calmar_ratio"),
        win_rate_pct=metrics.get("win_rate_pct"),
        best_day_pct=metrics.get("best_day_pct"),
        worst_day_pct=metrics.get("worst_day_pct"),
        longest_drawdown_days=metrics.get("longest_drawdown_days"),
        trading_days=len(points),
        risk_free_rate_pct=0.0,
        points=points,
        sources=sorted(set(sources or [])),
        warnings=resolved_warnings,
    )


async def load_equity_curve(
    replay: LedgerReplay,
    settings: PortfolioAccountSettings,
    *,
    end_date: date | None = None,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioEquityCurveResponse:
    resolved_fx_rates = {"CNY": 1.0, **(fx_rates or {})}
    if not replay.transactions:
        today = end_date or market_today()
        return PortfolioEquityCurveResponse(
            mode="total_assets" if settings.initial_cash is not None else "securities_only",
            start_date=None,
            end_date=today,
            base_currency="CNY",
            fx_rates=resolved_fx_rates,
            initial_cash=settings.initial_cash,
            current_total_assets=settings.initial_cash,
            current_securities_value=0,
            total_return_pct=0 if settings.initial_cash is not None else None,
            max_drawdown_pct=0 if settings.initial_cash is not None else None,
            points=[],
            warnings=["暂无交易流水，无法生成资产变化曲线。"],
        )

    start_date = min(parse_trade_time(item.trade_time).date() for item in replay.transactions)
    completed_end = end_date or await get_completed_market_date(market_today())
    resolved_end = max(completed_end, start_date)
    stock_codes = sorted({item.stock_code for item in replay.transactions})
    semaphore = asyncio.Semaphore(_HISTORY_CONCURRENCY)

    async def load_one(code: str):
        async with semaphore:
            try:
                result = await get_kline(
                    code,
                    "daily",
                    start_date.strftime("%Y%m%d"),
                    resolved_end.strftime("%Y%m%d"),
                    "",
                )
            except Exception as error:
                logging.getLogger(__name__).debug("历史行情加载失败 code=%s: %s", code, error)
                return code, {}, None, f"{code} 历史行情加载失败：{type(error).__name__}"
            prices = {date.fromisoformat(item.date): item.close for item in result.items if item.close > 0}
            return code, prices, result.source, None

    loaded = await asyncio.gather(*(load_one(code) for code in stock_codes))
    histories: dict[str, dict[date, float]] = {}
    sources: list[str] = []
    warnings: list[str] = []
    for code, prices, source, warning in loaded:
        histories[code] = prices
        if source:
            sources.append(source)
        if warning:
            warnings.append(warning)

    return build_equity_curve(
        replay,
        histories,
        settings,
        start_date=start_date,
        end_date=resolved_end,
        sources=sources,
        warnings=warnings,
        fx_rates=resolved_fx_rates,
    )
