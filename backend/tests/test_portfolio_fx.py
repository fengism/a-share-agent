from datetime import date

import pytest

from app.modules.portfolio.accounting import replay_transactions
from app.modules.portfolio.builder import build_portfolio
from app.modules.portfolio.equity_curve import build_equity_curve
from app.modules.portfolio.fx import _parse_sina_fx_rate
from app.modules.portfolio.schemas import PortfolioAccountSettings


def _row(
    row_id: int,
    stock_code: str,
    trade_time: str,
    *,
    side: str = "buy",
    price: float = 400.0,
    shares: int = 100,
    stock_name: str = "腾讯控股",
    fee: float = 0.0,
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
        "fee": str(fee),
        "note": "",
        "created_at": trade_time,
    }


def test_parse_sina_fx_rate():
    assert _parse_sina_fx_rate('var hq_str_fx_shkdcny="0.9000,0.9010,0.8990,0.8500";') == 0.901
    assert _parse_sina_fx_rate('var hq_str_fx_shkdcny="";') is None
    assert _parse_sina_fx_rate("garbage") is None


def test_hk_position_and_summary_are_converted_to_cny():
    replay = replay_transactions([_row(1, "00700", "2026-07-14 10:00:00")])
    portfolio = build_portfolio(
        replay,
        {"00700": {"name": "腾讯控股", "price": 420.0, "last_close": 400.0}},
        quoted_at="2026-07-15 15:00:00",
        quote_source="test",
        quote_stale=False,
        settings=PortfolioAccountSettings(initial_cash=100_000),
        as_of_date=date(2026, 7, 15),
        fx_rates={"CNY": 1.0, "HKD": 0.9},
    )

    assert portfolio.summary.base_currency == "CNY"
    assert portfolio.summary.fx_rates["HKD"] == 0.9
    position = portfolio.positions[0]
    assert position.currency == "HKD"
    assert position.fx_rate_to_cny == 0.9
    assert position.cost_value_native == 40_000.0
    assert position.cost_value == 36_000.0
    assert position.market_value == 37_800.0
    assert position.profit_amount == 1_800.0
    assert position.daily_profit_amount == 1_800.0

    stock = portfolio.stocks[0]
    assert stock.currency == "HKD"
    assert stock.average_cost == 400.0
    assert stock.cost_value == 36_000.0
    assert stock.market_value == 37_800.0
    assert stock.lot_size == 1
    # 港股 T+0，当日买入也可卖
    assert stock.sellable_shares == 100

    summary = portfolio.summary
    assert summary.total_cost == 36_000.0
    assert summary.total_market_value == 37_800.0
    assert summary.cash_balance == 64_000.0
    assert summary.total_asset_value == 101_800.0
    assert summary.previous_close_value == 36_000.0
    assert summary.daily_profit_amount == 1_800.0
    assert summary.daily_profit_pct == 5.0

    transaction = portfolio.transactions[0]
    assert transaction.currency == "HKD"
    assert transaction.fx_rate_to_cny == 0.9
    assert transaction.trade_amount_native == 40_000.0
    assert transaction.trade_amount == 36_000.0


def test_hk_without_fx_rate_warns_and_falls_back_to_one_to_one():
    replay = replay_transactions([_row(1, "00700", "2026-07-14 10:00:00")])
    portfolio = build_portfolio(
        replay,
        {"00700": {"name": "腾讯控股", "price": 420.0, "last_close": 400.0}},
        quoted_at="2026-07-15 15:00:00",
        quote_source="test",
        quote_stale=False,
        settings=PortfolioAccountSettings(initial_cash=100_000),
        as_of_date=date(2026, 7, 15),
    )

    assert portfolio.positions[0].cost_value == 40_000.0
    assert any("兑人民币汇率不可用" in warning for warning in portfolio.risk.warnings)


def test_equity_curve_converts_hk_cash_and_securities():
    replay = replay_transactions([_row(1, "00700", "2026-01-02 10:00:00")])
    response = build_equity_curve(
        replay,
        {"00700": {date(2026, 1, 2): 420.0}},
        PortfolioAccountSettings(initial_cash=100_000),
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 2),
        fx_rates={"CNY": 1.0, "HKD": 0.9},
    )

    assert response.base_currency == "CNY"
    point = response.points[-1]
    assert point.cash_balance == 64_000.0
    assert point.securities_value == 37_800.0
    assert point.total_assets == 101_800.0


@pytest.mark.parametrize("currency,rate", [("CNY", 1.0), ("HKD", 0.9)])
def test_fx_rate_conversion_is_idempotent_for_cny(currency: str, rate: float):
    replay = replay_transactions(
        [
            _row(
                1,
                "600519" if currency == "CNY" else "00700",
                "2026-07-14 10:00:00",
                price=10.0,
                shares=100,
                stock_name="测试",
            )
        ]
    )
    portfolio = build_portfolio(
        replay,
        {replay.transactions[0].stock_code: {"price": 10.0, "last_close": 10.0}},
        quoted_at="2026-07-15 15:00:00",
        quote_source="test",
        quote_stale=False,
        settings=PortfolioAccountSettings(initial_cash=10_000),
        as_of_date=date(2026, 7, 15),
        fx_rates={"CNY": 1.0, "HKD": rate},
    )

    assert portfolio.positions[0].fx_rate_to_cny == rate
    assert portfolio.positions[0].cost_value == pytest.approx(1000 * rate)
