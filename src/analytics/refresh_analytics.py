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


def refresh_daily_performance(conn, account_id: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM daily_performance
            WHERE account_id = %s
            """,
            (account_id,),
        )

        cur.execute(
            """
            INSERT INTO daily_performance (
                account_id,
                day,
                trades_count,
                wins_count,
                losses_count,
                gross_pnl,
                fees,
                funding,
                net_pnl,
                avg_win,
                avg_loss,
                win_rate,
                created_at,
                updated_at
            )
            SELECT
                account_id,
                (COALESCE(ended_at, started_at) AT TIME ZONE 'UTC')::date AS day,
                COUNT(*) AS trades_count,
                SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS wins_count,
                SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losses_count,
                COALESCE(SUM(gross_pnl), 0) AS gross_pnl,
                COALESCE(SUM(fees), 0) AS fees,
                COALESCE(SUM(funding), 0) AS funding,
                COALESCE(SUM(net_pnl), 0) AS net_pnl,
                AVG(CASE WHEN net_pnl > 0 THEN net_pnl END) AS avg_win,
                AVG(CASE WHEN net_pnl < 0 THEN net_pnl END) AS avg_loss,
                CASE
                    WHEN COUNT(*) = 0 THEN 0
                    ELSE ROUND(SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END)::numeric / COUNT(*), 6)
                END AS win_rate,
                now(),
                now()
            FROM trade_group
            WHERE account_id = %s
              AND status = 'closed'
            GROUP BY
                account_id,
                (COALESCE(ended_at, started_at) AT TIME ZONE 'UTC')::date
            """,
            (account_id,),
        )


def refresh_symbol_performance(conn, account_id: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM symbol_performance
            WHERE account_id = %s
            """,
            (account_id,),
        )

        cur.execute(
            """
            INSERT INTO symbol_performance (
                account_id,
                symbol,
                trades_count,
                wins_count,
                losses_count,
                gross_pnl,
                fees,
                funding,
                net_pnl,
                avg_trade,
                avg_win,
                avg_loss,
                win_rate,
                updated_at
            )
            SELECT
                account_id,
                symbol,
                COUNT(*) AS trades_count,
                SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS wins_count,
                SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losses_count,
                COALESCE(SUM(gross_pnl), 0) AS gross_pnl,
                COALESCE(SUM(fees), 0) AS fees,
                COALESCE(SUM(funding), 0) AS funding,
                COALESCE(SUM(net_pnl), 0) AS net_pnl,
                COALESCE(AVG(net_pnl), 0) AS avg_trade,
                AVG(CASE WHEN net_pnl > 0 THEN net_pnl END) AS avg_win,
                AVG(CASE WHEN net_pnl < 0 THEN net_pnl END) AS avg_loss,
                CASE
                    WHEN COUNT(*) = 0 THEN 0
                    ELSE ROUND(SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END)::numeric / COUNT(*), 6)
                END AS win_rate,
                now()
            FROM trade_group
            WHERE account_id = %s
              AND status = 'closed'
            GROUP BY account_id, symbol
            """,
            (account_id,),
        )


def run():
    print("=== REFRESH ANALYTICS START ===")
    print(f"ACCOUNT_ID: {ACCOUNT_ID}")

    conn = get_connection()
    try:
        refresh_daily_performance(conn, ACCOUNT_ID)
        refresh_symbol_performance(conn, ACCOUNT_ID)

        conn.commit()
        print("analytics refresh committed")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()

    print("=== REFRESH ANALYTICS DONE ===")


if __name__ == "__main__":
    run()