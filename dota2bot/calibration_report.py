"""Calibration diagnostics for the frozen paper model artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .executable_value_model import SLIPPAGE_2C
from .paper_strategy_logger import (
    DEFAULT_MODEL_ARTIFACT_DIR,
    EXECUTABLE_BACKTEST_PATH,
    HISTORICAL_RESEARCH_ELIGIBILITY_MODE,
    load_paper_model_bundle,
    prepare_paper_feature_frame,
    add_model_scores,
    strategy_filter_mask,
)


ASK_BUCKETS = [0.0, 0.20, 0.30, 0.40, 0.50, 1.0]
EDGE_BUCKETS = [-np.inf, 0.0, 0.05, 0.10, 0.15, 0.20, np.inf]
CALIBRATION_ELIGIBILITY_MODES = {HISTORICAL_RESEARCH_ELIGIBILITY_MODE, "live_executable"}


def run_paper_calibration_report(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    artifact_dir: Path = DEFAULT_MODEL_ARTIFACT_DIR,
    eligibility_mode: str = HISTORICAL_RESEARCH_ELIGIBILITY_MODE,
    output_format: str = "markdown",
) -> str:
    if eligibility_mode not in CALIBRATION_ELIGIBILITY_MODES:
        raise ValueError(f"unknown calibration eligibility_mode={eligibility_mode!r}")
    frame = pd.read_parquet(executable_path)
    bundle = load_paper_model_bundle(artifact_dir=artifact_dir)
    featured = prepare_paper_feature_frame(frame, eligibility_mode=eligibility_mode)
    rows: list[dict[str, Any]] = []
    for spec in bundle.specs:
        model, features = bundle.models[spec.model_name]
        scored = add_model_scores(featured.copy(), model, features, score_kind=bundle.score_kinds.get(spec.model_name, spec.score_kind))
        eligibility_col = "tradable_research" if eligibility_mode == HISTORICAL_RESEARCH_ELIGIBILITY_MODE else "tradable_paper"
        eligible = (
            scored["settled_win"].notna()
            & scored[eligibility_col].fillna(False).astype(bool)
            & strategy_filter_mask(scored, spec)
        )
        sub = scored[eligible].copy()
        if sub.empty:
            continue
        sub["model_name"] = spec.model_name
        sub["ask"] = pd.to_numeric(sub["book_best_ask"], errors="coerce")
        sub["settled_win_bool"] = sub["settled_win"].astype(bool)
        sub["pnl_2c_if_bought"] = np.where(
            sub["settled_win_bool"],
            1.0 - sub["ask"] - SLIPPAGE_2C,
            -sub["ask"] - SLIPPAGE_2C,
        )
        sub["signal"] = sub["edge"] >= spec.entry_threshold
        sub["ask_bucket"] = pd.cut(sub["ask"], ASK_BUCKETS, include_lowest=True)
        sub["edge_bucket"] = pd.cut(pd.to_numeric(sub["edge"], errors="coerce"), EDGE_BUCKETS)
        rows.extend(_row_bucket_rows(sub, "ask_bucket"))
        rows.extend(_row_bucket_rows(sub, "edge_bucket"))
        trades = _first_signal_trades(sub)
        if not trades.empty:
            rows.extend(_trade_bucket_rows(trades, "ask_bucket"))
            rows.extend(_trade_bucket_rows(trades, "edge_bucket"))
    summary = {"eligibility_mode": eligibility_mode, "rows": rows}
    if output_format == "json":
        return json.dumps(summary, indent=2, sort_keys=True)
    return _format_markdown(summary)


def add_paper_calibration_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_MODEL_ARTIFACT_DIR))
    parser.add_argument("--eligibility-mode", choices=sorted(CALIBRATION_ELIGIBILITY_MODES), default=HISTORICAL_RESEARCH_ELIGIBILITY_MODE)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")


def _row_bucket_rows(frame: pd.DataFrame, bucket_col: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for (model_name, bucket), sub in frame.groupby(["model_name", bucket_col], observed=True, dropna=False):
        pwin = pd.to_numeric(sub["fair_prob"], errors="coerce")
        actual = sub["settled_win_bool"].astype(float)
        brier = ((pwin - actual) ** 2).mean()
        out.append(
            {
                "table": bucket_col,
                "level": "row",
                "model_name": str(model_name),
                "bucket": str(bucket),
                "rows": int(len(sub)),
                "signals": int(sub["signal"].sum()),
                "avg_ask": _mean(sub["ask"]),
                "avg_pwin": _mean(pwin),
                "actual_win_rate": _mean(actual),
                "avg_edge": _mean(pd.to_numeric(sub["edge"], errors="coerce")),
                "brier": float(brier) if not pd.isna(brier) else None,
                "pnl_2c_if_bought": float(sub["pnl_2c_if_bought"].sum()),
                "signal_pnl_2c": float(sub.loc[sub["signal"], "pnl_2c_if_bought"].sum()),
            }
        )
    return out


def _trade_bucket_rows(frame: pd.DataFrame, bucket_col: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for (model_name, bucket), sub in frame.groupby(["model_name", bucket_col], observed=True, dropna=False):
        wins = sub["settled_win_bool"].astype(float)
        out.append(
            {
                "table": f"trade_{bucket_col}",
                "level": "trade",
                "model_name": str(model_name),
                "bucket": str(bucket),
                "trades": int(len(sub)),
                "avg_ask": _mean(sub["ask"]),
                "avg_pwin": _mean(pd.to_numeric(sub["fair_prob"], errors="coerce")),
                "trade_win_rate": _mean(wins),
                "avg_edge": _mean(pd.to_numeric(sub["edge"], errors="coerce")),
                "trade_pnl_2c": float(sub["pnl_2c_if_bought"].sum()),
            }
        )
    return out


def _format_markdown(summary: dict[str, Any]) -> str:
    lines = ["# Paper Model Calibration", "", f"- eligibility: {summary.get('eligibility_mode')}", ""]
    for table_name, title in [("ask_bucket", "Row Ask Buckets"), ("edge_bucket", "Row Edge Buckets")]:
        rows = [row for row in summary["rows"] if row["table"] == table_name]
        lines.extend(
            [
                f"## {title}",
                "",
                "| model | bucket | rows | signals | avg ask | avg P(win) | actual win | avg edge | brier | pnl 2c if bought | signal pnl 2c |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        row["model_name"],
                        row["bucket"],
                        str(row["rows"]),
                        str(row["signals"]),
                        _num(row["avg_ask"]),
                        _num(row["avg_pwin"]),
                        _pct(row["actual_win_rate"]),
                        _num(row["avg_edge"]),
                        _num(row["brier"]),
                        _signed(row["pnl_2c_if_bought"]),
                        _signed(row["signal_pnl_2c"]),
                    ]
                )
                + " |"
            )
        lines.append("")
    for table_name, title in [("trade_ask_bucket", "Trade Ask Buckets"), ("trade_edge_bucket", "Trade Edge Buckets")]:
        rows = [row for row in summary["rows"] if row["table"] == table_name]
        lines.extend(
            [
                f"## {title}",
                "",
                "| model | bucket | trades | avg ask | avg P(win) | trade win | avg edge | trade pnl 2c |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in rows:
            lines.append(
                "| "
                + " | ".join(
                    [
                        row["model_name"],
                        row["bucket"],
                        str(row["trades"]),
                        _num(row["avg_ask"]),
                        _num(row["avg_pwin"]),
                        _pct(row["trade_win_rate"]),
                        _num(row["avg_edge"]),
                        _signed(row["trade_pnl_2c"]),
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def _first_signal_trades(frame: pd.DataFrame) -> pd.DataFrame:
    signal = frame[frame["signal"].fillna(False).astype(bool)].copy()
    if signal.empty:
        return signal
    game = signal["current_game_number"].astype("string").fillna("").str.strip()
    game = game.mask(game.eq("") | game.str.lower().isin(["nan", "none", "<na>"]), "MAPEQUIV")
    signal["map_exposure_id"] = signal["match_id"].astype(str) + "::" + game.astype(str)
    signal = signal.sort_values(["model_name", "map_exposure_id", "received_at_ns"])
    return signal.drop_duplicates(["model_name", "map_exposure_id"], keep="first")


def _mean(values: pd.Series) -> float | None:
    values = pd.to_numeric(values, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def _num(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.4f}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value * 100:.1f}%"


def _signed(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.4f}"
