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
BYBIT_CLOSED_PNL_LIMIT = int(os.getenv("BYBIT_CLOSED_PNL_LIMIT", "50"))
BYBIT_RECV_WINDOW = os.getenv("BYBIT_RECV_WINDOW", "5000")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
BYBIT_CLOSED_PNL_MAX_PAGES = int(os.getenv("BYBIT_CLOSED_PNL_MAX_PAGES", "20"))


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
              AND entity = 'closed_pnl'
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
                'closed_pnl',
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


def insert_raw_closed_pnl(conn, pnl_item: dict) -> bool:
    """
    У raw_closed_pnl нет нормального natural unique key в текущей схеме,
    поэтому для первой версии делаем защиту через NOT EXISTS по набору полей.
    Потом можно будет добавить отдельный unique index.
    """
    created_time = ms_to_dt(pnl_item.get("createdTime"))
    updated_time = ms_to_dt(pnl_item.get("updatedTime"))

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_closed_pnl (
                account_id,
                symbol,
                category,
                side,
                qty,
                avg_entry_price,
                avg_exit_price,
                closed_pnl,
                created_time,
                updated_time,
                raw_json
            )
            SELECT
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            WHERE NOT EXISTS (
                SELECT 1
                FROM raw_closed_pnl
                WHERE account_id = %s
                  AND symbol = %s
                  AND category = %s
                  AND COALESCE(side, '') = COALESCE(%s, '')
                  AND COALESCE(qty, 0) = COALESCE(%s, 0)
                  AND COALESCE(avg_entry_price, 0) = COALESCE(%s, 0)
                  AND COALESCE(avg_exit_price, 0) = COALESCE(%s, 0)
                  AND COALESCE(closed_pnl, 0) = COALESCE(%s, 0)
                  AND COALESCE(created_time, 'epoch'::timestamptz) = COALESCE(%s, 'epoch'::timestamptz)
                  AND COALESCE(updated_time, 'epoch'::timestamptz) = COALESCE(%s, 'epoch'::timestamptz)
            )
            """,
            (
                ACCOUNT_ID,
                pnl_item.get("symbol"),
                pnl_item.get("category", BYBIT_CATEGORY),
                pnl_item.get("side"),
                to_decimal(pnl_item.get("qty")),
                to_decimal(pnl_item.get("avgEntryPrice")),
                to_decimal(pnl_item.get("avgExitPrice")),
                to_decimal(pnl_item.get("closedPnl")),
                created_time,
                updated_time,
                json.dumps(pnl_item, ensure_ascii=False),

                ACCOUNT_ID,
                pnl_item.get("symbol"),
                pnl_item.get("category", BYBIT_CATEGORY),
                pnl_item.get("side"),
                to_decimal(pnl_item.get("qty")),
                to_decimal(pnl_item.get("avgEntryPrice")),
                to_decimal(pnl_item.get("avgExitPrice")),
                to_decimal(pnl_item.get("closedPnl")),
                created_time,
                updated_time,
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


def fetch_closed_pnl_page(cursor_value: str | None = None) -> dict:
    params = {
        "category": BYBIT_CATEGORY,
        "limit": BYBIT_CLOSED_PNL_LIMIT,
    }

    if cursor_value:
        params["cursor"] = cursor_value

    return bybit_get("/v5/position/closed-pnl", params)


# -----------------------------
# Main sync
# -----------------------------
def run():
    print("=== BYBIT CLOSED PNL COLLECTOR START ===")
    print(f"DATABASE_URL exists: {bool(DATABASE_URL)}")
    print(f"BYBIT_BASE_URL: {BYBIT_BASE_URL}")
    print(f"BYBIT_API_KEY exists: {bool(BYBIT_API_KEY)}")
    print(f"BYBIT_API_SECRET exists: {bool(BYBIT_API_SECRET)}")
    print(f"ACCOUNT_ID: {ACCOUNT_ID}")
    print(f"CATEGORY: {BYBIT_CATEGORY}")
    print(f"LIMIT: {BYBIT_CLOSED_PNL_LIMIT}")
    print(f"MAX_PAGES: {BYBIT_CLOSED_PNL_MAX_PAGES}")

    conn = get_connection()
    print("DB connected")

    state = get_sync_state(conn)
    current_cursor = state["cursor"] if state else None
    print(f"Existing sync cursor: {current_cursor}")
    print(f"Existing last_seen_time: {state['last_seen_time'] if state else None}")

    total_received = 0
    total_inserted = 0
    newest_updated_time = state["last_seen_time"] if state else None

    page_no = 1

    while page_no <= BYBIT_CLOSED_PNL_MAX_PAGES:
        print(f"\n--- page {page_no} ---")
        data = fetch_closed_pnl_page(current_cursor)

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

        for pnl_item in items:
            total_received += 1

            updated_dt = ms_to_dt(pnl_item.get("updatedTime"))
            if updated_dt and (newest_updated_time is None or updated_dt > newest_updated_time):
                newest_updated_time = updated_dt

            if insert_raw_closed_pnl(conn, pnl_item):
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

    upsert_sync_state(conn, current_cursor, newest_updated_time)

    print("\n=== CLOSED PNL SYNC DONE ===")
    print(f"Total received: {total_received}")
    print(f"Total inserted: {total_inserted}")
    print(f"Newest updated time: {newest_updated_time}")
    print(f"Saved cursor: {current_cursor}")

    conn.close()


if __name__ == "__main__":
    run()