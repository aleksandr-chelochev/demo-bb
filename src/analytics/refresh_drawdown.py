import os
from decimal import Decimal, InvalidOperation
from typing import Optional, List

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "39a8151d-c349-4ea6-88f7-b111f19908a1")


def require_env(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def to_decimal(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def get_connection():
    dsn = require_env("DATABASE_URL", DATABASE_URL)
    return psycopg.connect(dsn, row_factory=dict_row)


def load_equity_rows(conn, account_id: str) -> List[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ts, equity
            FROM equity_snapshot
            WHERE account_id = %s
            ORDER BY ts
            """,
            (account_id,),
        )
        return cur.fetchall()


def rebuild_drawdown(conn, account_id: str):
    rows = load_equity_rows(conn, account_id)

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM drawdown_snapshot WHERE account_id = %s",
            (account_id,),
        )

    if not rows:
        return 0

    payload = []
    high_watermark = None

    for row in rows:
        ts = row["ts"]
        equity = to_decimal(row["equity"])

        if high_watermark is None or equity > high_watermark:
            high_watermark = equity

        drawdown_abs = equity - high_watermark

        if high_watermark == 0:
            drawdown_pct = Decimal("0")
        else:
            drawdown_pct = drawdown_abs / high_watermark

        payload.append({
            "account_id": account_id,
            "ts": ts,
            "equity": equity,
            "high_watermark": high_watermark,
            "drawdown_abs": drawdown_abs,
            "drawdown_pct": drawdown_pct,
        })

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO drawdown_snapshot (
                account_id,
                ts,
                equity,
                high_watermark,
                drawdown_abs,
                drawdown_pct
            )
            VALUES (
                %(account_id)s,
                %(ts)s,
                %(equity)s,
                %(high_watermark)s,
                %(drawdown_abs)s,
                %(drawdown_pct)s
            )
            """,
            payload,
        )

    return len(payload)


def run():
    print("=== REFRESH DRAWDOWN START ===")
    print(f"ACCOUNT_ID: {ACCOUNT_ID}")

    conn = get_connection()
    try:
        inserted = rebuild_drawdown(conn, ACCOUNT_ID)
        conn.commit()
        print(f"Drawdown rows rebuilt: {inserted}")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()

    print("=== REFRESH DRAWDOWN DONE ===")


if __name__ == "__main__":
    run()