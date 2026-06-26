"""Research-only entry quality report for the active paper strategy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .active_strategy_backtest import (
    DEFAULT_LIVE_SETTLED_PATH,
    _add_map_exposure_id,
    _load_backtest_rows,
    _score_active_strategy_rows,
)
from .decision_reports import first_signal_trades
from .paper_strategy_logger import (
    EXECUTABLE_BACKTEST_PATH,
    HISTORICAL_RESEARCH_ELIGIBILITY_MODE,
    score_paper_decisions,
    strategy_filter_mask,
    train_paper_model_bundle,
)
from .strategy_contract import ACTIVE_MARKET_ANCHOR_SPECS


DEFAULT_MIN_TRADES = 10
EDGE_MINS = [0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20]
ASK_MAXES = [0.30, 0.35, 0.40, 0.45, 0.50]
GAME_TIME_MINS = [600, 900, 1200, 1500]


def run_entry_quality_report(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    live_settled_path: Path = DEFAULT_LIVE_SETTLED_PATH,
    include_live: bool = False,
    min_trades: int = DEFAULT_MIN_TRADES,
) -> dict[str, Any]:
    rows = _load_backtest_rows(
        executable_path=executable_path,
        live_settled_path=live_settled_path,
        include_live=include_live,
    )
    scored = prepare_entry_quality_frame(rows=rows, executable_path=executable_path)
    baseline_entries = active_entries_for_filter(scored, lambda frame: pd.Series(True, index=frame.index))
    baseline = trade_metrics(baseline_entries)
    agreement = agreement_diagnostics(rows=rows, executable_path=executable_path)
    return {
        "strategy": ACTIVE_MARKET_ANCHOR_SPECS[0].model_name,
        "entry_threshold": float(ACTIVE_MARKET_ANCHOR_SPECS[0].entry_threshold),
        "include_live": bool(include_live),
        "input_rows": int(len(rows)),
        "decision_rows": int(len(scored)),
        "min_trades": int(min_trades),
        "baseline": baseline,
        "buckets": bucket_diagnostics(baseline_entries),
        "candidates": candidate_grid(scored, baseline_pnl=baseline["pnl_2c"], min_trades=min_trades),
        "agreement": agreement,
    }


def prepare_entry_quality_frame(*, rows: pd.DataFrame, executable_path: Path) -> pd.DataFrame:
    scored = _score_active_strategy_rows(rows=rows, executable_path=executable_path)
    scored = _add_map_exposure_id(scored)
    for col in [
        "book_best_ask",
        "edge",
        "game_time_sec",
        "side_mom_100",
        "side_mom_300",
        "side_kill_mom",
    ]:
        if col in scored.columns:
            scored[f"{col}_num"] = pd.to_numeric(scored[col], errors="coerce")
        else:
            scored[f"{col}_num"] = np.nan
    return scored


def active_entries_for_filter(scored: pd.DataFrame, filter_fn: Callable[[pd.DataFrame], pd.Series]) -> pd.DataFrame:
    spec = ACTIVE_MARKET_ANCHOR_SPECS[0]
    filter_mask = filter_fn(scored).fillna(False).astype(bool)
    signal = scored[
        scored["active_backtest_tradable"].fillna(False).astype(bool)
        & strategy_filter_mask(scored, spec)
        & (scored["edge_num"] >= spec.entry_threshold)
        & filter_mask
    ].copy()
    if signal.empty:
        return signal
    signal = signal.sort_values(["map_exposure_id", "received_at_ns"])
    trades = signal.drop_duplicates(["map_exposure_id"], keep="first").reset_index(drop=True)
    return trades[trades["settled_win"].notna()].copy()


def trade_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "matches": 0,
            "win_rate": None,
            "avg_ask": None,
            "pnl_2c": 0.0,
            "worst_trade": None,
        }
    ask = pd.to_numeric(trades["book_best_ask"], errors="coerce")
    wins = trades["settled_win"].fillna(False).astype(bool)
    pnl = pd.Series([1.0 - (price + 0.02) if win else -(price + 0.02) for price, win in zip(ask, wins, strict=False)])
    return {
        "trades": int(len(trades)),
        "matches": int(trades["match_id"].nunique()) if "match_id" in trades.columns else 0,
        "win_rate": float(wins.mean()) if len(trades) else None,
        "avg_ask": None if ask.dropna().empty else float(ask.mean()),
        "pnl_2c": float(pnl.sum()),
        "worst_trade": None if pnl.empty else float(pnl.min()),
    }


def bucket_diagnostics(entries: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    return {
        "edge": bucket_rows(entries, "edge_num", edge_bucket),
        "ask": bucket_rows(entries, "book_best_ask_num", ask_bucket),
        "game_time": bucket_rows(entries, "game_time_sec_num", game_time_bucket),
        "side_mom_100": bucket_rows(entries, "side_mom_100_num", sign_bucket),
        "side_mom_300": bucket_rows(entries, "side_mom_300_num", sign_bucket),
        "side_kill_mom": bucket_rows(entries, "side_kill_mom_num", sign_bucket),
    }


def bucket_rows(frame: pd.DataFrame, value_col: str, label_fn: Callable[[float], str]) -> list[dict[str, Any]]:
    if frame.empty or value_col not in frame.columns:
        return []
    work = frame.copy()
    values = pd.to_numeric(work[value_col], errors="coerce")
    work = work[values.notna()].copy()
    if work.empty:
        return []
    work["_bucket"] = values[values.notna()].map(label_fn)
    rows = []
    for bucket, sub in work.groupby("_bucket", sort=False, dropna=False):
        row = {"bucket": str(bucket)}
        row.update(trade_metrics(sub))
        rows.append(row)
    return rows


def candidate_grid(scored: pd.DataFrame, *, baseline_pnl: float, min_trades: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for edge_min in EDGE_MINS:
        candidates.append(candidate_row(scored, f"edge>={edge_min:.2f}", baseline_pnl, min_trades, lambda frame, value=edge_min: frame["edge_num"] >= value))
    for ask_max in ASK_MAXES:
        candidates.append(candidate_row(scored, f"ask<={ask_max:.2f}", baseline_pnl, min_trades, lambda frame, value=ask_max: frame["book_best_ask_num"] <= value))
    for game_min in GAME_TIME_MINS:
        candidates.append(candidate_row(scored, f"game_time>={game_min}", baseline_pnl, min_trades, lambda frame, value=game_min: frame["game_time_sec_num"] >= value))
    for edge_min in EDGE_MINS:
        for ask_max in ASK_MAXES:
            candidates.append(
                candidate_row(
                    scored,
                    f"edge>={edge_min:.2f} ask<={ask_max:.2f}",
                    baseline_pnl,
                    min_trades,
                    lambda frame, edge=edge_min, ask=ask_max: (frame["edge_num"] >= edge) & (frame["book_best_ask_num"] <= ask),
                )
            )
    for edge_min in EDGE_MINS:
        for game_min in GAME_TIME_MINS:
            candidates.append(
                candidate_row(
                    scored,
                    f"edge>={edge_min:.2f} game_time>={game_min}",
                    baseline_pnl,
                    min_trades,
                    lambda frame, edge=edge_min, game=game_min: (frame["edge_num"] >= edge) & (frame["game_time_sec_num"] >= game),
                )
            )
    return sorted(candidates, key=lambda row: (row["recommendation"] == "promote_candidate", row["pnl_2c"]), reverse=True)


def candidate_row(
    scored: pd.DataFrame,
    name: str,
    baseline_pnl: float,
    min_trades: int,
    filter_fn: Callable[[pd.DataFrame], pd.Series],
) -> dict[str, Any]:
    entries = active_entries_for_filter(scored, filter_fn)
    metrics = trade_metrics(entries)
    metrics["filter"] = name
    metrics["delta_vs_baseline"] = float(metrics["pnl_2c"] - baseline_pnl)
    metrics["recommendation"] = (
        "promote_candidate"
        if metrics["trades"] >= min_trades and metrics["pnl_2c"] > baseline_pnl
        else "keep_active"
    )
    return metrics


def agreement_diagnostics(*, rows: pd.DataFrame, executable_path: Path) -> list[dict[str, Any]]:
    bundle = train_paper_model_bundle(executable_path=executable_path)
    decisions = score_paper_decisions(rows, bundle, eligibility_mode=HISTORICAL_RESEARCH_ELIGIBILITY_MODE)
    trades = first_signal_trades(decisions)
    if trades.empty or "exposure_signal_group" not in trades.columns:
        return []
    out: list[dict[str, Any]] = []
    for group, sub in trades.groupby("exposure_signal_group", dropna=False):
        row = {"exposure_signal_group": str(group)}
        row.update(decision_trade_metrics(sub))
        out.append(row)
    return sorted(out, key=lambda row: row["pnl_2c"], reverse=True)


def decision_trade_metrics(trades: pd.DataFrame) -> dict[str, Any]:
    settled = trades[trades["settled_win"].notna()].copy() if "settled_win" in trades.columns else trades.iloc[0:0].copy()
    if settled.empty:
        return {"trades": int(len(trades)), "settled": 0, "win_rate": None, "avg_ask": None, "pnl_2c": 0.0}
    wins = settled["settled_win"].fillna(False).astype(bool)
    ask = pd.to_numeric(settled["ask"], errors="coerce")
    pnl = pd.to_numeric(settled["pnl_slip_2c"], errors="coerce")
    return {
        "trades": int(len(trades)),
        "settled": int(len(settled)),
        "win_rate": float(wins.mean()),
        "avg_ask": None if ask.dropna().empty else float(ask.mean()),
        "pnl_2c": float(pnl.sum()),
    }


def format_entry_quality_report(result: dict[str, Any], *, output_format: str = "markdown") -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True)
    lines = [
        "# Entry Quality Report",
        "",
        f"- strategy: {result['strategy']}",
        f"- entry threshold: {result['entry_threshold']}",
        f"- include live: {result['include_live']}",
        f"- input rows: {result['input_rows']}",
        f"- min trades: {result['min_trades']}",
        "",
        "## Baseline",
        "",
        metrics_table([{"name": "active", **result["baseline"]}], name_col="name"),
        "",
        "## Buckets",
    ]
    for title, rows in result["buckets"].items():
        lines.extend(["", f"### {title}", "", metrics_table(rows, name_col="bucket")])
    lines.extend(
        [
            "",
            "## Candidate Filters",
            "",
            candidate_table(result["candidates"][:25]),
            "",
            "## Agreement",
            "",
            agreement_table(result["agreement"]),
        ]
    )
    return "\n".join(lines)


def metrics_table(rows: list[dict[str, Any]], *, name_col: str) -> str:
    lines = [
        f"| {name_col} | trades | matches | win | avg ask | pnl 2c | worst |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get(name_col, "")),
                    str(row.get("trades", 0)),
                    str(row.get("matches", 0)),
                    _pct(row.get("win_rate")),
                    _num(row.get("avg_ask")),
                    _signed(row.get("pnl_2c")),
                    _signed(row.get("worst_trade")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def candidate_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| filter | trades | win | avg ask | pnl 2c | delta | recommendation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["filter"],
                    str(row["trades"]),
                    _pct(row["win_rate"]),
                    _num(row["avg_ask"]),
                    _signed(row["pnl_2c"]),
                    _signed(row["delta_vs_baseline"]),
                    row["recommendation"],
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def agreement_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| exposure group | trades | settled | win | avg ask | pnl 2c |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["exposure_signal_group"],
                    str(row["trades"]),
                    str(row["settled"]),
                    _pct(row["win_rate"]),
                    _num(row["avg_ask"]),
                    _signed(row["pnl_2c"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def add_entry_quality_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--live-settled-path", default=str(DEFAULT_LIVE_SETTLED_PATH))
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--min-trades", type=int, default=DEFAULT_MIN_TRADES)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")


def edge_bucket(value: float) -> str:
    if value < 0.10:
        return "0.05-0.10"
    if value < 0.15:
        return "0.10-0.15"
    if value < 0.20:
        return "0.15-0.20"
    return ">=0.20"


def ask_bucket(value: float) -> str:
    if value < 0.30:
        return "0.20-0.30"
    if value < 0.40:
        return "0.30-0.40"
    return "0.40-0.50"


def game_time_bucket(value: float) -> str:
    if value < 900:
        return "600-900"
    if value < 1200:
        return "900-1200"
    if value < 1800:
        return "1200-1800"
    return ">=1800"


def sign_bucket(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "zero"


def _pct(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.4f}"


def _signed(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.4f}"
