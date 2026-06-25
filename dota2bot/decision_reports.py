"""Settle and report paper strategy decision ledgers."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .schemas import DECISION_COLUMNS


DEFAULT_DECISION_NAME = "strategy_decisions"
DEFAULT_SETTLED_SIDE_NAME = "live_settled_side_snapshots"
DEFAULT_SETTLED_DECISION_NAME = "settled_strategy_decisions"
CANDIDATE_PRIORITY = {
    "primary": 0,
    "benchmark": 1,
    "full_state_benchmark": 1,
    "control": 2,
}


def run_settle_decisions(
    *,
    logs_root: Path = Path("logs"),
    decisions_name: str = DEFAULT_DECISION_NAME,
    settled_side_name: str = DEFAULT_SETTLED_SIDE_NAME,
    output_name: str = DEFAULT_SETTLED_DECISION_NAME,
) -> dict[str, Any]:
    decisions = _read_parquet_dir(logs_root / decisions_name)
    if decisions.empty:
        return {"decision_rows": 0, "settled_rows": 0, "signal_rows": 0, "output_path": None}
    sides = _read_latest_or_dir(logs_root / settled_side_name)
    if sides.empty:
        return {"decision_rows": int(len(decisions)), "settled_rows": 0, "signal_rows": 0, "output_path": None}

    for col in DECISION_COLUMNS:
        if col not in decisions.columns:
            decisions[col] = None
    join_cols = ["match_id", "market_id", "token_id", "received_at_ns"]
    side_cols = join_cols + ["settled_win", "hold_to_settlement_pnl_per_share"]
    available_side_cols = [col for col in side_cols if col in sides.columns]
    for col in join_cols:
        if col in decisions.columns:
            decisions[col] = decisions[col].astype("string")
        if col in sides.columns:
            sides[col] = sides[col].astype("string")
    merged = decisions.merge(
        sides[available_side_cols].drop_duplicates(join_cols, keep="first"),
        on=join_cols,
        how="left",
        suffixes=("", "_side"),
    )
    if "settled_win_side" in merged.columns:
        missing = merged["settled_win"].isna()
        merged.loc[missing, "settled_win"] = merged.loc[missing, "settled_win_side"]
        merged = merged.drop(columns=["settled_win_side"])

    for col in ["paper_pnl_per_share", "pnl_slip_1c", "pnl_slip_2c"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").astype("float64")
    signal = merged["signal"].fillna(False).astype(bool)
    ask = pd.to_numeric(merged["ask"], errors="coerce")
    settled = merged["settled_win"].map(_bool_or_none)
    settled_mask = settled.notna()
    pnl_mask = signal & settled_mask
    if pnl_mask.any():
        merged.loc[pnl_mask, "paper_pnl_per_share"] = _pnl(ask[pnl_mask], settled[pnl_mask], 0.0)
        merged.loc[pnl_mask, "pnl_slip_1c"] = _pnl(ask[pnl_mask], settled[pnl_mask], 0.01)
        merged.loc[pnl_mask, "pnl_slip_2c"] = _pnl(ask[pnl_mask], settled[pnl_mask], 0.02)
    if "hold_to_settlement_pnl_per_share" in merged.columns:
        merged = merged.drop(columns=["hold_to_settlement_pnl_per_share"])

    out = _add_signal_group_columns(merged)[DECISION_COLUMNS].copy()
    out_dir = logs_root / output_name
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "latest.parquet"
    out.to_parquet(output_path, index=False, compression="zstd")
    settled_decisions = out["settled_win"].notna()
    return {
        "decision_rows": int(len(out)),
        "settled_rows": int(settled_decisions.sum()),
        "signal_rows": int(signal.sum()),
        "settled_signal_rows": int((signal & settled_decisions).sum()),
        "output_path": str(output_path),
    }


def run_report_decisions(
    *,
    logs_root: Path = Path("logs"),
    decisions_name: str = DEFAULT_SETTLED_DECISION_NAME,
    output_format: str = "markdown",
) -> str:
    decisions = _read_latest_or_dir(logs_root / decisions_name)
    if decisions.empty and decisions_name == DEFAULT_SETTLED_DECISION_NAME:
        decisions = _read_parquet_dir(logs_root / DEFAULT_DECISION_NAME)
    summary = summarize_decisions(decisions)
    if output_format == "json":
        return json.dumps(summary, indent=2, sort_keys=True)
    return _format_markdown(summary)


def run_settle_decisions_loop(
    *,
    logs_root: Path = Path("logs"),
    decisions_name: str = DEFAULT_DECISION_NAME,
    settled_side_name: str = DEFAULT_SETTLED_SIDE_NAME,
    output_name: str = DEFAULT_SETTLED_DECISION_NAME,
    interval_sec: float = 120.0,
) -> None:
    while True:
        result = run_settle_decisions(
            logs_root=logs_root,
            decisions_name=decisions_name,
            settled_side_name=settled_side_name,
            output_name=output_name,
        )
        print(result, flush=True)
        time.sleep(interval_sec)


def summarize_decisions(decisions: pd.DataFrame) -> dict[str, Any]:
    if decisions.empty:
        return {
            "rows": 0,
            "signal_rows": 0,
            "trade_rows": 0,
            "global_trade_rows": 0,
            "settled_rows": 0,
            "settled_signal_rows": 0,
            "global_settled_signal_rows": 0,
            "models": [],
            "signal_groups": [],
            "global_exposure": {},
        }
    decisions = _add_signal_group_columns(decisions)
    signal = decisions["signal"].fillna(False).astype(bool) if "signal" in decisions.columns else pd.Series(False, index=decisions.index)
    settled = decisions["settled_win"].notna() if "settled_win" in decisions.columns else pd.Series(False, index=decisions.index)
    trades = first_signal_trades(decisions)
    global_trades = first_global_signal_trades(_exclude_control_decisions(decisions))
    global_settled_trades = global_trades[global_trades["settled_win"].notna()].copy() if not global_trades.empty else global_trades
    global_wins = global_settled_trades["settled_win"].map(_bool_or_none).fillna(False).astype(bool) if not global_settled_trades.empty else pd.Series(dtype=bool)
    rows: list[dict[str, Any]] = []
    for model_name, sub in decisions.groupby("model_name", dropna=False):
        sub_signal = sub["signal"].fillna(False).astype(bool)
        model_trades = trades[trades["model_name"].astype(str) == str(model_name)].copy()
        settled_trades = model_trades[model_trades["settled_win"].notna()].copy()
        wins = settled_trades["settled_win"].map(_bool_or_none).fillna(False).astype(bool)
        row = {
            "model_name": str(model_name),
            "decision_rows": int(len(sub)),
            "signal_rows": int(sub_signal.sum()),
            "trade_rows": int(len(model_trades)),
            "pending_trade_rows": int(model_trades["settled_win"].isna().sum()) if not model_trades.empty else 0,
            "settled_signal_rows": int(len(settled_trades)),
            "win_rate": float(wins.mean()) if len(settled_trades) else None,
            "avg_ask": float(pd.to_numeric(settled_trades["ask"], errors="coerce").mean()) if len(settled_trades) else None,
            "paper_pnl": _sum_or_none(settled_trades, "paper_pnl_per_share"),
            "pnl_slip_1c": _sum_or_none(settled_trades, "pnl_slip_1c"),
            "pnl_slip_2c": _sum_or_none(settled_trades, "pnl_slip_2c"),
        }
        rows.append(row)
    group_rows: list[dict[str, Any]] = []
    group_col = "exposure_signal_group" if "exposure_signal_group" in trades.columns else "signal_group"
    if group_col in decisions.columns:
        for group, sub in trades.groupby(group_col, dropna=False):
            group_rows.append(
                {
                    "signal_group": str(group),
                    "trade_rows": int(len(sub)),
                    "settled_signal_rows": int(sub["settled_win"].notna().sum()) if "settled_win" in sub.columns else 0,
                    "pnl_slip_1c": _sum_or_none(sub[sub["settled_win"].notna()], "pnl_slip_1c")
                    if "settled_win" in sub.columns
                    else None,
                }
            )
    return {
        "rows": int(len(decisions)),
        "signal_rows": int(signal.sum()),
        "trade_rows": int(len(trades)),
        "global_trade_rows": int(len(global_trades)),
        "settled_rows": int(settled.sum()),
        "settled_signal_rows": int(trades["settled_win"].notna().sum()) if not trades.empty else 0,
        "global_settled_signal_rows": int(len(global_settled_trades)),
        "global_exposure": {
            "trade_rows": int(len(global_trades)),
            "pending_trade_rows": int(global_trades["settled_win"].isna().sum()) if not global_trades.empty else 0,
            "settled_signal_rows": int(len(global_settled_trades)),
            "win_rate": float(global_wins.mean()) if len(global_settled_trades) else None,
            "avg_ask": float(pd.to_numeric(global_settled_trades["ask"], errors="coerce").mean()) if len(global_settled_trades) else None,
            "paper_pnl": _sum_or_none(global_settled_trades, "paper_pnl_per_share"),
            "pnl_slip_1c": _sum_or_none(global_settled_trades, "pnl_slip_1c"),
            "pnl_slip_2c": _sum_or_none(global_settled_trades, "pnl_slip_2c"),
        },
        "models": sorted(rows, key=lambda row: (row["pnl_slip_1c"] is not None, row["pnl_slip_1c"] or 0), reverse=True),
        "signal_groups": sorted(group_rows, key=lambda row: row["trade_rows"], reverse=True),
    }


def first_signal_trades(decisions: pd.DataFrame) -> pd.DataFrame:
    """Collapse repeated signal snapshots to first paper trade per model/map."""
    if decisions.empty or "signal" not in decisions.columns:
        return decisions.iloc[0:0].copy()
    signal = decisions[decisions["signal"].fillna(False).astype(bool)].copy()
    if signal.empty:
        return signal
    signal = _add_map_exposure_id(signal)
    sort_cols = [col for col in ["model_name", "map_exposure_id", "received_at_ns"] if col in signal.columns]
    signal = signal.sort_values(sort_cols)
    return signal.drop_duplicates(["model_name", "map_exposure_id"], keep="first").reset_index(drop=True)


def first_global_signal_trades(decisions: pd.DataFrame) -> pd.DataFrame:
    """Collapse repeated and overlapping non-control model signals to one map trade."""
    if decisions.empty or "signal" not in decisions.columns:
        return decisions.iloc[0:0].copy()
    signal = decisions[decisions["signal"].fillna(False).astype(bool)].copy()
    if signal.empty:
        return signal
    signal = _add_map_exposure_id(signal)
    signal["_candidate_priority"] = _candidate_priority(signal)
    sort_cols = [
        col
        for col in ["map_exposure_id", "received_at_ns", "_candidate_priority", "decision_id"]
        if col in signal.columns
    ]
    signal = signal.sort_values(sort_cols)
    return signal.drop_duplicates(["map_exposure_id"], keep="first").drop(columns=["_candidate_priority"], errors="ignore").reset_index(drop=True)


def _exclude_control_decisions(decisions: pd.DataFrame) -> pd.DataFrame:
    if decisions.empty or "candidate_group" not in decisions.columns:
        return decisions
    candidate_group = decisions["candidate_group"].astype("string").fillna("")
    return decisions[candidate_group.str.lower() != "control"].copy()


def _add_map_exposure_id(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "current_game_number" in out.columns:
        game = out["current_game_number"].astype("string").fillna("").str.strip()
        game = game.mask(game.eq("") | game.str.lower().isin(["nan", "none", "<na>"]), "MAPEQUIV")
    else:
        game = pd.Series("MAPEQUIV", index=out.index, dtype="string")
    match_id = out["match_id"].astype(str) if "match_id" in out.columns else out["decision_id"].astype(str)
    out["map_exposure_id"] = match_id + "::" + game.astype(str)
    return out


def _add_signal_group_columns(decisions: pd.DataFrame) -> pd.DataFrame:
    if decisions.empty or "signal" not in decisions.columns:
        return decisions.copy()
    out = _add_map_exposure_id(decisions)
    if "candidate_group" not in out.columns or out["candidate_group"].isna().all():
        fallback = out["signal_group"] if "signal_group" in out.columns else pd.Series("no_signal", index=out.index)
        fallback = fallback.astype("string").fillna("no_signal")
        out["snapshot_signal_group"] = fallback
        out["exposure_signal_group"] = fallback
        out["signal_group"] = fallback
        return out.drop(columns=["map_exposure_id"], errors="ignore")
    out["snapshot_signal_group"] = _group_for_keys(out, ["match_id", "canonical_exposure_id", "received_at_ns", "side"])
    out["exposure_signal_group"] = _group_for_keys(out, ["match_id", "map_exposure_id"])
    out["signal_group"] = out["exposure_signal_group"]
    return out.drop(columns=["map_exposure_id"], errors="ignore")


def _group_for_keys(frame: pd.DataFrame, key_cols: list[str]) -> pd.Series:
    missing = [col for col in key_cols if col not in frame.columns]
    if missing:
        return pd.Series("no_signal", index=frame.index, dtype="string")
    signal = frame[frame["signal"].fillna(False).astype(bool)].copy()
    if signal.empty:
        return pd.Series("no_signal", index=frame.index, dtype="string")
    signal_keys = _string_key_frame(signal, key_cols)
    group_map = {}
    for key, sub_idx in signal_keys.groupby(key_cols, dropna=False).groups.items():
        sub = signal.loc[sub_idx]
        groups = set(sub.get("candidate_group", pd.Series(dtype=object)).astype("string").str.lower().dropna())
        if not isinstance(key, tuple):
            key = (key,)
        group_map[key] = _signal_group_label(groups)
    frame_keys = _string_key_frame(frame, key_cols)
    keys = frame_keys.apply(lambda row: tuple(row[col] for col in key_cols), axis=1)
    return keys.map(group_map).fillna("no_signal")


def _string_key_frame(frame: pd.DataFrame, key_cols: list[str]) -> pd.DataFrame:
    return frame[key_cols].astype("string").fillna("<NA>")


def _signal_group_label(groups: set[str]) -> str:
    groups = {group for group in groups if group and group != "<na>"}
    if not groups:
        return "no_signal"
    has_primary = "primary" in groups
    has_benchmark = bool(groups.intersection({"benchmark", "full_state_benchmark"}))
    has_control = "control" in groups
    if has_primary and has_benchmark and has_control:
        return "primary_benchmark_control"
    if has_primary and has_benchmark:
        return "primary_and_benchmark"
    if has_primary and has_control:
        return "primary_and_control"
    if has_primary:
        return "primary_only"
    if has_benchmark and has_control:
        return "benchmark_and_control"
    if has_benchmark:
        return "benchmark_only"
    if has_control:
        return "control_only"
    return "other_signal"


def _candidate_priority(frame: pd.DataFrame) -> pd.Series:
    if "candidate_group" not in frame.columns:
        return pd.Series(9, index=frame.index)
    return frame["candidate_group"].astype("string").str.lower().map(CANDIDATE_PRIORITY).fillna(9).astype(int)


def add_settle_decision_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--decisions-name", default=DEFAULT_DECISION_NAME)
    parser.add_argument("--settled-side-name", default=DEFAULT_SETTLED_SIDE_NAME)
    parser.add_argument("--output-name", default=DEFAULT_SETTLED_DECISION_NAME)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=120.0)


def add_report_decision_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--decisions-name", default=DEFAULT_SETTLED_DECISION_NAME)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")


def _format_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Decision Report",
        "",
        f"- decision rows: {summary['rows']}",
        f"- signal rows: {summary['signal_rows']}",
        f"- model map trades: {summary['trade_rows']}",
        f"- global exposure trades: {summary['global_trade_rows']}",
        f"- settled canonical trades: {summary['settled_signal_rows']}",
        f"- settled global exposure trades: {summary['global_settled_signal_rows']}",
        "",
        "## Global Exposure",
        "",
        "| trades | settled | pending | win | avg ask | pnl | pnl 1c | pnl 2c |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| "
        + " | ".join(
            [
                str(summary["global_exposure"].get("trade_rows", 0)),
                str(summary["global_exposure"].get("settled_signal_rows", 0)),
                str(summary["global_exposure"].get("pending_trade_rows", 0)),
                _pct(summary["global_exposure"].get("win_rate")),
                _num(summary["global_exposure"].get("avg_ask")),
                _signed(summary["global_exposure"].get("paper_pnl")),
                _signed(summary["global_exposure"].get("pnl_slip_1c")),
                _signed(summary["global_exposure"].get("pnl_slip_2c")),
            ]
        )
        + " |",
        "",
        "## Models",
        "",
        "| model | raw signals | trades | settled | pending | win | avg ask | pnl | pnl 1c | pnl 2c |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["models"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["model_name"],
                    str(row["signal_rows"]),
                    str(row["trade_rows"]),
                    str(row["settled_signal_rows"]),
                    str(row["pending_trade_rows"]),
                    _pct(row["win_rate"]),
                    _num(row["avg_ask"]),
                    _signed(row["paper_pnl"]),
                    _signed(row["pnl_slip_1c"]),
                    _signed(row["pnl_slip_2c"]),
                ]
            )
            + " |"
        )
    if summary["signal_groups"]:
        lines.extend(["", "## Signal Groups", "", "| group | trades | settled | pnl 1c |", "| --- | ---: | ---: | ---: |"])
        for row in summary["signal_groups"]:
            lines.append(
                f"| {row['signal_group']} | {row['trade_rows']} | {row['settled_signal_rows']} | {_signed(row['pnl_slip_1c'])} |"
            )
    return "\n".join(lines)


def _read_latest_or_dir(path: Path) -> pd.DataFrame:
    latest = path / "latest.parquet"
    if latest.exists():
        return pd.read_parquet(latest)
    return _read_parquet_dir(path)


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    con = duckdb.connect()
    return con.execute(
        "select * from read_parquet(?, union_by_name=true)",
        [str(path / "*.parquet")],
    ).fetchdf()


def _pnl(ask: pd.Series, settled: pd.Series, slippage: float) -> pd.Series:
    entry = ask + slippage
    return pd.Series(
        [1.0 - price if bool(win) else -price for price, win in zip(entry, settled, strict=False)],
        index=ask.index,
    )


def _sum_or_none(frame: pd.DataFrame, col: str) -> float | None:
    if frame.empty or col not in frame.columns:
        return None
    values = pd.to_numeric(frame[col], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.sum())


def _bool_or_none(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _pct(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.3f}"


def _signed(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.4f}"
