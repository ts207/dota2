import argparse
import json
from pathlib import Path
from typing import Any
from collections import defaultdict
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

def _clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

def _bool_or_none(x):
    if pd.isna(x): return None
    return bool(x)

def run_sizing_report(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = "paper_positions",
    source: str = "active",
    bankroll: float = 1000.0,
    max_shares: float = 25.0,
    max_position_notional: float = 100.0,
    max_map_notional: float = 200.0,
    output_format: str = "markdown",
) -> list[dict[str, Any]]:
    input_dir = logs_root / input_name
    if not input_dir.exists():
        print(f"Directory {input_dir} not found.")
        return

    frame = _read_parquet_dir(input_dir)
    if frame.empty:
        print("No positions found.")
        return

    # Filter rules
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

    # Ensure required columns
    for col in ["edge", "fair_prob", "entry_ask"]:
        if col not in allowed.columns:
            allowed[col] = 0.0

    if "book_ask_size" not in allowed.columns:
        allowed["book_ask_size"] = np.nan

    if "source_update_age_sec" not in allowed.columns:
        if "book_age_ms" in allowed.columns:
            allowed["source_update_age_sec"] = pd.to_numeric(allowed["book_age_ms"], errors="coerce") / 1000.0
        else:
            allowed["source_update_age_sec"] = np.nan

    # Calculate liquidity cap
    allowed["book_ask_size"] = pd.to_numeric(allowed["book_ask_size"], errors="coerce")
    allowed["liquidity_unknown"] = allowed["book_ask_size"].isna()
    allowed["liquidity_cap"] = np.where(
        allowed["liquidity_unknown"],
        max_shares,
        allowed["book_ask_size"] * 0.25
    )

    # Sort chronologically
    if "entry_received_at_ns" in allowed.columns:
        allowed = allowed.sort_values("entry_received_at_ns")

    # Sizing schemes
    schemes = [
        "flat_1",
        "flat_5",
        "flat_25_liquidity_unchecked",
        "edge_scaled_0.5pct_bankroll_cap25",
        "kill_mom_scaled_0.5pct_cap25",
        "kelly_05_cap25",
        "kelly_10_cap25",
        "group_specific_default"
    ]

    results = []
    
    for scheme in schemes:
        map_used_notional = defaultdict(float)
        sim_shares_list = []
        liq_capped_list = []
        
        for idx, row in allowed.iterrows():
            entry_ask = float(row["entry_ask"])
            if entry_ask <= 0:
                entry_ask = 1.0 # fallback
                
            liq_cap = float(row["liquidity_cap"])
            edge = float(row["edge"])
            fair_prob = float(row["fair_prob"])
            map_id = row["map_exposure_id"]

            if scheme == "flat_1":
                desired_shares = 1.0
            elif scheme == "flat_5":
                desired_shares = 5.0
            elif scheme == "flat_25_liquidity_unchecked":
                desired_shares = min(25.0, liq_cap)
            elif scheme == "edge_scaled_0.5pct_bankroll_cap25":
                base_notional = bankroll * 0.005
                multiplier = _clamp(edge / 0.10, 0.25, 2.0) if not pd.isna(edge) else 0.25
                target_notional = base_notional * multiplier
                desired_shares = target_notional / entry_ask
            elif scheme == "kill_mom_scaled_0.5pct_cap25":
                side_kill_mom = float(row.get("side_kill_mom", 0.0))
                source_age = float(row.get("source_update_age_sec", 0.0))
                if pd.isna(side_kill_mom): side_kill_mom = 0.0
                if pd.isna(source_age): source_age = 5.0

                base_notional = bankroll * 0.005
                kill_multiplier = _clamp(side_kill_mom / 3.0, 0.5, 2.0)
                age_multiplier = _clamp((5.0 - source_age) / 5.0, 0.25, 1.0)
                target_notional = base_notional * kill_multiplier * age_multiplier
                desired_shares = target_notional / entry_ask
            elif scheme == "kelly_05_cap25":
                effective_price = entry_ask + 0.02
                kelly_fraction = max(0.0, (fair_prob - effective_price) / (1 - effective_price) if effective_price < 1 and not pd.isna(fair_prob) else 0.0)
                target_notional = bankroll * 0.05 * kelly_fraction
                desired_shares = target_notional / entry_ask
            elif scheme == "kelly_10_cap25":
                effective_price = entry_ask + 0.02
                kelly_fraction = max(0.0, (fair_prob - effective_price) / (1 - effective_price) if effective_price < 1 and not pd.isna(fair_prob) else 0.0)
                target_notional = bankroll * 0.10 * kelly_fraction
                desired_shares = target_notional / entry_ask
            elif scheme == "group_specific_default":
                group = row.get("candidate_group")
                if group == "primary":
                    base_notional = bankroll * 0.005
                    multiplier = _clamp(edge / 0.10, 0.25, 2.0) if not pd.isna(edge) else 0.25
                    target_notional = base_notional * multiplier
                    desired_shares = target_notional / entry_ask
                elif group == "gettoplive_candidate":
                    side_kill_mom = float(row.get("side_kill_mom", 0.0))
                    source_age = float(row.get("source_update_age_sec", 0.0))
                    if pd.isna(side_kill_mom): side_kill_mom = 0.0
                    if pd.isna(source_age): source_age = 5.0

                    base_notional = bankroll * 0.005
                    kill_multiplier = _clamp(side_kill_mom / 3.0, 0.5, 2.0)
                    age_multiplier = _clamp((5.0 - source_age) / 5.0, 0.25, 1.0)
                    target_notional = base_notional * kill_multiplier * age_multiplier
                    desired_shares = target_notional / entry_ask
                else:
                    desired_shares = 1.0 # fallback
            else:
                desired_shares = 0.0

            # Apply caps
            capped_shares = min(desired_shares, max_shares)
            capped_shares = min(capped_shares, max_position_notional / entry_ask)
            
            # Apply liquidity cap to non-flat_1/5
            if scheme not in ["flat_1", "flat_5"]:
                capped_shares = min(capped_shares, liq_cap)

            desired_notional = capped_shares * entry_ask
            remaining_map_notional = max_map_notional - map_used_notional[map_id]
            final_notional = min(desired_notional, remaining_map_notional)
            
            final_shares = final_notional / entry_ask
            map_used_notional[map_id] += final_notional
            
            sim_shares_list.append(final_shares)
            
            # Check if liquidity capped (only matters if we were above liq cap before other caps, or if final == liq_cap)
            # Simplified: Did liquidity cap reduce it below desired_shares (after max_shares/max_notional)?
            capped_by_liq = (capped_shares == liq_cap and desired_shares > liq_cap)
            liq_capped_list.append(capped_by_liq)

        scheme_df = allowed.copy()
        scheme_df["sim_shares"] = sim_shares_list
        scheme_df["liq_capped"] = liq_capped_list
        
        # Calculate PnL (only for settled)
        scheme_df["sim_stake"] = scheme_df["sim_shares"] * scheme_df["entry_ask"]
        scheme_df["sim_pnl_2c"] = scheme_df["sim_shares"] * scheme_df["pnl_per_share_2c"]
        scheme_df["worst_case_loss"] = scheme_df["sim_shares"] * (scheme_df["entry_ask"] + 0.02)
        
        settled = scheme_df[scheme_df["settled_win"].notna()].copy()
        
        if not settled.empty:
            total_pnl = settled["sim_pnl_2c"].sum()
            total_stake = settled["sim_stake"].sum()
            roi = total_pnl / total_stake if total_stake > 0 else 0.0
            
            settled["cum_pnl"] = settled["sim_pnl_2c"].cumsum()
            settled["cum_pnl_peak"] = settled["cum_pnl"].cummax()
            settled["drawdown"] = settled["cum_pnl_peak"] - settled["cum_pnl"]
            max_dd = settled["drawdown"].max()
            
            worst_position = settled["sim_pnl_2c"].min()
        else:
            total_pnl = 0.0
            total_stake = 0.0
            roi = 0.0
            max_dd = 0.0
            worst_position = 0.0
            
        results.append({
            "sizing": scheme,
            "positions": len(scheme_df),
            "settled": len(settled),
            "win": settled["settled_win"].map(_bool_or_none).astype(bool).mean() if not settled.empty else 0.0,
            "avg_ask": settled["entry_ask"].mean() if not settled.empty else 0.0,
            "avg_edge": settled["edge"].mean() if not settled.empty else 0.0,
            "avg_shares": settled["sim_shares"].mean() if not settled.empty else 0.0,
            "total_stake": total_stake,
            "pnl_2c": total_pnl,
            "roi": roi,
            "max_dd": max_dd,
            "worst_position": worst_position,
            "liq_unknown_pct": scheme_df["liquidity_unknown"].mean(),
            "liq_capped_pct": scheme_df["liq_capped"].mean(),
            "df": scheme_df,
            "settled_df": settled
        })

    # Render Report
    print("# Sizing Report")
    print(f"\nSource: {source} (bankroll=${bankroll}, max_shares={max_shares}, map_cap=${max_map_notional})")
    
    print("\n## Main Summary\n")
    main_cols = ["sizing", "positions", "settled", "win", "avg ask", "avg edge", "avg shares", "total stake", "pnl 2c", "ROI", "max DD", "worst position"]
    main_rows = []
    for r in results:
        main_rows.append({
            "sizing": r["sizing"],
            "positions": r["positions"],
            "settled": r["settled"],
            "win": f"{r['win']*100:.1f}%",
            "avg ask": f"{r['avg_ask']:.3f}",
            "avg edge": f"{r['avg_edge']*100:.2f}%",
            "avg shares": f"{r['avg_shares']:.1f}",
            "total stake": f"{r['total_stake']:.1f}",
            "pnl 2c": f"{r['pnl_2c']:.2f}",
            "ROI": f"{r['roi']*100:.2f}%",
            "max DD": f"{r['max_dd']:.2f}",
            "worst position": f"{r['worst_position']:.2f}"
        })
    _print_table(pd.DataFrame(main_rows))
    
    print("## Candidate Group Breakdown\n")
    cg_rows = []
    for r in results:
        sdf = r["settled_df"]
        if sdf.empty: continue
        cg = sdf.groupby("candidate_group").agg(
            positions=("position_id", "count"),
            stake=("sim_stake", "sum"),
            pnl_2c=("sim_pnl_2c", "sum")
        ).reset_index()
        for _, row in cg.iterrows():
            cg_rows.append({
                "sizing": r["sizing"],
                "group": row["candidate_group"],
                "positions": row["positions"],
                "stake": f"{row['stake']:.1f}",
                "pnl 2c": f"{row['pnl_2c']:.2f}",
                "ROI": f"{(row['pnl_2c']/row['stake'])*100:.2f}%" if row['stake'] > 0 else "0.0%"
            })
            
        # Add combined if there's more than 1 group
        if len(cg) > 1:
            cg_rows.append({
                "sizing": r["sizing"],
                "group": "active_combined",
                "positions": cg["positions"].sum(),
                "stake": f"{cg['stake'].sum():.1f}",
                "pnl 2c": f"{cg['pnl_2c'].sum():.2f}",
                "ROI": f"{(cg['pnl_2c'].sum()/cg['stake'].sum())*100:.2f}%" if cg['stake'].sum() > 0 else "0.0%"
            })
    _print_table(pd.DataFrame(cg_rows))

    print("## By Strategy\n")
    strat_rows = []
    for r in results:
        sdf = r["settled_df"]
        if sdf.empty: continue
        st = sdf.groupby("strategy_name").agg(
            positions=("position_id", "count"),
            stake=("sim_stake", "sum"),
            pnl_2c=("sim_pnl_2c", "sum")
        ).reset_index()
        for _, row in st.iterrows():
            strat_rows.append({
                "sizing": r["sizing"],
                "strategy": row["strategy_name"],
                "positions": row["positions"],
                "stake": f"{row['stake']:.1f}",
                "pnl 2c": f"{row['pnl_2c']:.2f}",
                "ROI": f"{(row['pnl_2c']/row['stake'])*100:.2f}%" if row['stake'] > 0 else "0.0%"
            })
    _print_table(pd.DataFrame(strat_rows))
    
    print("## Map Concentration\n")
    map_rows = []
    for r in results:
        sdf = r["settled_df"]
        if sdf.empty: continue
        mc = sdf.groupby("match_id").agg(
            positions=("position_id", "count"),
            stake=("sim_stake", "sum"),
            pnl_2c=("sim_pnl_2c", "sum")
        ).reset_index()
        
        total_stake = mc["stake"].sum()
        total_pnl = mc["pnl_2c"].sum()
        
        largest_stake = mc["stake"].max()
        largest_pnl = mc["pnl_2c"].max()
        largest_loss = mc["pnl_2c"].min()
        
        top3_pnl_maps = mc.sort_values("pnl_2c", ascending=False).head(3)
        top3_stake_maps = mc.sort_values("stake", ascending=False).head(3)
        
        top3_pnl_pct = top3_pnl_maps["pnl_2c"].sum() / total_pnl if total_pnl != 0 else 0.0
        top3_stake_pct = top3_stake_maps["stake"].sum() / total_stake if total_stake != 0 else 0.0
        
        map_rows.append({
            "sizing": r["sizing"],
            "largest map stake": f"{largest_stake:.1f}",
            "largest map PnL": f"{largest_pnl:.2f}",
            "largest map loss": f"{largest_loss:.2f}",
            "top 3 maps as % of PnL": f"{top3_pnl_pct*100:.1f}%",
            "top 3 maps as % of stake": f"{top3_stake_pct*100:.1f}%"
        })
    _print_table(pd.DataFrame(map_rows))
    
    print("## Input Completeness\n")
    print(f"- fair_prob present: {allowed['fair_prob'].notna().mean()*100:.1f}%")
    print(f"- edge present: {allowed['edge'].notna().mean()*100:.1f}%")
    print(f"- book_ask_size present: {(~allowed['liquidity_unknown']).mean()*100:.1f}%")
    if "source_update_age_sec" in allowed.columns:
        print(f"- source_update_age_sec present: {allowed['source_update_age_sec'].notna().mean()*100:.1f}%")
    if "side_kill_mom" in allowed.columns:
        print(f"- side_kill_mom present: {allowed['side_kill_mom'].notna().mean()*100:.1f}%")
    print()

    print("## Per-Strategy Suggested Default\n")
    print("- primary recommended sizing: edge_scaled")
    print("- gettoplive recommended sizing: flat_1 or kill_mom_scaled")
    print("- combined active recommended sizing: group_specific_default\n")

    print("## Liquidity Summary\n")
    liq_rows = []
    for r in results:
        liq_rows.append({
            "sizing": r["sizing"],
            "liquidity capped": f"{r['liq_capped_pct']*100:.1f}%",
            "liquidity unknown": f"{r['liq_unknown_pct']*100:.1f}%"
        })
    _print_table(pd.DataFrame(liq_rows))

    print("## Warnings\n")
    warnings = []
    for r in results:
        if r["liq_unknown_pct"] > 0.30:
            warnings.append(f"[{r['sizing']}] liquidity unknown on >30% positions ({r['liq_unknown_pct']*100:.1f}%)")
        if r["settled"] < 50:
            warnings.append(f"[{r['sizing']}] less than 50 settled positions ({r['settled']})")
        if r["max_dd"] > bankroll * 0.10:
            warnings.append(f"[{r['sizing']}] max drawdown exceeds 10% of bankroll ({r['max_dd']:.2f} > {bankroll*0.10})")
    
    if source == "all_non_control" or source == "benchmark":
        warnings.append("benchmark included in source")

    if not warnings:
        print("None")
    else:
        for w in warnings:
            print(f"- {w}")
            
    return results

def add_sizing_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--input-name", type=str, default="paper_positions")
    parser.add_argument("--source", type=str, default="active", choices=["active", "primary", "gettoplive", "benchmark", "all_non_control"])
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--max-shares", type=float, default=25.0)
    parser.add_argument("--max-position-notional", type=float, default=100.0)
    parser.add_argument("--max-map-notional", type=float, default=200.0)
    parser.add_argument("--format", type=str, default="markdown")

def main() -> None:
    parser = argparse.ArgumentParser()
    add_sizing_report_args(parser)
    args = parser.parse_args()
    
    run_sizing_report(
        logs_root=args.logs_root,
        input_name=args.input_name,
        source=args.source,
        bankroll=args.bankroll,
        max_shares=args.max_shares,
        max_position_notional=args.max_position_notional,
        max_map_notional=args.max_map_notional,
        output_format=args.format,
    )

if __name__ == "__main__":
    main()
