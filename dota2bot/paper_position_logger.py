from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from .exposure_manager import ExposureManager
from .paper_strategy_logger import (
    DEFAULT_INPUT_NAME,
    DEFAULT_MODEL_ARTIFACT_DIR,
    _read_parquet_dir,
)
from .run_loop import run_supervisor
from .utils.duckdb_utils import ParquetAppendLog

POSITION_COLUMNS = [
    "position_id",
    "decision_id",
    "strategy_name",
    "model_name",
    "candidate_group",
    "match_id",
    "current_game_number",
    "canonical_exposure_id",
    "token_id",
    "side",
    "entry_received_at_ns",
    "entry_ask",
    "shares",
    "notional",
    "exposure_count_for_map",
    "blocked_reason",
    "settled_win",
    "pnl_2c",
]

def run_paper_positions(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = "paper_validation_decisions",
    output_name: str = "paper_positions",
    batch_rows: int = 5000,
    limit: int | None = None,
    min_received_at_ns: int | None = None,
) -> dict[str, Any]:
    # Determine the actual input directory by finding the latest decisions hash
    # Or expect the caller to provide the exact input_name
    input_dir = logs_root / input_name
    
    # Read the decision ledger
    # Note: For stateful exposure manager, we really should read from the beginning
    # to maintain proper map_exposure counts, or at least read the last 24h.
    # For now, we read what is requested.
    frame = _read_parquet_dir(input_dir, min_received_at_ns=min_received_at_ns)
    if limit is not None:
        frame = frame.tail(limit).copy()
        
    if frame.empty:
        return {
            "input_rows": 0,
            "position_rows": 0,
            "allowed_positions": 0,
            "blocked_positions": 0,
        }
        
    manager = ExposureManager()
    positions = manager.process_decisions(frame)
    
    if positions.empty:
         return {
            "input_rows": len(frame),
            "position_rows": 0,
            "allowed_positions": 0,
            "blocked_positions": 0,
        }
        
    # We always rewrite or append?
    # Since state depends on history, rebuilding the positions ledger from scratch is safest
    # when rules change. But for live running, appending is better.
    # We'll just use ParquetAppendLog
    log = ParquetAppendLog(logs_root, output_name, POSITION_COLUMNS, batch_rows=batch_rows)
    # We should deduplicate against existing position_ids or decision_ids if appending.
    # For simplicity in this script, we'll assume we process and append.
    
    log.extend(positions.to_dict(orient="records"))
    log.flush()
    
    allowed = int(positions["blocked_reason"].isna().sum())
    
    return {
        "input_rows": len(frame),
        "position_rows": len(positions),
        "allowed_positions": allowed,
        "blocked_positions": len(positions) - allowed,
    }

def add_paper_position_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--input-name", type=str, default="paper_validation_decisions")
    parser.add_argument("--output-name", type=str, default="paper_positions")
    
def main() -> None:
    parser = argparse.ArgumentParser()
    add_paper_position_args(parser)
    args = parser.parse_args()
    
    res = run_paper_positions(
        logs_root=args.logs_root,
        input_name=args.input_name,
        output_name=args.output_name,
    )
    for k, v in res.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
