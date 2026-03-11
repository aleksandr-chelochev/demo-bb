import os
import json
import time
import hmac
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

import requests
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api-demo.bybit.com")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "39a8151d-c349-4ea6-88f7-b111f19908a1")

BYBIT_ACCOUNT_TYPE = os.getenv("BYBIT_ACCOUNT_TYPE", "UNIFIED")
BYBIT_COIN = os.getenv("BYBIT_COIN", "USDT")
BYBIT_RECV_WINDOW = os.getenv("BYBIT_RECV_WINDOW", "5000")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))


def require_env(name: str, value: Optional[str]) -> str:
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def to_decimal(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_signature(timestamp: str, api_key: str, recv_window: str, query_string: str, api_secret: str) -> str:
    payload = f"{timestamp}{api_key}{recv_window}{query_string}"
    return hmac.new(
        api_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_query(params: dict) -> str:
    items = []
    for key, value in params.items():
        if value is not None and value != "":
            items.append(f"{key}={value}")
    return "&".join(items)


def get_connection():
    dsn = require_env("DATABASE_URL", DATABASE_URL)
    return psycopg.connect(dsn, row_factory=dict_row)


def bybit_get(endpoint: str, params: dict) -> dict:
    api_key = require_env("BYBIT_API_KEY", BYBIT_API_KEY)
    api_secret = require_env("BYBIT_API_SECRET", BYBIT_API_SECRET)
    base_url = require_env("BYBIT_BASE_URL", BYBIT_BASE_URL)

    timestamp = str(int(time.time() * 1000))
    recv_window = BYBIT_RECV_WINDOW
    query_string = build_query(params)
    signature = build_signature(timestamp, api_key, recv_window, query_string, api_secret)

    headers = {
        "X-BAPI-API-KEY": api_key,
        "X-BAPI-SIGN": signature,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
    }

    url = f"{base_url}{endpoint}"
    if query_string:
        url = f"{url}?{query_string}"

    response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def fetch_wallet_balance() -> dict:
    params = {
        "accountType": BYBIT_ACCOUNT_TYPE,
        "coin": BYBIT_COIN,
    }
    return bybit_get("/v5/account/wallet-balance", params)


def extract_snapshot_fields(data: dict) -> dict:
    result = data.get("result") or {}
    account_list = result.get("list") or []
    if not account_list:
        raise RuntimeError("Bybit wallet balance returned empty list")

    account_data = account_list[0]
    coin_list = account_data.get("coin") or []

    coin_data = None
    for item in coin_list:
        if item.get("coin") == BYBIT_COIN:
            coin_data = item
            break

    if coin_data is None:
        raise RuntimeError(f"Coin {BYBIT_COIN} not found in Bybit wallet balance response")

    ts = utc_now()

    equity = to_decimal(coin_data.get("equity"))
    wallet_balance = to_decimal(coin_data.get("walletBalance"))
    available_balance = to_decimal(coin_data.get("availableToWithdraw") or coin_data.get("availableBalance"))
    unrealized_pnl = to_decimal(coin_data.get("unrealisedPnl"))

    # Для balance пока используем wallet_balance как наиболее близкий смысл
    balance = wallet_balance

    if equity is None:
        raise RuntimeError("Bybit wallet balance response has no equity")

    return {
        "ts": ts,
        "equity": equity,
        "balance": balance,
        "wallet_balance": wallet_balance,
        "available_balance": available_balance,
        "unrealized_pnl": unrealized_pnl,
        "raw_json": json.dumps(data, ensure_ascii=False),
    }


def insert_equity_snapshot(conn, snapshot: dict) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO equity_snapshot (
                account_id,
                ts,
                balance,
                equity,
                available_balance,
                unrealized_pnl,
                wallet_balance,
                raw_json
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (account_id, ts) DO NOTHING
            """,
            (
                ACCOUNT_ID,
                snapshot["ts"],
                snapshot["balance"],
                snapshot["equity"],
                snapshot["available_balance"],
                snapshot["unrealized_pnl"],
                snapshot["wallet_balance"],
                snapshot["raw_json"],
            ),
        )
        return cur.rowcount > 0


def run():
    print("=== BYBIT EQUITY COLLECTOR START ===")
    print(f"ACCOUNT_ID: {ACCOUNT_ID}")
    print(f"BYBIT_BASE_URL: {BYBIT_BASE_URL}")
    print(f"BYBIT_ACCOUNT_TYPE: {BYBIT_ACCOUNT_TYPE}")
    print(f"BYBIT_COIN: {BYBIT_COIN}")

    conn = get_connection()
    try:
        data = fetch_wallet_balance()

        print("BYBIT RESPONSE retCode:", data.get("retCode"))
        print("BYBIT RESPONSE retMsg:", data.get("retMsg"))

        if data.get("retCode") != 0:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            raise RuntimeError(f"Bybit API error: {data.get('retMsg')}")

        snapshot = extract_snapshot_fields(data)
        inserted = insert_equity_snapshot(conn, snapshot)
        conn.commit()

        print(f"Snapshot ts: {snapshot['ts']}")
        print(f"Equity: {snapshot['equity']}")
        print(f"Wallet balance: {snapshot['wallet_balance']}")
        print(f"Available balance: {snapshot['available_balance']}")
        print(f"Unrealized PnL: {snapshot['unrealized_pnl']}")
        print(f"Inserted: {inserted}")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        conn.close()

    print("=== BYBIT EQUITY COLLECTOR DONE ===")


if __name__ == "__main__":
    run()