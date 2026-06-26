"""Research-only GetTopLive state-change markout report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .active_strategy_backtest import DEFAULT_LIVE_SETTLED_PATH, _load_backtest_rows
from .paper_strategy_logger import (
    EXECUTABLE_BACKTEST_PATH,
    HISTORICAL_RESEARCH_ELIGIBILITY_MODE,
    prepare_paper_feature_frame,
)
from .strategy_contract import ACTIVE_MARKET_EQUIVALENT_SCOPES


DEFAULT_HORIZONS_SEC = [30, 60, 120, 300]
ENTRY_SLIPPAGE = 0.02
EXIT_SLIPPAGE = 0.01
ROUND_TRIP_SLIPPAGE = ENTRY_SLIPPAGE + EXIT_SLIPPAGE


EventPredicate = Callable[[pd.DataFrame], pd.Series]


def run_gettoplive_markout_report(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    live_settled_path: Path = DEFAULT_LIVE_SETTLED_PATH,
    include_live: bool = False,
    horizons_sec: list[int] | None = None,
    min_game_time_sec: int = 600,
    min_events: int = 3,
) -> dict[str, Any]:
    horizons_sec = horizons_sec or list(DEFAULT_HORIZONS_SEC)
    rows = _load_backtest_rows(
        executable_path=executable_path,
        live_settled_path=live_settled_path,
        include_live=include_live,
    )
    featured = prepare_gettoplive_markout_frame(rows)
    eligible = eligible_markout_rows(featured, min_game_time_sec=min_game_time_sec)
    events = select_gettoplive_events(eligible)
    marked = add_future_markouts(events, eligible, horizons_sec=horizons_sec)
    chronological = chronological_candidate_summary(
        marked,
        horizons_sec=horizons_sec,
        min_events=min_events,
    )
    settlement_chronological = chronological_settlement_candidate_summary(
        marked,
        min_events=min_events,
    )
    return {
        "report": "gettoplive_markout",
        "include_live": bool(include_live),
        "input_rows": int(len(rows)),
        "eligible_rows": int(len(eligible)),
        "eligible_matches": int(eligible["match_id"].nunique()) if not eligible.empty else 0,
        "event_rows": int(len(events)),
        "event_matches": int(events["match_id"].nunique()) if not events.empty else 0,
        "horizons_sec": horizons_sec,
        "min_game_time_sec": int(min_game_time_sec),
        "min_events": int(min_events),
        "event_summary": event_settlement_summary(marked, min_events=min_events),
        "horizon_summary": horizon_markout_summary(marked, horizons_sec=horizons_sec, min_events=min_events),
        "candidate_summary": candidate_filter_summary(marked, horizons_sec=horizons_sec, min_events=min_events),
        "chronological_candidate_summary": chronological,
        "chronological_candidate_details": chronological_candidate_details(marked, chronological, limit=60),
        "chronological_settlement_candidate_summary": settlement_chronological,
        "chronological_settlement_candidate_details": chronological_settlement_candidate_details(
            marked,
            settlement_chronological,
            limit=80,
        ),
        "details": event_details(marked, horizons_sec=horizons_sec, limit=25),
    }


def prepare_gettoplive_markout_frame(rows: pd.DataFrame) -> pd.DataFrame:
    frame = prepare_paper_feature_frame(rows, eligibility_mode=HISTORICAL_RESEARCH_ELIGIBILITY_MODE)
    frame = add_map_exposure_id(frame)
    numeric_cols = [
        "received_at_ns",
        "game_time_sec",
        "book_best_ask",
        "book_best_bid",
        "book_mid",
        "book_spread",
        "book_ask_size",
        "book_age_ms",
        "source_update_age_sec",
        "side_nw",
        "side_score",
        "side_mom_100",
        "side_mom_300",
        "side_kill_mom",
        "side_transition_nw_delta",
        "side_transition_kill_delta",
        "side_transition_score_delta",
        "structure_score",
    ]
    for col in numeric_cols:
        if col in frame.columns:
            frame[f"{col}_num"] = pd.to_numeric(frame[col], errors="coerce")
        else:
            frame[f"{col}_num"] = np.nan
    if "book_mid_num" not in frame.columns:
        frame["book_mid_num"] = np.nan
    frame["entry_mid_num"] = frame["book_mid_num"].where(
        frame["book_mid_num"].notna(),
        (frame["book_best_bid_num"] + frame["book_best_ask_num"]) / 2.0,
    )
    return frame


def eligible_markout_rows(frame: pd.DataFrame, *, min_game_time_sec: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    scope_ok = frame["market_scope"].isin(ACTIVE_MARKET_EQUIVALENT_SCOPES) if "market_scope" in frame.columns else False
    eligible = frame[
        frame["tradable_research"].fillna(False).astype(bool)
        & scope_ok
        & (frame["game_time_sec_num"] >= min_game_time_sec)
        & frame["received_at_ns_num"].notna()
        & frame["book_best_ask_num"].notna()
        & frame["book_best_bid_num"].notna()
    ].copy()
    return eligible.sort_values(["map_exposure_id", "canonical_exposure_id", "received_at_ns_num"]).reset_index(drop=True)


def event_predicates() -> list[tuple[str, EventPredicate]]:
    return [
        ("mom100_up_1k", lambda f: f["side_mom_100_num"] >= 1000),
        ("mom100_up_3k", lambda f: f["side_mom_100_num"] >= 3000),
        ("mom300_up_5k", lambda f: f["side_mom_300_num"] >= 5000),
        ("kill_mom_up", lambda f: f["side_kill_mom_num"] >= 1),
        ("nw_transition_up_1k", lambda f: f["side_transition_nw_delta_num"] >= 1000),
        ("nw_transition_up_3k", lambda f: f["side_transition_nw_delta_num"] >= 3000),
        ("kill_transition_up", lambda f: f["side_transition_kill_delta_num"] >= 1),
        ("confirmed_transition", lambda f: f["transition_signal_type"].astype(str).eq("confirmed_transition")),
        (
            "score_nw_catchup",
            lambda f: f["transition_signal_type"].astype(str).isin(
                ["score_then_nw_catchup", "nw_then_score_catchup"]
            ),
        ),
    ]


def select_gettoplive_events(frame: pd.DataFrame) -> pd.DataFrame:
    event_frames: list[pd.DataFrame] = []
    for event_name, predicate in event_predicates():
        mask = predicate(frame).fillna(False).astype(bool)
        sub = frame[mask].copy()
        if sub.empty:
            continue
        sub["event_name"] = event_name
        sub = sub.sort_values(["map_exposure_id", "canonical_exposure_id", "received_at_ns_num"])
        sub = sub.drop_duplicates(["map_exposure_id", "canonical_exposure_id", "event_name"], keep="first")
        event_frames.append(sub)
    if not event_frames:
        return pd.DataFrame()
    events = pd.concat(event_frames, ignore_index=True)
    events["settlement_pnl_2c"] = [
        _settlement_pnl_2c(ask, win)
        for ask, win in zip(events["book_best_ask_num"], events.get("settled_win", pd.Series([None] * len(events))), strict=False)
    ]
    return events.sort_values(["event_name", "map_exposure_id", "received_at_ns_num"]).reset_index(drop=True)


def add_future_markouts(events: pd.DataFrame, frame: pd.DataFrame, *, horizons_sec: list[int]) -> pd.DataFrame:
    out = events.copy()
    if out.empty:
        return out
    lookup: dict[tuple[str, str], pd.DataFrame] = {}
    work = frame[frame["received_at_ns_num"].notna()].copy()
    work["_token_key"] = work["token_id"].astype("string").fillna("").astype(str)
    for key, sub in work.groupby(["map_exposure_id", "_token_key"], dropna=False, sort=False):
        lookup[(str(key[0]), str(key[1]))] = sub.sort_values("received_at_ns_num").reset_index(drop=True)

    for horizon in horizons_sec:
        for col in [
            f"future_received_at_ns_{horizon}",
            f"future_bid_{horizon}",
            f"future_mid_{horizon}",
            f"future_ask_{horizon}",
            f"bid_markout_{horizon}",
            f"mid_markout_{horizon}",
            f"sell_bid_pnl_{horizon}",
        ]:
            out[col] = np.nan

    for idx, event in out.iterrows():
        key = (str(event.get("map_exposure_id")), str(event.get("token_id") or ""))
        future = lookup.get(key)
        if future is None or future.empty:
            continue
        times = future["received_at_ns_num"].to_numpy(dtype=float)
        event_ns = float(event["received_at_ns_num"])
        entry_ask = float(event["book_best_ask_num"])
        entry_mid = float(event["entry_mid_num"]) if not pd.isna(event.get("entry_mid_num")) else np.nan
        for horizon in horizons_sec:
            target = event_ns + horizon * 1_000_000_000
            pos = int(np.searchsorted(times, target, side="left"))
            if pos >= len(future):
                continue
            row = future.iloc[pos]
            future_bid = _float_or_nan(row.get("book_best_bid_num"))
            future_ask = _float_or_nan(row.get("book_best_ask_num"))
            future_mid = _float_or_nan(row.get("book_mid_num"))
            if pd.isna(future_mid) and not pd.isna(future_bid) and not pd.isna(future_ask):
                future_mid = (future_bid + future_ask) / 2.0
            out.loc[idx, f"future_received_at_ns_{horizon}"] = _float_or_nan(row.get("received_at_ns_num"))
            out.loc[idx, f"future_bid_{horizon}"] = future_bid
            out.loc[idx, f"future_mid_{horizon}"] = future_mid
            out.loc[idx, f"future_ask_{horizon}"] = future_ask
            out.loc[idx, f"bid_markout_{horizon}"] = future_bid - entry_ask if not pd.isna(future_bid) else np.nan
            out.loc[idx, f"mid_markout_{horizon}"] = future_mid - entry_mid if not pd.isna(future_mid) and not pd.isna(entry_mid) else np.nan
            out.loc[idx, f"sell_bid_pnl_{horizon}"] = future_bid - entry_ask - ROUND_TRIP_SLIPPAGE if not pd.isna(future_bid) else np.nan
    return out


def event_settlement_summary(events: pd.DataFrame, *, min_events: int) -> list[dict[str, Any]]:
    rows = []
    if events.empty:
        return rows
    for event_name, sub in events.groupby("event_name", sort=False):
        if len(sub) < min_events:
            continue
        wins = sub["settled_win"].dropna().astype(bool) if "settled_win" in sub.columns else pd.Series(dtype=bool)
        pnl = pd.to_numeric(sub["settlement_pnl_2c"], errors="coerce")
        rows.append(
            {
                "event": str(event_name),
                "events": int(len(sub)),
                "matches": int(sub["match_id"].nunique()) if "match_id" in sub.columns else 0,
                "map_exposures": int(sub["map_exposure_id"].nunique()) if "map_exposure_id" in sub.columns else 0,
                "avg_ask": _mean(sub["book_best_ask_num"]),
                "settled": int(wins.count()),
                "settlement_win_rate": None if wins.empty else float(wins.mean()),
                "settlement_pnl_2c": float(pnl.sum()),
            }
        )
    return sorted(rows, key=lambda row: row["settlement_pnl_2c"], reverse=True)


def horizon_markout_summary(events: pd.DataFrame, *, horizons_sec: list[int], min_events: int) -> list[dict[str, Any]]:
    rows = []
    if events.empty:
        return rows
    for event_name, sub in events.groupby("event_name", sort=False):
        for horizon in horizons_sec:
            pnl_col = f"sell_bid_pnl_{horizon}"
            bid_col = f"bid_markout_{horizon}"
            mid_col = f"mid_markout_{horizon}"
            if pnl_col not in sub.columns:
                continue
            usable = sub[pd.to_numeric(sub[pnl_col], errors="coerce").notna()].copy()
            if len(usable) < min_events:
                continue
            pnl = pd.to_numeric(usable[pnl_col], errors="coerce")
            bid = pd.to_numeric(usable[bid_col], errors="coerce")
            mid = pd.to_numeric(usable[mid_col], errors="coerce")
            rows.append(
                {
                    "event": str(event_name),
                    "horizon_sec": int(horizon),
                    "events_with_future": int(len(usable)),
                    "matches": int(usable["match_id"].nunique()) if "match_id" in usable.columns else 0,
                    "avg_entry_ask": _mean(usable["book_best_ask_num"]),
                    "avg_bid_markout": _mean(bid),
                    "avg_mid_markout": _mean(mid),
                    "positive_sell_rate": float((pnl > 0).mean()) if len(pnl) else None,
                    "total_sell_bid_pnl": float(pnl.sum()),
                    "avg_sell_bid_pnl": float(pnl.mean()),
                }
            )
    return sorted(rows, key=lambda row: (row["horizon_sec"], row["total_sell_bid_pnl"]), reverse=False)


def candidate_filters() -> list[tuple[str, EventPredicate]]:
    return [
        ("ask20_50_gt900", lambda f: f["book_best_ask_num"].between(0.20, 0.50) & (f["game_time_sec_num"] >= 900)),
        ("ask20_50_gt1200", lambda f: f["book_best_ask_num"].between(0.20, 0.50) & (f["game_time_sec_num"] >= 1200)),
        ("ask20_50_gt1800", lambda f: f["book_best_ask_num"].between(0.20, 0.50) & (f["game_time_sec_num"] >= 1800)),
        ("ask30_50_gt1200", lambda f: f["book_best_ask_num"].between(0.30, 0.50) & (f["game_time_sec_num"] >= 1200)),
        ("ask30_50_gt1800", lambda f: f["book_best_ask_num"].between(0.30, 0.50) & (f["game_time_sec_num"] >= 1800)),
        (
            "ask20_50_gt1800_mom100pos",
            lambda f: f["book_best_ask_num"].between(0.20, 0.50)
            & (f["game_time_sec_num"] >= 1800)
            & (f["side_mom_100_num"] >= 0),
        ),
        (
            "ask50_80_src_age5",
            lambda f: f["book_best_ask_num"].between(0.50, 0.80) & (f["source_update_age_sec_num"] <= 5),
        ),
        (
            "ask50_80_src_age5_nwpos",
            lambda f: f["book_best_ask_num"].between(0.50, 0.80)
            & (f["source_update_age_sec_num"] <= 5)
            & (f["side_nw_num"] > 0),
        ),
    ]


def candidate_filter_summary(events: pd.DataFrame, *, horizons_sec: list[int], min_events: int) -> list[dict[str, Any]]:
    rows = []
    if events.empty:
        return rows
    for event_name, event_rows in events.groupby("event_name", sort=False):
        for filter_name, predicate in candidate_filters():
            sub = event_rows[predicate(event_rows).fillna(False).astype(bool)].copy()
            if len(sub) < min_events:
                continue
            for horizon in horizons_sec:
                pnl_col = f"sell_bid_pnl_{horizon}"
                if pnl_col not in sub.columns:
                    continue
                usable = sub[pd.to_numeric(sub[pnl_col], errors="coerce").notna()].copy()
                if len(usable) < min_events:
                    continue
                pnl = pd.to_numeric(usable[pnl_col], errors="coerce")
                settlement = pd.to_numeric(usable["settlement_pnl_2c"], errors="coerce")
                rows.append(
                    {
                        "event": str(event_name),
                        "filter": filter_name,
                        "horizon_sec": int(horizon),
                        "events_with_future": int(len(usable)),
                        "matches": int(usable["match_id"].nunique()) if "match_id" in usable.columns else 0,
                        "avg_entry_ask": _mean(usable["book_best_ask_num"]),
                        "positive_sell_rate": float((pnl > 0).mean()) if len(pnl) else None,
                        "total_sell_bid_pnl": float(pnl.sum()),
                        "avg_sell_bid_pnl": float(pnl.mean()),
                        "settlement_pnl_2c": float(settlement.sum()),
                    }
                )
    return sorted(rows, key=lambda row: row["total_sell_bid_pnl"], reverse=True)


def chronological_candidate_summary(
    events: pd.DataFrame,
    *,
    horizons_sec: list[int],
    min_events: int,
    lockbox_fraction: float = 0.30,
) -> list[dict[str, Any]]:
    rows = []
    if events.empty:
        return rows
    for event_name, event_rows in events.groupby("event_name", sort=False):
        for filter_name, predicate in candidate_filters():
            sub = event_rows[predicate(event_rows).fillna(False).astype(bool)].copy()
            if len(sub) < min_events:
                continue
            trades = first_candidate_event_per_map(sub)
            if len(trades) < min_events:
                continue
            for horizon in horizons_sec:
                pnl_col = f"sell_bid_pnl_{horizon}"
                if pnl_col not in trades.columns:
                    continue
                usable = trades[pd.to_numeric(trades[pnl_col], errors="coerce").notna()].copy()
                if len(usable) < min_events:
                    continue
                dev, lockbox = chronological_match_split(usable, lockbox_fraction=lockbox_fraction)
                if dev.empty or lockbox.empty:
                    continue
                dev_metrics = strategy_metrics(dev, pnl_col=pnl_col)
                lockbox_metrics = strategy_metrics(lockbox, pnl_col=pnl_col)
                combined_metrics = strategy_metrics(usable, pnl_col=pnl_col)
                rows.append(
                    {
                        "event": str(event_name),
                        "filter": filter_name,
                        "horizon_sec": int(horizon),
                        "dev": dev_metrics,
                        "lockbox": lockbox_metrics,
                        "combined": combined_metrics,
                        "recommendation": candidate_recommendation(dev_metrics, lockbox_metrics, min_events=min_events),
                    }
                )
    return sorted(
        rows,
        key=lambda row: (
            row["recommendation"] == "research_candidate",
            row["lockbox"]["sell_bid_pnl"],
            row["combined"]["sell_bid_pnl"],
        ),
        reverse=True,
    )


def first_candidate_event_per_map(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    return (
        events.sort_values(["map_exposure_id", "received_at_ns_num", "canonical_exposure_id"])
        .drop_duplicates(["map_exposure_id"], keep="first")
        .reset_index(drop=True)
    )


def chronological_match_split(events: pd.DataFrame, *, lockbox_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    if events.empty:
        return events.copy(), events.copy()
    match_times = (
        events.groupby("match_id", dropna=False)["received_at_ns_num"]
        .min()
        .sort_values()
        .reset_index()
    )
    if len(match_times) < 2:
        return events.copy(), events.iloc[0:0].copy()
    lockbox_count = max(1, int(np.ceil(len(match_times) * lockbox_fraction)))
    if lockbox_count >= len(match_times):
        lockbox_count = len(match_times) - 1
    lockbox_matches = set(match_times.tail(lockbox_count)["match_id"].astype(str))
    match_key = events["match_id"].astype(str)
    dev = events[~match_key.isin(lockbox_matches)].copy()
    lockbox = events[match_key.isin(lockbox_matches)].copy()
    return dev.reset_index(drop=True), lockbox.reset_index(drop=True)


def strategy_metrics(events: pd.DataFrame, *, pnl_col: str) -> dict[str, Any]:
    if events.empty:
        return {
            "events": 0,
            "matches": 0,
            "avg_ask": None,
            "positive_sell_rate": None,
            "sell_bid_pnl": 0.0,
            "avg_sell_bid_pnl": None,
            "settlement_pnl_2c": 0.0,
        }
    pnl = pd.to_numeric(events[pnl_col], errors="coerce")
    settlement = pd.to_numeric(events["settlement_pnl_2c"], errors="coerce")
    return {
        "events": int(len(events)),
        "matches": int(events["match_id"].nunique()) if "match_id" in events.columns else 0,
        "avg_ask": _mean(events["book_best_ask_num"]),
        "positive_sell_rate": float((pnl > 0).mean()) if len(pnl) else None,
        "sell_bid_pnl": float(pnl.sum()),
        "avg_sell_bid_pnl": float(pnl.mean()) if len(pnl) else None,
        "settlement_pnl_2c": float(settlement.sum()),
    }


def candidate_recommendation(dev: dict[str, Any], lockbox: dict[str, Any], *, min_events: int) -> str:
    if dev["events"] < min_events or lockbox["events"] < min_events:
        return "too_few_lockbox"
    if dev["sell_bid_pnl"] > 0 and lockbox["sell_bid_pnl"] > 0:
        return "research_candidate"
    if lockbox["sell_bid_pnl"] > 0:
        return "lockbox_positive_only"
    return "reject"


def chronological_settlement_candidate_summary(
    events: pd.DataFrame,
    *,
    min_events: int,
    lockbox_fraction: float = 0.30,
) -> list[dict[str, Any]]:
    rows = []
    if events.empty:
        return rows
    for event_name, event_rows in events.groupby("event_name", sort=False):
        for filter_name, predicate in candidate_filters():
            sub = event_rows[predicate(event_rows).fillna(False).astype(bool)].copy()
            if len(sub) < min_events:
                continue
            trades = first_candidate_event_per_map(sub)
            trades = trades[pd.to_numeric(trades["settlement_pnl_2c"], errors="coerce").notna()].copy()
            if len(trades) < min_events:
                continue
            dev, lockbox = chronological_match_split(trades, lockbox_fraction=lockbox_fraction)
            if dev.empty or lockbox.empty:
                continue
            dev_metrics = settlement_strategy_metrics(dev)
            lockbox_metrics = settlement_strategy_metrics(lockbox)
            combined_metrics = settlement_strategy_metrics(trades)
            rows.append(
                {
                    "event": str(event_name),
                    "filter": filter_name,
                    "dev": dev_metrics,
                    "lockbox": lockbox_metrics,
                    "combined": combined_metrics,
                    "recommendation": settlement_candidate_recommendation(dev_metrics, lockbox_metrics, min_events=min_events),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["recommendation"] == "research_candidate",
            row["lockbox"]["settlement_pnl_2c"],
            row["combined"]["settlement_pnl_2c"],
        ),
        reverse=True,
    )


def settlement_strategy_metrics(events: pd.DataFrame) -> dict[str, Any]:
    if events.empty:
        return {
            "events": 0,
            "matches": 0,
            "avg_ask": None,
            "win_rate": None,
            "settlement_pnl_2c": 0.0,
            "avg_settlement_pnl_2c": None,
            "bootstrap_p05": None,
            "bootstrap_median": None,
            "bootstrap_prob_positive": None,
            "max_match_pnl": None,
            "worst_match_pnl": None,
            "max_match_share": None,
        }
    pnl = pd.to_numeric(events["settlement_pnl_2c"], errors="coerce")
    wins = events["settled_win"].dropna().astype(bool) if "settled_win" in events.columns else pd.Series(dtype=bool)
    robustness = bootstrap_match_pnl(events, pnl_col="settlement_pnl_2c")
    concentration = concentration_metrics(events, pnl_col="settlement_pnl_2c")
    return {
        "events": int(len(events)),
        "matches": int(events["match_id"].nunique()) if "match_id" in events.columns else 0,
        "avg_ask": _mean(events["book_best_ask_num"]),
        "win_rate": None if wins.empty else float(wins.mean()),
        "settlement_pnl_2c": float(pnl.sum()),
        "avg_settlement_pnl_2c": float(pnl.mean()) if len(pnl) else None,
        **robustness,
        **concentration,
    }


def settlement_candidate_recommendation(dev: dict[str, Any], lockbox: dict[str, Any], *, min_events: int) -> str:
    if dev["events"] < min_events or lockbox["events"] < min_events:
        return "too_few_lockbox"
    if dev["settlement_pnl_2c"] > 0 and lockbox["settlement_pnl_2c"] > 0:
        return "research_candidate"
    if lockbox["settlement_pnl_2c"] > 0:
        return "lockbox_positive_only"
    return "reject"


def match_level_pnl(events: pd.DataFrame, *, pnl_col: str) -> pd.Series:
    if events.empty or pnl_col not in events.columns:
        return pd.Series(dtype=float)
    pnl = pd.to_numeric(events[pnl_col], errors="coerce")
    usable = events.loc[pnl.notna()].copy()
    if usable.empty:
        return pd.Series(dtype=float)
    usable["_pnl"] = pnl.loc[usable.index].astype(float)
    if "match_id" not in usable.columns:
        return pd.Series([float(usable["_pnl"].sum())], index=["all"], dtype=float)
    return usable.groupby(usable["match_id"].astype(str), dropna=False)["_pnl"].sum().astype(float)


def bootstrap_match_pnl(
    events: pd.DataFrame,
    *,
    pnl_col: str,
    iterations: int = 2000,
    seed: int = 7,
) -> dict[str, float | None]:
    match_pnl = match_level_pnl(events, pnl_col=pnl_col)
    if match_pnl.empty:
        return {
            "bootstrap_p05": None,
            "bootstrap_median": None,
            "bootstrap_prob_positive": None,
        }
    values = match_pnl.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(iterations, len(values)), replace=True).sum(axis=1)
    return {
        "bootstrap_p05": float(np.quantile(samples, 0.05)),
        "bootstrap_median": float(np.median(samples)),
        "bootstrap_prob_positive": float((samples > 0).mean()),
    }


def concentration_metrics(events: pd.DataFrame, *, pnl_col: str) -> dict[str, float | None]:
    match_pnl = match_level_pnl(events, pnl_col=pnl_col)
    if match_pnl.empty:
        return {
            "max_match_pnl": None,
            "worst_match_pnl": None,
            "max_match_share": None,
        }
    total = float(match_pnl.sum())
    max_match_pnl = float(match_pnl.max())
    worst_match_pnl = float(match_pnl.min())
    return {
        "max_match_pnl": max_match_pnl,
        "worst_match_pnl": worst_match_pnl,
        "max_match_share": None if total <= 1e-9 else max_match_pnl / total,
    }


def chronological_candidate_details(
    events: pd.DataFrame,
    candidates: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if events.empty or not candidates:
        return []
    filters = dict(candidate_filters())
    rows: list[dict[str, Any]] = []
    research_candidates = [row for row in candidates if row.get("recommendation") == "research_candidate"]
    for candidate in research_candidates:
        event_name = str(candidate["event"])
        filter_name = str(candidate["filter"])
        horizon = int(candidate["horizon_sec"])
        predicate = filters.get(filter_name)
        if predicate is None:
            continue
        sub = events[
            (events["event_name"].astype(str) == event_name)
            & predicate(events).fillna(False).astype(bool)
        ].copy()
        trades = first_candidate_event_per_map(sub)
        pnl_col = f"sell_bid_pnl_{horizon}"
        future_bid_col = f"future_bid_{horizon}"
        if pnl_col not in trades.columns:
            continue
        trades = trades[pd.to_numeric(trades[pnl_col], errors="coerce").notna()].copy()
        if trades.empty:
            continue
        dev, lockbox = chronological_match_split(trades, lockbox_fraction=0.30)
        lockbox_matches = set(lockbox["match_id"].astype(str))
        for _, row in trades.sort_values("received_at_ns_num").iterrows():
            split = "lockbox" if str(row.get("match_id")) in lockbox_matches else "dev"
            rows.append(
                {
                    "event": event_name,
                    "filter": filter_name,
                    "horizon_sec": horizon,
                    "split": split,
                    "match_id": _json_value(row.get("match_id")),
                    "current_game_number": _json_value(row.get("current_game_number")),
                    "side": _json_value(row.get("side")),
                    "received_at_utc": _json_value(row.get("received_at_utc")),
                    "game_time_sec": _json_value(row.get("game_time_sec_num")),
                    "entry_ask": _json_value(row.get("book_best_ask_num")),
                    "entry_bid": _json_value(row.get("book_best_bid_num")),
                    "future_bid": _json_value(row.get(future_bid_col)),
                    "sell_bid_pnl": _json_value(row.get(pnl_col)),
                    "settled_win": _json_value(row.get("settled_win")),
                    "settlement_pnl_2c": _json_value(row.get("settlement_pnl_2c")),
                    "source_update_age_sec": _json_value(row.get("source_update_age_sec_num")),
                    "side_nw": _json_value(row.get("side_nw_num")),
                    "side_mom_100": _json_value(row.get("side_mom_100_num")),
                    "side_mom_300": _json_value(row.get("side_mom_300_num")),
                    "side_kill_mom": _json_value(row.get("side_kill_mom_num")),
                }
            )
    return rows[:limit]


def chronological_settlement_candidate_details(
    events: pd.DataFrame,
    candidates: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if events.empty or not candidates:
        return []
    filters = dict(candidate_filters())
    rows: list[dict[str, Any]] = []
    research_candidates = [row for row in candidates if row.get("recommendation") == "research_candidate"]
    for candidate in research_candidates:
        event_name = str(candidate["event"])
        filter_name = str(candidate["filter"])
        predicate = filters.get(filter_name)
        if predicate is None:
            continue
        sub = events[
            (events["event_name"].astype(str) == event_name)
            & predicate(events).fillna(False).astype(bool)
        ].copy()
        trades = first_candidate_event_per_map(sub)
        trades = trades[pd.to_numeric(trades["settlement_pnl_2c"], errors="coerce").notna()].copy()
        if trades.empty:
            continue
        dev, lockbox = chronological_match_split(trades, lockbox_fraction=0.30)
        lockbox_matches = set(lockbox["match_id"].astype(str))
        for _, row in trades.sort_values("received_at_ns_num").iterrows():
            split = "lockbox" if str(row.get("match_id")) in lockbox_matches else "dev"
            rows.append(
                {
                    "event": event_name,
                    "filter": filter_name,
                    "split": split,
                    "match_id": _json_value(row.get("match_id")),
                    "current_game_number": _json_value(row.get("current_game_number")),
                    "side": _json_value(row.get("side")),
                    "received_at_utc": _json_value(row.get("received_at_utc")),
                    "game_time_sec": _json_value(row.get("game_time_sec_num")),
                    "entry_ask": _json_value(row.get("book_best_ask_num")),
                    "entry_bid": _json_value(row.get("book_best_bid_num")),
                    "settled_win": _json_value(row.get("settled_win")),
                    "settlement_pnl_2c": _json_value(row.get("settlement_pnl_2c")),
                    "source_update_age_sec": _json_value(row.get("source_update_age_sec_num")),
                    "side_nw": _json_value(row.get("side_nw_num")),
                    "side_mom_100": _json_value(row.get("side_mom_100_num")),
                    "side_mom_300": _json_value(row.get("side_mom_300_num")),
                    "side_kill_mom": _json_value(row.get("side_kill_mom_num")),
                }
            )
    return rows[:limit]


def event_details(events: pd.DataFrame, *, horizons_sec: list[int], limit: int) -> list[dict[str, Any]]:
    if events.empty:
        return []
    best_horizon = horizons_sec[0]
    col = f"sell_bid_pnl_{best_horizon}"
    if col not in events.columns:
        return []
    work = events[pd.to_numeric(events[col], errors="coerce").notna()].copy()
    if work.empty:
        return []
    work = work.sort_values(col, ascending=False).head(limit)
    detail_cols = [
        "event_name",
        "match_id",
        "current_game_number",
        "side",
        "received_at_utc",
        "game_time_sec_num",
        "book_best_ask_num",
        "book_best_bid_num",
        "side_nw_num",
        "side_mom_100_num",
        "side_mom_300_num",
        "side_kill_mom_num",
        "settled_win",
        "settlement_pnl_2c",
        col,
    ]
    out = []
    for _, row in work.iterrows():
        out.append({name: _json_value(row.get(name)) for name in detail_cols})
    return out


def add_gettoplive_markout_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--live-settled-path", default=str(DEFAULT_LIVE_SETTLED_PATH))
    parser.add_argument("--include-live", action="store_true")
    parser.add_argument("--horizons-sec", default="30,60,120,300")
    parser.add_argument("--min-game-time-sec", type=int, default=600)
    parser.add_argument("--min-events", type=int, default=3)
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")


def format_gettoplive_markout_report(result: dict[str, Any], *, output_format: str = "markdown") -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True)
    lines = [
        "# GetTopLive Markout Report",
        "",
        f"- include live: {result['include_live']}",
        f"- input rows: {result['input_rows']}",
        f"- eligible rows: {result['eligible_rows']}",
        f"- eligible matches: {result['eligible_matches']}",
        f"- event rows: {result['event_rows']}",
        f"- event matches: {result['event_matches']}",
        f"- min game time sec: {result['min_game_time_sec']}",
        f"- horizons sec: {', '.join(str(v) for v in result['horizons_sec'])}",
        "",
        "Sell-bid PnL assumes buying at event ask with 2c entry cost and selling future bid with 1c exit cost.",
        "",
        "## Future Bid Markouts",
        "",
        markout_table(result["horizon_summary"]),
        "",
        "## Settlement By Event",
        "",
        settlement_table(result["event_summary"]),
        "",
        "## Candidate Subsets",
        "",
        candidate_table(result["candidate_summary"][:30]),
        "",
        "## Chronological Candidate Split",
        "",
        chronological_candidate_table(result["chronological_candidate_summary"][:30]),
        "",
        "## Research Candidate Trades",
        "",
        chronological_detail_table(result["chronological_candidate_details"]),
        "",
        "## Chronological Settlement Candidate Split",
        "",
        chronological_settlement_candidate_table(result["chronological_settlement_candidate_summary"][:30]),
        "",
        "## Settlement Candidate Trades",
        "",
        chronological_settlement_detail_table(result["chronological_settlement_candidate_details"]),
        "",
        "## Best 30s Event Rows",
        "",
        detail_table(result["details"]),
    ]
    return "\n".join(lines)


def markout_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No event/horizon bucket met the minimum event count."
    lines = [
        "| event | horizon | events | matches | avg ask | avg bid markout | avg mid markout | positive sell | total sell pnl | avg sell pnl |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['event']} | {row['horizon_sec']} | {row['events_with_future']} | {row['matches']} | "
            f"{_fmt(row['avg_entry_ask'])} | {_signed(row['avg_bid_markout'])} | {_signed(row['avg_mid_markout'])} | "
            f"{_pct(row['positive_sell_rate'])} | {_signed(row['total_sell_bid_pnl'])} | {_signed(row['avg_sell_bid_pnl'])} |"
        )
    return "\n".join(lines)


def settlement_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No event bucket met the minimum event count."
    lines = [
        "| event | events | matches | maps | avg ask | settled | win | settlement pnl 2c |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['event']} | {row['events']} | {row['matches']} | {row['map_exposures']} | "
            f"{_fmt(row['avg_ask'])} | {row['settled']} | {_pct(row['settlement_win_rate'])} | {_signed(row['settlement_pnl_2c'])} |"
        )
    return "\n".join(lines)


def candidate_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No candidate subset met the minimum event count."
    lines = [
        "| event | filter | horizon | events | matches | avg ask | positive sell | total sell pnl | avg sell pnl | settlement pnl 2c |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['event']} | {row['filter']} | {row['horizon_sec']} | {row['events_with_future']} | {row['matches']} | "
            f"{_fmt(row['avg_entry_ask'])} | {_pct(row['positive_sell_rate'])} | {_signed(row['total_sell_bid_pnl'])} | "
            f"{_signed(row['avg_sell_bid_pnl'])} | {_signed(row['settlement_pnl_2c'])} |"
        )
    return "\n".join(lines)


def chronological_candidate_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No chronological candidate met the minimum event count."
    lines = [
        "| event | filter | horizon | dev events | dev sell pnl | lockbox events | lockbox sell pnl | combined sell pnl | combined settlement | recommendation |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        dev = row["dev"]
        lockbox = row["lockbox"]
        combined = row["combined"]
        lines.append(
            f"| {row['event']} | {row['filter']} | {row['horizon_sec']} | "
            f"{dev['events']} | {_signed(dev['sell_bid_pnl'])} | "
            f"{lockbox['events']} | {_signed(lockbox['sell_bid_pnl'])} | "
            f"{_signed(combined['sell_bid_pnl'])} | {_signed(combined['settlement_pnl_2c'])} | "
            f"{row['recommendation']} |"
        )
    return "\n".join(lines)


def chronological_detail_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No research-candidate trade details."
    lines = [
        "| split | event | filter | horizon | match | game | side | time | ask | future bid | sell pnl | settle pnl | win | src age | nw | killmom |",
        "| --- | --- | --- | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('split')} | {row.get('event')} | {row.get('filter')} | {row.get('horizon_sec')} | "
            f"{row.get('match_id')} | {row.get('current_game_number')} | {row.get('side')} | "
            f"{_fmt(row.get('game_time_sec'), digits=0)} | {_fmt(row.get('entry_ask'))} | "
            f"{_fmt(row.get('future_bid'))} | {_signed(row.get('sell_bid_pnl'))} | "
            f"{_signed(row.get('settlement_pnl_2c'))} | {row.get('settled_win')} | "
            f"{_fmt(row.get('source_update_age_sec'))} | {_fmt(row.get('side_nw'), digits=0)} | "
            f"{_fmt(row.get('side_kill_mom'), digits=0)} |"
        )
    return "\n".join(lines)


def chronological_settlement_candidate_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No chronological settlement candidate met the minimum event count."
    lines = [
        "| event | filter | dev events | dev settle pnl | lockbox events | lockbox settle pnl | combined settle pnl | combined win | boot p05 | boot+ | max share | recommendation |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        dev = row["dev"]
        lockbox = row["lockbox"]
        combined = row["combined"]
        lines.append(
            f"| {row['event']} | {row['filter']} | "
            f"{dev['events']} | {_signed(dev['settlement_pnl_2c'])} | "
            f"{lockbox['events']} | {_signed(lockbox['settlement_pnl_2c'])} | "
            f"{_signed(combined['settlement_pnl_2c'])} | {_pct(combined['win_rate'])} | "
            f"{_signed(combined.get('bootstrap_p05'))} | {_pct(combined.get('bootstrap_prob_positive'))} | "
            f"{_pct(combined.get('max_match_share'))} | "
            f"{row['recommendation']} |"
        )
    return "\n".join(lines)


def chronological_settlement_detail_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No settlement-candidate trade details."
    lines = [
        "| split | event | filter | match | game | side | time | ask | settle pnl | win | src age | nw | mom100 | killmom |",
        "| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('split')} | {row.get('event')} | {row.get('filter')} | "
            f"{row.get('match_id')} | {row.get('current_game_number')} | {row.get('side')} | "
            f"{_fmt(row.get('game_time_sec'), digits=0)} | {_fmt(row.get('entry_ask'))} | "
            f"{_signed(row.get('settlement_pnl_2c'))} | {row.get('settled_win')} | "
            f"{_fmt(row.get('source_update_age_sec'))} | {_fmt(row.get('side_nw'), digits=0)} | "
            f"{_fmt(row.get('side_mom_100'), digits=0)} | {_fmt(row.get('side_kill_mom'), digits=0)} |"
        )
    return "\n".join(lines)


def detail_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No detail rows."
    lines = [
        "| event | match | game | side | time | ask | bid | nw | mom100 | killmom | settled | settle pnl | sell pnl 30s |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('event_name')} | {row.get('match_id')} | {row.get('current_game_number')} | {row.get('side')} | "
            f"{_fmt(row.get('game_time_sec_num'), digits=0)} | {_fmt(row.get('book_best_ask_num'))} | {_fmt(row.get('book_best_bid_num'))} | "
            f"{_fmt(row.get('side_nw_num'), digits=0)} | {_fmt(row.get('side_mom_100_num'), digits=0)} | "
            f"{_fmt(row.get('side_kill_mom_num'), digits=0)} | {row.get('settled_win')} | "
            f"{_signed(row.get('settlement_pnl_2c'))} | {_signed(row.get('sell_bid_pnl_30'))} |"
        )
    return "\n".join(lines)


def parse_horizons(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("horizons cannot be empty")
    if any(value <= 0 for value in values):
        raise ValueError("horizons must be positive seconds")
    return values


def add_map_exposure_id(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "current_game_number" in out.columns:
        game = out["current_game_number"].astype("string").fillna("").str.strip()
        game = game.mask(game.eq("") | game.str.lower().isin(["nan", "none", "<na>"]), "MAPEQUIV")
    else:
        game = pd.Series("MAPEQUIV", index=out.index, dtype="string")
    out["map_exposure_id"] = out["match_id"].astype(str) + "::" + game.astype(str)
    return out


def _settlement_pnl_2c(ask: Any, settled_win: Any) -> float:
    price = _float_or_nan(ask)
    if pd.isna(price) or pd.isna(settled_win):
        return np.nan
    win = bool(settled_win)
    return 1.0 - price - ENTRY_SLIPPAGE if win else -(price + ENTRY_SLIPPAGE)


def _mean(values: pd.Series) -> float | None:
    value = pd.to_numeric(values, errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def _float_or_nan(value: Any) -> float:
    try:
        if value is None or pd.isna(value):
            return np.nan
        return float(value)
    except (TypeError, ValueError):
        return np.nan


def _json_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _fmt(value: Any, *, digits: int = 4) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _signed(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):+.4f}"


def _pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{100 * float(value):.1f}%"
