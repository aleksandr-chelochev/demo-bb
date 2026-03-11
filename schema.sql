CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE account (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exchange text NOT NULL,
    env text NOT NULL,
    label text,
    bybit_uid text,
    account_mode text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sync_state (
    source text NOT NULL,
    account_id uuid NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    entity text NOT NULL,
    cursor text,
    last_seen_time timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, account_id, entity)
);

CREATE TABLE raw_execution (
    id bigserial PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    exec_id text NOT NULL,
    order_id text,
    symbol text NOT NULL,
    category text NOT NULL,
    side text,
    exec_type text,
    price numeric,
    qty numeric,
    value numeric,
    fee numeric,
    fee_currency text,
    is_maker boolean,
    exec_time timestamptz NOT NULL,
    raw_json jsonb NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account_id, exec_id)
);

CREATE TABLE raw_order (
    id bigserial PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    order_id text NOT NULL,
    order_link_id text,
    symbol text NOT NULL,
    category text NOT NULL,
    side text,
    order_type text,
    status text,
    qty numeric,
    price numeric,
    avg_price numeric,
    cum_exec_qty numeric,
    cum_exec_value numeric,
    cum_exec_fee numeric,
    created_time timestamptz,
    updated_time timestamptz,
    raw_json jsonb NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account_id, order_id, updated_time)
);

CREATE TABLE raw_closed_pnl (
    id bigserial PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    symbol text NOT NULL,
    category text NOT NULL,
    side text,
    qty numeric,
    avg_entry_price numeric,
    avg_exit_price numeric,
    closed_pnl numeric,
    created_time timestamptz,
    updated_time timestamptz,
    raw_json jsonb NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE raw_transaction_log (
    id bigserial PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    transaction_id text,
    symbol text,
    currency text,
    type text,
    cash_flow numeric,
    change_amount numeric,
    fee numeric,
    funding numeric,
    transaction_time timestamptz NOT NULL,
    raw_json jsonb NOT NULL,
    inserted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account_id, transaction_id)
);

CREATE TABLE trade_group (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id uuid NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    symbol text NOT NULL,
    group_type text NOT NULL DEFAULT 'single',
    started_at timestamptz NOT NULL,
    ended_at timestamptz,
    direction text,
    entry_count int NOT NULL DEFAULT 0,
    exit_count int NOT NULL DEFAULT 0,
    total_qty numeric DEFAULT 0,
    gross_pnl numeric DEFAULT 0,
    fees numeric DEFAULT 0,
    funding numeric DEFAULT 0,
    net_pnl numeric DEFAULT 0,
    hold_seconds bigint,
    outcome text,
    note text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_raw_execution_account_time
    ON raw_execution(account_id, exec_time DESC);

CREATE INDEX idx_raw_execution_symbol_time
    ON raw_execution(symbol, exec_time DESC);

CREATE INDEX idx_raw_order_account_time
    ON raw_order(account_id, updated_time DESC);

CREATE INDEX idx_raw_transaction_time
    ON raw_transaction_log(account_id, transaction_time DESC);

CREATE INDEX idx_trade_group_account_start
    ON trade_group(account_id, started_at DESC);

