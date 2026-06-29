from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from .exposure_manager import ExposureManager
from .logging_store import ParquetAppendLog
from .paper_strategy_logger import _read_parquet_dir
from .strategy_contract import ACTIVE_PAPER_DECISIONS_NAME, ACTIVE_SETTLED_PAPER_DECISIONS_NAME

POSITION_COLUMNS = [
    "position_id",
    "decision_id",
    "strategy_name",
    "model_name",
    "candidate_group",
    "match_id",
    "current_game_number",
    "map_exposure_id",
    "token_id",
    "side",
    "entry_received_at_ns",
    "entry_ask",
    "shares",
    "notional",
    "exposure_count_for_map",
    "blocked_reason",
    "settled_win",
    "pnl_per_share_2c",
    "position_pnl_2c",
]

def run_paper_positions(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = ACTIVE_SETTLED_PAPER_DECISIONS_NAME,
    output_name: str = "paper_positions",
    batch_rows: int = 5000,
    mode: str = "rebuild",
) -> dict[str, Any]:
    input_dir = logs_root / input_name
    output_dir = logs_root / output_name
    
    manager = ExposureManager()
    
    if mode == "append" and output_dir.exists():
        existing_pos = _read_parquet_dir(output_dir)
        manager.load_state(existing_pos)
        min_ns = None
        if not existing_pos.empty and "entry_received_at_ns" in existing_pos.columns:
            max_ns = existing_pos["entry_received_at_ns"].dropna().max()
            if pd.notna(max_ns):
                min_ns = int(max_ns)
        
        frame = _read_parquet_dir(input_dir, min_received_at_ns=min_ns)
    else:
        if mode == "rebuild" and output_dir.exists():
            import shutil
            shutil.rmtree(output_dir)
        frame = _read_parquet_dir(input_dir)
        existing_pos = pd.DataFrame(columns=POSITION_COLUMNS)

    if frame.empty:
        return {
            "input_rows": 0,
            "position_rows": 0,
            "allowed_positions": 0,
            "blocked_positions": 0,
        }
        
    positions = manager.process_decisions(frame)
    
    if positions.empty:
         return {
            "input_rows": len(frame),
            "position_rows": 0,
            "allowed_positions": 0,
            "blocked_positions": 0,
        }
        
    if mode == "append" and not existing_pos.empty:
        positions = positions[~positions["position_id"].isin(existing_pos["position_id"])].copy()
        
    if positions.empty:
        return {
            "input_rows": len(frame),
            "position_rows": 0,
            "allowed_positions": 0,
            "blocked_positions": 0,
        }

    log = ParquetAppendLog(logs_root, output_name, POSITION_COLUMNS, batch_rows=batch_rows)
    log.extend(positions.to_dict(orient="records"))
    log.flush()
    
    allowed = int(positions["blocked_reason"].isna().sum())
    
    return {
        "input_rows": len(frame),
        "position_rows": len(positions),
        "allowed_positions": allowed,
        "blocked_positions": len(positions) - allowed,
    }

def run_paper_positions_loop(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = ACTIVE_SETTLED_PAPER_DECISIONS_NAME,
    output_name: str = "paper_positions",
    batch_rows: int = 5000,
    mode: str = "rebuild",
    interval_sec: float = 300.0,
) -> None:
    import time
    while True:
        try:
            res = run_paper_positions(
                logs_root=logs_root,
                input_name=input_name,
                output_name=output_name,
                batch_rows=batch_rows,
                mode=mode,
            )
            print(res, flush=True)
        except Exception as e:
            print(f"Error in paper_positions_loop: {e}", flush=True)
        time.sleep(interval_sec)

def add_paper_position_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--input-name", type=str, default=ACTIVE_SETTLED_PAPER_DECISIONS_NAME)
    parser.add_argument("--output-name", type=str, default="paper_positions")
    parser.add_argument("--mode", type=str, choices=["rebuild", "append"], default="rebuild")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=300.0)
    
def main() -> None:
    parser = argparse.ArgumentParser()
    add_paper_position_args(parser)
    args = parser.parse_args()
    
    res = run_paper_positions(
        logs_root=args.logs_root,
        input_name=args.input_name,
        output_name=args.output_name,
        mode=args.mode,
    )
    for k, v in res.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()
