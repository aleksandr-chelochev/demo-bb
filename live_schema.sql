--
-- PostgreSQL database dump
--

\restrict LKuvrodfJTOHfeBQezwtGDXQBQyZAoCkFHjdWGhbfVi48KL5krKIlT38l9k12Y6

-- Dumped from database version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.account (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    exchange text NOT NULL,
    env text NOT NULL,
    label text,
    bybit_uid text,
    account_mode text,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.account OWNER TO trader;

--
-- Name: daily_performance; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.daily_performance (
    account_id uuid NOT NULL,
    day date NOT NULL,
    trades_count integer DEFAULT 0 NOT NULL,
    wins_count integer DEFAULT 0 NOT NULL,
    losses_count integer DEFAULT 0 NOT NULL,
    gross_pnl numeric DEFAULT 0 NOT NULL,
    fees numeric DEFAULT 0 NOT NULL,
    funding numeric DEFAULT 0 NOT NULL,
    net_pnl numeric DEFAULT 0 NOT NULL,
    avg_win numeric,
    avg_loss numeric,
    win_rate numeric,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.daily_performance OWNER TO trader;

--
-- Name: drawdown_snapshot; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.drawdown_snapshot (
    id bigint NOT NULL,
    account_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    equity numeric NOT NULL,
    high_watermark numeric NOT NULL,
    drawdown_abs numeric NOT NULL,
    drawdown_pct numeric NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.drawdown_snapshot OWNER TO trader;

--
-- Name: drawdown_snapshot_id_seq; Type: SEQUENCE; Schema: public; Owner: trader
--

CREATE SEQUENCE public.drawdown_snapshot_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.drawdown_snapshot_id_seq OWNER TO trader;

--
-- Name: drawdown_snapshot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: trader
--

ALTER SEQUENCE public.drawdown_snapshot_id_seq OWNED BY public.drawdown_snapshot.id;


--
-- Name: equity_snapshot; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.equity_snapshot (
    id bigint NOT NULL,
    account_id uuid NOT NULL,
    ts timestamp with time zone NOT NULL,
    balance numeric,
    equity numeric NOT NULL,
    available_balance numeric,
    unrealized_pnl numeric,
    wallet_balance numeric,
    raw_json jsonb NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.equity_snapshot OWNER TO trader;

--
-- Name: equity_curve; Type: MATERIALIZED VIEW; Schema: public; Owner: trader
--

CREATE MATERIALIZED VIEW public.equity_curve AS
 SELECT account_id,
    ts,
    equity
   FROM public.equity_snapshot
  ORDER BY ts
  WITH NO DATA;


ALTER MATERIALIZED VIEW public.equity_curve OWNER TO trader;

--
-- Name: equity_snapshot_id_seq; Type: SEQUENCE; Schema: public; Owner: trader
--

CREATE SEQUENCE public.equity_snapshot_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.equity_snapshot_id_seq OWNER TO trader;

--
-- Name: equity_snapshot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: trader
--

ALTER SEQUENCE public.equity_snapshot_id_seq OWNED BY public.equity_snapshot.id;


--
-- Name: raw_closed_pnl; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.raw_closed_pnl (
    id bigint NOT NULL,
    account_id uuid NOT NULL,
    symbol text NOT NULL,
    category text NOT NULL,
    side text,
    qty numeric,
    avg_entry_price numeric,
    avg_exit_price numeric,
    closed_pnl numeric,
    created_time timestamp with time zone,
    updated_time timestamp with time zone,
    raw_json jsonb NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_closed_pnl OWNER TO trader;

--
-- Name: raw_closed_pnl_id_seq; Type: SEQUENCE; Schema: public; Owner: trader
--

CREATE SEQUENCE public.raw_closed_pnl_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_closed_pnl_id_seq OWNER TO trader;

--
-- Name: raw_closed_pnl_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: trader
--

ALTER SEQUENCE public.raw_closed_pnl_id_seq OWNED BY public.raw_closed_pnl.id;


--
-- Name: raw_execution; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.raw_execution (
    id bigint NOT NULL,
    account_id uuid NOT NULL,
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
    exec_time timestamp with time zone NOT NULL,
    raw_json jsonb NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_execution OWNER TO trader;

--
-- Name: raw_execution_id_seq; Type: SEQUENCE; Schema: public; Owner: trader
--

CREATE SEQUENCE public.raw_execution_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_execution_id_seq OWNER TO trader;

--
-- Name: raw_execution_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: trader
--

ALTER SEQUENCE public.raw_execution_id_seq OWNED BY public.raw_execution.id;


--
-- Name: raw_order; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.raw_order (
    id bigint NOT NULL,
    account_id uuid NOT NULL,
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
    created_time timestamp with time zone,
    updated_time timestamp with time zone,
    raw_json jsonb NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_order OWNER TO trader;

--
-- Name: raw_order_id_seq; Type: SEQUENCE; Schema: public; Owner: trader
--

CREATE SEQUENCE public.raw_order_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_order_id_seq OWNER TO trader;

--
-- Name: raw_order_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: trader
--

ALTER SEQUENCE public.raw_order_id_seq OWNED BY public.raw_order.id;


--
-- Name: raw_transaction_log; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.raw_transaction_log (
    id bigint NOT NULL,
    account_id uuid NOT NULL,
    transaction_id text,
    symbol text,
    currency text,
    type text,
    cash_flow numeric,
    change_amount numeric,
    fee numeric,
    funding numeric,
    transaction_time timestamp with time zone NOT NULL,
    raw_json jsonb NOT NULL,
    inserted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.raw_transaction_log OWNER TO trader;

--
-- Name: raw_transaction_log_id_seq; Type: SEQUENCE; Schema: public; Owner: trader
--

CREATE SEQUENCE public.raw_transaction_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.raw_transaction_log_id_seq OWNER TO trader;

--
-- Name: raw_transaction_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: trader
--

ALTER SEQUENCE public.raw_transaction_log_id_seq OWNED BY public.raw_transaction_log.id;


--
-- Name: symbol_performance; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.symbol_performance (
    account_id uuid NOT NULL,
    symbol text NOT NULL,
    trades_count integer DEFAULT 0 NOT NULL,
    wins_count integer DEFAULT 0 NOT NULL,
    losses_count integer DEFAULT 0 NOT NULL,
    gross_pnl numeric DEFAULT 0 NOT NULL,
    fees numeric DEFAULT 0 NOT NULL,
    funding numeric DEFAULT 0 NOT NULL,
    net_pnl numeric DEFAULT 0 NOT NULL,
    avg_trade numeric,
    avg_win numeric,
    avg_loss numeric,
    win_rate numeric,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.symbol_performance OWNER TO trader;

--
-- Name: sync_state; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.sync_state (
    source text NOT NULL,
    account_id uuid NOT NULL,
    entity text NOT NULL,
    cursor text,
    last_seen_time timestamp with time zone,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    status text,
    error_message text,
    rows_fetched integer,
    last_success_at timestamp with time zone
);


ALTER TABLE public.sync_state OWNER TO trader;

--
-- Name: trade_group; Type: TABLE; Schema: public; Owner: trader
--

CREATE TABLE public.trade_group (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    account_id uuid NOT NULL,
    symbol text NOT NULL,
    group_type text DEFAULT 'single'::text NOT NULL,
    started_at timestamp with time zone NOT NULL,
    ended_at timestamp with time zone,
    direction text,
    entry_count integer DEFAULT 0 NOT NULL,
    exit_count integer DEFAULT 0 NOT NULL,
    total_qty numeric DEFAULT 0,
    gross_pnl numeric DEFAULT 0,
    fees numeric DEFAULT 0,
    funding numeric DEFAULT 0,
    net_pnl numeric DEFAULT 0,
    hold_seconds bigint,
    outcome text,
    note text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    entry_price_avg numeric,
    exit_price_avg numeric,
    execution_count integer DEFAULT 0 NOT NULL,
    max_position_qty numeric,
    status text DEFAULT 'closed'::text NOT NULL,
    trade_key text,
    metadata jsonb
);


ALTER TABLE public.trade_group OWNER TO trader;

--
-- Name: v_daily_trade_performance; Type: VIEW; Schema: public; Owner: trader
--

CREATE VIEW public.v_daily_trade_performance AS
 SELECT account_id,
    ((COALESCE(ended_at, started_at) AT TIME ZONE 'UTC'::text))::date AS day,
    count(*) AS trades_count,
    sum(
        CASE
            WHEN (net_pnl > (0)::numeric) THEN 1
            ELSE 0
        END) AS wins_count,
    sum(
        CASE
            WHEN (net_pnl < (0)::numeric) THEN 1
            ELSE 0
        END) AS losses_count,
    COALESCE(sum(gross_pnl), (0)::numeric) AS gross_pnl,
    COALESCE(sum(fees), (0)::numeric) AS fees,
    COALESCE(sum(funding), (0)::numeric) AS funding,
    COALESCE(sum(net_pnl), (0)::numeric) AS net_pnl,
    avg(
        CASE
            WHEN (net_pnl > (0)::numeric) THEN net_pnl
            ELSE NULL::numeric
        END) AS avg_win,
    avg(
        CASE
            WHEN (net_pnl < (0)::numeric) THEN net_pnl
            ELSE NULL::numeric
        END) AS avg_loss,
        CASE
            WHEN (count(*) = 0) THEN (0)::numeric
            ELSE round(((sum(
            CASE
                WHEN (net_pnl > (0)::numeric) THEN 1
                ELSE 0
            END))::numeric / (count(*))::numeric), 6)
        END AS win_rate
   FROM public.trade_group
  GROUP BY account_id, (((COALESCE(ended_at, started_at) AT TIME ZONE 'UTC'::text))::date);


ALTER VIEW public.v_daily_trade_performance OWNER TO trader;

--
-- Name: v_symbol_stats; Type: VIEW; Schema: public; Owner: trader
--

CREATE VIEW public.v_symbol_stats AS
 SELECT account_id,
    symbol,
    count(*) AS trades_count,
    COALESCE(sum(gross_pnl), (0)::numeric) AS gross_pnl,
    COALESCE(sum(fees), (0)::numeric) AS fees,
    COALESCE(sum(funding), (0)::numeric) AS funding,
    COALESCE(sum(net_pnl), (0)::numeric) AS net_pnl,
    COALESCE(avg(net_pnl), (0)::numeric) AS avg_trade,
    sum(
        CASE
            WHEN (net_pnl > (0)::numeric) THEN 1
            ELSE 0
        END) AS wins_count,
    sum(
        CASE
            WHEN (net_pnl < (0)::numeric) THEN 1
            ELSE 0
        END) AS losses_count,
    avg(
        CASE
            WHEN (net_pnl > (0)::numeric) THEN net_pnl
            ELSE NULL::numeric
        END) AS avg_win,
    avg(
        CASE
            WHEN (net_pnl < (0)::numeric) THEN net_pnl
            ELSE NULL::numeric
        END) AS avg_loss,
        CASE
            WHEN (count(*) = 0) THEN (0)::numeric
            ELSE round(((sum(
            CASE
                WHEN (net_pnl > (0)::numeric) THEN 1
                ELSE 0
            END))::numeric / (count(*))::numeric), 6)
        END AS win_rate
   FROM public.trade_group
  GROUP BY account_id, symbol;


ALTER VIEW public.v_symbol_stats OWNER TO trader;

--
-- Name: v_trade_stats; Type: VIEW; Schema: public; Owner: trader
--

CREATE VIEW public.v_trade_stats AS
 SELECT account_id,
    count(*) AS trades_count,
    COALESCE(sum(gross_pnl), (0)::numeric) AS gross_pnl,
    COALESCE(sum(fees), (0)::numeric) AS fees,
    COALESCE(sum(funding), (0)::numeric) AS funding,
    COALESCE(sum(net_pnl), (0)::numeric) AS net_pnl,
    COALESCE(avg(net_pnl), (0)::numeric) AS avg_trade,
    sum(
        CASE
            WHEN (net_pnl > (0)::numeric) THEN 1
            ELSE 0
        END) AS wins_count,
    sum(
        CASE
            WHEN (net_pnl < (0)::numeric) THEN 1
            ELSE 0
        END) AS losses_count,
    avg(
        CASE
            WHEN (net_pnl > (0)::numeric) THEN net_pnl
            ELSE NULL::numeric
        END) AS avg_win,
    avg(
        CASE
            WHEN (net_pnl < (0)::numeric) THEN net_pnl
            ELSE NULL::numeric
        END) AS avg_loss,
        CASE
            WHEN (count(*) = 0) THEN (0)::numeric
            ELSE round(((sum(
            CASE
                WHEN (net_pnl > (0)::numeric) THEN 1
                ELSE 0
            END))::numeric / (count(*))::numeric), 6)
        END AS win_rate
   FROM public.trade_group
  GROUP BY account_id;


ALTER VIEW public.v_trade_stats OWNER TO trader;

--
-- Name: drawdown_snapshot id; Type: DEFAULT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.drawdown_snapshot ALTER COLUMN id SET DEFAULT nextval('public.drawdown_snapshot_id_seq'::regclass);


--
-- Name: equity_snapshot id; Type: DEFAULT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.equity_snapshot ALTER COLUMN id SET DEFAULT nextval('public.equity_snapshot_id_seq'::regclass);


--
-- Name: raw_closed_pnl id; Type: DEFAULT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_closed_pnl ALTER COLUMN id SET DEFAULT nextval('public.raw_closed_pnl_id_seq'::regclass);


--
-- Name: raw_execution id; Type: DEFAULT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_execution ALTER COLUMN id SET DEFAULT nextval('public.raw_execution_id_seq'::regclass);


--
-- Name: raw_order id; Type: DEFAULT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_order ALTER COLUMN id SET DEFAULT nextval('public.raw_order_id_seq'::regclass);


--
-- Name: raw_transaction_log id; Type: DEFAULT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_transaction_log ALTER COLUMN id SET DEFAULT nextval('public.raw_transaction_log_id_seq'::regclass);


--
-- Name: account account_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.account
    ADD CONSTRAINT account_pkey PRIMARY KEY (id);


--
-- Name: daily_performance daily_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.daily_performance
    ADD CONSTRAINT daily_performance_pkey PRIMARY KEY (account_id, day);


--
-- Name: drawdown_snapshot drawdown_snapshot_account_id_ts_key; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.drawdown_snapshot
    ADD CONSTRAINT drawdown_snapshot_account_id_ts_key UNIQUE (account_id, ts);


--
-- Name: drawdown_snapshot drawdown_snapshot_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.drawdown_snapshot
    ADD CONSTRAINT drawdown_snapshot_pkey PRIMARY KEY (id);


--
-- Name: equity_snapshot equity_snapshot_account_id_ts_key; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.equity_snapshot
    ADD CONSTRAINT equity_snapshot_account_id_ts_key UNIQUE (account_id, ts);


--
-- Name: equity_snapshot equity_snapshot_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.equity_snapshot
    ADD CONSTRAINT equity_snapshot_pkey PRIMARY KEY (id);


--
-- Name: raw_closed_pnl raw_closed_pnl_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_closed_pnl
    ADD CONSTRAINT raw_closed_pnl_pkey PRIMARY KEY (id);


--
-- Name: raw_execution raw_execution_account_id_exec_id_key; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_execution
    ADD CONSTRAINT raw_execution_account_id_exec_id_key UNIQUE (account_id, exec_id);


--
-- Name: raw_execution raw_execution_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_execution
    ADD CONSTRAINT raw_execution_pkey PRIMARY KEY (id);


--
-- Name: raw_order raw_order_account_id_order_id_updated_time_key; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_order
    ADD CONSTRAINT raw_order_account_id_order_id_updated_time_key UNIQUE (account_id, order_id, updated_time);


--
-- Name: raw_order raw_order_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_order
    ADD CONSTRAINT raw_order_pkey PRIMARY KEY (id);


--
-- Name: raw_transaction_log raw_transaction_log_account_id_transaction_id_key; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_transaction_log
    ADD CONSTRAINT raw_transaction_log_account_id_transaction_id_key UNIQUE (account_id, transaction_id);


--
-- Name: raw_transaction_log raw_transaction_log_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_transaction_log
    ADD CONSTRAINT raw_transaction_log_pkey PRIMARY KEY (id);


--
-- Name: symbol_performance symbol_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.symbol_performance
    ADD CONSTRAINT symbol_performance_pkey PRIMARY KEY (account_id, symbol);


--
-- Name: sync_state sync_state_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.sync_state
    ADD CONSTRAINT sync_state_pkey PRIMARY KEY (source, account_id, entity);


--
-- Name: trade_group trade_group_pkey; Type: CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.trade_group
    ADD CONSTRAINT trade_group_pkey PRIMARY KEY (id);


--
-- Name: idx_daily_performance_account_day; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_daily_performance_account_day ON public.daily_performance USING btree (account_id, day DESC);


--
-- Name: idx_daily_performance_day; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_daily_performance_day ON public.daily_performance USING btree (day DESC);


--
-- Name: idx_drawdown_snapshot_account_dd; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_drawdown_snapshot_account_dd ON public.drawdown_snapshot USING btree (account_id, drawdown_pct);


--
-- Name: idx_drawdown_snapshot_account_ts; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_drawdown_snapshot_account_ts ON public.drawdown_snapshot USING btree (account_id, ts DESC);


--
-- Name: idx_equity_snapshot_account_ts; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_equity_snapshot_account_ts ON public.equity_snapshot USING btree (account_id, ts DESC);


--
-- Name: idx_raw_closed_pnl_account_symbol_time; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_raw_closed_pnl_account_symbol_time ON public.raw_closed_pnl USING btree (account_id, symbol, updated_time DESC);


--
-- Name: idx_raw_closed_pnl_account_time; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_raw_closed_pnl_account_time ON public.raw_closed_pnl USING btree (account_id, updated_time DESC);


--
-- Name: idx_raw_execution_account_time; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_raw_execution_account_time ON public.raw_execution USING btree (account_id, exec_time DESC);


--
-- Name: idx_raw_execution_symbol_time; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_raw_execution_symbol_time ON public.raw_execution USING btree (symbol, exec_time DESC);


--
-- Name: idx_raw_order_account_time; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_raw_order_account_time ON public.raw_order USING btree (account_id, updated_time DESC);


--
-- Name: idx_raw_transaction_time; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_raw_transaction_time ON public.raw_transaction_log USING btree (account_id, transaction_time DESC);


--
-- Name: idx_symbol_performance_net_pnl; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_symbol_performance_net_pnl ON public.symbol_performance USING btree (account_id, net_pnl DESC);


--
-- Name: idx_sync_state_account_entity; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_sync_state_account_entity ON public.sync_state USING btree (account_id, entity);


--
-- Name: idx_sync_state_updated_at; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_sync_state_updated_at ON public.sync_state USING btree (updated_at DESC);


--
-- Name: idx_trade_group_account_direction_end; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_trade_group_account_direction_end ON public.trade_group USING btree (account_id, direction, ended_at DESC);


--
-- Name: idx_trade_group_account_end; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_trade_group_account_end ON public.trade_group USING btree (account_id, ended_at DESC);


--
-- Name: idx_trade_group_account_outcome_end; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_trade_group_account_outcome_end ON public.trade_group USING btree (account_id, outcome, ended_at DESC);


--
-- Name: idx_trade_group_account_start; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_trade_group_account_start ON public.trade_group USING btree (account_id, started_at DESC);


--
-- Name: idx_trade_group_account_symbol_end; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_trade_group_account_symbol_end ON public.trade_group USING btree (account_id, symbol, ended_at DESC);


--
-- Name: idx_trade_group_trade_key; Type: INDEX; Schema: public; Owner: trader
--

CREATE INDEX idx_trade_group_trade_key ON public.trade_group USING btree (account_id, trade_key);


--
-- Name: uq_raw_closed_pnl_dedupe; Type: INDEX; Schema: public; Owner: trader
--

CREATE UNIQUE INDEX uq_raw_closed_pnl_dedupe ON public.raw_closed_pnl USING btree (account_id, symbol, category, COALESCE(side, ''::text), COALESCE(qty, (0)::numeric), COALESCE(avg_entry_price, (0)::numeric), COALESCE(avg_exit_price, (0)::numeric), COALESCE(closed_pnl, (0)::numeric), updated_time);


--
-- Name: daily_performance daily_performance_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.daily_performance
    ADD CONSTRAINT daily_performance_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: drawdown_snapshot drawdown_snapshot_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.drawdown_snapshot
    ADD CONSTRAINT drawdown_snapshot_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: equity_snapshot equity_snapshot_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.equity_snapshot
    ADD CONSTRAINT equity_snapshot_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: raw_closed_pnl raw_closed_pnl_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_closed_pnl
    ADD CONSTRAINT raw_closed_pnl_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: raw_execution raw_execution_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_execution
    ADD CONSTRAINT raw_execution_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: raw_order raw_order_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_order
    ADD CONSTRAINT raw_order_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: raw_transaction_log raw_transaction_log_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.raw_transaction_log
    ADD CONSTRAINT raw_transaction_log_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: symbol_performance symbol_performance_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.symbol_performance
    ADD CONSTRAINT symbol_performance_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: sync_state sync_state_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.sync_state
    ADD CONSTRAINT sync_state_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- Name: trade_group trade_group_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: trader
--

ALTER TABLE ONLY public.trade_group
    ADD CONSTRAINT trade_group_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.account(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict LKuvrodfJTOHfeBQezwtGDXQBQyZAoCkFHjdWGhbfVi48KL5krKIlT38l9k12Y6

