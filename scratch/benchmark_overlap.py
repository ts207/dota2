import pandas as pd
from pathlib import Path
from dota2bot.paper_strategy_logger import _read_parquet_dir

def run_benchmark_analysis():
    print("Loading paper positions...")
    frame = _read_parquet_dir(Path("logs/paper_positions"))
    allowed = frame[frame["blocked_reason"].isna()].copy()
    
    bench = allowed[allowed["candidate_group"] == "benchmark"].copy()
    gtl = allowed[allowed["candidate_group"] == "gettoplive_candidate"].copy()
    
    print(f"Benchmark positions: {len(bench)}")
    print(f"GetTopLive positions: {len(gtl)}")
    
    # Time-valid overlap
    # benchmark signal timestamp <= GetTopLive signal timestamp
    # benchmark signal timestamp >= GetTopLive signal timestamp - confirmation_window
    windows = [30, 60, 120, 300, 10000000] # 10000000 is "anytime"
    
    gtl_sized = None
    from dota2bot.sizing_engine import simulate_sizing
    gtl_sized = simulate_sizing(gtl, sizing="kill_mom_scaled", bankroll=1000.0, max_shares=25.0, max_map_notional=200.0)
    gtl_sized = gtl_sized[gtl_sized["settled_win"].notna()].copy()
    
    print("\n# GetTopLive PnL breakdown (kill_mom_scaled)")
    print(f"Total GTL PnL: {gtl_sized['sim_pnl_2c'].sum():.2f} ({len(gtl_sized)} trades)")
    
    bench_sub = bench[["map_exposure_id", "side", "entry_received_at_ns"]].copy()
    gtl_sub = gtl_sized[["map_exposure_id", "side", "entry_received_at_ns", "sim_pnl_2c"]].copy()
    bench_sub["entry_received_at_ns"] = pd.to_numeric(bench_sub["entry_received_at_ns"], errors="coerce")
    gtl_sub["entry_received_at_ns"] = pd.to_numeric(gtl_sub["entry_received_at_ns"], errors="coerce")

    
    for w in windows:
        # Cross join on map_exposure_id and side
        merged = pd.merge(gtl_sub, bench_sub, on=["map_exposure_id", "side"], suffixes=("", "_bench"))
        
        if w < 10000000:
            mask = (merged["entry_received_at_ns_bench"] <= merged["entry_received_at_ns"]) & \
                   (merged["entry_received_at_ns_bench"] >= merged["entry_received_at_ns"] - w * 1e9)
        else:
            mask = pd.Series(True, index=merged.index)
            
        valid_bench = merged[mask]
        confirmed_maps = valid_bench[["map_exposure_id", "side"]].drop_duplicates()
        
        # Mark GTL
        gtl_confirmed = pd.merge(gtl_sized, confirmed_maps, on=["map_exposure_id", "side"], how="inner")
        
        pnl = gtl_confirmed["sim_pnl_2c"].sum()
        trades = len(gtl_confirmed)
        
        window_str = f"{w}s" if w < 10000000 else "anytime"
        print(f"Window {window_str:7} | Confirmed PnL: {pnl:6.2f} | Trades: {trades:2} | "
              f"Remaining PnL: {gtl_sized['sim_pnl_2c'].sum() - pnl:6.2f}")

if __name__ == "__main__":
    run_benchmark_analysis()
