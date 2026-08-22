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
    PortfolioClosedPosition,
    PortfolioLotMatch,
    PortfolioPosition,
    PortfolioResponse,
    PortfolioRiskSummary,
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
) -> PortfolioTransactionPreview:
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
    stocks.sort(key=lambda item: item.market_value or 0, reverse=True)
    total_market_value = sum((stock.market_value or 0 for stock in stocks), 0.0)
    total_absolute_profit = sum((abs(stock.profit_amount or 0) for stock in stocks), 0.0)
    for stock in stocks:
        stock.allocation_pct = (
            round(stock.market_value / total_market_value * 100, 2)
            if stock.market_value is not None and total_market_value
            else None
        )
        stock.profit_contribution_pct = (
            round((stock.profit_amount or 0) / total_absolute_profit * 100, 2)
            if stock.profit_amount is not None and total_absolute_profit
            else None
        )
    return stocks


def _build_risk_summary(stocks: list[PortfolioStockSummary]) -> PortfolioRiskSummary:
    priced_stocks = [stock for stock in stocks if stock.allocation_pct is not None]
    unpriced_stock_count = len(stocks) - len(priced_stocks)
    if not priced_stocks:
        return PortfolioRiskSummary(
            concentration_level="unknown",
            priced_stock_count=0,
            unpriced_stock_count=unpriced_stock_count,
            warnings=["暂无可用行情，无法评估持仓集中度。"],
        )

    largest_position = priced_stocks[0]
    max_single_stock_pct = largest_position.allocation_pct or 0
    top3_concentration_pct = round(sum((stock.allocation_pct or 0) for stock in priced_stocks[:3]), 2)
    priced_stock_count = len(priced_stocks)

    if priced_stock_count <= 2 or max_single_stock_pct >= 50 or (
        priced_stock_count >= 4 and top3_concentration_pct >= 80
    ):
        concentration_level = "high"
    elif priced_stock_count == 3 or max_single_stock_pct >= 30 or top3_concentration_pct >= 60:
        concentration_level = "medium"
    else:
        concentration_level = "low"

    warnings = []
    if unpriced_stock_count:
        warnings.append(f"{unpriced_stock_count} 只股票缺少行情，集中度仅基于已定价持仓计算。")
    if priced_stock_count <= 3:
        warnings.append(f"当前仅有 {priced_stock_count} 只已定价持仓，分散度有限。")
    if max_single_stock_pct >= 30:
        warnings.append(
            f"最大持仓 {largest_position.stock_name} 占比 {max_single_stock_pct:.2f}%，单股波动影响较大。"
        )
    if priced_stock_count >= 4 and top3_concentration_pct >= 60:
        warnings.append(f"前三大持仓合计占比 {top3_concentration_pct:.2f}%，组合收益较依赖少数股票。")

    return PortfolioRiskSummary(
        largest_position_stock_code=largest_position.stock_code,
        largest_position_stock_name=largest_position.stock_name,
        max_single_stock_pct=max_single_stock_pct,
        top3_concentration_pct=top3_concentration_pct,
        concentration_level=concentration_level,
        priced_stock_count=priced_stock_count,
        unpriced_stock_count=unpriced_stock_count,
        warnings=warnings,
    )


def _build_summary(
    positions: list[PortfolioPosition],
    stocks: list[PortfolioStockSummary],
    replay: LedgerReplay,
) -> PortfolioSummary:
    total_cost = _money(sum(position.cost_value for position in positions))
    priced_positions = [position for position in positions if position.market_value is not None]
    priced_cost = _money(sum(position.cost_value for position in priced_positions))
    total_market_value = _money(sum(position.market_value or 0 for position in priced_positions))
    unrealized_profit = _money(total_market_value - priced_cost)
    realized_profit = _money(replay.total_realized)
    combined_profit = _money(unrealized_profit + realized_profit)
    total_profit_pct = round(unrealized_profit / priced_cost * 100, 2) if priced_cost else None
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
) -> PortfolioResponse:
    positions = [position_from_lot(lot, quotes.get(lot.stock_code, {})) for lot in replay.open_lots]
    stocks = _build_stock_summaries(_group_positions(positions), replay)
    transactions = [transaction_from_replay(transaction) for transaction in reversed(replay.transactions)]
    return PortfolioResponse(
        positions=positions,
        stocks=stocks,
        transactions=transactions,
        closed_positions=_build_closed_positions(replay),
        summary=_build_summary(positions, stocks, replay),
        risk=_build_risk_summary(stocks),
        quoted_at=quoted_at,
        quote_source=quote_source,
        quote_stale=quote_stale,
    )
