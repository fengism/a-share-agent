from datetime import date
from decimal import Decimal

import pytest

from app.modules.portfolio.accounting import OpenLot, replay_transactions
from app.modules.portfolio.availability import (
    is_t_plus_one,
    lot_size,
    round_down_to_lot,
    round_up_to_lot,
    sellable_shares,
)
from app.modules.portfolio.builder import build_portfolio
from app.modules.portfolio.equity_curve import build_equity_curve
from app.modules.portfolio.schemas import PortfolioAccountSettings


def _row(
    row_id: int,
    stock_code: str,
    trade_time: str,
    *,
    side: str = "buy",
    price: float = 10.0,
    shares: int = 100,
    stock_name: str = "测试股票",
) -> dict:
    return {
        "id": row_id,
        "user_id": 1,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "side": side,
        "trade_price": str(price),
        "trade_time": trade_time,
        "shares": shares,
        "fee": "0",
        "note": "",
        "created_at": trade_time,
    }


def test_position_daily_profit_and_t_plus_one_availability():
    replay = replay_transactions(
        [
            _row(1, "600519", "2026-07-14 10:00:00", price=1500, stock_name="贵州茅台"),
            _row(2, "600519", "2026-07-15 10:00:00", price=1500, stock_name="贵州茅台"),
        ]
    )
    portfolio = build_portfolio(
        replay,
        {"600519": {"name": "贵州茅台", "price": 1600, "last_close": 1550}},
        quoted_at="2026-07-15 15:00:00",
        quote_source="test",
        quote_stale=False,
        settings=PortfolioAccountSettings(initial_cash=1_000_000),
        as_of_date=date(2026, 7, 15),
    )

    by_time = {position.buy_time: position for position in portfolio.positions}
    assert by_time["2026-07-14 10:00:00"].sellable_shares == 100
    assert by_time["2026-07-14 10:00:00"].frozen_shares == 0
    assert by_time["2026-07-15 10:00:00"].sellable_shares == 0
    assert by_time["2026-07-15 10:00:00"].frozen_shares == 100
    assert by_time["2026-07-15 10:00:00"].daily_profit_amount == 5000.0

    stock = portfolio.stocks[0]
    assert stock.sellable_shares == 100
    assert stock.frozen_shares == 100
    assert stock.daily_profit_amount == 10000.0
    assert stock.lot_size == 100
    assert portfolio.summary.previous_close_value == 310000.0
    assert portfolio.summary.daily_profit_amount == 10000.0
    assert portfolio.summary.daily_profit_pct == 3.23


def test_risk_metrics_and_trim_suggestion_respect_lot_and_sellable_shares():
    replay = replay_transactions([_row(1, "600519", "2026-07-01 10:00:00", price=10, shares=1000)])
    portfolio = build_portfolio(
        replay,
        {"600519": {"name": "贵州茅台", "price": 10.5, "last_close": 10.0}},
        quoted_at="2026-07-15 15:00:00",
        quote_source="test",
        quote_stale=False,
        settings=PortfolioAccountSettings(
            initial_cash=20_000,
            max_single_stock_pct=30,
            max_sector_pct=40,
            max_total_position_pct=80,
        ),
        industries={"600519": {"sw_level1_name": "食品饮料"}},
        as_of_date=date(2026, 7, 15),
    )

    risk = portfolio.risk
    assert risk.top5_concentration_pct == 51.22
    assert risk.concentration_index == 2623.49
    assert risk.effective_holding_count == 3.81
    assert risk.cash_pct == 48.78
    assert risk.concentration_level == "high"

    assert len(risk.trim_suggestions) == 1
    suggestion = risk.trim_suggestions[0]
    assert suggestion.stock_code == "600519"
    assert suggestion.suggested_shares == 500
    assert suggestion.sellable_shares == 1000
    assert suggestion.lot_size == 100
    assert suggestion.estimated_amount == 5250.0
    assert suggestion.reasons


