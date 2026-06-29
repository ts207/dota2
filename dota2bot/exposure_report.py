from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .exposure_manager import ExposureManager, DEFAULT_LIMITS
from .paper_strategy_logger import _read_parquet_dir
from .strategy_contract import ACTIVE_SETTLED_PAPER_DECISIONS_NAME

def _print_table(df: pd.DataFrame) -> None:
    if df.empty:
        print("*No data*")
        return
    print(f"| {' | '.join(df.columns)} |")
    print(f"| {' | '.join(['---'] * len(df.columns))} |")
    for row in df.itertuples(index=False):
        print(f"| {' | '.join(str(x) for x in row)} |")
    print()


def run_exposure_report(*, logs_root: Path = Path("logs"), input_name: str = ACTIVE_SETTLED_PAPER_DECISIONS_NAME) -> None:
    input_dir = logs_root / input_name
    if not input_dir.exists():
        print(f"Directory {input_dir} not found.")
        return

    frame = _read_parquet_dir(input_dir)
    if frame.empty:
        print("No data in ledger.")
        return

    print("# Exposure Report\n")

    signals = frame[frame["signal"].fillna(False).astype(bool)].copy()
    if signals.empty:
        print("No signals found.")
        return
        
    print(f"- raw signal rows: {len(signals)}")
    
    signals["map_exposure_id"] = signals.apply(lambda row: f"{row.get('match_id', '')}::{row.get('current_game_number', 1)}", axis=1)
    unique_maps = signals["map_exposure_id"].nunique()
    print(f"- unique map exposures: {unique_maps}")
    
    manager = ExposureManager()
    positions = manager.process_decisions(signals)
    
    allowed = positions[positions["blocked_reason"].isna()]
    blocked = positions[~positions["blocked_reason"].isna()]
    
    print(f"- allowed positions: {len(allowed)}")
    print(f"- blocked repeated signals: {len(blocked)}")
    
    if not blocked.empty:
        max_repeats = blocked.groupby("map_exposure_id").size().max()
        print(f"- max repeated signals per map: {max_repeats}")
    else:
        print("- max repeated signals per map: 0")
        
    print("\n## PnL under different Caps\n")
    
    caps = [1, 2, 3, 5, 9999]
    cap_results = []
    
    for cap in caps:
        mod_limits = {}
        for k, v in DEFAULT_LIMITS.items():
            if v.max_entries_per_map == 0:
                mod_limits[k] = v
            elif cap == 9999:
                mod_limits[k] = replace(v, max_entries_per_map=9999, max_total_shares_per_map=9999.0, max_total_notional_per_map=99999.0, min_seconds_between_entries=0)
            else:
                mod_limits[k] = replace(v, max_entries_per_map=cap, max_total_shares_per_map=float(cap))
            
        mgr = ExposureManager(limits=mod_limits)
        pos = mgr.process_decisions(signals)
        pos_allowed = pos[pos["blocked_reason"].isna()]
        
        settled = pos_allowed[pos_allowed["settled_win"].notna()]
        pnl = settled["position_pnl_2c"].sum() if not settled.empty else 0.0
        
        cap_label = str(cap) if cap != 9999 else "machine-gun"
        cap_results.append({
            "cap": cap_label,
            "allowed_positions": len(pos_allowed),
            "settled": len(settled),
            "pnl_2c": f"{pnl:+.4f}"
        })
        
    df_caps = pd.DataFrame(cap_results)
    _print_table(df_caps)
    
    print("## Map Exposure Extremes (Machine-Gun)\n")
    
    mgr_mg = ExposureManager(limits={k: replace(v, max_entries_per_map=9999, max_total_shares_per_map=9999.0, max_total_notional_per_map=99999.0, min_seconds_between_entries=0) for k, v in DEFAULT_LIMITS.items()})
    pos_mg = mgr_mg.process_decisions(signals)
    pos_mg_allowed = pos_mg[pos_mg["blocked_reason"].isna()]
    pos_mg_settled = pos_mg_allowed[pos_mg_allowed["settled_win"].notna()]
    
    if not pos_mg_settled.empty:
        map_pnl = pos_mg_settled.groupby(["map_exposure_id", "strategy_name"])["position_pnl_2c"].sum().reset_index()
        map_pnl = map_pnl.sort_values("position_pnl_2c")
        
        worst = map_pnl.head(3)
        best = map_pnl.tail(3).sort_values("position_pnl_2c", ascending=False)
        
        print("### Largest Losing Exposures\n")
        _print_table(worst)
        
        print("### Largest Winning Exposures\n")
        _print_table(best)


def add_exposure_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--input-name", type=str, default=ACTIVE_SETTLED_PAPER_DECISIONS_NAME)


def main() -> None:
    parser = argparse.ArgumentParser()
    add_exposure_report_args(parser)
    args = parser.parse_args()
    
    run_exposure_report(
        logs_root=args.logs_root,
        input_name=args.input_name,
    )


if __name__ == "__main__":
    main()
