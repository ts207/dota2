import pandas as pd
from pathlib import Path
from dota2bot.paper_strategy_logger import _read_parquet_dir

def run_benchmark_analysis():
    print("Loading paper positions...")
    frame = _read_parquet_dir(Path("logs/paper_positions"))
    allowed = frame[frame["blocked_reason"].isna()].copy()
    
    # We want benchmark and gettoplive_candidate
    bench = allowed[allowed["candidate_group"] == "benchmark"].copy()
    gtl = allowed[allowed["candidate_group"] == "gettoplive_candidate"].copy()
    
    print(f"Benchmark positions: {len(bench)}")
    print(f"GetTopLive positions: {len(gtl)}")
    
    # Group by match and side
    bench_sides = bench.groupby(["map_exposure_id", "side"]).size().reset_index(name="bench_count")
    gtl_sides = gtl.groupby(["map_exposure_id", "side"]).size().reset_index(name="gtl_count")
    
    # Merge to find same-side overlap and unique
    same_side = pd.merge(bench_sides, gtl_sides, on=["map_exposure_id", "side"], how="inner")
    print(f"Same-side overlap maps: {len(same_side)}")
    
    # Opposite side conflicts
    # same map_exposure_id, different side
    gtl_opp = gtl_sides.copy()
    gtl_opp["opp_side"] = gtl_opp["side"].apply(lambda x: "radiant" if x == "dire" else "dire")
    opp_side = pd.merge(bench_sides, gtl_opp, left_on=["map_exposure_id", "side"], right_on=["map_exposure_id", "opp_side"], how="inner")
    print(f"Opposite-side conflict maps: {len(opp_side)}")
    
    # Calculate PnL for benchmark
    # We will compute PnL at flat_1
    from dota2bot.sizing_engine import simulate_sizing
    bench = simulate_sizing(bench, sizing="flat_1", bankroll=1000.0, max_shares=25.0)
    bench = bench[bench["settled_win"].notna()].copy()
    
    # Mark benchmark rows based on overlap
    # We need to map each benchmark row to whether it overlaps with gettoplive
    bench["has_same_side_gtl"] = bench.apply(lambda r: not same_side[(same_side["map_exposure_id"] == r["map_exposure_id"]) & (same_side["side"] == r["side"])].empty, axis=1)
    
    unique_bench = bench[~bench["has_same_side_gtl"]]
    overlap_bench = bench[bench["has_same_side_gtl"]]
    
    print("\n# Benchmark PnL breakdown (flat_1)")
    print(f"Total Benchmark PnL: {bench['sim_pnl_2c'].sum():.2f} ({len(bench)} trades)")
    print(f"Unique Benchmark PnL: {unique_bench['sim_pnl_2c'].sum():.2f} ({len(unique_bench)} trades)")
    print(f"Overlapping Benchmark PnL: {overlap_bench['sim_pnl_2c'].sum():.2f} ({len(overlap_bench)} trades)")
    
    # Let's check GTL performance filtered by Benchmark
    gtl_sized = simulate_sizing(gtl, sizing="kill_mom_scaled", bankroll=1000.0, max_shares=25.0, max_map_notional=200.0)
    gtl_sized = gtl_sized[gtl_sized["settled_win"].notna()].copy()
    gtl_sized["has_bench_confirm"] = gtl_sized.apply(lambda r: not same_side[(same_side["map_exposure_id"] == r["map_exposure_id"]) & (same_side["side"] == r["side"])].empty, axis=1)
    
    unique_gtl = gtl_sized[~gtl_sized["has_bench_confirm"]]
    overlap_gtl = gtl_sized[gtl_sized["has_bench_confirm"]]
    
    print("\n# GetTopLive PnL breakdown (kill_mom_scaled)")
    print(f"Total GTL PnL: {gtl_sized['sim_pnl_2c'].sum():.2f} ({len(gtl_sized)} trades)")
    print(f"GTL w/ Benchmark Confirmation: {overlap_gtl['sim_pnl_2c'].sum():.2f} ({len(overlap_gtl)} trades)")
    print(f"GTL w/o Benchmark Confirmation: {unique_gtl['sim_pnl_2c'].sum():.2f} ({len(unique_gtl)} trades)")

if __name__ == "__main__":
    run_benchmark_analysis()
