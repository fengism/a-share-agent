from collections.abc import Callable

from app.modules.portfolio.schemas import (
    PortfolioPosition,
    PortfolioResponse,
    PortfolioStockSummary,
    PortfolioSummary,
)

CurrentPriceResolver = Callable[[dict], float | None]
PositionFactory = Callable[[dict, dict], PortfolioPosition]


def current_price(quote: dict) -> float | None:
    price = float(quote.get("price") or quote.get("last_close") or 0)
    return price if price > 0 else None


def position_from_row(
    row: dict,
    quote: dict,
    current_price_resolver: CurrentPriceResolver = current_price,
) -> PortfolioPosition:
    buy_price = float(row["buy_price"])
    shares = int(row["shares"])
    resolved_price = current_price_resolver(quote)
    cost_value = round(buy_price * shares, 2)
    market_value = round(resolved_price * shares, 2) if resolved_price is not None else None
    profit_amount = round(market_value - cost_value, 2) if market_value is not None else None
    profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None else None
    return PortfolioPosition(
        id=row["id"],
        stock_code=row["stock_code"],
        stock_name=quote.get("name") or row["stock_name"] or row["stock_code"],
        buy_price=buy_price,
        buy_time=row["buy_time"],
        shares=shares,
        current_price=resolved_price,
        change_pct=float(quote["change_pct"]) if quote.get("change_pct") is not None else None,
        cost_value=cost_value,
        market_value=market_value,
        profit_amount=profit_amount,
        profit_pct=profit_pct,
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


def _build_stock_summaries(grouped: dict[str, dict]) -> list[PortfolioStockSummary]:
    stocks = []
    for stock_code, item in grouped.items():
        total_shares = item["total_shares"]
        cost_value = round(item["cost_value"], 2)
        resolved_price = item["current_price"]
        market_value = round(resolved_price * total_shares, 2) if resolved_price is not None else None
        profit_amount = round(market_value - cost_value, 2) if market_value is not None else None
        profit_pct = round(profit_amount / cost_value * 100, 2) if profit_amount is not None else None
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
            )
        )
    stocks.sort(key=lambda item: item.market_value or 0, reverse=True)
    return stocks


def _build_summary(
    positions: list[PortfolioPosition],
    stocks: list[PortfolioStockSummary],
) -> PortfolioSummary:
    total_cost = round(sum(position.cost_value for position in positions), 2)
    priced_positions = [position for position in positions if position.market_value is not None]
    priced_cost = round(sum(position.cost_value for position in priced_positions), 2)
    total_market_value = round(sum(position.market_value or 0 for position in priced_positions), 2)
    total_profit_amount = round(total_market_value - priced_cost, 2)
    total_profit_pct = round(total_profit_amount / priced_cost * 100, 2) if priced_cost else None
    return PortfolioSummary(
        stock_count=len(stocks),
        position_count=len(positions),
        total_cost=total_cost,
        priced_cost=priced_cost,
        total_market_value=total_market_value,
        total_profit_amount=total_profit_amount,
        total_profit_pct=total_profit_pct,
        profitable_count=sum(1 for stock in stocks if (stock.profit_amount or 0) > 0),
        losing_count=sum(1 for stock in stocks if (stock.profit_amount or 0) < 0),
        unpriced_count=sum(1 for stock in stocks if stock.current_price is None),
    )


def build_portfolio(
    rows: list[dict],
    quotes: dict[str, dict],
    *,
    quoted_at: str,
    quote_source: str,
    quote_stale: bool,
    position_factory: PositionFactory = position_from_row,
) -> PortfolioResponse:
    positions = [position_factory(row, quotes.get(row["stock_code"], {})) for row in rows]
    stocks = _build_stock_summaries(_group_positions(positions))
    return PortfolioResponse(
        positions=positions,
        stocks=stocks,
        summary=_build_summary(positions, stocks),
        quoted_at=quoted_at,
        quote_source=quote_source,
        quote_stale=quote_stale,
    )
