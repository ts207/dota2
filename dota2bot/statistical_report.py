import argparse
import json
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np

from .paper_strategy_logger import _read_parquet_dir

def _print_table(df: pd.DataFrame) -> None:
    if df.empty:
        print("*No data*")
        return
    print(f"| {' | '.join(df.columns)} |")
    print(f"| {' | '.join(['---'] * len(df.columns))} |")
    for row in df.itertuples(index=False):
        print(f"| {' | '.join(str(x) for x in row)} |")
    print()

def _bool_or_none(x):
    if pd.isna(x): return None
    return bool(x)

def _bootstrap_ci(data: np.ndarray, samples: int = 5000) -> tuple[float, float, float]:
    if len(data) == 0:
        return 0.0, 0.0, 0.0
    boot_sums = np.random.choice(data, size=(samples, len(data)), replace=True).sum(axis=1)
    return np.percentile(boot_sums, 5), np.percentile(boot_sums, 95), (boot_sums > 0).mean()

def run_statistical_report(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = "paper_positions",
    source: str = "active",
    sizing: str = "flat_1",
    bootstrap_samples: int = 5000,
    output_format: str = "markdown",
) -> None:
    input_dir = logs_root / input_name
    if not input_dir.exists():
        print(f"Directory {input_dir} not found.")
        return

    frame = _read_parquet_dir(input_dir)
    if frame.empty:
        print("No positions found.")
        return

    allowed = frame[frame["blocked_reason"].isna()].copy()
    if allowed.empty:
        print("No allowed positions.")
        return

    # Filter source
    if source == "active":
        allowed = allowed[allowed["candidate_group"].isin(["primary", "gettoplive_candidate"])]
    elif source == "primary":
        allowed = allowed[allowed["candidate_group"] == "primary"]
    elif source == "gettoplive":
        allowed = allowed[allowed["candidate_group"] == "gettoplive_candidate"]
    elif source == "benchmark":
        allowed = allowed[allowed["candidate_group"] == "benchmark"]
    elif source == "all_non_control":
        allowed = allowed[allowed["candidate_group"].isin(["primary", "benchmark", "gettoplive_candidate"])]
    else:
        raise ValueError(f"Unknown source {source}")

    if allowed.empty:
        print(f"No allowed positions after filtering for source: {source}")
        return

    # Ensure numerical
    for c in ["entry_ask", "pnl_per_share_2c", "edge", "fair_prob", "side_kill_mom", "book_age_ms", "game_time_sec"]:
        if c in allowed.columns:
            allowed[c] = pd.to_numeric(allowed[c], errors="coerce")

    # Sizing
    if sizing == "flat_1":
        allowed["sim_shares"] = 1.0
    elif sizing == "group_specific_default":
        def _group_size(r):
            grp = r.get("candidate_group", "")
            ask = float(r.get("entry_ask", 0.0))
            if grp == "primary":
                edge = float(r.get("edge", 0.0)) if not pd.isna(r.get("edge")) else 0.0
                if edge <= 0.05: return 0.0
                return min(25.0, (edge * 100 * 0.5) / ask if ask > 0 else 0)
            elif grp == "gettoplive_candidate":
                mom = float(r.get("side_kill_mom", 0.0)) if not pd.isna(r.get("side_kill_mom")) else 0.0
                if mom <= 0: return 0.0
                return min(25.0, (mom * 0.5) / ask if ask > 0 else 0)
            return 1.0
        allowed["sim_shares"] = allowed.apply(_group_size, axis=1)
    else:
        allowed["sim_shares"] = 1.0

    allowed["sim_stake"] = allowed["sim_shares"] * allowed["entry_ask"]
    allowed["sim_pnl_2c"] = allowed["sim_shares"] * allowed["pnl_per_share_2c"]

    settled = allowed[allowed["settled_win"].notna()].copy()
    settled["win"] = settled["settled_win"].map(_bool_or_none)

    print(f"# Statistical Report (source={source}, sizing={sizing})\n")

    if settled.empty:
        print("No settled positions.")
        return

    print("## Core Metrics\n")
    core_rows = []
    
    # By strategy
    for strat, sub in settled.groupby("strategy_name"):
        wins = sub["win"].sum()
        losses = (~sub["win"]).sum()
        pnl = sub["sim_pnl_2c"]
        stake = sub["sim_stake"].sum()
        avg_ask = sub["entry_ask"].mean()
        be = avg_ask + 0.02
        roi = pnl.sum() / stake if stake > 0 else 0
        
        std_pnl = pnl.std()
        tstat = pnl.mean() / (std_pnl / np.sqrt(len(pnl))) if std_pnl > 0 and len(pnl) > 0 else 0
        
        prof_factor = sub[sub["sim_pnl_2c"] > 0]["sim_pnl_2c"].sum() / abs(sub[sub["sim_pnl_2c"] < 0]["sim_pnl_2c"].sum()) if (sub["sim_pnl_2c"] < 0).any() else float('inf')
        
        sub = sub.sort_values("entry_received_at_ns")
        cum_pnl = pnl.cumsum()
        max_dd = (cum_pnl.cummax() - cum_pnl).max()
        
        core_rows.append({
            "Strategy": strat,
            "Positions": len(sub),
            "Maps": sub["map_exposure_id"].nunique(),
            "Win Rate": f"{wins/len(sub)*100:.1f}%",
            "Avg Ask": f"{avg_ask:.3f}",
            "B/E WR": f"{be*100:.1f}%",
            "Stake": f"{stake:.1f}",
            "PnL 2c": f"{pnl.sum():.2f}",
            "ROI": f"{roi*100:.1f}%",
            "Avg PnL": f"{pnl.mean():.2f}",
            "Med PnL": f"{pnl.median():.2f}",
            "Std PnL": f"{std_pnl:.2f}",
            "T-Stat": f"{tstat:.2f}",
            "Prof Factor": f"{prof_factor:.2f}",
            "Max DD": f"{max_dd:.2f}",
            "Worst Pos": f"{pnl.min():.2f}"
        })
    _print_table(pd.DataFrame(core_rows))

    print("## Bootstrap Analysis\n")
    boot_rows = []
    for strat, sub in settled.groupby("strategy_name"):
        pnl_arr = sub["sim_pnl_2c"].values
        p5, p95, prob_pos = _bootstrap_ci(pnl_arr, bootstrap_samples)
        
        # Map bootstrap
        map_pnls = sub.groupby("map_exposure_id")["sim_pnl_2c"].sum().values
        mp5, mp95, mprob_pos = _bootstrap_ci(map_pnls, bootstrap_samples)
        
        boot_rows.append({
            "Strategy": strat,
            "Pos 5% CI": f"{p5:.2f}",
            "Pos 95% CI": f"{p95:.2f}",
            "Pos P(>0)": f"{prob_pos*100:.1f}%",
            "Map 5% CI": f"{mp5:.2f}",
            "Map 95% CI": f"{mp95:.2f}",
            "Map P(>0)": f"{mprob_pos*100:.1f}%",
        })
    _print_table(pd.DataFrame(boot_rows))

    print("## Map Concentration\n")
    conc_rows = []
    for strat, sub in settled.groupby("strategy_name"):
        map_pnls = sub.groupby("map_exposure_id")["sim_pnl_2c"].sum().sort_values(ascending=False)
        total_pnl = map_pnls.sum()
        total_stake = sub["sim_stake"].sum()
        
        pnl_wo_best = total_pnl - map_pnls.max() if len(map_pnls) > 0 else 0
        pnl_wo_worst = total_pnl - map_pnls.min() if len(map_pnls) > 0 else 0
        pnl_wo_top3 = total_pnl - map_pnls.head(3).sum() if len(map_pnls) > 0 else 0
        
        top1_pct = (map_pnls.max() / total_pnl * 100) if total_pnl > 0 else 0
        top3_pct = (map_pnls.head(3).sum() / total_pnl * 100) if total_pnl > 0 else 0
        
        map_stakes = sub.groupby("map_exposure_id")["sim_stake"].sum().sort_values(ascending=False)
        top3_stake_pct = (map_stakes.head(3).sum() / total_stake * 100) if total_stake > 0 else 0
        
        hhi = (np.sum((map_pnls.abs() / map_pnls.abs().sum())**2) * 10000) if map_pnls.abs().sum() > 0 else 0
        
        conc_rows.append({
            "Strategy": strat,
            "PnL": f"{total_pnl:.2f}",
            "w/o Best": f"{pnl_wo_best:.2f}",
            "w/o Worst": f"{pnl_wo_worst:.2f}",
            "w/o Top3": f"{pnl_wo_top3:.2f}",
            "Top1 %": f"{top1_pct:.1f}%",
            "Top3 %": f"{top3_pct:.1f}%",
            "Top3 Stake %": f"{top3_stake_pct:.1f}%",
            "Abs HHI": f"{hhi:.0f}"
        })
    _print_table(pd.DataFrame(conc_rows))

    print("## Bucket Analysis\n")
    for strat, sub in settled.groupby("strategy_name"):
        print(f"### {strat}")
        group = sub["candidate_group"].iloc[0]
        
        if group == "primary":
            for col in ["edge", "fair_prob", "entry_ask"]:
                if col in sub.columns:
                    bkts = pd.qcut(sub[col], q=4, duplicates="drop")
                    df = sub.groupby(bkts)["sim_pnl_2c"].agg(["count", "sum", "mean"]).reset_index()
                    print(f"**By {col} Quartile**")
                    _print_table(df)
        elif group == "gettoplive_candidate":
            for col in ["side_kill_mom", "entry_ask"]:
                if col in sub.columns:
                    bkts = pd.qcut(sub[col], q=4, duplicates="drop")
                    df = sub.groupby(bkts)["sim_pnl_2c"].agg(["count", "sum", "mean"]).reset_index()
                    print(f"**By {col} Quartile**")
                    _print_table(df)

def add_statistical_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--input-name", type=str, default="paper_positions")
    parser.add_argument("--source", type=str, default="active", choices=["active", "primary", "gettoplive", "benchmark", "all_non_control"])
    parser.add_argument("--sizing", type=str, default="flat_1", choices=["flat_1", "group_specific_default", "all"])
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--format", type=str, default="markdown")

def main() -> None:
    parser = argparse.ArgumentParser()
    add_statistical_report_args(parser)
    args = parser.parse_args()
    run_statistical_report(
        logs_root=args.logs_root,
        input_name=args.input_name,
        source=args.source,
        sizing=args.sizing,
        bootstrap_samples=args.bootstrap_samples,
        output_format=args.format,
    )

if __name__ == "__main__":
    main()
