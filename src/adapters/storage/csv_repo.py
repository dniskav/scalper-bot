from __future__ import annotations

from pathlib import Path
import csv
from typing import Dict, Any, Optional

from ports.storage_port import StoragePort


DATA_DIR = Path("data")
TRADES_CSV = DATA_DIR / "trades.csv"
STATE_CSV = DATA_DIR / "state.csv"


class CsvRepository(StoragePort):
    def __init__(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not TRADES_CSV.exists():
            with TRADES_CSV.open("w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "ts",
                        "exchange",
                        "market",
                        "mode",
                        "symbol",
                        "side",
                        "entry",
                        "exit",
                        "qty",
                        "notional",
                        "sl",
                        "tp",
                        "rr",
                        "pnl_abs",
                        "pnl_pct",
                        "fees",
                        "reason",
                        "risk_per_unit",
                        "is_at_breakeven",
                        "sl_origin",
                        "mfe_price",
                    ],
                )
                writer.writeheader()

    def append_trade(self, row: Dict[str, Any]) -> None:
        with TRADES_CSV.open("a", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "ts",
                    "exchange",
                    "market",
                    "mode",
                    "symbol",
                    "side",
                    "entry",
                    "exit",
                    "qty",
                    "notional",
                    "sl",
                    "tp",
                    "rr",
                    "pnl_abs",
                    "pnl_pct",
                    "fees",
                    "reason",
                    "risk_per_unit",
                    "is_at_breakeven",
                    "sl_origin",
                    "mfe_price",
                ],
            )
            writer.writerow(row)

    def write_state(self, row: Dict[str, Any]) -> None:
        with STATE_CSV.open("w", newline="") as f:
            base_fields = list(sorted(row.keys()))
            for extra in ["risk_per_unit", "is_at_breakeven", "sl_origin", "mfe_price"]:
                if extra not in base_fields:
                    base_fields.append(extra)
            writer = csv.DictWriter(f, fieldnames=base_fields)
            writer.writeheader()
            writer.writerow(row)

    def read_state(self) -> Dict[str, Any] | None:
        if not STATE_CSV.exists():
            return None
        with STATE_CSV.open("r", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                return dict(r)
        return None
