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


def fmt_num(value, digits=2, signed=False) -> str:
    if value is None:
        return "n/a"
    val = float(value)
    if abs(val) < 1e-12:
        val = 0.0
    if signed and val != 0:
        return f"{val:+,.{digits}f}"
    return f"{val:,.{digits}f}"


def fmt_pct(value, digits=2) -> str:
    if value is None:
        return "n/a"
    val = float(value) * 100
    if abs(val) < 1e-12:
        val = 0.0
    if val != 0:
        return f"{val:+,.{digits}f}%"
    return f"{val:,.{digits}f}%"


def get_trade_stats(conn, account_id: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS trades_count,
                COALESCE(SUM(net_pnl), 0) AS net_pnl,
                COALESCE(AVG(net_pnl), 0) AS avg_trade,
                SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS wins_count,
                SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losses_count,
                AVG(CASE WHEN net_pnl > 0 THEN net_pnl END) AS avg_win,
                AVG(CASE WHEN net_pnl < 0 THEN net_pnl END) AS avg_loss,
                CASE
                    WHEN COUNT(*) = 0 THEN 0
                    ELSE ROUND(
                        SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END)::numeric / COUNT(*),
                        6
                    )
                END AS win_rate
            FROM trade
            WHERE account_id = %s
            """,
            (account_id,),
        )
        return cur.fetchone()


def get_today_stats(conn, account_id: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(trades_count), 0) AS trades_count,
                COALESCE(SUM(wins_count), 0) AS wins_count,
                COALESCE(SUM(losses_count), 0) AS losses_count,
                COALESCE(SUM(gross_pnl), 0) AS gross_pnl,
                COALESCE(SUM(fees), 0) AS fees,
                COALESCE(SUM(funding), 0) AS funding,
                COALESCE(SUM(net_pnl), 0) AS net_pnl,
                CASE
                    WHEN COALESCE(SUM(trades_count), 0) = 0 THEN 0
                    ELSE ROUND(SUM(wins_count)::numeric / SUM(trades_count), 6)
                END AS win_rate
            FROM daily_performance
            WHERE account_id = %s
              AND day = CURRENT_DATE
            """,
            (account_id,),
        )
        return cur.fetchone()


def get_last_n_days_stats(conn, account_id: str, days: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(trades_count), 0) AS trades_count,
                COALESCE(SUM(wins_count), 0) AS wins_count,
                COALESCE(SUM(losses_count), 0) AS losses_count,
                COALESCE(SUM(gross_pnl), 0) AS gross_pnl,
                COALESCE(SUM(fees), 0) AS fees,
                COALESCE(SUM(funding), 0) AS funding,
                COALESCE(SUM(net_pnl), 0) AS net_pnl,
                CASE
                    WHEN COALESCE(SUM(trades_count), 0) = 0 THEN 0
                    ELSE ROUND(SUM(wins_count)::numeric / SUM(trades_count), 6)
                END AS win_rate
            FROM daily_performance
            WHERE account_id = %s
              AND day >= CURRENT_DATE - (%s::int - 1)
            """,
            (account_id, days),
        )
        return cur.fetchone()


def get_latest_equity(conn, account_id: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM equity_snapshot
            WHERE account_id = %s
            ORDER BY ts DESC
            LIMIT 1
            """,
            (account_id,),
        )
        return cur.fetchone()


