import os
import json
import time
import hmac
import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


# -----------------------------
# Env / config
# -----------------------------
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BYBIT_BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api-demo.bybit.com")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "39a8151d-c349-4ea6-88f7-b111f19908a1")

BYBIT_CATEGORY = os.getenv("BYBIT_CATEGORY", "linear")
BYBIT_LIMIT = int(os.getenv("BYBIT_LIMIT", "50"))
BYBIT_RECV_WINDOW = os.getenv("BYBIT_RECV_WINDOW", "5000")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))


# -----------------------------
# Helpers
# -----------------------------
def require_env(name: str, value: str | None) -> str:
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


def to_bool(value):
    if isinstance(value, bool):
        return value
    if value in ("true", "True", "1", 1):
        return True
    if value in ("false", "False", "0", 0):
        return False
    return None


def ms_to_dt(ms_value):
    if ms_value is None or ms_value == "":
        return None
    return datetime.fromtimestamp(int(ms_value) / 1000, tz=timezone.utc)


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


# -----------------------------
# DB
# -----------------------------
def get_connection():
    dsn = require_env("DATABASE_URL", DATABASE_URL)
    return psycopg.connect(dsn, row_factory=dict_row)


def get_sync_state(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT source, account_id, entity, cursor, last_seen_time, updated_at
            FROM sync_state
            WHERE source = 'bybit'
              AND account_id = %s
              AND entity = 'execution'
            """,
            (ACCOUNT_ID,),
        )
        return cur.fetchone()


def upsert_sync_state(conn, cursor_value: str | None, last_seen_time):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_state (
                source,
                account_id,
                entity,
                cursor,
                last_seen_time,
                updated_at
            )
            VALUES (
                'bybit',
                %s,
                'execution',
                %s,
                %s,
                now()
            )
            ON CONFLICT (source, account_id, entity)
            DO UPDATE SET
                cursor = EXCLUDED.cursor,
                last_seen_time = EXCLUDED.last_seen_time,
                updated_at = now()
            """,
            (ACCOUNT_ID, cursor_value, last_seen_time),
        )
    conn.commit()


def insert_raw_execution(conn, execution: dict) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_execution (
                account_id,
                exec_id,
                order_id,
                symbol,
                category,
                side,
                exec_type,
                price,
                qty,
                value,
                fee,
                fee_currency,
                is_maker,
                exec_time,
                raw_json
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (account_id, exec_id) DO NOTHING
            """,
            (
                ACCOUNT_ID,
                execution.get("execId"),
                execution.get("orderId"),
                execution.get("symbol"),
                execution.get("category", BYBIT_CATEGORY),
                execution.get("side"),
                execution.get("execType"),
                to_decimal(execution.get("execPrice")),
                to_decimal(execution.get("execQty")),
                to_decimal(execution.get("execValue")),
                to_decimal(execution.get("execFee")),
                execution.get("feeCurrency"),
                to_bool(execution.get("isMaker")),
                ms_to_dt(execution.get("execTime")),
                json.dumps(execution, ensure_ascii=False),
            ),
        )
        inserted = cur.rowcount > 0
    return inserted


# -----------------------------
# Bybit API
# -----------------------------
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


def fetch_execution_page(cursor_value: str | None = None) -> dict:
    params = {
        "category": BYBIT_CATEGORY,
        "limit": BYBIT_LIMIT,
    }

    if cursor_value:
        params["cursor"] = cursor_value

    return bybit_get("/v5/execution/list", params)


# -----------------------------
# Main sync
# -----------------------------
def run():
    print("=== BYBIT EXECUTION COLLECTOR START ===")
    print(f"DATABASE_URL exists: {bool(DATABASE_URL)}")
    print(f"BYBIT_BASE_URL: {BYBIT_BASE_URL}")
    print(f"BYBIT_API_KEY exists: {bool(BYBIT_API_KEY)}")
    print(f"BYBIT_API_SECRET exists: {bool(BYBIT_API_SECRET)}")
    print(f"ACCOUNT_ID: {ACCOUNT_ID}")
    print(f"CATEGORY: {BYBIT_CATEGORY}")
    print(f"LIMIT: {BYBIT_LIMIT}")

    conn = get_connection()
    print("DB connected")

    state = get_sync_state(conn)
    current_cursor = state["cursor"] if state else None
    print(f"Existing sync cursor: {current_cursor}")
    print(f"Existing last_seen_time: {state['last_seen_time'] if state else None}")

    total_received = 0
    total_inserted = 0
    newest_exec_time = state["last_seen_time"] if state else None

    page_no = 1
    max_pages = 20

    while page_no <= max_pages:
        print(f"\n--- page {page_no} ---")
        data = fetch_execution_page(current_cursor)

        print("BYBIT RESPONSE retCode:", data.get("retCode"))
        print("BYBIT RESPONSE retMsg:", data.get("retMsg"))

        if data.get("retCode") != 0:
            print(json.dumps(data, indent=2, ensure_ascii=False))
            raise RuntimeError(f"Bybit API error: {data.get('retMsg')}")

        result = data.get("result") or {}
        items = result.get("list") or []
        next_cursor = result.get("nextPageCursor")

        print(f"Fetched items: {len(items)}")
        print(f"Next cursor: {next_cursor}")

        if not items:
            break

        inserted_this_page = 0

        for execution in items:
            total_received += 1

            exec_dt = ms_to_dt(execution.get("execTime"))
            if exec_dt and (newest_exec_time is None or exec_dt > newest_exec_time):
                newest_exec_time = exec_dt

            if insert_raw_execution(conn, execution):
                inserted_this_page += 1
                total_inserted += 1

        conn.commit()
        print(f"Inserted this page: {inserted_this_page}")

        if not next_cursor or next_cursor == current_cursor:
            current_cursor = next_cursor
            break

        current_cursor = next_cursor
        page_no += 1

        time.sleep(0.15)

    upsert_sync_state(conn, current_cursor, newest_exec_time)

    print("\n=== SYNC DONE ===")
    print(f"Total received: {total_received}")
    print(f"Total inserted: {total_inserted}")
    print(f"Newest exec time: {newest_exec_time}")
    print(f"Saved cursor: {current_cursor}")

    conn.close()


if __name__ == "__main__":
    run()