import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, getcontext
from typing import Optional, List

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


load_dotenv()
getcontext().prec = 28

DATABASE_URL = os.getenv("DATABASE_URL")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "39a8151d-c349-4ea6-88f7-b111f19908a1")

ZERO = Decimal("0")
EPS = Decimal("0.00000001")


def require_env(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def to_decimal(value) -> Decimal:
    if value is None or value == "":
        return ZERO
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return ZERO


def is_zero(value: Decimal) -> bool:
    return abs(value) <= EPS


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_connection():
    dsn = require_env("DATABASE_URL", DATABASE_URL)
    return psycopg.connect(dsn, row_factory=dict_row)


@dataclass
class ExecRow:
    id: int
    account_id: str
    exec_id: str
    order_id: Optional[str]
    symbol: str
    side: str
    price: Decimal
    qty: Decimal
    value: Decimal
    fee: Decimal
    exec_time: datetime


@dataclass
class TradeAccumulator:
    account_id: str
    symbol: str
    direction: str  # long | short
    started_at: datetime

    entry_count: int = 0
    exit_count: int = 0
    execution_count: int = 0

    # absolute open size of this cycle
    position_qty: Decimal = field(default_factory=lambda: ZERO)

    # sum of entry qty only
    total_qty: Decimal = field(default_factory=lambda: ZERO)
    max_position_qty: Decimal = field(default_factory=lambda: ZERO)

    # raw buy/sell sums for pnl
    buy_qty_sum: Decimal = field(default_factory=lambda: ZERO)
    buy_value_sum: Decimal = field(default_factory=lambda: ZERO)

    sell_qty_sum: Decimal = field(default_factory=lambda: ZERO)
    sell_value_sum: Decimal = field(default_factory=lambda: ZERO)

    fees_sum: Decimal = field(default_factory=lambda: ZERO)
    funding_sum: Decimal = field(default_factory=lambda: ZERO)

    first_exec_time: Optional[datetime] = None
    last_exec_time: Optional[datetime] = None

    order_ids: set = field(default_factory=set)
    exec_ids: set = field(default_factory=set)

    def _touch(self, exec_time: datetime, order_id: Optional[str], exec_id: str):
        self.execution_count += 1
        if self.first_exec_time is None:
            self.first_exec_time = exec_time
        self.last_exec_time = exec_time
        if order_id:
            self.order_ids.add(order_id)
        self.exec_ids.add(exec_id)

    def apply_entry(self, side: str, qty: Decimal, value: Decimal, fee: Decimal, exec_time: datetime, order_id: Optional[str], exec_id: str):
        self._touch(exec_time, order_id, exec_id)
        self.entry_count += 1
        self.total_qty += qty
        self.fees_sum += fee

        if side == "Buy":
            self.buy_qty_sum += qty
            self.buy_value_sum += value
        elif side == "Sell":
            self.sell_qty_sum += qty
            self.sell_value_sum += value
        else:
            raise ValueError(f"Unsupported entry side: {side}")

        self.position_qty += qty
        if self.position_qty > self.max_position_qty:
            self.max_position_qty = self.position_qty

    def apply_exit(self, side: str, qty: Decimal, value: Decimal, fee: Decimal, exec_time: datetime, order_id: Optional[str], exec_id: str):
        self._touch(exec_time, order_id, exec_id)
        self.exit_count += 1
        self.fees_sum += fee

        if side == "Buy":
            self.buy_qty_sum += qty
            self.buy_value_sum += value
        elif side == "Sell":
            self.sell_qty_sum += qty
            self.sell_value_sum += value
        else:
            raise ValueError(f"Unsupported exit side: {side}")

        self.position_qty -= qty

    def close_payload(self) -> dict:
        ended_at = self.last_exec_time or self.started_at
        hold_seconds = int((ended_at - self.started_at).total_seconds()) if ended_at and self.started_at else None

        gross_pnl = self.sell_value_sum - self.buy_value_sum
        fees = self.fees_sum
        funding = self.funding_sum
        net_pnl = gross_pnl - fees + funding

        if net_pnl > 0:
            outcome = "win"
        elif net_pnl < 0:
            outcome = "loss"
        else:
            outcome = "flat"

        if self.direction == "long":
            entry_price_avg = (self.buy_value_sum / self.buy_qty_sum) if not is_zero(self.buy_qty_sum) else None
            exit_price_avg = (self.sell_value_sum / self.sell_qty_sum) if not is_zero(self.sell_qty_sum) else None
        else:
            entry_price_avg = (self.sell_value_sum / self.sell_qty_sum) if not is_zero(self.sell_qty_sum) else None
            exit_price_avg = (self.buy_value_sum / self.buy_qty_sum) if not is_zero(self.buy_qty_sum) else None

        trade_key = f"{self.account_id}:{self.symbol}:{self.direction}:{self.started_at.isoformat()}"

        metadata = {
            "order_ids": sorted(self.order_ids),
            "exec_ids_count": len(self.exec_ids),
            "buy_qty_sum": str(self.buy_qty_sum),
            "buy_value_sum": str(self.buy_value_sum),
            "sell_qty_sum": str(self.sell_qty_sum),
            "sell_value_sum": str(self.sell_value_sum),
            "first_exec_time": self.first_exec_time.isoformat() if self.first_exec_time else None,
            "last_exec_time": self.last_exec_time.isoformat() if self.last_exec_time else None,
        }

        return {
            "account_id": self.account_id,
            "symbol": self.symbol,
            "group_type": "cycle",
            "started_at": self.started_at,
            "ended_at": ended_at,
            "direction": self.direction,
            "entry_count": self.entry_count,
            "exit_count": self.exit_count,
            "total_qty": self.total_qty,
            "gross_pnl": gross_pnl,
            "fees": fees,
            "funding": funding,
            "net_pnl": net_pnl,
            "hold_seconds": hold_seconds,
            "outcome": outcome,
            "entry_price_avg": entry_price_avg,
            "exit_price_avg": exit_price_avg,
            "execution_count": self.execution_count,
            "max_position_qty": self.max_position_qty,
            "status": "closed",
            "trade_key": trade_key,
            "metadata": json.dumps(metadata, ensure_ascii=False),
        }


def load_executions(conn, account_id: str) -> List[ExecRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                account_id,
                exec_id,
                order_id,
                symbol,
                side,
                price,
                qty,
                value,
                fee,
                exec_time
            FROM raw_execution
            WHERE account_id = %s
              AND side IN ('Buy', 'Sell')
            ORDER BY symbol, exec_time, id
            """,
            (account_id,),
        )
        rows = cur.fetchall()

    result: List[ExecRow] = []
    for r in rows:
        result.append(
            ExecRow(
                id=r["id"],
                account_id=str(r["account_id"]),
                exec_id=r["exec_id"],
                order_id=r["order_id"],
                symbol=r["symbol"],
                side=r["side"],
                price=to_decimal(r["price"]),
                qty=to_decimal(r["qty"]),
                value=to_decimal(r["value"]),
                fee=to_decimal(r["fee"]),
                exec_time=r["exec_time"],
            )
        )
    return result


def create_acc_from_exec(exec_row: ExecRow, direction: Optional[str] = None, qty: Optional[Decimal] = None, value: Optional[Decimal] = None, fee: Optional[Decimal] = None) -> TradeAccumulator:
    real_direction = direction or ("long" if exec_row.side == "Buy" else "short")
    q = exec_row.qty if qty is None else qty
    v = exec_row.value if value is None else value
    f = exec_row.fee if fee is None else fee

    acc = TradeAccumulator(
        account_id=exec_row.account_id,
        symbol=exec_row.symbol,
        direction=real_direction,
        started_at=exec_row.exec_time,
    )
    acc.apply_entry(
        side=exec_row.side,
        qty=q,
        value=v,
        fee=f,
        exec_time=exec_row.exec_time,
        order_id=exec_row.order_id,
        exec_id=exec_row.exec_id,
    )
    return acc


def expected_sides(direction: str) -> tuple[str, str]:
    if direction == "long":
        return "Buy", "Sell"   # entry, exit
    if direction == "short":
        return "Sell", "Buy"   # entry, exit
    raise ValueError(f"Unsupported direction: {direction}")


def split_exec(ex: ExecRow, qty: Decimal) -> tuple[Decimal, Decimal]:
    """
    Split value/fee proportionally for partial fill usage.
    """
    if is_zero(ex.qty):
        return ZERO, ZERO
    ratio = qty / ex.qty
    value = ex.value * ratio
    fee = ex.fee * ratio
    return value, fee


def build_trade_groups(executions: List[ExecRow]) -> List[dict]:
    groups: List[dict] = []
    current_by_symbol: dict[str, Optional[TradeAccumulator]] = {}

    for ex in executions:
        if is_zero(ex.qty):
            continue

        current = current_by_symbol.get(ex.symbol)

        # no active cycle -> start new one
        if current is None:
            current_by_symbol[ex.symbol] = create_acc_from_exec(ex)
            continue

        entry_side, exit_side = expected_sides(current.direction)

        # same-side fill -> add to current position
        if ex.side == entry_side:
            current.apply_entry(
                side=ex.side,
                qty=ex.qty,
                value=ex.value,
                fee=ex.fee,
                exec_time=ex.exec_time,
                order_id=ex.order_id,
                exec_id=ex.exec_id,
            )
            continue

        # opposite-side fill -> close or flip
        if ex.side != exit_side:
            raise ValueError(f"Unexpected side={ex.side} for current direction={current.direction} symbol={ex.symbol}")

        remaining_qty = ex.qty

        while remaining_qty > EPS:
            # active cycle unexpectedly missing
            if current is None:
                # open new cycle with remainder
                rem_value, rem_fee = split_exec(ex, remaining_qty)
                current = create_acc_from_exec(ex, qty=remaining_qty, value=rem_value, fee=rem_fee)
                current_by_symbol[ex.symbol] = current
                remaining_qty = ZERO
                break

            closable_qty = min(current.position_qty, remaining_qty)
            close_value, close_fee = split_exec(ex, closable_qty)

            current.apply_exit(
                side=ex.side,
                qty=closable_qty,
                value=close_value,
                fee=close_fee,
                exec_time=ex.exec_time,
                order_id=ex.order_id,
                exec_id=ex.exec_id,
            )

            remaining_qty -= closable_qty

            # closed exactly
            if is_zero(current.position_qty):
                groups.append(current.close_payload())
                current = None
                current_by_symbol[ex.symbol] = None

            # if not closed, then remaining_qty must be 0 in valid close path
            # if remaining_qty > 0 and current was closed, then we have a flip
            if current is None and remaining_qty > EPS:
                rem_value, rem_fee = split_exec(ex, remaining_qty)
                # flip opens opposite direction with the same side as current exec
                new_direction = "long" if ex.side == "Buy" else "short"
                current = create_acc_from_exec(
                    ex,
                    direction=new_direction,
                    qty=remaining_qty,
                    value=rem_value,
                    fee=rem_fee,
                )
                current_by_symbol[ex.symbol] = current
                remaining_qty = ZERO
                break

    return groups


def delete_existing_trade_groups(conn, account_id: str):
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM trade_group WHERE account_id = %s",
            (account_id,),
        )


def insert_trade_groups(conn, groups: List[dict]):
    if not groups:
        return

    sql = """
        INSERT INTO trade_group (
            account_id,
            symbol,
            group_type,
            started_at,
            ended_at,
            direction,
            entry_count,
            exit_count,
            total_qty,
            gross_pnl,
            fees,
            funding,
            net_pnl,
            hold_seconds,
            outcome,
            entry_price_avg,
            exit_price_avg,
            execution_count,
            max_position_qty,
            status,
            trade_key,
            metadata,
            created_at
        )
        VALUES (
            %(account_id)s,
            %(symbol)s,
            %(group_type)s,
            %(started_at)s,
            %(ended_at)s,
            %(direction)s,
            %(entry_count)s,
            %(exit_count)s,
            %(total_qty)s,
            %(gross_pnl)s,
            %(fees)s,
            %(funding)s,
            %(net_pnl)s,
            %(hold_seconds)s,
            %(outcome)s,
            %(entry_price_avg)s,
            %(exit_price_avg)s,
            %(execution_count)s,
            %(max_position_qty)s,
            %(status)s,
            %(trade_key)s,
            %(metadata)s::jsonb,
            %(created_at)s
        )
    """

    now_ts = utc_now()
    payload = []
    for g in groups:
        g["created_at"] = now_ts
        payload.append(g)

    with conn.cursor() as cur:
        cur.executemany(sql, payload)


def run():
    print("=== REBUILD TRADE_GROUP V2 START ===")
    print(f"ACCOUNT_ID: {ACCOUNT_ID}")

    conn = get_connection()
    try:
        executions = load_executions(conn, ACCOUNT_ID)
        print(f"Loaded executions: {len(executions)}")

        groups = build_trade_groups(executions)
        print(f"Built closed groups: {len(groups)}")

        delete_existing_trade_groups(conn, ACCOUNT_ID)
        insert_trade_groups(conn, groups)

        conn.commit()
        print("trade_group rebuild committed")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()

    print("=== REBUILD TRADE_GROUP V2 DONE ===")


if __name__ == "__main__":
    run()