def get_drawdown_summary(conn, account_id: str):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                latest.ts,
                latest.equity,
                latest.high_watermark,
                latest.drawdown_abs AS current_drawdown_abs,
                latest.drawdown_pct AS current_drawdown_pct,
                agg.max_drawdown_abs,
                agg.max_drawdown_pct,
                agg.ath_equity
            FROM (
                SELECT
                    ts,
                    equity,
                    high_watermark,
                    drawdown_abs,
                    drawdown_pct
                FROM drawdown_snapshot
                WHERE account_id = %s
                ORDER BY ts DESC
                LIMIT 1
            ) latest
            CROSS JOIN (
                SELECT
                    MIN(drawdown_abs) AS max_drawdown_abs,
                    MIN(drawdown_pct) AS max_drawdown_pct,
                    MAX(high_watermark) AS ath_equity
                FROM drawdown_snapshot
                WHERE account_id = %s
            ) agg
            """,
            (account_id, account_id),
        )
        return cur.fetchone()


def get_top_symbols(conn, account_id: str, limit: int = 5):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                symbol,
                trades_count,
                net_pnl,
                win_rate
            FROM symbol_performance
            WHERE account_id = %s
            ORDER BY net_pnl DESC, symbol
            LIMIT %s
            """,
            (account_id, limit),
        )
        return cur.fetchall()


def build_stats_text(account_id: str = ACCOUNT_ID) -> str:
    conn = get_connection()
    try:
        overall = get_trade_stats(conn, account_id)
        today = get_today_stats(conn, account_id)
        week = get_last_n_days_stats(conn, account_id, 7)
        equity = get_latest_equity(conn, account_id)
        dd = get_drawdown_summary(conn, account_id)
        top_symbols = get_top_symbols(conn, account_id, 5)

        lines = []
        lines.append("Trading Stats")
        lines.append(f"Account: {account_id}")
        lines.append("")

        if overall:
            lines.append("Overall:")
            lines.append(f"• Trades: {overall['trades_count']}")
            lines.append(f"• Net PnL: {fmt_num(overall['net_pnl'], signed=True)}")
            lines.append(f"• Win rate: {fmt_pct(overall['win_rate'])}")
            lines.append(f"• Avg trade: {fmt_num(overall['avg_trade'], signed=True)}")
            lines.append(f"• Avg win: {fmt_num(overall['avg_win'], signed=True)}")
            lines.append(f"• Avg loss: {fmt_num(overall['avg_loss'], signed=True)}")
            lines.append("")

        if today and int(today["trades_count"] or 0) > 0:
            lines.append("Today:")
            lines.append(f"• Trades: {today['trades_count']}")
            lines.append(f"• Net PnL: {fmt_num(today['net_pnl'], signed=True)}")
            lines.append(f"• Win rate: {fmt_pct(today['win_rate'])}")
            lines.append("")
        else:
            lines.append("Today:")
            lines.append("• No closed trades today")
            lines.append("")

        if week:
            lines.append("Last 7 days:")
            lines.append(f"• Trades: {week['trades_count']}")
            lines.append(f"• Net PnL: {fmt_num(week['net_pnl'], signed=True)}")
            lines.append(f"• Win rate: {fmt_pct(week['win_rate'])}")
            lines.append("")

        if equity:
            lines.append("Equity:")
            lines.append(f"• Equity: {fmt_num(equity['equity'])}")
            lines.append(f"• Wallet balance: {fmt_num(equity['wallet_balance'])}")
            lines.append(f"• Unrealized PnL: {fmt_num(equity['unrealized_pnl'], signed=True)}")
            lines.append("")

        if dd:
            lines.append("Drawdown:")
            lines.append(f"• ATH equity: {fmt_num(dd['ath_equity'])}")
            lines.append(
                f"• Current DD: {fmt_num(dd['current_drawdown_abs'])} ({fmt_pct(dd['current_drawdown_pct'])})"
            )
            lines.append(
                f"• Max DD: {fmt_num(dd['max_drawdown_abs'])} ({fmt_pct(dd['max_drawdown_pct'])})"
            )
            lines.append("")

        if top_symbols:
            lines.append("Top symbols:")
            for row in top_symbols:
                lines.append(
                    f"• {row['symbol']}: {fmt_num(row['net_pnl'], signed=True)} | trades={row['trades_count']} | win={fmt_pct(row['win_rate'])}"
                )

        return "\n".join(lines)
    finally:
        conn.close()


if __name__ == "__main__":
    print(build_stats_text())