from decimal import Decimal

from app.modules.portfolio.accounting import (
    LedgerReplay,
    LotMatch,
    OpenLot,
    ReplayedTransaction,
    TransactionPreview,
    parse_trade_time,
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
)


def current_price(quote: dict) -> float | None:
    price = float(quote.get("price") or quote.get("last_close") or 0)
    return price if price > 0 else None


def _money(value: Decimal | float | int) -> float:
    return round(float(value), 2)


def position_from_lot(lot: OpenLot, quote: dict) -> PortfolioPosition:
    resolved_price = current_price(quote)
    cost_value = _money(lot.remaining_cost)
    market_value = _money(resolved_price * lot.remaining_shares) if resolved_price is not None else None
    profit_amount = _money(market_value - cost_value) if market_value is not None else None
    profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None and cost_value else None
    return PortfolioPosition(
        id=lot.transaction_id,
        stock_code=lot.stock_code,
        stock_name=quote.get("name") or lot.stock_name or lot.stock_code,
        buy_price=float(lot.buy_price),
        buy_time=lot.buy_time,
        shares=lot.remaining_shares,
        current_price=resolved_price,
        change_pct=float(quote["change_pct"]) if quote.get("change_pct") is not None else None,
        cost_value=cost_value,
        market_value=market_value,
        profit_amount=profit_amount,
        profit_pct=profit_pct,
    )


def position_from_transaction(row: dict, quote: dict) -> PortfolioPosition:
    shares = int(row["shares"])
    trade_price = float(row["trade_price"])
    resolved_price = current_price(quote)
    cost_value = _money(trade_price * shares + float(row.get("fee") or 0))
    market_value = _money(resolved_price * shares) if resolved_price is not None else None
    profit_amount = _money(market_value - cost_value) if market_value is not None else None
    profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None and cost_value else None
    return PortfolioPosition(
        id=int(row["id"]),
        stock_code=str(row["stock_code"]),
        stock_name=quote.get("name") or row["stock_name"] or row["stock_code"],
        buy_price=trade_price,
        buy_time=str(row["trade_time"]),
        shares=shares,
        current_price=resolved_price,
        change_pct=float(quote["change_pct"]) if quote.get("change_pct") is not None else None,
        cost_value=cost_value,
        market_value=market_value,
        profit_amount=profit_amount,
        profit_pct=profit_pct,
    )


def lot_match_from_replay(match: LotMatch) -> PortfolioLotMatch:
    return PortfolioLotMatch(
        buy_transaction_id=match.buy_transaction_id,
        buy_time=match.buy_time,
        buy_price=float(match.buy_price),
        shares=match.shares,
        unit_cost=float(match.unit_cost),
        matched_cost=_money(match.matched_cost),
    )


def transaction_from_replay(transaction: ReplayedTransaction) -> PortfolioTransaction:
    return PortfolioTransaction(
        id=transaction.id,
        stock_code=transaction.stock_code,
        stock_name=transaction.stock_name or transaction.stock_code,
        side=transaction.side,
        trade_price=float(transaction.trade_price),
        trade_time=transaction.trade_time,
        shares=transaction.shares,
        fee=_money(transaction.fee),
        note=transaction.note,
        created_at=transaction.created_at,
        matched_cost=_money(transaction.matched_cost) if transaction.matched_cost is not None else None,
        realized_profit_amount=(
            _money(transaction.realized_profit) if transaction.realized_profit is not None else None
        ),
        matches=[lot_match_from_replay(match) for match in transaction.matches],
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
    return PortfolioTransactionPreview(
        stock_code=request.stock_code,
        side=request.side,
        trade_time=request.trade_time.isoformat(timespec="seconds"),
        available_shares=preview.available_shares,
        shares_after_trade=preview.shares_after_trade,
        current_shares_after=preview.current_shares_after,
        matched_cost=_money(preview.matched_cost) if preview.matched_cost is not None else None,
        realized_profit_amount=(_money(preview.realized_profit) if preview.realized_profit is not None else None),
        matches=[lot_match_from_replay(match) for match in preview.matches],
        trade_amount=_money(request.trade_price * request.shares),
        fee=_money(request.fee),
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
                "cost_value": 0.0,
                "current_price": position.current_price,
                "change_pct": position.change_pct,
            },
        )
        item["position_count"] += 1
        item["total_shares"] += position.shares
        item["cost_value"] += position.cost_value
        if position.current_price is not None:
            item["current_price"] = position.current_price
            item["change_pct"] = position.change_pct
    return grouped


