"""Simple historical backtest for the single active paper strategy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .paper_strategy_logger import (
    DEFAULT_ELIGIBILITY_MODE,
    EXECUTABLE_BACKTEST_PATH,
    add_model_scores,
    prepare_paper_feature_frame,
    strategy_filter_mask,
    train_paper_model_bundle,
)
from .schemas import SIDE_SNAPSHOT_COLUMNS
from .strategy_contract import ACTIVE_MARKET_ANCHOR_SPECS


DEFAULT_LIVE_SETTLED_PATH = Path("logs/live_settled_side_snapshots/latest.parquet")
ACTIVE_STRATEGY_ELIGIBILITY_MODE = "historical_executable"


def run_active_strategy_backtest(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    live_settled_path: Path = DEFAULT_LIVE_SETTLED_PATH,
    include_live: bool = True,
) -> dict[str, Any]:
    """Run one simple backtest for the active strategy contract.

    This intentionally does not do model comparison, threshold search, walk-forward
    reporting, or ensemble collapsing. It trains the active paper model bundle on
    the executable dataset, scores all requested historical rows, and keeps the
    first signal per canonical exposure for the single active strategy.
    """
    rows = _load_backtest_rows(executable_path=executable_path, live_settled_path=live_settled_path, include_live=include_live)
    scored = _score_active_strategy_rows(rows=rows, executable_path=executable_path)
    result = _summarize_threshold(scored, ACTIVE_MARKET_ANCHOR_SPECS[0].entry_threshold)
    result["input_rows"] = int(len(rows))
    return result


def run_active_strategy_threshold_sweep(
    *,
    thresholds: list[float],
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    live_settled_path: Path = DEFAULT_LIVE_SETTLED_PATH,
    include_live: bool = True,
) -> dict[str, Any]:
    rows = _load_backtest_rows(executable_path=executable_path, live_settled_path=live_settled_path, include_live=include_live)
    scored = _score_active_strategy_rows(rows=rows, executable_path=executable_path)
    return {
        "strategy": ACTIVE_MARKET_ANCHOR_SPECS[0].model_name,
        "eligibility_mode": ACTIVE_STRATEGY_ELIGIBILITY_MODE,
        "input_rows": int(len(rows)),
        "thresholds": [_summarize_threshold(scored, threshold) for threshold in thresholds],
    }


def _score_active_strategy_rows(*, rows: pd.DataFrame, executable_path: Path) -> pd.DataFrame:
    spec = ACTIVE_MARKET_ANCHOR_SPECS[0]
    bundle = train_paper_model_bundle(executable_path=executable_path, specs=list(ACTIVE_MARKET_ANCHOR_SPECS))
    model, features = bundle.models[spec.model_name]
    scored = prepare_paper_feature_frame(rows, eligibility_mode=DEFAULT_ELIGIBILITY_MODE)
    for col in features:
        if col not in scored.columns:
            scored[col] = pd.NA
    scored = add_model_scores(scored, model, features, score_kind=bundle.score_kinds.get(spec.model_name, spec.score_kind))
    scored["active_backtest_tradable"] = scored["tradable_research"].fillna(False).astype(bool)
    scored["eligibility_mode"] = ACTIVE_STRATEGY_ELIGIBILITY_MODE
    return scored


def _summarize_threshold(scored: pd.DataFrame, threshold: float) -> dict[str, Any]:
    spec = ACTIVE_MARKET_ANCHOR_SPECS[0]
    signal = scored[
        scored["active_backtest_tradable"].fillna(False).astype(bool)
        & strategy_filter_mask(scored, spec)
        & (scored["edge"] >= threshold)
    ].copy()
    if not signal.empty:
        signal = _add_map_exposure_id(signal)
        signal = signal.sort_values(["map_exposure_id", "received_at_ns"])
        trades = signal.drop_duplicates(["map_exposure_id"], keep="first").reset_index(drop=True)
    else:
        trades = signal
    settled = trades[trades["settled_win"].notna()].copy() if "settled_win" in trades.columns else trades.iloc[0:0].copy()
    ask = pd.to_numeric(settled["book_best_ask"], errors="coerce") if "book_best_ask" in settled.columns else pd.Series(dtype=float)
    settled_win = settled["settled_win"].fillna(False).astype(bool) if "settled_win" in settled.columns else pd.Series(dtype=bool)
    pnl = pd.Series(dtype=float)
    pnl_1c = pd.Series(dtype=float)
    pnl_2c = pd.Series(dtype=float)
    if not settled.empty:
        pnl = pd.Series([1.0 - price if win else -price for price, win in zip(ask, settled_win)], index=settled.index)
        pnl_1c = pd.Series([1.0 - (price + 0.01) if win else -(price + 0.01) for price, win in zip(ask, settled_win)], index=settled.index)
        pnl_2c = pd.Series([1.0 - (price + 0.02) if win else -(price + 0.02) for price, win in zip(ask, settled_win)], index=settled.index)
    return {
        "strategy": spec.model_name,
        "entry_threshold": float(threshold),
        "eligibility_mode": ACTIVE_STRATEGY_ELIGIBILITY_MODE,
        "decision_rows": int(len(scored)),
        "raw_signal_rows": int(len(signal)),
        "trades": int(len(trades)),
        "settled_trades": int(len(settled)),
        "matches": int(settled["match_id"].nunique()) if not settled.empty and "match_id" in settled.columns else 0,
        "win_rate": _mean_bool(settled, "settled_win"),
        "avg_ask": _mean_num(settled, "book_best_ask"),
        "pnl": float(pnl.sum()) if not pnl.empty else 0.0,
        "pnl_1c": float(pnl_1c.sum()) if not pnl_1c.empty else 0.0,
        "pnl_2c": float(pnl_2c.sum()) if not pnl_2c.empty else 0.0,
    }


def add_backtest_active_strategy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--live-settled-path", default=str(DEFAULT_LIVE_SETTLED_PATH))
    parser.add_argument("--no-live", action="store_true", help="use only the clean executable dataset")
    parser.add_argument("--thresholds", default=None, help="comma-separated thresholds to test, for example 0.08,0.10,0.12,0.15")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def format_active_strategy_backtest(result: dict[str, Any], *, output_format: str = "text") -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True)
    if "thresholds" in result:
        lines = [
            "Active Strategy Threshold Backtest",
            f"strategy: {result['strategy']}",
            f"eligibility: {result['eligibility_mode']}",
            f"input rows: {result['input_rows']}",
            "",
            "| threshold | trades | matches | win | avg ask | pnl | pnl 1c | pnl 2c |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in result["thresholds"]:
            lines.append(
                f"| {row['entry_threshold']:.2f} | {row['settled_trades']} | {row['matches']} | "
                f"{_pct(row['win_rate'])} | {_num(row['avg_ask'])} | {_signed(row['pnl'])} | "
                f"{_signed(row['pnl_1c'])} | {_signed(row['pnl_2c'])} |"
            )
        return "\n".join(lines)
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


def _add_map_exposure_id(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    game = out["current_game_number"].astype("string").fillna("").str.strip()
    game = game.mask(game.eq("") | game.str.lower().isin(["nan", "none", "<na>"]), "MAPEQUIV")
    out["map_exposure_id"] = out["match_id"].astype(str) + "::" + game.astype(str)
    return out


def parse_thresholds(raw: str | None) -> list[float] | None:
    if raw is None:
        return None
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("threshold list cannot be empty")
    return values


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
