"""Research-only exit backtest for the active paper strategy."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
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
from .paper_strategy_logger import EXECUTABLE_BACKTEST_PATH, strategy_filter_mask
from .strategy_contract import ACTIVE_MARKET_ANCHOR_SPECS


ENTRY_SLIPPAGE = 0.02
EXIT_SLIPPAGE = 0.01
EXIT_ROUND_TRIP_COST = ENTRY_SLIPPAGE + EXIT_SLIPPAGE
DEFAULT_MIN_HOLD_SEC = "0"


@dataclass(frozen=True)
class ExitPolicy:
    name: str
    predicate: Callable[[pd.DataFrame, pd.Series], pd.DataFrame]


def run_exit_backtest(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    live_settled_path: Path = DEFAULT_LIVE_SETTLED_PATH,
    include_live: bool = False,
    min_hold_sec_values: list[int] | None = None,
) -> dict[str, Any]:
    """Backtest fixed sell-at-bid exit policies against hold-to-settlement."""
    min_hold_sec_values = min_hold_sec_values or [0]
    rows = _load_backtest_rows(
        executable_path=executable_path,
        live_settled_path=live_settled_path,
        include_live=include_live,
    )
    scored = prepare_exit_research_frame(rows=rows, executable_path=executable_path)
    entries = active_entry_rows(scored)
    scenarios = [
        summarize_exit_policies(scored=scored, entries=entries, min_hold_sec=min_hold_sec)
        for min_hold_sec in min_hold_sec_values
    ]
    return {
        "strategy": ACTIVE_MARKET_ANCHOR_SPECS[0].model_name,
        "entry_threshold": float(ACTIVE_MARKET_ANCHOR_SPECS[0].entry_threshold),
        "include_live": bool(include_live),
        "input_rows": int(len(rows)),
        "decision_rows": int(len(scored)),
        "entry_rows": int(len(entries)),
        "settled_entry_rows": int(entries["settled_win"].notna().sum()) if "settled_win" in entries.columns else 0,
        "scenarios": scenarios,
    }


def prepare_exit_research_frame(*, rows: pd.DataFrame, executable_path: Path) -> pd.DataFrame:
    scored = _score_active_strategy_rows(rows=rows, executable_path=executable_path)
    scored = _add_map_exposure_id(scored)
    for col in [
        "received_at_ns",
        "book_best_bid",
        "book_best_ask",
        "edge",
        "side_mom_100",
        "side_mom_300",
        "game_time_sec",
    ]:
        if col in scored.columns:
            scored[f"{col}_num"] = pd.to_numeric(scored[col], errors="coerce")
        else:
            scored[f"{col}_num"] = np.nan
    return scored


def active_entry_rows(scored: pd.DataFrame) -> pd.DataFrame:
    spec = ACTIVE_MARKET_ANCHOR_SPECS[0]
    signal = scored[
        scored["active_backtest_tradable"].fillna(False).astype(bool)
        & strategy_filter_mask(scored, spec)
        & (scored["edge_num"] >= spec.entry_threshold)
    ].copy()
    if signal.empty:
        return signal
    signal = signal.sort_values(["map_exposure_id", "received_at_ns_num"])
    entries = signal.drop_duplicates(["map_exposure_id"], keep="first").reset_index(drop=True)
    return entries[entries["settled_win"].notna()].copy()


def summarize_exit_policies(*, scored: pd.DataFrame, entries: pd.DataFrame, min_hold_sec: int) -> dict[str, Any]:
    policies = exit_policies()
    hold_rows = [simulate_entry(scored, entry, policies["hold"], min_hold_sec=min_hold_sec) for _, entry in entries.iterrows()]
    hold_pnl = float(sum(row["realized_pnl"] for row in hold_rows))
    policy_rows = []
    for policy in policies.values():
        rows = [simulate_entry(scored, entry, policy, min_hold_sec=min_hold_sec) for _, entry in entries.iterrows()]
        policy_rows.append(summarize_policy_rows(policy.name, rows, hold_pnl))
    return {
        "min_hold_sec": int(min_hold_sec),
        "entries": int(len(entries)),
        "hold_pnl_2c": hold_pnl,
        "policies": policy_rows,
    }


def exit_policies() -> dict[str, ExitPolicy]:
    return {
        "hold": ExitPolicy("hold", lambda future, entry: future.iloc[0:0]),
        "edge_lt_0": ExitPolicy("edge_lt_0", lambda future, entry: future[future["edge_num"] < 0]),
        "edge_below_entry_by_05": ExitPolicy(
            "edge_below_entry_by_05",
            lambda future, entry: future[future["edge_num"] < float(entry["edge_num"]) - 0.05],
        ),
        "edge_below_entry_by_10": ExitPolicy(
            "edge_below_entry_by_10",
            lambda future, entry: future[future["edge_num"] < float(entry["edge_num"]) - 0.10],
        ),
        "edge_below_entry_by_15": ExitPolicy(
            "edge_below_entry_by_15",
            lambda future, entry: future[future["edge_num"] < float(entry["edge_num"]) - 0.15],
        ),
        "bid_down_10c": ExitPolicy(
            "bid_down_10c",
            lambda future, entry: future[future["book_best_bid_num"] <= float(entry["book_best_ask_num"]) - 0.10],
        ),
        "bid_down_15c": ExitPolicy(
            "bid_down_15c",
            lambda future, entry: future[future["book_best_bid_num"] <= float(entry["book_best_ask_num"]) - 0.15],
        ),
        "bid_down_20c": ExitPolicy(
            "bid_down_20c",
            lambda future, entry: future[future["book_best_bid_num"] <= float(entry["book_best_ask_num"]) - 0.20],
        ),
        "take_profit_15c": ExitPolicy(
            "take_profit_15c",
            lambda future, entry: future[future["book_best_bid_num"] >= float(entry["book_best_ask_num"]) + 0.15],
        ),
        "take_profit_20c": ExitPolicy(
            "take_profit_20c",
            lambda future, entry: future[future["book_best_bid_num"] >= float(entry["book_best_ask_num"]) + 0.20],
        ),
        "take_profit_25c": ExitPolicy(
            "take_profit_25c",
            lambda future, entry: future[future["book_best_bid_num"] >= float(entry["book_best_ask_num"]) + 0.25],
        ),
        "late_mom100_neg_bid70": ExitPolicy(
            "late_mom100_neg_bid70",
            _late_momentum_exit(min_game_time_sec=1200, min_bid=0.70),
        ),
        "late_mom100_mom300_neg_bid70": ExitPolicy(
            "late_mom100_mom300_neg_bid70",
            _late_momentum_exit(min_game_time_sec=1200, min_bid=0.70, require_mom300_negative=True),
        ),
        "late_mom100_mom300_neg_bid80_after2700": ExitPolicy(
            "late_mom100_mom300_neg_bid80_after2700",
            _late_momentum_exit(min_game_time_sec=2700, min_bid=0.80, require_mom300_negative=True),
        ),
        "mom100_negative": ExitPolicy(
            "mom100_negative",
            lambda future, entry: future[future["side_mom_100_num"] < 0],
        ),
        "mom100_and_mom300_negative": ExitPolicy(
            "mom100_and_mom300_negative",
            lambda future, entry: future[(future["side_mom_100_num"] < 0) & (future["side_mom_300_num"] < 0)],
        ),
    }


def _late_momentum_exit(
    *,
    min_game_time_sec: float,
    min_bid: float,
    require_mom300_negative: bool = False,
) -> Callable[[pd.DataFrame, pd.Series], pd.DataFrame]:
    def predicate(future: pd.DataFrame, entry: pd.Series) -> pd.DataFrame:
        condition = (
            (future["game_time_sec_num"] >= min_game_time_sec)
            & (future["side_mom_100_num"] < 0)
            & (future["book_best_bid_num"] >= min_bid)
        )
        if require_mom300_negative:
            condition &= future["side_mom_300_num"] < 0
        return future[condition]

    return predicate


def simulate_entry(scored: pd.DataFrame, entry: pd.Series, policy: ExitPolicy, *, min_hold_sec: int) -> dict[str, Any]:
    hold_pnl = hold_settlement_pnl(entry)
    future = future_exit_rows(scored, entry, min_hold_sec=min_hold_sec)
    hit = policy.predicate(future, entry)
    if hit.empty:
        return {
            "policy": policy.name,
            "exited": False,
            "settled_win": _bool_or_none(entry.get("settled_win")),
            "hold_pnl_2c": hold_pnl,
            "realized_pnl": hold_pnl,
            "exit_bid": None,
        }
    exit_row = hit.iloc[0]
    exit_bid = float(exit_row["book_best_bid_num"])
    realized = exit_bid - float(entry["book_best_ask_num"]) - EXIT_ROUND_TRIP_COST
    return {
        "policy": policy.name,
        "exited": True,
        "settled_win": _bool_or_none(entry.get("settled_win")),
        "hold_pnl_2c": hold_pnl,
        "realized_pnl": realized,
        "exit_bid": exit_bid,
    }


def future_exit_rows(scored: pd.DataFrame, entry: pd.Series, *, min_hold_sec: int) -> pd.DataFrame:
    min_ns = float(entry["received_at_ns_num"]) + min_hold_sec * 1_000_000_000
    future = scored[
        (scored["map_exposure_id"].astype(str) == str(entry["map_exposure_id"]))
        & (scored["received_at_ns_num"] > min_ns)
        & scored["book_best_bid_num"].notna()
    ].copy()
    token_id = entry.get("token_id")
    if token_id is not None and not pd.isna(token_id):
        future = future[future["token_id"].astype(str) == str(token_id)]
    else:
        future = future[future["side"].astype(str) == str(entry.get("side"))]
    return future.sort_values("received_at_ns_num").reset_index(drop=True)


def hold_settlement_pnl(entry: pd.Series) -> float:
    ask = float(entry["book_best_ask_num"])
    win = bool(entry["settled_win"])
    return 1.0 - ask - ENTRY_SLIPPAGE if win else -(ask + ENTRY_SLIPPAGE)


def summarize_policy_rows(policy_name: str, rows: list[dict[str, Any]], hold_pnl: float) -> dict[str, Any]:
    frame = pd.DataFrame(rows)
    exited = frame["exited"].fillna(False).astype(bool) if not frame.empty else pd.Series(dtype=bool)
    wins = frame["settled_win"].fillna(False).astype(bool) if not frame.empty else pd.Series(dtype=bool)
    realized = pd.to_numeric(frame["realized_pnl"], errors="coerce") if not frame.empty else pd.Series(dtype=float)
    exit_bid = pd.to_numeric(frame["exit_bid"], errors="coerce") if "exit_bid" in frame.columns else pd.Series(dtype=float)
    pnl = float(realized.sum()) if not realized.empty else 0.0
    return {
        "policy": policy_name,
        "entries": int(len(frame)),
        "exited_trades": int(exited.sum()),
        "held_trades": int((~exited).sum()) if not frame.empty else 0,
        "winners_exited": int((exited & wins).sum()) if not frame.empty else 0,
        "losers_exited": int((exited & ~wins).sum()) if not frame.empty else 0,
        "avg_exit_bid": None if exit_bid.dropna().empty else float(exit_bid.dropna().mean()),
        "realized_pnl": pnl,
        "hold_pnl_2c": hold_pnl,
        "delta_vs_hold": pnl - hold_pnl,
        "worst_trade": None if realized.dropna().empty else float(realized.min()),
        "recommendation": "promote_candidate" if policy_name != "hold" and pnl > hold_pnl else "keep_hold",
    }


def format_exit_backtest(result: dict[str, Any], *, output_format: str = "markdown") -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True)
    lines = [
        "# Exit Backtest",
        "",
        f"- strategy: {result['strategy']}",
        f"- entry threshold: {result['entry_threshold']}",
        f"- include live: {result['include_live']}",
        f"- input rows: {result['input_rows']}",
        f"- active entries: {result['settled_entry_rows']}",
    ]
    for scenario in result["scenarios"]:
        lines.extend(
            [
                "",
                f"## Min Hold {scenario['min_hold_sec']}s",
                "",
                f"- hold PnL 2c: {_signed(scenario['hold_pnl_2c'])}",
                "",
                "| policy | entries | exited | held | winners exited | losers exited | avg exit bid | pnl | delta | worst | recommendation |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for row in scenario["policies"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        row["policy"],
                        str(row["entries"]),
                        str(row["exited_trades"]),
                        str(row["held_trades"]),
                        str(row["winners_exited"]),
                        str(row["losers_exited"]),
                        _num(row["avg_exit_bid"]),
                        _signed(row["realized_pnl"]),
                        _signed(row["delta_vs_hold"]),
                        _signed(row["worst_trade"]),
                        row["recommendation"],
                    ]
                )
                + " |"
            )
    return "\n".join(lines)


def add_backtest_exit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--live-settled-path", default=str(DEFAULT_LIVE_SETTLED_PATH))
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--min-hold-sec", default=DEFAULT_MIN_HOLD_SEC)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")


def parse_min_hold_values(raw: str) -> list[int]:
    values = [int(part.strip()) for part in str(raw).split(",") if part.strip()]
    if not values:
        raise ValueError("min-hold-sec cannot be empty")
    if any(value < 0 for value in values):
        raise ValueError("min-hold-sec values must be non-negative")
    return values


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


def _num(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.4f}"


def _signed(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.4f}"
