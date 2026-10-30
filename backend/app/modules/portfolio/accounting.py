"""Portfolio transaction replay and FIFO cost accounting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.core.timezones import SHANGHAI_TIMEZONE


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def parse_trade_time(value: str) -> datetime:
    parsed_trade_time = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed_trade_time.tzinfo is None:
        parsed_trade_time = parsed_trade_time.replace(tzinfo=SHANGHAI_TIMEZONE)
    return parsed_trade_time.astimezone(SHANGHAI_TIMEZONE)


def _trade_order_key(row: dict[str, Any]) -> tuple[datetime, int]:
    return parse_trade_time(str(row["trade_time"])).astimezone(timezone.utc), int(row["id"])


class InsufficientSharesError(ValueError):
    def __init__(
        self,
        stock_code: str,
        *,
        available_shares: int,
        requested_shares: int,
    ) -> None:
        super().__init__(
            f"卖出股数超过可用持仓: stock_code={stock_code} available={available_shares} requested={requested_shares}"
        )
        self.stock_code = stock_code
        self.available_shares = available_shares
        self.requested_shares = requested_shares


class LedgerOwnerMismatchError(ValueError):
    def __init__(self, expected_user_id: int, actual_user_id: int) -> None:
        super().__init__(f"交易流水包含多个用户: expected_user_id={expected_user_id} actual_user_id={actual_user_id}")
        self.expected_user_id = expected_user_id
        self.actual_user_id = actual_user_id


@dataclass(frozen=True, slots=True)
class OpenLot:
    transaction_id: int
    stock_code: str
    stock_name: str
    buy_price: Decimal
    buy_time: str
    original_shares: int
    remaining_shares: int
    unit_cost: Decimal

    @property
    def remaining_cost(self) -> Decimal:
        return self.unit_cost * self.remaining_shares


@dataclass(frozen=True, slots=True)
class LotMatch:
    buy_transaction_id: int
    buy_time: str
    buy_price: Decimal
    shares: int
    unit_cost: Decimal
    matched_cost: Decimal


@dataclass(frozen=True, slots=True)
class ReplayedTransaction:
    id: int
    user_id: int
    stock_code: str
    stock_name: str
    side: str
    trade_price: Decimal
    trade_time: str
    shares: int
    fee: Decimal
    note: str
    created_at: str
    matched_cost: Decimal | None
    realized_profit: Decimal | None
    matches: tuple[LotMatch, ...]


@dataclass(frozen=True, slots=True)
class LedgerReplay:
    open_lots: list[OpenLot]
    transactions: list[ReplayedTransaction]
    realized_by_stock: dict[str, Decimal]

    @property
    def total_realized(self) -> Decimal:
        return sum(self.realized_by_stock.values(), Decimal("0"))


@dataclass(frozen=True, slots=True)
class TransactionPreview:
    available_shares: int
    sellable_shares: int
    shares_after_trade: int
    current_shares_after: int
    matched_cost: Decimal | None
    realized_profit: Decimal | None
    matches: tuple[LotMatch, ...]


@dataclass(slots=True)
class _LotBalance:
    transaction_id: int
    stock_code: str
    stock_name: str
    buy_price: Decimal
    buy_time: str
    original_shares: int
    remaining_shares: int
    unit_cost: Decimal

    def snapshot(self) -> OpenLot:
        return OpenLot(
            transaction_id=self.transaction_id,
            stock_code=self.stock_code,
            stock_name=self.stock_name,
            buy_price=self.buy_price,
            buy_time=self.buy_time,
            original_shares=self.original_shares,
            remaining_shares=self.remaining_shares,
            unit_cost=self.unit_cost,
        )


def replay_transactions(rows: list[dict[str, Any]]) -> LedgerReplay:
    ordered = sorted(rows, key=_trade_order_key)
    lots_by_stock: dict[str, list[_LotBalance]] = {}
    realized_by_stock: dict[str, Decimal] = {}
    replayed: list[ReplayedTransaction] = []
    ledger_user_id: int | None = None

    for row in ordered:
        transaction_id = int(row["id"])
        user_id = int(row["user_id"])
        if ledger_user_id is None:
            ledger_user_id = user_id
        elif user_id != ledger_user_id:
            raise LedgerOwnerMismatchError(ledger_user_id, user_id)
        stock_code = str(row["stock_code"])
        stock_name = str(row["stock_name"])
        side = str(row["side"]).lower()
        trade_price = _decimal(row["trade_price"])
        trade_time = str(row["trade_time"])
        shares = int(row["shares"])
        fee = _decimal(row.get("fee", 0))
        note = str(row.get("note") or "")
        created_at = str(row.get("created_at") or trade_time)
        matched_cost: Decimal | None = None
        realized_profit: Decimal | None = None
        matches: list[LotMatch] = []

        if side == "buy":
            unit_cost = (trade_price * shares + fee) / shares
            lots_by_stock.setdefault(stock_code, []).append(
                _LotBalance(
                    transaction_id=transaction_id,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    buy_price=trade_price,
                    buy_time=trade_time,
                    original_shares=shares,
                    remaining_shares=shares,
                    unit_cost=unit_cost,
                )
            )
        elif side == "sell":
            lots = lots_by_stock.setdefault(stock_code, [])
            available_shares = sum(lot.remaining_shares for lot in lots)
            if shares > available_shares:
                raise InsufficientSharesError(
                    stock_code,
                    available_shares=available_shares,
                    requested_shares=shares,
                )
            remaining_to_match = shares
            matched_cost = Decimal("0")
            for lot in lots:
                if remaining_to_match == 0:
                    break
                matched_shares = min(lot.remaining_shares, remaining_to_match)
                lot.remaining_shares -= matched_shares
                remaining_to_match -= matched_shares
                lot_matched_cost = lot.unit_cost * matched_shares
                matched_cost += lot_matched_cost
                matches.append(
                    LotMatch(
                        buy_transaction_id=lot.transaction_id,
                        buy_time=lot.buy_time,
                        buy_price=lot.buy_price,
                        shares=matched_shares,
                        unit_cost=lot.unit_cost,
                        matched_cost=lot_matched_cost,
                    )
                )
            realized_profit = trade_price * shares - fee - matched_cost
            realized_by_stock[stock_code] = realized_by_stock.get(stock_code, Decimal("0")) + realized_profit
        else:
            raise ValueError(f"不支持的交易方向: {side}")

        replayed.append(
            ReplayedTransaction(
                id=transaction_id,
                user_id=user_id,
                stock_code=stock_code,
                stock_name=stock_name,
                side=side,
                trade_price=trade_price,
                trade_time=trade_time,
                shares=shares,
                fee=fee,
                note=note,
                created_at=created_at,
                matched_cost=matched_cost,
                realized_profit=realized_profit,
                matches=tuple(matches),
            )
        )

    open_lots = [lot.snapshot() for lots in lots_by_stock.values() for lot in lots if lot.remaining_shares > 0]
    open_lots.sort(key=lambda lot: (lot.buy_time, lot.transaction_id))
    return LedgerReplay(
        open_lots=open_lots,
        transactions=replayed,
        realized_by_stock=realized_by_stock,
    )


def preview_transaction(
    rows: list[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    t_plus_one: bool = True,
) -> TransactionPreview:
    candidate_id = int(candidate["id"])
    candidate_stock_code = str(candidate["stock_code"])
    ordered = sorted([*rows, candidate], key=_trade_order_key)
    candidate_index = next(index for index, row in enumerate(ordered) if int(row["id"]) == candidate_id)
    before_replay = replay_transactions(ordered[:candidate_index])
    available_shares = sum(
        lot.remaining_shares for lot in before_replay.open_lots if lot.stock_code == candidate_stock_code
    )
    candidate_trade_date = parse_trade_time(str(candidate["trade_time"])).date()
    sellable_shares = sum(
        lot.remaining_shares
        for lot in before_replay.open_lots
        if lot.stock_code == candidate_stock_code
        and (not t_plus_one or parse_trade_time(lot.buy_time).date() < candidate_trade_date)
    )
    replay = replay_transactions(ordered)
    previewed = next(transaction for transaction in replay.transactions if transaction.id == candidate_id)
    shares = int(candidate["shares"])
    shares_after_trade = available_shares + shares if candidate["side"] == "buy" else available_shares - shares
    current_shares_after = sum(
        lot.remaining_shares for lot in replay.open_lots if lot.stock_code == candidate_stock_code
    )
    return TransactionPreview(
        available_shares=available_shares,
        sellable_shares=sellable_shares,
        shares_after_trade=shares_after_trade,
        current_shares_after=current_shares_after,
        matched_cost=previewed.matched_cost,
        realized_profit=previewed.realized_profit,
        matches=previewed.matches,
    )


__all__ = [
    "InsufficientSharesError",
    "LedgerReplay",
    "LedgerOwnerMismatchError",
    "LotMatch",
    "OpenLot",
    "ReplayedTransaction",
    "TransactionPreview",
    "parse_trade_time",
    "preview_transaction",
    "replay_transactions",
]
