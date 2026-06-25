"""Simple historical backtest for the single active paper strategy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .decision_reports import first_signal_trades
from .paper_strategy_logger import (
    DEFAULT_ELIGIBILITY_MODE,
    EXECUTABLE_BACKTEST_PATH,
    score_paper_decisions,
    train_paper_model_bundle,
)
from .schemas import SIDE_SNAPSHOT_COLUMNS
from .strategy_contract import ACTIVE_MARKET_ANCHOR_SPECS


DEFAULT_LIVE_SETTLED_PATH = Path("logs/live_settled_side_snapshots/latest.parquet")


def run_active_strategy_backtest(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    live_settled_path: Path = DEFAULT_LIVE_SETTLED_PATH,
    include_live: bool = True,
    eligibility_mode: str = DEFAULT_ELIGIBILITY_MODE,
) -> dict[str, Any]:
    """Run one simple backtest for the active strategy contract.

    This intentionally does not do model comparison, threshold search, walk-forward
    reporting, or ensemble collapsing. It trains the active paper model bundle on
    the executable dataset, scores all requested historical rows, and keeps the
    first signal per canonical exposure for the single active strategy.
    """
    rows = _load_backtest_rows(executable_path=executable_path, live_settled_path=live_settled_path, include_live=include_live)
    bundle = train_paper_model_bundle(executable_path=executable_path)
    decisions = score_paper_decisions(rows, bundle, eligibility_mode=eligibility_mode)
    trades = first_signal_trades(decisions)
    settled = trades[trades["settled_win"].notna()].copy() if "settled_win" in trades.columns else trades.iloc[0:0].copy()
    active_models = [spec.model_name for spec in ACTIVE_MARKET_ANCHOR_SPECS]
    return {
        "strategy": active_models[0] if active_models else None,
        "entry_threshold": ACTIVE_MARKET_ANCHOR_SPECS[0].entry_threshold if ACTIVE_MARKET_ANCHOR_SPECS else None,
        "eligibility_mode": eligibility_mode,
        "input_rows": int(len(rows)),
        "decision_rows": int(len(decisions)),
        "raw_signal_rows": int(decisions["signal"].fillna(False).astype(bool).sum()) if not decisions.empty else 0,
        "trades": int(len(trades)),
        "settled_trades": int(len(settled)),
        "matches": int(settled["match_id"].nunique()) if not settled.empty and "match_id" in settled.columns else 0,
        "win_rate": _mean_bool(settled, "settled_win"),
        "avg_ask": _mean_num(settled, "ask"),
        "pnl": _sum_num(settled, "paper_pnl_per_share"),
        "pnl_1c": _sum_num(settled, "pnl_slip_1c"),
        "pnl_2c": _sum_num(settled, "pnl_slip_2c"),
    }


def add_backtest_active_strategy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--live-settled-path", default=str(DEFAULT_LIVE_SETTLED_PATH))
    parser.add_argument("--no-live", action="store_true", help="use only the clean executable dataset")
    parser.add_argument("--eligibility-mode", default=DEFAULT_ELIGIBILITY_MODE, choices=["research", "live_executable"])
    parser.add_argument("--format", choices=["text", "json"], default="text")


def format_active_strategy_backtest(result: dict[str, Any], *, output_format: str = "text") -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True)
    return "\n".join(
        [
            "Active Strategy Backtest",
            f"strategy: {result['strategy']}",
            f"threshold: {result['entry_threshold']}",
            f"eligibility: {result['eligibility_mode']}",
            f"input rows: {result['input_rows']}",
            f"raw signal rows: {result['raw_signal_rows']}",
            f"trades: {result['settled_trades']}",
            f"matches: {result['matches']}",
            f"win rate: {_pct(result['win_rate'])}",
            f"avg ask: {_num(result['avg_ask'])}",
            f"pnl: {_signed(result['pnl'])}",
            f"pnl 1c: {_signed(result['pnl_1c'])}",
            f"pnl 2c: {_signed(result['pnl_2c'])}",
        ]
    )


def _load_backtest_rows(*, executable_path: Path, live_settled_path: Path, include_live: bool) -> pd.DataFrame:
    clean = pd.read_parquet(executable_path)
    frames = [clean]
    if include_live and live_settled_path.exists():
        frames.append(pd.read_parquet(live_settled_path))
    all_cols = sorted(set(SIDE_SNAPSHOT_COLUMNS).union(*(set(frame.columns) for frame in frames)))
    rows = pd.concat([frame.reindex(columns=all_cols) for frame in frames], ignore_index=True)
    identity_cols = [col for col in ["match_id", "market_id", "token_id", "received_at_ns"] if col in rows.columns]
    if identity_cols:
        rows = rows.drop_duplicates(identity_cols, keep="first")
    return rows.reset_index(drop=True)


def _sum_num(frame: pd.DataFrame, col: str) -> float | None:
    if frame.empty or col not in frame.columns:
        return None
    return float(pd.to_numeric(frame[col], errors="coerce").sum())


def _mean_num(frame: pd.DataFrame, col: str) -> float | None:
    if frame.empty or col not in frame.columns:
        return None
    value = pd.to_numeric(frame[col], errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def _mean_bool(frame: pd.DataFrame, col: str) -> float | None:
    if frame.empty or col not in frame.columns:
        return None
    return float(frame[col].fillna(False).astype(bool).mean())


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _signed(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.4f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"
