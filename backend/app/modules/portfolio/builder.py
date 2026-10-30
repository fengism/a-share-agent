import math
from datetime import date
from decimal import Decimal

from app.core.market import market_today, safe_float
from app.modules.portfolio.accounting import (
    LedgerReplay,
    LotMatch,
    OpenLot,
    ReplayedTransaction,
    TransactionPreview,
    parse_trade_time,
)
from app.modules.portfolio.availability import (
    A_SHARE_LOT_SIZE,
    is_t_plus_one,
    lot_size,
    round_down_to_lot,
    round_up_to_lot,
)
from app.modules.portfolio.schemas import (
    PortfolioAccountSettings,
    PortfolioClosedPosition,
    PortfolioLotMatch,
    PortfolioPosition,
    PortfolioResponse,
    PortfolioRiskSummary,
    PortfolioSectorAllocation,
    PortfolioStockSummary,
    PortfolioSummary,
    PortfolioTransaction,
    PortfolioTransactionCreate,
    PortfolioTransactionPreview,
    PortfolioTrimSuggestion,
    is_hk_stock_code,
)


def _currency_for(stock_code: str) -> str:
    return "HKD" if is_hk_stock_code(stock_code) else "CNY"


def _fx_rate_for(stock_code: str, fx_rates: dict[str, float] | None) -> float:
    """返回标的币种到人民币的汇率；缺失时按 1:1 兜底并交由上层提示。"""

    currency = _currency_for(stock_code)
    if currency == "CNY":
        return 1.0
    rate = (fx_rates or {}).get(currency)
    if rate is not None and math.isfinite(rate) and rate > 0:
        return float(rate)
    return 1.0


def current_price(quote: dict) -> float | None:
    price = float(quote.get("price") or quote.get("last_close") or 0)
    return price if price > 0 else None


def previous_close(quote: dict, price: float | None) -> float | None:
    """优先使用行情源的昨收，缺失时用涨跌幅反推。"""

    last_close = safe_float(quote.get("last_close"))
    if last_close is not None and math.isfinite(last_close) and last_close > 0:
        return last_close
    change_pct = safe_float(quote.get("change_pct"))
    if price is not None and price > 0 and change_pct is not None and math.isfinite(change_pct) and change_pct > -100:
        return round(price / (1 + change_pct / 100), 4)
    return None


def _daily_profit(shares: int, price: float | None, prev_close: float | None) -> tuple[float | None, float | None]:
    if price is None or prev_close is None or prev_close <= 0:
        return None, None
    amount = round((price - prev_close) * shares, 2)
    return amount, round((price / prev_close - 1) * 100, 2)


def _position_availability(lot: OpenLot, *, as_of_date: date) -> tuple[int, int]:
    if is_t_plus_one(lot.stock_code) and parse_trade_time(lot.buy_time).date() >= as_of_date:
        sellable = 0
    else:
        sellable = lot.remaining_shares
    return sellable, lot.remaining_shares - sellable


def _money(value: Decimal | float | int) -> float:
    return round(float(value), 2)