def test_equity_curve_risk_metrics():
    replay = replay_transactions([_row(1, "600519", "2026-01-02 10:00:00", price=10, shares=1000)])
    response = build_equity_curve(
        replay,
        {
            "600519": {
                date(2026, 1, 2): 10.0,
                date(2026, 1, 3): 11.0,
                date(2026, 1, 4): 9.0,
                date(2026, 1, 6): 12.0,
            }
        },
        PortfolioAccountSettings(initial_cash=100_000),
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 6),
    )

    assert response.trading_days == 4
    assert response.max_drawdown_pct == pytest.approx(-1.98, abs=1e-3)
    assert response.annualized_return_pct is not None
    assert response.annualized_volatility_pct is not None
    assert response.sharpe_ratio is not None
    assert response.calmar_ratio is not None
    assert response.win_rate_pct == 66.67
    assert response.best_day_pct == 3.03
    assert response.worst_day_pct == -1.98
    assert response.longest_drawdown_days == 1
    assert response.risk_free_rate_pct == 0.0


def test_availability_helpers_handle_lots_and_hk_t_plus_zero():
    assert is_t_plus_one("600519") is True
    assert is_t_plus_one("00700") is False
    assert lot_size("600519") == 100
    assert lot_size("00700") == 1

    assert round_down_to_lot(60.6, "600519") == 0
    assert round_down_to_lot(260, "600519") == 200
    assert round_up_to_lot(60.6, "600519") == 100
    assert round_up_to_lot(200.1, "600519") == 300
    assert round_up_to_lot(0, "600519") == 0

    lots = [
        OpenLot(
            transaction_id=1,
            stock_code="00700",
            stock_name="腾讯控股",
            buy_price=Decimal("300"),
            buy_time="2026-07-15 10:00:00",
            original_shares=100,
            remaining_shares=100,
            unit_cost=Decimal("300"),
        )
    ]
    # 港股 T+0：当日买入也可卖出
    assert sellable_shares(lots, "00700", as_of_date=date(2026, 7, 15)) == 100


@pytest.mark.asyncio
async def test_resolve_portfolio_as_of_date_uses_trading_calendar_for_a_shares(monkeypatch):
    import app.core.market as market_module
    import app.financial_data.market.trading_session as trading_session
    from app.modules.portfolio.availability import resolve_portfolio_as_of_date

    monkeypatch.setattr(market_module, "market_today", lambda: date(2026, 7, 18))
    calls: list[date] = []

    async def fake_market_date_on_or_before(requested_date: date) -> date:
        calls.append(requested_date)
        return date(2026, 7, 17)

    monkeypatch.setattr(trading_session, "get_market_date_on_or_before", fake_market_date_on_or_before)

    # 周六查询 A 股组合：对齐到最近交易日周五，周五买入仍处于冻结状态。
    assert await resolve_portfolio_as_of_date(["600519"]) == date(2026, 7, 17)
    assert calls == [date(2026, 7, 18)]
    # 纯港股组合为 T+0，不触发交易日历请求。
    assert await resolve_portfolio_as_of_date(["00700"]) == date(2026, 7, 18)
    assert calls == [date(2026, 7, 18)]


def test_remaining_add_capacity_and_stale_quote_warning():
    replay = replay_transactions([_row(1, "600519", "2026-07-01 10:00:00", price=10, shares=1000)])
    portfolio = build_portfolio(
        replay,
        {"600519": {"name": "贵州茅台", "price": 10.5, "last_close": 10.0}},
        quoted_at="2026-07-15 15:00:00",
        quote_source="test",
        quote_stale=True,
        settings=PortfolioAccountSettings(
            initial_cash=20_000,
            max_total_position_pct=80,
        ),
        as_of_date=date(2026, 7, 15),
    )

    # 总资产 20500（现金 10000 + 证券 10500），80% 上限对应 16400；
    # 剩余仓位空间 5900，小于可用现金 10000，因此取 5900。
    assert portfolio.risk.remaining_add_capacity == 5900.0
    assert any("行情非最新" in warning for warning in portfolio.risk.warnings)
