"""Portfolio historical equity curve calculation."""

from __future__ import annotations

import asyncio
import logging
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
)

_HISTORY_CONCURRENCY = 4


def _money(value: Decimal) -> float:
    return round(float(value), 2)


def _percent(value: Decimal) -> float:
    return round(float(value), 4)


def build_equity_curve(
    replay: LedgerReplay,
    price_history: dict[str, dict[date, float]],
    settings: PortfolioAccountSettings,
    *,
    start_date: date,
    end_date: date,
    sources: list[str] | None = None,
    warnings: list[str] | None = None,
) -> PortfolioEquityCurveResponse:
    """Replay cash and share balances, valuing positions at daily unadjusted closes."""
    transactions_by_date: dict[date, list[ReplayedTransaction]] = defaultdict(list)
    for transaction in replay.transactions:
        transactions_by_date[parse_trade_time(transaction.trade_time).date()].append(transaction)

    prices_by_date: dict[date, dict[str, Decimal]] = defaultdict(dict)
    for code, history in price_history.items():
        for trading_date, close in history.items():
            if start_date <= trading_date <= end_date and close > 0:
                prices_by_date[trading_date][code] = Decimal(str(close))

    curve_dates = {
        trading_date
        for trading_date in prices_by_date
        if start_date <= trading_date <= end_date
    }
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
            trade_value = transaction.trade_price * transaction.shares
            if transaction.side == "buy":
                shares_by_code[transaction.stock_code] += transaction.shares
                if cash_configured:
                    cash -= trade_value + transaction.fee
            else:
                shares_by_code[transaction.stock_code] -= transaction.shares
                if cash_configured:
                    cash += trade_value - transaction.fee
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
            securities_value += price * shares

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

        points.append(PortfolioEquityCurvePoint(
            date=curve_date,
            cash_balance=_money(cash) if cash_configured else None,
            securities_value=_money(securities_value),
            total_assets=_money(total_assets) if total_assets is not None else None,
            cumulative_return_pct=(
                _percent(cumulative_return) if cumulative_return is not None else None
            ),
            drawdown_pct=_percent(drawdown) if drawdown is not None else None,
            unpriced_count=unpriced_count,
        ))

    resolved_warnings = list(warnings or [])
    if missing_price_codes:
        resolved_warnings.append(
            "以下证券缺少可用历史价格，相关日期资产可能低估："
            + "、".join(sorted(missing_price_codes))
        )
    if not cash_configured:
        resolved_warnings.append("未配置初始资金，仅展示证券市值曲线，不计算总资产、收益率和回撤。")
    resolved_warnings.append("曲线按交易流水与不复权收盘价估值，不包含未录入的分红、税费和资金转入转出。")

    last_point = points[-1] if points else None
    return PortfolioEquityCurveResponse(
        mode="total_assets" if cash_configured else "securities_only",
        start_date=start_date,
        end_date=end_date,
        initial_cash=settings.initial_cash,
        current_total_assets=last_point.total_assets if last_point else None,
        current_securities_value=last_point.securities_value if last_point else None,
        total_return_pct=last_point.cumulative_return_pct if last_point else None,
        max_drawdown_pct=_percent(max_drawdown) if cash_configured and points else None,
        points=points,
        sources=sorted(set(sources or [])),
        warnings=resolved_warnings,
    )


async def load_equity_curve(
    replay: LedgerReplay,
    settings: PortfolioAccountSettings,
    *,
    end_date: date | None = None,
) -> PortfolioEquityCurveResponse:
    if not replay.transactions:
        today = end_date or market_today()
        return PortfolioEquityCurveResponse(
            mode="total_assets" if settings.initial_cash is not None else "securities_only",
            start_date=None,
            end_date=today,
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
            prices = {
                date.fromisoformat(item.date): item.close
                for item in result.items
                if item.close > 0
            }
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
    )