def _build_stock_summaries(
    grouped: dict[str, dict],
    replay: LedgerReplay,
) -> list[PortfolioStockSummary]:
    stocks = []
    for stock_code, item in grouped.items():
        total_shares = item["total_shares"]
        cost_value = _money(item["cost_value"])
        resolved_price = item["current_price"]
        market_value = _money(resolved_price * total_shares) if resolved_price is not None else None
        profit_amount = _money(market_value - cost_value) if market_value is not None else None
        profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None and cost_value else None
        realized_profit = _money(replay.realized_by_stock.get(stock_code, Decimal("0")))
        total_profit = _money(realized_profit + profit_amount) if profit_amount is not None else None
        stocks.append(
            PortfolioStockSummary(
                stock_code=stock_code,
                stock_name=item["stock_name"],
                position_count=item["position_count"],
                total_shares=total_shares,
                average_cost=round(cost_value / total_shares, 4),
                current_price=resolved_price,
                change_pct=item["change_pct"],
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


def _build_risk_summary(
    stocks: list[PortfolioStockSummary],
    summary: PortfolioSummary,
    settings: PortfolioAccountSettings,
) -> PortfolioRiskSummary:
    allocated_stocks = [stock for stock in stocks if stock.allocation_pct is not None]
    priced_stock_count = sum(stock.current_price is not None for stock in stocks)
    unpriced_stock_count = len(stocks) - priced_stock_count
    unclassified_stock_count = sum(stock.sector_name is None for stock in stocks)
    sector_allocations = _build_sector_allocations(stocks, summary)
    largest_sector = sector_allocations[0] if sector_allocations else None
    cash_overdrawn = bool(summary.cash_configured and summary.cash_balance is not None and summary.cash_balance < 0)
    non_positive_assets = bool(
        summary.cash_configured and summary.total_asset_value is not None and summary.total_asset_value <= 0
    )

    warnings: list[str] = []
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
            sector_allocations=sector_allocations,
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
            sector_allocations=sector_allocations,
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
        concentration_level=concentration_level,
        priced_stock_count=priced_stock_count,
        unpriced_stock_count=unpriced_stock_count,
        max_total_position_limit_pct=settings.max_total_position_pct,
        max_single_stock_limit_pct=settings.max_single_stock_pct,
        max_sector_limit_pct=settings.max_sector_pct,
        largest_sector_name=largest_sector.sector_name if largest_sector else None,
        largest_sector_pct=largest_sector.allocation_pct if largest_sector else None,
        sector_allocations=sector_allocations,
        warnings=warnings,
    )


def _build_summary(
    positions: list[PortfolioPosition],
    stocks: list[PortfolioStockSummary],
    replay: LedgerReplay,
    settings: PortfolioAccountSettings,
) -> PortfolioSummary:
    total_cost = _money(sum(position.cost_value for position in positions))
    priced_positions = [position for position in positions if position.market_value is not None]
    priced_cost = _money(sum(position.cost_value for position in priced_positions))
    total_market_value = _money(sum(position.market_value or 0 for position in priced_positions))
    unrealized_profit = _money(total_market_value - priced_cost)
    realized_profit = _money(replay.total_realized)
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
            trade_value = transaction.trade_price * transaction.shares
            if transaction.side == "buy":
                cash_flow -= trade_value + transaction.fee
            else:
                cash_flow += trade_value - transaction.fee
        cash_balance = _money(cash_flow)
        total_asset_value = _money(cash_balance + estimated_securities_value)
        total_position_pct = (
            round(estimated_securities_value / total_asset_value * 100, 2) if total_asset_value > 0 else None
        )
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
    )


def _build_closed_positions(replay: LedgerReplay) -> list[PortfolioClosedPosition]:
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
                transaction_count=len(transactions),
                buy_count=sum(transaction.side == "buy" for transaction in transactions),
                sell_count=len(sells),
                total_shares=sum(transaction.shares for transaction in sells),
                matched_cost=_money(matched_cost),
                realized_profit_amount=_money(realized_profit),
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
) -> PortfolioResponse:
    resolved_settings = (
        settings
        if isinstance(settings, PortfolioAccountSettings)
        else PortfolioAccountSettings.model_validate(settings or {})
    )
    positions = [position_from_lot(lot, quotes.get(lot.stock_code, {})) for lot in replay.open_lots]
    stocks = _build_stock_summaries(_group_positions(positions), replay)
    summary = _build_summary(positions, stocks, replay, resolved_settings)
    _apply_allocations(stocks, summary, industries or {})
    stocks.sort(key=lambda item: _estimated_stock_value(item), reverse=True)
    transactions = [transaction_from_replay(transaction) for transaction in reversed(replay.transactions)]
    return PortfolioResponse(
        positions=positions,
        stocks=stocks,
        transactions=transactions,
        closed_positions=_build_closed_positions(replay),
        summary=summary,
        risk=_build_risk_summary(stocks, summary, resolved_settings),
        settings=resolved_settings,
        quoted_at=quoted_at,
        quote_source=quote_source,
        quote_stale=quote_stale,
    )
