import argparse
from pathlib import Path
import pandas as pd
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

def run_position_report(*, logs_root: Path = Path("logs"), input_name: str = "paper_positions") -> None:
    input_dir = logs_root / input_name
    if not input_dir.exists():
        print(f"Directory {input_dir} not found.")
        return

    frame = _read_parquet_dir(input_dir)
    if frame.empty:
        print("No positions found.")
        return

    allowed = frame[frame["blocked_reason"].isna()].copy()
    blocked = frame[~frame["blocked_reason"].isna()].copy()
    settled = allowed[allowed["settled_win"].notna()].copy()
    pending = allowed[allowed["settled_win"].isna()].copy()

    print("# Position Report\n")
    print(f"- total position records: {len(frame)}")
    print(f"- allowed positions: {len(allowed)}")
    print(f"- blocked decisions: {len(blocked)}")
    print(f"- settled allowed positions: {len(settled)}")
    print(f"- pending allowed positions: {len(pending)}")
    print()

    total_pnl_per_share = settled["pnl_per_share_2c"].sum() if not settled.empty else 0.0
    total_position_pnl = settled["position_pnl_2c"].sum() if not settled.empty else 0.0

    print(f"**Total Settled PnL per share (2c):** {total_pnl_per_share:+.4f}")
    print(f"**Total Settled Position PnL (2c):** {total_position_pnl:+.4f}")
    print()

    if not settled.empty:
        print("## By Candidate Group\n")
        cg = settled.groupby("candidate_group").agg(
            positions=("position_id", "count"),
            pnl_per_share=("pnl_per_share_2c", "sum"),
            position_pnl=("position_pnl_2c", "sum")
        ).reset_index()
        _print_table(cg)

        print("## By Strategy Name\n")
        sn = settled.groupby("strategy_name").agg(
            positions=("position_id", "count"),
            pnl_per_share=("pnl_per_share_2c", "sum"),
            position_pnl=("position_pnl_2c", "sum")
        ).reset_index()
        _print_table(sn)
        
        print("## By Map Exposure Concentration (Allowed Positions)\n")
        # count how many times a map_exposure_id appears in allowed
        mc = allowed.groupby("map_exposure_id").size().value_counts().reset_index()
        mc.columns = ["allowed_positions_per_map", "map_count"]
        mc = mc.sort_values("allowed_positions_per_map")
        _print_table(mc)

        print("## Largest Losing Controlled Exposures\n")
        me = settled.groupby(["map_exposure_id", "strategy_name"])["position_pnl_2c"].sum().reset_index()
        me = me.sort_values("position_pnl_2c")
        _print_table(me.head(3))

        print("## Largest Winning Controlled Exposures\n")
        _print_table(me.tail(3).sort_values("position_pnl_2c", ascending=False))

def add_position_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", type=Path, default=Path("logs"))
    parser.add_argument("--input-name", type=str, default="paper_positions")

def main() -> None:
    parser = argparse.ArgumentParser()
    add_position_report_args(parser)
    args = parser.parse_args()
    
    run_position_report(
        logs_root=args.logs_root,
        input_name=args.input_name,
    )

if __name__ == "__main__":
    main()