def position_from_lot(
    lot: OpenLot,
    quote: dict,
    *,
    as_of_date: date | None = None,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioPosition:
    resolved_date = as_of_date or market_today()
    resolved_price = current_price(quote)
    prev_close = previous_close(quote, resolved_price)
    daily_amount, daily_pct = _daily_profit(lot.remaining_shares, resolved_price, prev_close)
    sellable, frozen = _position_availability(lot, as_of_date=resolved_date)
    currency = _currency_for(lot.stock_code)
    fx_rate = _fx_rate_for(lot.stock_code, fx_rates)
    cost_value_native = _money(lot.remaining_cost)
    cost_value = _money(cost_value_native * fx_rate)
    market_value = _money(resolved_price * lot.remaining_shares * fx_rate) if resolved_price is not None else None
    daily_amount = _money(daily_amount * fx_rate) if daily_amount is not None else None
    profit_amount = _money(market_value - cost_value) if market_value is not None else None
    profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None and cost_value else None
    return PortfolioPosition(
        id=lot.transaction_id,
        stock_code=lot.stock_code,
        stock_name=quote.get("name") or lot.stock_name or lot.stock_code,
        buy_price=float(lot.buy_price),
        buy_time=lot.buy_time,
        shares=lot.remaining_shares,
        currency=currency,
        fx_rate_to_cny=fx_rate,
        current_price=resolved_price,
        change_pct=float(quote["change_pct"]) if quote.get("change_pct") is not None else None,
        prev_close=prev_close,
        daily_profit_amount=daily_amount,
        daily_profit_pct=daily_pct,
        sellable_shares=sellable,
        frozen_shares=frozen,
        cost_value=cost_value,
        cost_value_native=cost_value_native,
        market_value=market_value,
        profit_amount=profit_amount,
        profit_pct=profit_pct,
    )


def position_from_transaction(
    row: dict,
    quote: dict,
    *,
    as_of_date: date | None = None,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioPosition:
    resolved_date = as_of_date or market_today()
    shares = int(row["shares"])
    trade_price = float(row["trade_price"])
    resolved_price = current_price(quote)
    prev_close = previous_close(quote, resolved_price)
    daily_amount, daily_pct = _daily_profit(shares, resolved_price, prev_close)
    stock_code = str(row["stock_code"])
    currency = _currency_for(stock_code)
    fx_rate = _fx_rate_for(stock_code, fx_rates)
    resolved_lot = OpenLot(
        transaction_id=int(row["id"]),
        stock_code=stock_code,
        stock_name=str(row.get("stock_name") or ""),
        buy_price=Decimal(str(trade_price)),
        buy_time=str(row["trade_time"]),
        original_shares=shares,
        remaining_shares=shares,
        unit_cost=(Decimal(str(trade_price)) * shares + Decimal(str(row.get("fee") or 0))) / shares,
    )
    sellable, frozen = _position_availability(resolved_lot, as_of_date=resolved_date)
    cost_value_native = _money(trade_price * shares + float(row.get("fee") or 0))
    cost_value = _money(cost_value_native * fx_rate)
    market_value = _money(resolved_price * shares * fx_rate) if resolved_price is not None else None
    daily_amount = _money(daily_amount * fx_rate) if daily_amount is not None else None
    profit_amount = _money(market_value - cost_value) if market_value is not None else None
    profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None and cost_value else None
    return PortfolioPosition(
        id=int(row["id"]),
        stock_code=stock_code,
        stock_name=quote.get("name") or row["stock_name"] or stock_code,
        buy_price=trade_price,
        buy_time=str(row["trade_time"]),
        shares=shares,
        currency=currency,
        fx_rate_to_cny=fx_rate,
        current_price=resolved_price,
        change_pct=float(quote["change_pct"]) if quote.get("change_pct") is not None else None,
        prev_close=prev_close,
        daily_profit_amount=daily_amount,
        daily_profit_pct=daily_pct,
        sellable_shares=sellable,
        frozen_shares=frozen,
        cost_value=cost_value,
        cost_value_native=cost_value_native,
        market_value=market_value,
        profit_amount=profit_amount,
        profit_pct=profit_pct,
    )


def lot_match_from_replay(
    match: LotMatch,
    stock_code: str,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioLotMatch:
    currency = _currency_for(stock_code)
    fx_rate = Decimal(str(_fx_rate_for(stock_code, fx_rates)))
    return PortfolioLotMatch(
        buy_transaction_id=match.buy_transaction_id,
        buy_time=match.buy_time,
        buy_price=float(match.buy_price),
        shares=match.shares,
        unit_cost=float(match.unit_cost),
        matched_cost=_money(match.matched_cost * fx_rate),
        currency=currency,
    )


def transaction_from_replay(
    transaction: ReplayedTransaction,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioTransaction:
    currency = _currency_for(transaction.stock_code)
    fx_rate = _fx_rate_for(transaction.stock_code, fx_rates)
    decimal_fx_rate = Decimal(str(fx_rate))
    trade_amount_native = _money(transaction.trade_price * transaction.shares)
    return PortfolioTransaction(
        id=transaction.id,
        stock_code=transaction.stock_code,
        stock_name=transaction.stock_name or transaction.stock_code,
        side=transaction.side,
        trade_price=float(transaction.trade_price),
        trade_time=transaction.trade_time,
        shares=transaction.shares,
        fee=_money(transaction.fee * decimal_fx_rate),
        fee_native=_money(transaction.fee),
        note=transaction.note,
        created_at=transaction.created_at,
        currency=currency,
        fx_rate_to_cny=fx_rate,
        trade_amount=_money(trade_amount_native * fx_rate),
        trade_amount_native=trade_amount_native,
        matched_cost=(
            _money(transaction.matched_cost * decimal_fx_rate) if transaction.matched_cost is not None else None
        ),
        realized_profit_amount=(
            _money(transaction.realized_profit * decimal_fx_rate) if transaction.realized_profit is not None else None
        ),
        matches=[lot_match_from_replay(match, transaction.stock_code, fx_rates) for match in transaction.matches],
    )


def preview_from_replay(
    request: PortfolioTransactionCreate,
    preview: TransactionPreview,
    portfolio_after: PortfolioResponse | None = None,
    *,
    target_sector_name: str | None = None,
) -> PortfolioTransactionPreview:
    stock_after = next(
        (
            stock
            for stock in (portfolio_after.stocks if portfolio_after else [])
            if stock.stock_code == request.stock_code
        ),
        None,
    )
    resolved_sector_name = stock_after.sector_name if stock_after else target_sector_name
    sector_after = next(
        (
            sector
            for sector in (portfolio_after.risk.sector_allocations if portfolio_after else [])
            if resolved_sector_name is not None and sector.sector_name == resolved_sector_name
        ),
        None,
    )
    warnings: list[str] = []
    if portfolio_after is not None:
        settings = portfolio_after.settings
        summary = portfolio_after.summary
        if not summary.cash_configured:
            warnings.append("尚未配置初始资金，无法评估交易后的现金和真实仓位。")
        elif summary.cash_balance is not None and summary.cash_balance < 0:
            warnings.append(f"交易后现金将为 {summary.cash_balance:.2f} 元，已超出可用资金。")
        if summary.total_asset_value is not None and summary.total_asset_value <= 0:
            warnings.append("交易后总资产小于等于 0，无法计算有效仓位比例。")
        if stock_after is not None and resolved_sector_name is None:
            warnings.append("暂无该股票行业归属，交易后行业集中度可能被低估。")
        if summary.total_position_pct is not None and summary.total_position_pct > settings.max_total_position_pct:
            warnings.append(
                f"交易后总仓位 {summary.total_position_pct:.2f}% 超过上限 {settings.max_total_position_pct:.2f}%。"
            )
        if (
            stock_after
            and stock_after.allocation_pct is not None
            and (stock_after.allocation_pct > settings.max_single_stock_pct)
        ):
            warnings.append(
                f"交易后单股仓位 {stock_after.allocation_pct:.2f}% 超过上限 {settings.max_single_stock_pct:.2f}%。"
            )
        if (
            sector_after
            and sector_after.allocation_pct is not None
            and (sector_after.allocation_pct > settings.max_sector_pct)
        ):
            warnings.append(
                f"交易后{sector_after.sector_name}仓位 {sector_after.allocation_pct:.2f}% "
                f"超过上限 {settings.max_sector_pct:.2f}%。"
            )
    stock_position_pct_after = stock_after.allocation_pct if stock_after else None
    if portfolio_after is not None and request.side == "sell" and stock_after is None:
        stock_position_pct_after = 0
    sector_position_pct_after = sector_after.allocation_pct if sector_after else None
    if portfolio_after is not None and resolved_sector_name is not None and sector_after is None:
        sector_position_pct_after = 0
    frozen_shares = max(preview.available_shares - preview.sellable_shares, 0)
    trade_lot_size = lot_size(request.stock_code)
    if request.shares % trade_lot_size != 0:
        if trade_lot_size == A_SHARE_LOT_SIZE:
            warnings.append("A 股交易数量通常为 100 股的整数倍，请确认股数；不足一手可能无法成交。")
        else:
            warnings.append(f"港股每手股数因标的而异，当前按 {trade_lot_size} 股/手估算，请确认实际手数。")
    if is_t_plus_one(request.stock_code):
        if request.side == "sell" and request.shares > preview.sellable_shares:
            warnings.append(
                f"A 股 T+1：交易时点可卖 {preview.sellable_shares} 股，当日买入的 {frozen_shares} 股不可卖出。"
            )
    if request.side == "sell":
        sellable_after = preview.sellable_shares - request.shares
    else:
        sellable_after = preview.sellable_shares + (0 if is_t_plus_one(request.stock_code) else request.shares)
    fx_rates = portfolio_after.summary.fx_rates if portfolio_after else None
    currency = _currency_for(request.stock_code)
    fx_rate = _fx_rate_for(request.stock_code, fx_rates)
    decimal_fx_rate = Decimal(str(fx_rate))
    if currency != "CNY" and currency not in (fx_rates or {}):
        warnings.append("港元兑人民币汇率不可用，本次预演按 1:1 折算，跨市场金额可能失真。")
    trade_amount_native = _money(request.trade_price * request.shares)
    return PortfolioTransactionPreview(
        stock_code=request.stock_code,
        side=request.side,
        trade_time=request.trade_time.isoformat(timespec="seconds"),
        currency=currency,
        fx_rate_to_cny=fx_rate,
        available_shares=preview.available_shares,
        sellable_shares=preview.sellable_shares,
        frozen_shares=frozen_shares,
        sellable_after_trade=sellable_after,
        shares_after_trade=preview.shares_after_trade,
        current_shares_after=preview.current_shares_after,
        matched_cost=(_money(preview.matched_cost * decimal_fx_rate) if preview.matched_cost is not None else None),
        realized_profit_amount=(
            _money(preview.realized_profit * decimal_fx_rate) if preview.realized_profit is not None else None
        ),
        matches=[lot_match_from_replay(match, request.stock_code, fx_rates) for match in preview.matches],
        trade_amount=_money(trade_amount_native * fx_rate),
        trade_amount_native=trade_amount_native,
        fee=_money(Decimal(str(request.fee)) * decimal_fx_rate),
        fee_native=_money(request.fee),
        cash_balance_after=portfolio_after.summary.cash_balance if portfolio_after else None,
        estimated_total_assets_after=(portfolio_after.summary.total_asset_value if portfolio_after else None),
        total_position_pct_after=(portfolio_after.summary.total_position_pct if portfolio_after else None),
        stock_position_pct_after=stock_position_pct_after,
        sector_name=resolved_sector_name,
        sector_position_pct_after=sector_position_pct_after,
        warnings=warnings,
    )


def _group_positions(positions: list[PortfolioPosition]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}
    for position in positions:
        item = grouped.setdefault(
            position.stock_code,
            {
                "stock_name": position.stock_name,
                "position_count": 0,
                "total_shares": 0,
                "sellable_shares": 0,
                "frozen_shares": 0,
                "currency": position.currency,
                "fx_rate_to_cny": position.fx_rate_to_cny,
                "cost_value": 0.0,
                "cost_value_native": 0.0,
                "current_price": position.current_price,
                "change_pct": position.change_pct,
                "prev_close": position.prev_close,
                "previous_close_value": 0.0,
                "daily_profit_amount": None,
            },
        )
        item["position_count"] += 1
        item["total_shares"] += position.shares
        item["sellable_shares"] += position.sellable_shares or 0
        item["frozen_shares"] += position.frozen_shares or 0
        item["currency"] = position.currency
        item["fx_rate_to_cny"] = position.fx_rate_to_cny
        item["cost_value"] += position.cost_value
        item["cost_value_native"] += position.cost_value_native
        if position.current_price is not None:
            item["current_price"] = position.current_price
            item["change_pct"] = position.change_pct
        if position.prev_close is not None:
            item["prev_close"] = position.prev_close
            item["previous_close_value"] += position.prev_close * position.shares * position.fx_rate_to_cny
        if position.daily_profit_amount is not None:
            item["daily_profit_amount"] = round(
                (item["daily_profit_amount"] or 0) + position.daily_profit_amount,
                2,
            )
    return grouped


def _build_stock_summaries(
    grouped: dict[str, dict],
    replay: LedgerReplay,
) -> list[PortfolioStockSummary]:
    stocks = []
    for stock_code, item in grouped.items():
        total_shares = item["total_shares"]
        cost_value = _money(item["cost_value"])
        cost_value_native = _money(item["cost_value_native"])
        resolved_price = item["current_price"]
        fx_rate = float(item["fx_rate_to_cny"] or 1.0)
        market_value = _money(resolved_price * total_shares * fx_rate) if resolved_price is not None else None
        profit_amount = _money(market_value - cost_value) if market_value is not None else None
        profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None and cost_value else None
        realized_profit = _money(replay.realized_by_stock.get(stock_code, Decimal("0")) * Decimal(str(fx_rate)))
        total_profit = _money(realized_profit + profit_amount) if profit_amount is not None else None
        stocks.append(
            PortfolioStockSummary(
                stock_code=stock_code,
                stock_name=item["stock_name"],
                position_count=item["position_count"],
                total_shares=total_shares,
                average_cost=round(cost_value_native / total_shares, 4),
                currency=item["currency"],
                fx_rate_to_cny=fx_rate,
                current_price=resolved_price,
                change_pct=item["change_pct"],
                prev_close=item["prev_close"],
                daily_profit_amount=item["daily_profit_amount"],
                daily_profit_pct=(
                    round(item["daily_profit_amount"] / item["previous_close_value"] * 100, 2)
                    if item["daily_profit_amount"] is not None and item["previous_close_value"]
                    else None
                ),
                sellable_shares=item["sellable_shares"],
                frozen_shares=item["frozen_shares"],
                lot_size=lot_size(stock_code),
                cost_value=cost_value,
                market_value=market_value,
                profit_amount=profit_amount,
                profit_pct=profit_pct,
                realized_profit_amount=realized_profit,
                total_profit_amount=total_profit,
            )
        )
    stocks.sort(key=lambda item: item.market_value or item.cost_value, reverse=True)
    total_absolute_profit = sum((abs(stock.profit_amount or 0) for stock in stocks), 0.0)
    for stock in stocks:
        stock.profit_contribution_pct = (
            round((stock.profit_amount or 0) / total_absolute_profit * 100, 2)
            if stock.profit_amount is not None and total_absolute_profit
            else None
        )
    return stocks


def _estimated_stock_value(stock: PortfolioStockSummary) -> float:
    return stock.market_value if stock.market_value is not None else stock.cost_value


def _apply_allocations(
    stocks: list[PortfolioStockSummary],
    summary: PortfolioSummary,
    industries: dict[str, dict],
    settings: PortfolioAccountSettings,
) -> None:
    securities_value = summary.estimated_securities_value
    priced_market_value = summary.total_market_value
    for stock in stocks:
        estimated_value = _estimated_stock_value(stock)
        stock.securities_allocation_pct = (
            round(estimated_value / securities_value * 100, 2) if securities_value else None
        )
        if summary.cash_configured:
            stock.allocation_pct = (
                round(estimated_value / summary.total_asset_value * 100, 2)
                if summary.total_asset_value and summary.total_asset_value > 0
                else None
            )
        else:
            stock.allocation_pct = (
                round(stock.market_value / priced_market_value * 100, 2)
                if stock.market_value is not None and priced_market_value
                else None
            )
        industry = industries.get(stock.stock_code) or industries.get(stock.stock_code.split(".", 1)[0]) or {}
        stock.sector_name = str(industry.get("sw_level1_name") or "").strip() or None

    if not summary.cash_configured or summary.total_asset_value is None or summary.total_asset_value <= 0:
        return

    total_assets = summary.total_asset_value
    sector_values: dict[str, float] = {}
    for stock in stocks:
        if stock.sector_name:
            sector_values[stock.sector_name] = sector_values.get(stock.sector_name, 0.0) + _estimated_stock_value(stock)
    total_headroom = settings.max_total_position_pct / 100 * total_assets - summary.estimated_securities_value
    cash_headroom = max(summary.cash_balance or 0, 0)
    for stock in stocks:
        estimated_value = _estimated_stock_value(stock)
        caps = [
            settings.max_single_stock_pct / 100 * total_assets - estimated_value,
            total_headroom,
            cash_headroom,
        ]
        if stock.sector_name:
            caps.append(settings.max_sector_pct / 100 * total_assets - sector_values.get(stock.sector_name, 0.0))
        headroom = max(0.0, min(caps))
        price = (stock.current_price or stock.average_cost) * stock.fx_rate_to_cny
        shares = round_down_to_lot(headroom / price, stock.stock_code) if price and price > 0 else 0
        stock.max_additional_shares = shares
        stock.max_additional_value = _money(shares * price) if price and price > 0 else _money(headroom)


def _build_sector_allocations(
    stocks: list[PortfolioStockSummary],
    summary: PortfolioSummary,
) -> list[PortfolioSectorAllocation]:
    grouped: dict[str, dict[str, object]] = {}
    for stock in stocks:
        if not stock.sector_name:
            continue
        if summary.cash_configured:
            position_value = _estimated_stock_value(stock)
        elif stock.market_value is not None:
            position_value = stock.market_value
        else:
            continue
        item = grouped.setdefault(stock.sector_name, {"market_value": 0.0, "stock_codes": []})
        item["market_value"] = float(item["market_value"]) + position_value
        stock_codes = item["stock_codes"]
        if isinstance(stock_codes, list):
            stock_codes.append(stock.stock_code)
    denominator = summary.total_asset_value if summary.cash_configured else summary.total_market_value
    allocations = [
        PortfolioSectorAllocation(
            sector_name=name,
            market_value=_money(item["market_value"]),
            allocation_pct=(
                round(float(item["market_value"]) / denominator * 100, 2) if denominator and denominator > 0 else None
            ),
            stock_codes=list(item["stock_codes"]),
        )
        for name, item in grouped.items()
    ]
    allocations.sort(key=lambda item: item.market_value, reverse=True)
    return allocations


def _concentration_metrics(
    allocated_stocks: list[PortfolioStockSummary],
) -> tuple[float | None, float | None, float | None, float | None, float | None, float | None]:
    """分别计算含现金和纯证券两套集中度。

    含现金口径用于评估总资产分散度；纯证券口径用于回答“持仓股票有多集中”，
    两者分母不同，不能混用。
    """

    portfolio_weights = [(stock.allocation_pct or 0) / 100 for stock in allocated_stocks]
    securities_values = [_estimated_stock_value(stock) for stock in allocated_stocks]
    securities_total = sum(securities_values)
    securities_weights = [value / securities_total for value in securities_values] if securities_total > 0 else []

    def _metrics(weights: list[float]) -> tuple[float | None, float | None, float | None]:
        squared_sum = sum(weight * weight for weight in weights)
        if squared_sum <= 0:
            return None, None, None
        return (
            round(squared_sum * 10_000, 2),
            round(1 / squared_sum, 2),
            round(sum(sorted(weights, reverse=True)[:5]) * 100, 2),
        )

    portfolio_hhi, portfolio_effective_count, portfolio_top5 = _metrics(portfolio_weights)
    securities_hhi, securities_effective_count, securities_top5 = _metrics(securities_weights)
    return (
        portfolio_hhi,
        portfolio_effective_count,
        portfolio_top5,
        securities_hhi,
        securities_effective_count,
        securities_top5,
    )


def _build_trim_suggestions(
    stocks: list[PortfolioStockSummary],
    summary: PortfolioSummary,
    settings: PortfolioAccountSettings,
) -> list[PortfolioTrimSuggestion]:
    """按单股、行业、总仓位三个约束生成减仓建议。"""

    if not summary.cash_configured or summary.total_asset_value is None or summary.total_asset_value <= 0 or not stocks:
        return []
    total_assets = summary.total_asset_value
    values = {stock.stock_code: _estimated_stock_value(stock) for stock in stocks}
    original_values = dict(values)
    prices = {stock.stock_code: (stock.current_price or stock.average_cost) * stock.fx_rate_to_cny for stock in stocks}
    reasons: dict[str, list[str]] = {stock.stock_code: [] for stock in stocks}

    def apply_trim(stock_code: str, amount: float, reason: str) -> float:
        applied = max(0.0, min(amount, values[stock_code]))
        if applied <= 1e-9:
            return 0.0
        values[stock_code] -= applied
        if reason not in reasons[stock_code]:
            reasons[stock_code].append(reason)
        return applied

    # 1. 单股超限
    for stock in sorted(stocks, key=lambda item: values[item.stock_code], reverse=True):
        stock_code = stock.stock_code
        current_pct = values[stock_code] / total_assets * 100
        limit = settings.max_single_stock_pct
        if current_pct > limit + 1e-9:
            target_value = total_assets * limit / 100
            apply_trim(
                stock_code,
                values[stock_code] - target_value,
                f"单股仓位 {current_pct:.2f}% 超过上限 {limit:.2f}%",
            )

    # 2. 行业超限
    sector_members: dict[str, list[PortfolioStockSummary]] = {}
    for stock in stocks:
        if stock.sector_name:
            sector_members.setdefault(stock.sector_name, []).append(stock)
    for sector_name, members in sorted(
        sector_members.items(),
        key=lambda item: sum(values[stock.stock_code] for stock in item[1]),
        reverse=True,
    ):
        sector_value = sum(values[stock.stock_code] for stock in members)
        sector_pct = sector_value / total_assets * 100
        limit = settings.max_sector_pct
        if sector_pct <= limit + 1e-9:
            continue
        excess = sector_value - total_assets * limit / 100
        for stock in sorted(members, key=lambda item: values[item.stock_code], reverse=True):
            if excess <= 1e-9:
                break
            excess -= apply_trim(
                stock.stock_code,
                min(values[stock.stock_code], excess),
                f"{sector_name}行业仓位 {sector_pct:.2f}% 超过上限 {limit:.2f}%",
            )

    # 3. 总仓位超限
    total_value = sum(values.values())
    total_pct = total_value / total_assets * 100
    limit = settings.max_total_position_pct
    if total_pct > limit + 1e-9:
        excess = total_value - total_assets * limit / 100
        for stock in sorted(stocks, key=lambda item: values[item.stock_code], reverse=True):
            if excess <= 1e-9:
                break
            excess -= apply_trim(
                stock.stock_code,
                min(values[stock.stock_code], excess),
                f"总仓位 {total_pct:.2f}% 超过上限 {limit:.2f}%",
            )

    suggestions: list[PortfolioTrimSuggestion] = []
    for stock in stocks:
        trimmed_value = original_values[stock.stock_code] - values[stock.stock_code]
        price = prices[stock.stock_code]
        if trimmed_value <= 0 or price is None or price <= 0:
            continue
        sellable = stock.sellable_shares if stock.sellable_shares is not None else stock.total_shares
        shares = min(
            round_up_to_lot(trimmed_value / price, stock.stock_code),
            stock.total_shares,
            sellable,
        )
        if shares <= 0:
            continue
        estimated_amount = _money(shares * price)
        suggestions.append(
            PortfolioTrimSuggestion(
                stock_code=stock.stock_code,
                stock_name=stock.stock_name,
                sector_name=stock.sector_name,
                current_pct=round(original_values[stock.stock_code] / total_assets * 100, 2),
                target_pct=round(
                    (original_values[stock.stock_code] - estimated_amount) / total_assets * 100,
                    2,
                ),
                suggested_shares=shares,
                sellable_shares=sellable,
                estimated_amount=estimated_amount,
                lot_size=lot_size(stock.stock_code),
                reasons=reasons[stock.stock_code],
            )
        )
    suggestions.sort(key=lambda item: item.estimated_amount, reverse=True)
    return suggestions


def _remaining_add_capacity(
    summary: PortfolioSummary,
    settings: PortfolioAccountSettings,
) -> float | None:
    """组合级剩余加仓金额：总仓位上限与可用现金取较小值。"""

    if not summary.cash_configured or summary.total_asset_value is None:
        return None
    if summary.total_asset_value <= 0:
        return 0.0
    position_headroom = (
        settings.max_total_position_pct / 100 * summary.total_asset_value - summary.estimated_securities_value
    )
    cash_headroom = max(summary.cash_balance or 0.0, 0.0)
    return _money(max(0.0, min(position_headroom, cash_headroom)))


def _build_risk_summary(
    stocks: list[PortfolioStockSummary],
    summary: PortfolioSummary,
    settings: PortfolioAccountSettings,
    *,
    quote_stale: bool = False,
) -> PortfolioRiskSummary:
    allocated_stocks = [stock for stock in stocks if stock.allocation_pct is not None]
    priced_stock_count = sum(stock.current_price is not None for stock in stocks)
    unpriced_stock_count = len(stocks) - priced_stock_count
    unclassified_stock_count = sum(stock.sector_name is None for stock in stocks)
    sector_allocations = _build_sector_allocations(stocks, summary)
    largest_sector = sector_allocations[0] if sector_allocations else None
    trim_suggestions = _build_trim_suggestions(stocks, summary, settings)
    remaining_add_capacity = _remaining_add_capacity(summary, settings)
    (
        concentration_index,
        effective_holding_count,
        top5_concentration_pct,
        securities_concentration_index,
        securities_effective_holding_count,
        securities_top5_concentration_pct,
    ) = _concentration_metrics(allocated_stocks)
    cash_pct = (
        round(summary.cash_balance / summary.total_asset_value * 100, 2)
        if summary.cash_configured
        and summary.cash_balance is not None
        and summary.total_asset_value
        and summary.total_asset_value > 0
        else None
    )
    cash_overdrawn = bool(summary.cash_configured and summary.cash_balance is not None and summary.cash_balance < 0)
    non_positive_assets = bool(
        summary.cash_configured and summary.total_asset_value is not None and summary.total_asset_value <= 0
    )

    warnings: list[str] = []
    if quote_stale:
        warnings.append("行情非最新，减仓建议与剩余可加仓金额按过期价格估算，请以实时行情为准。")
    if not summary.cash_configured:
        warnings.append("尚未配置初始资金，当前占比为证券持仓内部权重。")
    if cash_overdrawn:
        warnings.append(f"当前现金余额为 {summary.cash_balance:.2f} 元，已超出可用资金。")
    if non_positive_assets:
        warnings.append("当前总资产小于等于 0，无法计算有效仓位比例。")
    if unpriced_stock_count:
        if summary.cash_configured:
            warnings.append(f"{unpriced_stock_count} 只股票缺少行情，已按剩余成本估值并参与仓位计算。")
        else:
            warnings.append(f"{unpriced_stock_count} 只股票缺少行情，集中度仅基于已定价持仓计算。")
    if unclassified_stock_count:
        warnings.append(f"{unclassified_stock_count} 只股票暂无行业归属，行业集中度可能被低估。")
    frozen_stock_count = sum(1 for stock in stocks if (stock.frozen_shares or 0) > 0)
    if frozen_stock_count:
        warnings.append(f"{frozen_stock_count} 只股票存在当日买入冻结，减仓建议按可卖数量计算。")
    missing_fx_currencies = sorted(
        {stock.currency for stock in stocks if stock.currency != "CNY" and stock.currency not in summary.fx_rates}
    )
    if missing_fx_currencies:
        currency_labels = {"HKD": "港元", "USD": "美元"}
        missing_label = "、".join(
            f"{currency_labels.get(currency, currency)}（{currency}）" for currency in missing_fx_currencies
        )
        warnings.append(f"{missing_label}兑人民币汇率不可用，相关市值和盈亏暂按 1:1 折算，跨市场汇总可能失真。")

    financial_risk = cash_overdrawn or non_positive_assets
    if not stocks:
        warnings.append("暂无持仓。")
        return PortfolioRiskSummary(
            concentration_level="high" if financial_risk else "unknown",
            priced_stock_count=0,
            unpriced_stock_count=0,
            max_total_position_limit_pct=settings.max_total_position_pct,
            max_single_stock_limit_pct=settings.max_single_stock_pct,
            max_sector_limit_pct=settings.max_sector_pct,
            cash_pct=cash_pct,
            remaining_add_capacity=remaining_add_capacity,
            securities_top5_concentration_pct=securities_top5_concentration_pct,
            securities_concentration_index=securities_concentration_index,
            securities_effective_holding_count=securities_effective_holding_count,
            sector_allocations=sector_allocations,
            trim_suggestions=trim_suggestions,
            warnings=warnings,
        )
    if not allocated_stocks:
        if not non_positive_assets:
            warnings.append("暂无可用估值，无法评估持仓集中度。")
        return PortfolioRiskSummary(
            concentration_level="high" if financial_risk else "unknown",
            priced_stock_count=priced_stock_count,
            unpriced_stock_count=unpriced_stock_count,
            max_total_position_limit_pct=settings.max_total_position_pct,
            max_single_stock_limit_pct=settings.max_single_stock_pct,
            max_sector_limit_pct=settings.max_sector_pct,
            largest_sector_name=largest_sector.sector_name if largest_sector else None,
            largest_sector_pct=largest_sector.allocation_pct if largest_sector else None,
            cash_pct=cash_pct,
            remaining_add_capacity=remaining_add_capacity,
            securities_top5_concentration_pct=securities_top5_concentration_pct,
            securities_concentration_index=securities_concentration_index,
            securities_effective_holding_count=securities_effective_holding_count,
            sector_allocations=sector_allocations,
            trim_suggestions=trim_suggestions,
            warnings=warnings,
        )

    largest_position = allocated_stocks[0]
    max_single_stock_pct = largest_position.allocation_pct or 0
    top3_concentration_pct = round(sum((stock.allocation_pct or 0) for stock in allocated_stocks[:3]), 2)
    total_position_exceeded = (
        summary.total_position_pct is not None and summary.total_position_pct > settings.max_total_position_pct
    )
    sector_exceeded = bool(
        largest_sector
        and largest_sector.allocation_pct is not None
        and largest_sector.allocation_pct > settings.max_sector_pct
    )
    if (
        financial_risk
        or total_position_exceeded
        or max_single_stock_pct > settings.max_single_stock_pct
        or sector_exceeded
    ):
        concentration_level = "high"
    elif (
        len(allocated_stocks) <= 3
        or max_single_stock_pct >= settings.max_single_stock_pct * 0.8
        or (largest_sector and (largest_sector.allocation_pct or 0) >= settings.max_sector_pct * 0.8)
    ):
        concentration_level = "medium"
    else:
        concentration_level = "low"

    if len(allocated_stocks) <= 3:
        warnings.append(f"当前仅有 {len(allocated_stocks)} 只可估值持仓，分散度有限。")
    if max_single_stock_pct > settings.max_single_stock_pct:
        warnings.append(
            f"最大持仓 {largest_position.stock_name} 占比 {max_single_stock_pct:.2f}%，"
            f"超过单股上限 {settings.max_single_stock_pct:.2f}%。"
        )
    if total_position_exceeded:
        warnings.append(f"总仓位 {summary.total_position_pct:.2f}% 超过上限 {settings.max_total_position_pct:.2f}%。")
    if sector_exceeded and largest_sector:
        warnings.append(
            f"{largest_sector.sector_name}行业占比 {largest_sector.allocation_pct:.2f}% "
            f"超过行业上限 {settings.max_sector_pct:.2f}%。"
        )

    return PortfolioRiskSummary(
        largest_position_stock_code=largest_position.stock_code,
        largest_position_stock_name=largest_position.stock_name,
        max_single_stock_pct=max_single_stock_pct,
        top3_concentration_pct=top3_concentration_pct,
        top5_concentration_pct=top5_concentration_pct,
        concentration_index=concentration_index,
        effective_holding_count=effective_holding_count,
        securities_top5_concentration_pct=securities_top5_concentration_pct,
        securities_concentration_index=securities_concentration_index,
        securities_effective_holding_count=securities_effective_holding_count,
        cash_pct=cash_pct,
        concentration_level=concentration_level,
        priced_stock_count=priced_stock_count,
        unpriced_stock_count=unpriced_stock_count,
        max_total_position_limit_pct=settings.max_total_position_pct,
        max_single_stock_limit_pct=settings.max_single_stock_pct,
        max_sector_limit_pct=settings.max_sector_pct,
        largest_sector_name=largest_sector.sector_name if largest_sector else None,
        largest_sector_pct=largest_sector.allocation_pct if largest_sector else None,
        remaining_add_capacity=remaining_add_capacity,
        sector_allocations=sector_allocations,
        trim_suggestions=trim_suggestions,
        warnings=warnings,
    )


def _build_summary(
    positions: list[PortfolioPosition],
    stocks: list[PortfolioStockSummary],
    replay: LedgerReplay,
    settings: PortfolioAccountSettings,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioSummary:
    total_cost = _money(sum(position.cost_value for position in positions))
    priced_positions = [position for position in positions if position.market_value is not None]
    priced_cost = _money(sum(position.cost_value for position in priced_positions))
    total_market_value = _money(sum(position.market_value or 0 for position in priced_positions))
    unrealized_profit = _money(total_market_value - priced_cost)
    realized_profit = _money(
        sum(
            (transaction.realized_profit or Decimal("0")) * Decimal(str(_fx_rate_for(transaction.stock_code, fx_rates)))
            for transaction in replay.transactions
        )
    )
    combined_profit = _money(unrealized_profit + realized_profit)
    total_profit_pct = round(unrealized_profit / priced_cost * 100, 2) if priced_cost else None
    estimated_securities_value = _money(
        sum(
            (position.market_value if position.market_value is not None else position.cost_value)
            for position in positions
        )
    )
    cash_configured = settings.initial_cash is not None
    cash_balance: float | None = None
    total_asset_value: float | None = None
    total_position_pct: float | None = None
    if cash_configured:
        cash_flow = Decimal(str(settings.initial_cash))
        for transaction in replay.transactions:
            fx_rate = Decimal(str(_fx_rate_for(transaction.stock_code, fx_rates)))
            trade_value = transaction.trade_price * transaction.shares * fx_rate
            fee = transaction.fee * fx_rate
            if transaction.side == "buy":
                cash_flow -= trade_value + fee
            else:
                cash_flow += trade_value - fee
        cash_balance = _money(cash_flow)
        total_asset_value = _money(cash_balance + estimated_securities_value)
        total_position_pct = (
            round(estimated_securities_value / total_asset_value * 100, 2) if total_asset_value > 0 else None
        )
    previous_close_value = _money(
        sum(
            stock.prev_close * stock.total_shares * stock.fx_rate_to_cny
            for stock in stocks
            if stock.prev_close is not None and stock.prev_close > 0
        )
    )
    daily_profit_amount = _money(sum(stock.daily_profit_amount or 0 for stock in stocks))
    daily_profit_pct: float | None = None
    if previous_close_value > 0:
        daily_profit_pct = round(daily_profit_amount / previous_close_value * 100, 2)
    return PortfolioSummary(
        stock_count=len(stocks),
        position_count=len(positions),
        transaction_count=len(replay.transactions),
        total_cost=total_cost,
        priced_cost=priced_cost,
        total_market_value=total_market_value,
        total_profit_amount=unrealized_profit,
        total_profit_pct=total_profit_pct,
        unrealized_profit_amount=unrealized_profit,
        realized_profit_amount=realized_profit,
        combined_profit_amount=combined_profit,
        profitable_count=sum(1 for stock in stocks if (stock.profit_amount or 0) > 0),
        losing_count=sum(1 for stock in stocks if (stock.profit_amount or 0) < 0),
        unpriced_count=sum(1 for stock in stocks if stock.current_price is None),
        cash_configured=cash_configured,
        initial_cash=settings.initial_cash,
        cash_balance=cash_balance,
        estimated_securities_value=estimated_securities_value,
        total_asset_value=total_asset_value,
        total_position_pct=total_position_pct,
        previous_close_value=previous_close_value,
        daily_profit_amount=daily_profit_amount,
        daily_profit_pct=daily_profit_pct,
    )


def _build_closed_positions(
    replay: LedgerReplay,
    fx_rates: dict[str, float] | None = None,
) -> list[PortfolioClosedPosition]:
    open_stock_codes = {lot.stock_code for lot in replay.open_lots}
    grouped: dict[str, list[ReplayedTransaction]] = {}
    for transaction in replay.transactions:
        grouped.setdefault(transaction.stock_code, []).append(transaction)

    closed_positions = []
    for stock_code, transactions in grouped.items():
        if stock_code in open_stock_codes:
            continue
        sells = [transaction for transaction in transactions if transaction.side == "sell"]
        if not sells:
            continue
        matched_cost = sum(
            (transaction.matched_cost or Decimal("0") for transaction in sells),
            Decimal("0"),
        )
        realized_profit = sum(
            (transaction.realized_profit or Decimal("0") for transaction in sells),
            Decimal("0"),
        )
        first_trade = min(transactions, key=lambda item: parse_trade_time(item.trade_time))
        last_trade = max(transactions, key=lambda item: parse_trade_time(item.trade_time))
        closed_positions.append(
            PortfolioClosedPosition(
                stock_code=stock_code,
                stock_name=last_trade.stock_name or stock_code,
                currency=_currency_for(stock_code),
                fx_rate_to_cny=_fx_rate_for(stock_code, fx_rates),
                transaction_count=len(transactions),
                buy_count=sum(transaction.side == "buy" for transaction in transactions),
                sell_count=len(sells),
                total_shares=sum(transaction.shares for transaction in sells),
                matched_cost=_money(matched_cost * Decimal(str(_fx_rate_for(stock_code, fx_rates)))),
                realized_profit_amount=_money(realized_profit * Decimal(str(_fx_rate_for(stock_code, fx_rates)))),
                realized_profit_pct=(round(float(realized_profit / matched_cost * 100), 2) if matched_cost else None),
                first_trade_time=first_trade.trade_time,
                last_trade_time=last_trade.trade_time,
                holding_days=(
                    parse_trade_time(last_trade.trade_time).date() - parse_trade_time(first_trade.trade_time).date()
                ).days,
            )
        )
    closed_positions.sort(key=lambda item: parse_trade_time(item.last_trade_time), reverse=True)
    return closed_positions


def build_portfolio(
    replay: LedgerReplay,
    quotes: dict[str, dict],
    *,
    quoted_at: str,
    quote_source: str,
    quote_stale: bool,
    settings: PortfolioAccountSettings | dict | None = None,
    industries: dict[str, dict] | None = None,
    as_of_date: date | None = None,
    fx_rates: dict[str, float] | None = None,
) -> PortfolioResponse:
    resolved_settings = (
        settings
        if isinstance(settings, PortfolioAccountSettings)
        else PortfolioAccountSettings.model_validate(settings or {})
    )
    resolved_date = as_of_date or market_today()
    resolved_fx_rates = {"CNY": 1.0, **(fx_rates or {})}
    positions = [
        position_from_lot(lot, quotes.get(lot.stock_code, {}), as_of_date=resolved_date, fx_rates=resolved_fx_rates)
        for lot in replay.open_lots
    ]
    stocks = _build_stock_summaries(_group_positions(positions), replay)
    summary = _build_summary(positions, stocks, replay, resolved_settings, resolved_fx_rates)
    summary.base_currency = "CNY"
    summary.fx_rates = resolved_fx_rates
    _apply_allocations(stocks, summary, industries or {}, resolved_settings)
    stocks.sort(key=lambda item: _estimated_stock_value(item), reverse=True)
    transactions = [
        transaction_from_replay(transaction, resolved_fx_rates) for transaction in reversed(replay.transactions)
    ]
    return PortfolioResponse(
        positions=positions,
        stocks=stocks,
        transactions=transactions,
        closed_positions=_build_closed_positions(replay, resolved_fx_rates),
        summary=summary,
        risk=_build_risk_summary(stocks, summary, resolved_settings, quote_stale=quote_stale),
        settings=resolved_settings,
        quoted_at=quoted_at,
        quote_source=quote_source,
        quote_stale=quote_stale,
    )
