import argparse
import json
from pathlib import Path
from typing import Any, Dict
import pandas as pd
import numpy as np

from .paper_strategy_logger import _read_parquet_dir
from .sizing_engine import simulate_sizing

def _print_table(df: pd.DataFrame) -> None:
    if df.empty:
        print("*No data*")
        return
    print(f"| {' | '.join(str(c) for c in df.columns)} |")
    print(f"| {' | '.join(['---'] * len(df.columns))} |")
    for row in df.itertuples(index=False):
        print(f"| {' | '.join(str(x) for x in row)} |")
    print()

def _bool_or_none(x):
    if pd.isna(x): return None
    return bool(x)

def _bootstrap_ci(data: np.ndarray, samples: int = 5000, seed: int = 42) -> tuple[float, float, float]:
    if len(data) == 0:
        return 0.0, 0.0, 0.0
    rng = np.random.default_rng(seed)
    boot_sums = rng.choice(data, size=(samples, len(data)), replace=True).sum(axis=1)
    return np.percentile(boot_sums, 5), np.percentile(boot_sums, 95), (boot_sums > 0).mean()

def run_statistical_report_for_sizing(
    frame: pd.DataFrame,
    source: str,
    sizing: str,
    bootstrap_samples: int,
    seed: int,
    strategy_name: str | None = None
) -> dict:
    allowed = frame[frame["blocked_reason"].isna()].copy()
    
    if allowed.empty:
        return {"error": "No allowed positions."}
    
    if strategy_name is not None:
        if "strategy_name" in allowed.columns:
            allowed = allowed[allowed["strategy_name"] == strategy_name]
        if allowed.empty:
            return {"error": f"No allowed positions after filtering for strategy_name={strategy_name}."}

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

    if allowed.empty:
        return {"error": f"No allowed positions after filtering for source: {source}"}

    for c in ["entry_ask", "pnl_per_share_2c", "edge", "fair_prob", "side_kill_mom", "book_age_ms", "game_time_sec"]:
        if c in allowed.columns:
            allowed[c] = pd.to_numeric(allowed[c], errors="coerce")

    allowed = simulate_sizing(
        allowed,
        sizing=sizing,
        bankroll=1000.0,
        max_shares=25.0,
        max_position_notional=100.0,
        max_map_notional=200.0
    )

    settled = allowed[allowed["settled_win"].notna()].copy()
    settled["win"] = settled["settled_win"].map(_bool_or_none)

    if settled.empty:
        return {"error": "No settled positions."}
        
    core_metrics = []
    boot_metrics = []
    conc_metrics = []
    buckets = {}
    
    for strat, sub in settled.groupby("strategy_name"):
        wins = sub["win"].sum()
        losses = (~sub["win"]).sum()
        sub = sub.sort_values("entry_received_at_ns")
        pnl = sub["sim_pnl_2c"]
        stake = sub["sim_stake"].sum()
        avg_ask = sub["entry_ask"].mean()
        be = avg_ask + 0.02
        roi = pnl.sum() / stake if stake > 0 else 0
        
        std_pnl = pnl.std()
        tstat = pnl.mean() / (std_pnl / np.sqrt(len(pnl))) if std_pnl > 0 and len(pnl) > 0 else 0
        
        prof_factor = sub[sub["sim_pnl_2c"] > 0]["sim_pnl_2c"].sum() / abs(sub[sub["sim_pnl_2c"] < 0]["sim_pnl_2c"].sum()) if (sub["sim_pnl_2c"] < 0).any() else float('inf')
        
        cum_pnl = pnl.cumsum()
        max_dd = (cum_pnl.cummax() - cum_pnl).max()
        
        core_metrics.append({
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

        pnl_arr = pnl.values
        p5, p95, prob_pos = _bootstrap_ci(pnl_arr, bootstrap_samples, seed=seed)
        
        map_pnls = sub.groupby("map_exposure_id")["sim_pnl_2c"].sum().values
        mp5, mp95, mprob_pos = _bootstrap_ci(map_pnls, bootstrap_samples, seed=seed)
        
        boot_metrics.append({
            "Strategy": strat,
            "Pos 5% CI": f"{p5:.2f}",
            "Pos 95% CI": f"{p95:.2f}",
            "Pos P(>0)": f"{prob_pos*100:.1f}%",
            "Map 5% CI": f"{mp5:.2f}",
            "Map 95% CI": f"{mp95:.2f}",
            "Map P(>0)": f"{mprob_pos*100:.1f}%",
        })

        map_pnls_series = sub.groupby("map_exposure_id")["sim_pnl_2c"].sum().sort_values(ascending=False)
        total_pnl = map_pnls_series.sum()
        total_stake = sub["sim_stake"].sum()
        
        pnl_wo_best = total_pnl - map_pnls_series.max() if len(map_pnls_series) > 0 else 0
        pnl_wo_worst = total_pnl - map_pnls_series.min() if len(map_pnls_series) > 0 else 0
        pnl_wo_top3 = total_pnl - map_pnls_series.head(3).sum() if len(map_pnls_series) > 0 else 0
        
        top1_pct = (map_pnls_series.max() / total_pnl * 100) if total_pnl > 0 else 0
        top3_pct = (map_pnls_series.head(3).sum() / total_pnl * 100) if total_pnl > 0 else 0
        
        map_stakes = sub.groupby("map_exposure_id")["sim_stake"].sum().sort_values(ascending=False)
        top3_stake_pct = (map_stakes.head(3).sum() / total_stake * 100) if total_stake > 0 else 0
        
        hhi = (np.sum((map_pnls_series.abs() / map_pnls_series.abs().sum())**2) * 10000) if map_pnls_series.abs().sum() > 0 else 0
        
        conc_metrics.append({
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

        group = sub["candidate_group"].iloc[0]
        strat_bkts = {}
        if group == "primary":
            for col in ["edge", "fair_prob", "entry_ask"]:
                if col in sub.columns:
                    bkts = pd.qcut(sub[col], q=4, duplicates="drop")
                    df = sub.groupby(bkts, observed=False)["sim_pnl_2c"].agg(["count", "sum", "mean"]).reset_index()
                    df[col] = df[col].astype(str)
                    strat_bkts[col] = df.to_dict(orient="records")
        elif group == "gettoplive_candidate":
            for col in ["side_kill_mom", "entry_ask"]:
                if col in sub.columns:
                    bkts = pd.qcut(sub[col], q=4, duplicates="drop")
                    df = sub.groupby(bkts, observed=False)["sim_pnl_2c"].agg(["count", "sum", "mean"]).reset_index()
                    df[col] = df[col].astype(str)
                    strat_bkts[col] = df.to_dict(orient="records")
        buckets[strat] = strat_bkts

    return {
        "source": source,
        "strategy_name": strategy_name,
        "sizing": sizing,
        "core_metrics": core_metrics,
        "boot_metrics": boot_metrics,
        "conc_metrics": conc_metrics,
        "buckets": buckets
    }

def run_statistical_report(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = "paper_positions",
    source: str = "active",
    sizing: str = "flat_1",
    bootstrap_samples: int = 5000,
    seed: int = 42,
    output_format: str = "markdown",
    strategy_name: str | None = None,
) -> None:
    input_dir = logs_root / input_name
    if not input_dir.exists():
        if output_format == "json":
            print(json.dumps({"error": f"Directory {input_dir} not found."}))
        else:
            print(f"Directory {input_dir} not found.")
        return

    frame = _read_parquet_dir(input_dir)
    if frame.empty:
        if output_format == "json":
            print(json.dumps({"error": "No positions found."}))
        else:
            print("No positions found.")
        return

    schemes = [sizing]
    if sizing == "all":
        schemes = [
            "flat_1", "flat_5", "kill_mom_scaled", 
            "edge_scaled", "conservative_group_default", "group_specific_default"
        ]
        
    all_results = []
    
    for scheme in schemes:
        res = run_statistical_report_for_sizing(
            frame=frame,
            source=source,
            sizing=scheme,
            bootstrap_samples=bootstrap_samples,
            seed=seed,
            strategy_name=strategy_name
        )
        all_results.append(res)
        
    if output_format == "json":
        print(json.dumps(all_results, indent=2))
    else:
        for res in all_results:
            if "error" in res:
                print(f"Error for sizing {res.get('sizing', 'unknown')}: {res['error']}")
                continue
                
            if res.get('strategy_name'):
                print(f"# Statistical Report (source={res['source']}, strategy_name={res['strategy_name']}, sizing={res['sizing']})\n")
            else:
                print(f"# Statistical Report (source={res['source']}, sizing={res['sizing']})\n")
            
            print("## Core Metrics\n")
            _print_table(pd.DataFrame(res["core_metrics"]))
            
            print("## Bootstrap Analysis\n")
            _print_table(pd.DataFrame(res["boot_metrics"]))
            
            print("## Map Concentration\n")
            _print_table(pd.DataFrame(res["conc_metrics"]))
            
            print("## Bucket Analysis\n")
            for strat, bkts in res["buckets"].items():
                print(f"### {strat}")
                for col, bkt_data in bkts.items():
                    print(f"**By {col} Quartile**")
                    _print_table(pd.DataFrame(bkt_data))
            print("---\n")

def add_statistical_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--input-name", type=str, default="paper_positions")
    parser.add_argument("--source", type=str, default="active", choices=["active", "primary", "gettoplive", "benchmark", "all_non_control"])
    parser.add_argument("--sizing", type=str, default="flat_1", choices=[
        "flat_1", "flat_5", "kill_mom_scaled", "edge_scaled", 
        "conservative_group_default", "group_specific_default", "all"
    ])
    parser.add_argument("--strategy-name", type=str, default=None, help="Filter to a specific strategy_name")
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--format", type=str, default="markdown", choices=["markdown", "json"])

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
        seed=args.seed,
        output_format=args.format,
        strategy_name=args.strategy_name,
    )

if __name__ == "__main__":
    main()
