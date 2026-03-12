import os
from typing import Optional

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


def get_connection():
    dsn = require_env("DATABASE_URL", DATABASE_URL)
    return psycopg.connect(dsn, row_factory=dict_row)


def rebuild_trades(conn, account_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM trade
            WHERE account_id = %s
              AND source = 'bybit_closed_pnl'
            """,
            (account_id,),
        )

        cur.execute(
            """
            INSERT INTO trade (
                account_id,
                symbol,
                source,
                source_row_id,
                side,
                qty,
                entry_price_avg,
                exit_price_avg,
                gross_pnl,
                fees,
                funding,
                net_pnl,
                opened_at,
                closed_at,
                duration_seconds,
                outcome,
                metadata,
                created_at,
                updated_at
            )
            SELECT
                rcp.account_id,
                rcp.symbol,
                'bybit_closed_pnl' AS source,
                rcp.id AS source_row_id,
                rcp.side,
                rcp.qty,
                rcp.avg_entry_price,
                rcp.avg_exit_price,
                rcp.closed_pnl AS gross_pnl,
                0 AS fees,
                0 AS funding,
                rcp.closed_pnl AS net_pnl,
                rcp.created_time AS opened_at,
                COALESCE(rcp.updated_time, rcp.created_time) AS closed_at,
                GREATEST(
                    0,
                    EXTRACT(
                        EPOCH FROM (
                            COALESCE(rcp.updated_time, rcp.created_time) - rcp.created_time
                        )
                    )::int
                ) AS duration_seconds,
                CASE
                    WHEN rcp.closed_pnl > 0 THEN 'win'
                    WHEN rcp.closed_pnl < 0 THEN 'loss'
                    ELSE 'flat'
                END AS outcome,
                jsonb_build_object(
                    'raw_closed_pnl_id', rcp.id,
                    'created_time', rcp.created_time,
                    'updated_time', rcp.updated_time
                ) AS metadata,
                now(),
                now()
            FROM raw_closed_pnl rcp
            WHERE rcp.account_id = %s
            """,
            (account_id,),
        )


def run():
    print("=== REBUILD TRADES START ===")
    print(f"ACCOUNT_ID: {ACCOUNT_ID}")
    conn = get_connection()
    try:
        rebuild_trades(conn, ACCOUNT_ID)
        conn.commit()
        print("trade rebuild committed")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()
        print("=== REBUILD TRADES DONE ===")


if __name__ == "__main__":
    run()