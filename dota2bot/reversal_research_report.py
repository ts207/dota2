import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from itertools import product

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
    if df.empty:
        return
    print("| " + " | ".join(df.columns) + " |")
    print("| " + " | ".join(["---"] * len(df.columns)) + " |")
    for _, row in df.iterrows():
        print("| " + " | ".join(str(val) for val in row.values) + " |")
    print()

def run_reversal_report(logs_root: Path, format_type: str = "markdown"):
    print("Loading historical backtest snapshots...")
    if not EXECUTABLE_BACKTEST_PATH.exists():
        print(f"Path not found: {EXECUTABLE_BACKTEST_PATH}")
        return
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
    
    # Build actual lag features with 60s tolerance
    df["target_time_300"] = df["received_at_ns"] - 300_000_000_000
    df = df.sort_values("target_time_300")
    
    df_past = df[["received_at_ns", "canonical_exposure_id", "side", "side_nw", "book_best_ask"]].copy()
    df_past = df_past.sort_values("received_at_ns")
    
    df = pd.merge_asof(
        df, df_past,
        left_on="target_time_300",
        right_on="received_at_ns",
        by=["canonical_exposure_id", "side"],
        direction="backward",
        tolerance=60_000_000_000,
        suffixes=("", "_lag_300")
    )
    
    # Require a valid lag row
    df = df[df["received_at_ns_lag_300"].notna()].copy()
    
    # Calculate recovery metrics based on actual lag
    df["side_lead_lag_300"] = df["side_nw_lag_300"]
    df["lead_recovery_300"] = df["side_nw"] - df["side_nw_lag_300"]
    df["ask_delta_300"] = df["book_best_ask"] - df["book_best_ask_lag_300"]
    
    df["recovery_ratio_300"] = np.where(
        (df["side_lead_lag_300"] < 0) & (df["side_lead_lag_300"].notna()),
        df["lead_recovery_300"] / df["side_lead_lag_300"].abs(),
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
    
    candidates = {}
    
    # Grid search for candidates
    # prior deficit, recovery, ask delta, ask range, game time, momentum confirmation
    deficits = [-4000, -5000, -6000]
    recoveries = [2000, 2500, 3000]
    ask_deltas = [0.10, 0.15]
    
    for d, r, ad in product(deficits, recoveries, ask_deltas):
        name = f"V_{d}_{r}_{ad}"
        mask = (
            (df["side_lead_lag_300"] <= d) &
            (df["lead_recovery_300"] >= r) &
            (df["recovery_ratio_300"] >= 0.35) &
            (df["ask_delta_300"] <= ad) &
            (df["side_mom_100"] >= 0) &
            (df["game_time_sec"] >= 900) &
            (df["book_best_ask"].between(0.20, 0.50))
        )
        cand_df = df[mask].sort_values("received_at_ns").drop_duplicates(subset=["canonical_exposure_id", "side"], keep="first")
        candidates[name] = cand_df
    
    main_rows = []
    overlap_rows = []
    
    for c_name, c_df in candidates.items():
        trades = len(c_df)
        if trades == 0: continue
        wins = c_df["settled_win"].sum()
        win_pct = wins / trades
        avg_ask = c_df["book_best_ask"].mean()
        avg_rec = c_df["lead_recovery_300"].mean()
        avg_ask_delta = c_df["ask_delta_300"].mean()
        pnl_2c = c_df["pnl_2c"].sum()
        
        # Stake-based ROI
        stake = c_df["book_best_ask"].sum()
        roi = pnl_2c / stake if stake > 0 else 0
        
        # Max DD and Worst position
        sorted_pnl = c_df.sort_values("received_at_ns")["pnl_2c"]
        cum_pnl = sorted_pnl.cumsum()
        max_dd = (cum_pnl.cummax() - cum_pnl).max() if len(cum_pnl) > 0 else 0
        worst = sorted_pnl.min() if len(sorted_pnl) > 0 else 0
        
        # Top map removal
        map_pnls = c_df.groupby("canonical_exposure_id")["pnl_2c"].sum()
        total_pnl = map_pnls.sum()
        pnl_wo_top3 = total_pnl - map_pnls.sort_values(ascending=False).head(3).sum() if len(map_pnls) > 0 else 0
        
        main_rows.append({
            "candidate": c_name,
            "trades": trades,
            "win_num": win_pct,
            "avg_ask_num": avg_ask,
            "avg_rec_num": avg_rec,
            "avg_ask_delta_num": avg_ask_delta,
            "pnl_2c_num": pnl_2c,
            "roi_num": roi,
            "max_dd_num": max_dd,
            "pnl_wo_top3_num": pnl_wo_top3,
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
        # Sort numerically before formatting
        main_df = pd.DataFrame(main_rows).sort_values("pnl_2c_num", ascending=False)
        
        formatted_main = pd.DataFrame()
        formatted_main["candidate"] = main_df["candidate"]
        formatted_main["trades"] = main_df["trades"]
        formatted_main["win"] = main_df["win_num"].apply(_format_pct)
        formatted_main["avg ask"] = main_df["avg_ask_num"].apply(lambda x: f"{x:.3f}")
        formatted_main["avg recovery"] = main_df["avg_rec_num"].apply(lambda x: f"{x:.0f}")
        formatted_main["avg ask_delta"] = main_df["avg_ask_delta_num"].apply(lambda x: f"{x:.3f}")
        formatted_main["pnl 2c"] = main_df["pnl_2c_num"].apply(lambda x: f"{x:.2f}")
        formatted_main["ROI"] = main_df["roi_num"].apply(_format_pct)
        formatted_main["max DD"] = main_df["max_dd_num"].apply(lambda x: f"{x:.2f}")
        formatted_main["pnl w/o top3"] = main_df["pnl_wo_top3_num"].apply(lambda x: f"{x:.2f}")
        
        _print_table(formatted_main)
        
        best_cand = formatted_main.iloc[0]["candidate"]
    else:
        best_cand = None
        
    print("## Overlap with Active Strategies\n")
    if overlap_rows:
        _print_table(pd.DataFrame(overlap_rows))
        
    if best_cand:
        print(f"## Concentration for Best Candidate ({best_cand})\n")
        c_df = candidates[best_cand]
        map_pnls = c_df.groupby("canonical_exposure_id")["pnl_2c"].sum()
        map_stakes = c_df.groupby("canonical_exposure_id").size()
        largest_losing = map_pnls.min() if len(map_pnls) > 0 else 0
        largest_winning = map_pnls.max() if len(map_pnls) > 0 else 0
        total_pnl = map_pnls.sum()
        total_stake = map_stakes.sum()
        top3_pnl_pct = map_pnls.sort_values(ascending=False).head(3).sum() / total_pnl if total_pnl > 0 else 0
        top3_stake_pct = map_stakes.sort_values(ascending=False).head(3).sum() / total_stake if total_stake > 0 else 0
        
        conc_df = pd.DataFrame([{
            "candidate": best_cand,
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
