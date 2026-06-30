import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from dota2bot.paper_strategy_logger import (
    EXECUTABLE_BACKTEST_PATH, 
    HISTORICAL_RESEARCH_ELIGIBILITY_MODE,
    score_paper_decisions,
    load_paper_model_bundle,
)
from dota2bot.gettoplive_markout_report import prepare_paper_feature_frame

def _format_pct(val) -> str:
    if pd.isna(val) or np.isinf(val): return "N/A"
    return f"{val * 100:.1f}%"

def _format_num(val) -> str:
    if pd.isna(val) or np.isinf(val): return "N/A"
    return f"{val:.2f}"

def _print_table(df: pd.DataFrame):
    print("| " + " | ".join(df.columns) + " |")
    print("| " + " | ".join(["---"] * len(df.columns)) + " |")
    for _, row in df.iterrows():
        print("| " + " | ".join(str(val) for val in row.values) + " |")
    print()

def run_reversal_report(logs_root: Path, format_type: str = "markdown"):
    print("Loading historical backtest snapshots...")
    rows = pd.read_parquet(EXECUTABLE_BACKTEST_PATH)
    
    print("Computing features...")
    frame = prepare_paper_feature_frame(rows, eligibility_mode=HISTORICAL_RESEARCH_ELIGIBILITY_MODE)
    
    # Run active models to find overlap
    print("Computing active strategy overlap...")
    bundle = load_paper_model_bundle()
    active_decisions_list = score_paper_decisions(rows, bundle, eligibility_mode=HISTORICAL_RESEARCH_ELIGIBILITY_MODE)
    active_df = pd.DataFrame(active_decisions_list)
    active_signals = active_df[active_df["signal"] == True]
    
    active_groups = active_signals.groupby(["match_id", "canonical_exposure_id", "side"]).agg(
        is_active=("signal", "any"),
        has_primary=("candidate_group", lambda g: (g == "primary").any()),
        has_gtl=("candidate_group", lambda g: (g == "gettoplive_candidate").any())
    ).reset_index()

    # Base Universe filter
    df = frame[
        (frame["tradable_research"] == True) &
        (frame["book_best_ask"].between(0.20, 0.60)) &
        (frame["game_time_sec"] >= 900)
    ].copy()
    
    if "book_age_s" in df.columns:
        df = df[df["book_age_s"] <= 10]
        
    print(f"Base universe rows: {len(df)}")
    
    df["side_lead_lag_300"] = df["side_nw"] - df["side_mom_300"]
    df["nw_recovery_300"] = df["side_mom_300"]
    df["recovery_ratio_300"] = np.where(
        df["side_lead_lag_300"] < 0,
        df["nw_recovery_300"] / df["side_lead_lag_300"].abs(),
        0.0
    )
    
    if "label_settled_win" in df.columns:
        df["settled_win"] = df["label_settled_win"]
    elif "settled_win" not in df.columns:
        df["settled_win"] = False
        
    df["pnl_2c"] = np.where(df["settled_win"], 1 - df["book_best_ask"] - 0.02, -df["book_best_ask"] - 0.02)
    
    # Merge active overlap
    df = df.merge(active_groups, on=["match_id", "canonical_exposure_id", "side"], how="left")
    df["is_active"] = df["is_active"].fillna(False)
    df["has_primary"] = df["has_primary"].fillna(False)
    df["has_gtl"] = df["has_gtl"].fillna(False)
    
    # We will define REVERSAL_CATCHUP_VALUE_V1
    v1_mask = (
        (df["side_lead_lag_300"] <= -5000) &
        (df["nw_recovery_300"] >= 2500) &
        (df["recovery_ratio_300"] >= 0.35) &
        (df["ask_delta_300"] <= 0.10) &
        (df["side_mom_100"] >= 0) &
        (df["game_time_sec"] >= 900) &
        (df["book_best_ask"].between(0.20, 0.50))
    )
    
    candidates = {
        "REVERSAL_CATCHUP_VALUE_V1": df[v1_mask].sort_values("received_at_ns").drop_duplicates(subset=["match_id", "canonical_exposure_id", "side"], keep="first")
    }
    
    main_rows = []
    overlap_rows = []
    
    for c_name, c_df in candidates.items():
        trades = len(c_df)
        if trades == 0: continue
        wins = c_df["settled_win"].sum()
        win_pct = wins / trades
        avg_ask = c_df["book_best_ask"].mean()
        avg_rec = c_df["nw_recovery_300"].mean()
        avg_ask_delta = c_df["ask_delta_300"].mean()
        pnl_2c = c_df["pnl_2c"].sum()
        roi = pnl_2c / trades
        
        # Max DD and Worst position
        sorted_pnl = c_df.sort_values("received_at_ns")["pnl_2c"]
        cum_pnl = sorted_pnl.cumsum()
        max_dd = (cum_pnl.cummax() - cum_pnl).max()
        worst = sorted_pnl.min()
        
        main_rows.append({
            "candidate": c_name,
            "trades": trades,
            "settled": trades,
            "win": _format_pct(win_pct),
            "avg ask": f"{avg_ask:.3f}",
            "avg recovery": f"{avg_rec:.0f}",
            "avg ask_delta": f"{avg_ask_delta:.3f}",
            "pnl 2c": f"{pnl_2c:.2f}",
            "ROI": _format_pct(roi),
            "max DD": f"{max_dd:.2f}",
            "worst": f"{worst:.2f}"
        })
        
        overlap_active = c_df["is_active"].sum()
        overlap_gtl = c_df["has_gtl"].sum()
        overlap_primary = c_df["has_primary"].sum()
        unique = trades - overlap_active
        
        overlap_rows.append({
            "candidate": c_name,
            "trades": trades,
            "overlap active": f"{overlap_active} ({_format_pct(overlap_active/trades)})",
            "unique trades": unique,
            "overlap gettoplive": overlap_gtl,
            "overlap primary": overlap_primary
        })
        
    print("\n# Reversal Research Report\n")
    print("## Main Summary\n")
    if main_rows:
        _print_table(pd.DataFrame(main_rows))
        
    print("## Overlap with Active Strategies\n")
    if overlap_rows:
        _print_table(pd.DataFrame(overlap_rows))
        
    print("## Failure Modes\n")
    print("""
fake comeback:
  recovered, then lost
late obvious comeback:
  ask already repriced
stale data:
  source age too high
overlap:
  already caught by active strategy
""")

    if len(candidates["REVERSAL_CATCHUP_VALUE_V1"]) > 0:
        v1_df = candidates["REVERSAL_CATCHUP_VALUE_V1"]
        print("## Concentration\n")
        map_pnls = v1_df.groupby("match_id")["pnl_2c"].sum()
        map_stakes = v1_df.groupby("match_id").size()
        largest_losing = map_pnls.min()
        largest_winning = map_pnls.max()
        total_pnl = map_pnls.sum()
        total_stake = map_stakes.sum()
        top3_pnl_pct = map_pnls.sort_values(ascending=False).head(3).sum() / total_pnl if total_pnl > 0 else 0
        top3_stake_pct = map_stakes.sort_values(ascending=False).head(3).sum() / total_stake if total_stake > 0 else 0
        
        conc_df = pd.DataFrame([{
            "candidate": "REVERSAL_CATCHUP_VALUE_V1",
            "largest losing map": f"{largest_losing:.2f}",
            "largest winning map": f"{largest_winning:.2f}",
            "top 3 maps % of PnL": _format_pct(top3_pnl_pct),
            "top 3 maps % of stake": _format_pct(top3_stake_pct)
        }])
        _print_table(conc_df)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--format", type=str, default="markdown")
    args = parser.parse_args()
    run_reversal_report(args.logs_root, args.format)
