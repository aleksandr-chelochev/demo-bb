import os
import logging
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.services.telegram_stats_service import build_stats_text, get_connection, fmt_num, fmt_pct


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "39a8151d-c349-4ea6-88f7-b111f19908a1")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def require_env(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 Trading Analytics Bot\n\n"
        "Commands:\n"
        "/stats — full stats\n"
        "/today — today stats\n"
        "/week — last 7 days\n"
        "/equity — latest equity\n"
        "/drawdown — drawdown summary\n"
        "/ping — bot health"
    )
    await update.message.reply_text(text)


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = build_stats_text(ACCOUNT_ID)
        await update.message.reply_text(text)
    except Exception as e:
        logger.exception("Failed /stats")
        await update.message.reply_text(f"Error while building stats: {e}")


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM daily_performance
                    WHERE account_id = %s
                      AND day = CURRENT_DATE
                    """,
                    (ACCOUNT_ID,),
                )
                row = cur.fetchone()

            if not row:
                text = "📅 Today\n\nNo closed trades today."
            else:
                text = (
                    "📅 Today\n\n"
                    f"Trades: {row['trades_count']}\n"
                    f"Gross PnL: {fmt_num(row['gross_pnl'], signed=True)}\n"
                    f"Fees: {fmt_num(row['fees'])}\n"
                    f"Funding: {fmt_num(row['funding'], signed=True)}\n"
                    f"Net PnL: {fmt_num(row['net_pnl'], signed=True)}\n"
                    f"Win rate: {fmt_pct(row['win_rate'])}\n"
                    f"Avg win: {fmt_num(row['avg_win'], signed=True)}\n"
                    f"Avg loss: {fmt_num(row['avg_loss'], signed=True)}"
                )
        finally:
            conn.close()

        await update.message.reply_text(text)
    except Exception as e:
        logger.exception("Failed /today")
        await update.message.reply_text(f"Error while loading today stats: {e}")


async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = get_connection()
        try:
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
                        COALESCE(SUM(net_pnl), 0) AS net_pnl
                    FROM daily_performance
                    WHERE account_id = %s
                      AND day >= CURRENT_DATE - INTERVAL '6 days'
                    """,
                    (ACCOUNT_ID,),
                )
                row = cur.fetchone()

            trades = int(row["trades_count"] or 0)
            wins = int(row["wins_count"] or 0)
            losses = int(row["losses_count"] or 0)
            win_rate = (wins / trades) if trades > 0 else 0

            text = (
                "📈 Last 7 Days\n\n"
                f"Trades: {trades}\n"
                f"Wins: {wins}\n"
                f"Losses: {losses}\n"
                f"Gross PnL: {fmt_num(row['gross_pnl'], signed=True)}\n"
                f"Fees: {fmt_num(row['fees'])}\n"
                f"Funding: {fmt_num(row['funding'], signed=True)}\n"
                f"Net PnL: {fmt_num(row['net_pnl'], signed=True)}\n"
                f"Win rate: {fmt_pct(win_rate)}"
            )
        finally:
            conn.close()

        await update.message.reply_text(text)
    except Exception as e:
        logger.exception("Failed /week")
        await update.message.reply_text(f"Error while loading week stats: {e}")


async def equity_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM equity_snapshot
                    WHERE account_id = %s
                    ORDER BY ts DESC
                    LIMIT 1
                    """,
                    (ACCOUNT_ID,),
                )
                row = cur.fetchone()

            if not row:
                text = "💰 Equity\n\nNo equity snapshots yet."
            else:
                text = (
                    "💰 Equity\n\n"
                    f"Timestamp: {row['ts']}\n"
                    f"Equity: {fmt_num(row['equity'])}\n"
                    f"Balance: {fmt_num(row['balance'])}\n"
                    f"Wallet balance: {fmt_num(row['wallet_balance'])}\n"
                    f"Available balance: {fmt_num(row['available_balance'])}\n"
                    f"Unrealized PnL: {fmt_num(row['unrealized_pnl'], signed=True)}"
                )
        finally:
            conn.close()

        await update.message.reply_text(text)
    except Exception as e:
        logger.exception("Failed /equity")
        await update.message.reply_text(f"Error while loading equity: {e}")


async def drawdown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = get_connection()
        try:
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
                    (ACCOUNT_ID, ACCOUNT_ID),
                )
                row = cur.fetchone()

            if not row:
                text = "📉 Drawdown\n\nNo drawdown snapshots yet."
            else:
                text = (
                    "📉 Drawdown\n\n"
                    f"Timestamp: {row['ts']}\n"
                    f"ATH equity: {fmt_num(row['ath_equity'])}\n"
                    f"Current equity: {fmt_num(row['equity'])}\n"
                    f"Current DD: {fmt_num(row['current_drawdown_abs'], signed=True)} ({fmt_pct(row['current_drawdown_pct'])})\n"
                    f"Max DD: {fmt_num(row['max_drawdown_abs'], signed=True)} ({fmt_pct(row['max_drawdown_pct'])})"
                )
        finally:
            conn.close()

        await update.message.reply_text(text)
    except Exception as e:
        logger.exception("Failed /drawdown")
        await update.message.reply_text(f"Error while loading drawdown: {e}")


def main():
    token = require_env("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("week", week_cmd))
    app.add_handler(CommandHandler("equity", equity_cmd))
    app.add_handler(CommandHandler("drawdown", drawdown_cmd))

    logger.info("Telegram bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()