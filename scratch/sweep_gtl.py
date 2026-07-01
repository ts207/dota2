import pandas as pd
import numpy as np
from pathlib import Path
from itertools import product
import time

from dota2bot.paper_strategy_logger import _read_parquet_dir
from dota2bot.sizing_engine import simulate_sizing
from dota2bot.statistical_report import _bool_or_none, _bootstrap_ci

def run_sweep():
    print("Loading paper positions...")
    frame = _read_parquet_dir(Path("logs/paper_positions"))
    gtl = frame[(frame["candidate_group"] == "gettoplive_candidate") & (frame["blocked_reason"].isna())].copy()
    
    for c in ["entry_ask", "pnl_per_share_2c", "edge", "fair_prob", "side_kill_mom", "book_age_ms", "game_time_sec"]:
        if c in gtl.columns:
            gtl[c] = pd.to_numeric(gtl[c], errors="coerce")
            
    # Sweep parameters
    max_asks = [0.60, 0.65, 0.70, 0.75, 0.80]
    min_moms = [1, 2, 3, 4]
    max_ages = [2, 3, 5, 10]
    min_times = [600, 900, 1200]
    
    results = []
    
    print(f"Running grid search over {len(max_asks)*len(min_moms)*len(max_ages)*len(min_times)} combinations...")
    start = time.time()
    
    for ask, mom, age, gt in product(max_asks, min_moms, max_ages, min_times):
        # Apply filters
        mask = (
            (gtl["entry_ask"] <= ask) &
            (gtl["side_kill_mom"] >= mom) &
            (gtl["book_age_ms"] <= age * 1000) &
            (gtl["game_time_sec"] >= gt)
        )
        sub = gtl[mask].copy()
        
        if sub.empty:
            continue
            
        # Simulate sizing
        sized = simulate_sizing(
            sub, 
            sizing="kill_mom_scaled", 
            bankroll=1000.0, 
            max_shares=25.0, 
            max_position_notional=100.0, 
            max_map_notional=200.0
        )
        
        settled = sized[sized["settled_win"].notna()].copy()
        if settled.empty:
            continue
            
        settled["win"] = settled["settled_win"].map(_bool_or_none)
        
        trades = len(settled)
        wins = settled["win"].sum()
        win_rate = wins / trades
        stake = settled["sim_stake"].sum()
        pnl = settled["sim_pnl_2c"].sum()
        roi = pnl / stake if stake > 0 else 0
        
        sorted_pnl = settled.sort_values("entry_received_at_ns")["sim_pnl_2c"]
        cum_pnl = sorted_pnl.cumsum()
        max_dd = (cum_pnl.cummax() - cum_pnl).max() if len(cum_pnl) > 0 else 0
        
        map_pnls = settled.groupby("map_exposure_id")["sim_pnl_2c"].sum()
        total_pnl = map_pnls.sum()
        pnl_wo_top3 = total_pnl - map_pnls.sort_values(ascending=False).head(3).sum() if len(map_pnls) > 0 else 0
        
        results.append({
            "max_ask": ask,
            "min_mom": mom,
            "max_age": age,
            "min_time": gt,
            "trades": trades,
            "win_rate": win_rate,
            "stake": stake,
            "pnl": pnl,
            "roi": roi,
            "max_dd": max_dd,
            "pnl_wo_top3": pnl_wo_top3
        })
        
    print(f"Finished in {time.time()-start:.1f}s")
    
    df = pd.DataFrame(results)
    # Sort by PnL
    df_pnl = df.sort_values("pnl", ascending=False).head(15)
    
    print("\n# Top 15 by PnL")
    for _, r in df_pnl.iterrows():
        print(f"Ask<={r['max_ask']:.2f}, Mom>={r['min_mom']}, Age<={r['max_age']}s, Time>={r['min_time']}s | "
              f"Trds: {r['trades']} | WR: {r['win_rate']*100:.1f}% | PnL: {r['pnl']:.2f} | ROI: {r['roi']*100:.1f}% | "
              f"MaxDD: {r['max_dd']:.2f} | PnL w/o Top3: {r['pnl_wo_top3']:.2f}")

    # Sort by ROI (min 10 trades)
    df_roi = df[df["trades"] >= 10].sort_values("roi", ascending=False).head(15)
    
    print("\n# Top 15 by ROI (min 10 trades)")
    for _, r in df_roi.iterrows():
        print(f"Ask<={r['max_ask']:.2f}, Mom>={r['min_mom']}, Age<={r['max_age']}s, Time>={r['min_time']}s | "
              f"Trds: {r['trades']} | WR: {r['win_rate']*100:.1f}% | PnL: {r['pnl']:.2f} | ROI: {r['roi']*100:.1f}% | "
              f"MaxDD: {r['max_dd']:.2f} | PnL w/o Top3: {r['pnl_wo_top3']:.2f}")

if __name__ == "__main__":
    run_sweep()
