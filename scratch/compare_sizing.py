import pandas as pd
from pathlib import Path
from dota2bot.statistical_report import run_statistical_report_for_sizing
from dota2bot.paper_strategy_logger import _read_parquet_dir

def aggregate_sizing_run(frame, source, sizing):
    from dota2bot.sizing_engine import simulate_sizing
    from dota2bot.statistical_report import _bool_or_none, _bootstrap_ci
    import numpy as np
    
    allowed = frame[frame["blocked_reason"].isna()].copy()
    if source == "active":
        allowed = allowed[allowed["candidate_group"].isin(["primary", "gettoplive_candidate"])]
    elif source == "gettoplive":
        allowed = allowed[allowed["candidate_group"] == "gettoplive_candidate"]
        
    for c in ["entry_ask", "pnl_per_share_2c", "edge", "fair_prob", "side_kill_mom", "book_age_ms", "game_time_sec"]:
        if c in allowed.columns:
            allowed[c] = pd.to_numeric(allowed[c], errors="coerce")
            
    allowed = simulate_sizing(allowed, sizing, bankroll=1000.0, max_shares=25.0, max_position_notional=100.0, max_map_notional=200.0)
    settled = allowed[allowed["settled_win"].notna()].copy()
    settled["win"] = settled["settled_win"].map(_bool_or_none)
    
    # Overall metrics
    trades = len(settled)
    maps = settled["map_exposure_id"].nunique()
    stake = settled["sim_stake"].sum()
    pnl = settled["sim_pnl_2c"].sum()
    roi = pnl / stake if stake > 0 else 0
    
    # max dd
    sorted_pnl = settled.sort_values("entry_received_at_ns")["sim_pnl_2c"]
    cum_pnl = sorted_pnl.cumsum()
    max_dd = (cum_pnl.cummax() - cum_pnl).max() if len(cum_pnl) > 0 else 0
    
    worst_pos = sorted_pnl.min() if len(sorted_pnl) > 0 else 0
    
    map_pnls = settled.groupby("map_exposure_id")["sim_pnl_2c"].sum()
    _, _, map_p_pos = _bootstrap_ci(map_pnls.values, 1000, 42)
    
    map_pnls_sorted = map_pnls.sort_values(ascending=False)
    pnl_wo_best = pnl - map_pnls_sorted.max() if len(map_pnls_sorted) > 0 else 0
    pnl_wo_top3 = pnl - map_pnls_sorted.head(3).sum() if len(map_pnls_sorted) > 0 else 0
    
    top1_pct = map_pnls_sorted.max() / pnl if pnl > 0 else 0
    top3_pct = map_pnls_sorted.head(3).sum() / pnl if pnl > 0 else 0
    
    return {
        "Config": f"{source} {sizing}",
        "Positions": trades,
        "Maps": maps,
        "Stake": f"{stake:.1f}",
        "PnL 2c": f"{pnl:.2f}",
        "ROI": f"{roi*100:.1f}%",
        "Max DD": f"{max_dd:.2f}",
        "Worst Pos": f"{worst_pos:.2f}",
        "Map P(>0)": f"{map_p_pos*100:.1f}%",
        "PnL w/o Best": f"{pnl_wo_best:.2f}",
        "PnL w/o Top3": f"{pnl_wo_top3:.2f}",
        "Top1 %": f"{top1_pct*100:.1f}%",
        "Top3 %": f"{top3_pct*100:.1f}%"
    }

frame = _read_parquet_dir(Path("logs/paper_positions"))
configs = [
    ("active", "flat_1"),
    ("active", "conservative_group_default"),
    ("active", "group_specific_default"),
    ("gettoplive", "kill_mom_scaled"),
]

rows = []
for source, sizing in configs:
    rows.append(aggregate_sizing_run(frame, source, sizing))

df = pd.DataFrame(rows)
print("| " + " | ".join(df.columns) + " |")
print("| " + " | ".join(["---"] * len(df.columns)) + " |")
for _, row in df.iterrows():
    print("| " + " | ".join(str(val) for val in row.values) + " |")
