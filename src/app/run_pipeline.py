import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

STEPS = [
    ("execution_collector", [sys.executable, str(ROOT / "src/collectors/bybit_execution_collector.py")]),
    ("order_collector", [sys.executable, str(ROOT / "src/collectors/bybit_order_collector.py")]),
    ("closed_pnl_collector", [sys.executable, str(ROOT / "src/collectors/bybit_closed_pnl_collector.py")]),
    ("equity_collector", [sys.executable, str(ROOT / "src/collectors/bybit_equity_collector.py")]),
    ("rebuild_trade_groups", [sys.executable, str(ROOT / "src/analytics/rebuild_trade_groups.py")]),
    ("rebuild_trades", [sys.executable, str(ROOT / "src/analytics/rebuild_trades.py")]),
    ("refresh_analytics", [sys.executable, str(ROOT / "src/analytics/refresh_analytics.py")]),
    ("refresh_drawdown", [sys.executable, str(ROOT / "src/analytics/refresh_drawdown.py")]),
]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def run_step(name: str, cmd: list[str]) -> None:
    print(f"\n[{utc_now()}] START {name}")
    print("CMD:", " ".join(cmd))

    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)

    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {name}, exit_code={result.returncode}")

    print(f"[{utc_now()}] DONE {name}")


def main():
    print(f"[{utc_now()}] PIPELINE START")
    for name, cmd in STEPS:
        run_step(name, cmd)
    print(f"[{utc_now()}] PIPELINE DONE")


if __name__ == "__main__":
    main()