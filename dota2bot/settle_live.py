"""Settle live side snapshots by joining completed match outcomes."""

from __future__ import annotations

import argparse
import asyncio
import time
from pathlib import Path
from typing import Any

import aiohttp
import duckdb
import pandas as pd

from .live_logger import (
    MAP_EQUIVALENT_SCOPES,
    MAP_WINNER_EXPLICIT,
    SERIES_DECIDER_EQUIVALENT,
    UNKNOWN_SCOPE,
    _bool_or_none,
    _classify_market_for_live_map,
    _side_is_radiant,
    _snapshot_quality,
)
from .live_sources import fetch_match_outcome, utc_from_ns
from .schemas import SIDE_SNAPSHOT_COLUMNS


OUTCOME_COLUMNS = [
    "match_id",
    "radiant_win",
    "outcome_source",
    "status",
    "error",
    "fetched_at_utc",
    "fetched_at_ns",
]


def run_settle_live(
    *,
    logs_root: Path = Path("logs"),
    output_name: str = "live_settled_side_snapshots",
    outcomes_name: str = "live_outcomes",
    concurrency: int = 6,
) -> dict[str, Any]:
    return asyncio.run(
        _run_settle_live_async(
            logs_root=logs_root,
            output_name=output_name,
            outcomes_name=outcomes_name,
            concurrency=concurrency,
        )
    )


def run_settle_live_loop(
    *,
    logs_root: Path = Path("logs"),
    output_name: str = "live_settled_side_snapshots",
    outcomes_name: str = "live_outcomes",
    concurrency: int = 6,
    interval_sec: float = 120.0,
) -> None:
    while True:
        result = run_settle_live(
            logs_root=logs_root,
            output_name=output_name,
            outcomes_name=outcomes_name,
            concurrency=concurrency,
        )
        print(result, flush=True)
        time.sleep(interval_sec)


async def _run_settle_live_async(
    *,
    logs_root: Path,
    output_name: str,
    outcomes_name: str,
    concurrency: int,
) -> dict[str, Any]:
    side_dir = logs_root / "live_side_snapshots"
    if not list(side_dir.glob("*.parquet")):
        return {"input_rows": 0, "settled_rows": 0, "output_path": None, "outcomes_path": None}

    sides = _read_parquet_dir(side_dir)
    sides = normalize_side_snapshot_frame(sides)
    match_ids = sorted(str(m) for m in sides["match_id"].dropna().astype(str).unique() if str(m))

    cached = _read_outcome_cache(logs_root / outcomes_name)
    need_fetch = [m for m in match_ids if cached.get(m, {}).get("status") != "settled"]
    fetched = await _fetch_outcomes(need_fetch, concurrency=concurrency)
    outcomes_by_match = {**cached, **{str(row["match_id"]): row for row in fetched}}

    outcome_rows = [_outcome_row(match_id, outcomes_by_match.get(match_id)) for match_id in match_ids]
    outcomes_df = pd.DataFrame(outcome_rows, columns=OUTCOME_COLUMNS)

    enriched = enrich_side_snapshots(sides, outcomes_df)
    before_dedupe_rows = len(enriched)
    enriched = dedupe_side_snapshots(enriched)
    duplicate_rows_dropped = before_dedupe_rows - len(enriched)

    out_dir = logs_root / output_name
    outcome_dir = logs_root / outcomes_name
    out_dir.mkdir(parents=True, exist_ok=True)
    outcome_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "latest.parquet"
    outcomes_path = outcome_dir / "latest.parquet"
    enriched.to_parquet(output_path, index=False, compression="zstd")
    outcomes_df.to_parquet(outcomes_path, index=False, compression="zstd")

    return {
        "input_rows": int(len(sides)),
        "matches": int(len(match_ids)),
        "fetched_outcomes": int(len(fetched)),
        "settled_matches": int((outcomes_df["status"] == "settled").sum()) if not outcomes_df.empty else 0,
        "pending_matches": int((outcomes_df["status"] != "settled").sum()) if not outcomes_df.empty else 0,
        "settled_rows": int(enriched["settled_win"].notna().sum()),
        "backtest_rows": int((enriched["settled_win"].notna() & enriched["book_best_ask"].notna()).sum()),
        "duplicate_rows_dropped": int(duplicate_rows_dropped),
        "output_path": str(output_path),
        "outcomes_path": str(outcomes_path),
    }


def normalize_side_snapshot_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in SIDE_SNAPSHOT_COLUMNS:
        if col not in out.columns:
            out[col] = None
    for col in [
        "market_id",
        "condition_id",
        "market_name",
        "market_type",
        "market_scope",
        "label_market_bucket",
        "series_type",
        "side",
        "token_id",
        "opposing_token_id",
        "quality_reason",
        "source_fresh",
        "book_fresh",
        "has_two_sided_book",
        "executable_snapshot",
        "settled_win",
        "radiant_win",
        "yes_won",
        "no_won",
        "side_is_radiant",
        "yes_is_radiant",
        "outcome_source",
        "hold_to_settlement_pnl_per_share",
        "hold_to_settlement_roi",
    ]:
        if col in out.columns:
            out[col] = out[col].astype("object")

    if "market_scope" in out.columns:
        missing_scope = out["market_scope"].isna() | out["market_scope"].astype(str).eq("")
    else:
        missing_scope = pd.Series(True, index=out.index)
    if missing_scope.any():
        out.loc[missing_scope, "market_scope"] = out.loc[missing_scope].apply(_derive_market_scope, axis=1)

    quality_missing = out["executable_snapshot"].isna() if "executable_snapshot" in out.columns else pd.Series(True, index=out.index)
    if quality_missing.any():
        for idx, row in out.loc[quality_missing].iterrows():
            quality = _snapshot_quality(
                row.to_dict(),
                {
                    "best_bid": row.get("book_best_bid"),
                    "best_ask": row.get("book_best_ask"),
                    "ask_size": row.get("book_ask_size"),
                    "spread": row.get("book_spread"),
                },
                _num_or_none(row.get("book_age_ms")),
                str(row.get("market_scope") or UNKNOWN_SCOPE),
            )
            for key, value in quality.items():
                out.at[idx, key] = value
    return out[SIDE_SNAPSHOT_COLUMNS]


def enrich_side_snapshots(sides: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    out = normalize_side_snapshot_frame(sides)
    outcome_map = {
        str(row["match_id"]): row
        for row in outcomes.to_dict(orient="records")
        if str(row.get("status")) == "settled" and _bool_or_none(row.get("radiant_win")) is not None
    }

    for idx, row in out.iterrows():
        outcome = outcome_map.get(str(row.get("match_id") or ""))
        if not outcome:
            continue
        radiant_win = bool(outcome["radiant_win"])
        side_is_radiant = _bool_or_none(row.get("side_is_radiant"))
        if side_is_radiant is None:
            side_is_radiant = _side_is_radiant(row.to_dict())
        if side_is_radiant is None:
            continue

        settled_win = radiant_win == side_is_radiant
        out.at[idx, "radiant_win"] = radiant_win
        out.at[idx, "side_is_radiant"] = side_is_radiant
        out.at[idx, "settled_win"] = settled_win
        out.at[idx, "outcome_source"] = outcome.get("outcome_source")

        yes_is_radiant = _bool_or_none(row.get("yes_is_radiant"))
        if yes_is_radiant is not None:
            yes_won = radiant_win == yes_is_radiant
            out.at[idx, "yes_won"] = yes_won
            out.at[idx, "no_won"] = not yes_won

        ask = _num_or_none(row.get("book_best_ask"))
        if ask is not None:
            pnl = (1.0 - ask) if settled_win else -ask
            out.at[idx, "hold_to_settlement_pnl_per_share"] = pnl
            out.at[idx, "hold_to_settlement_roi"] = pnl / ask if ask > 0 else None
    return out[SIDE_SNAPSHOT_COLUMNS]


def dedupe_side_snapshots(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    keys = ["match_id", "market_id", "token_id", "received_at_ns"]
    if not all(col in out.columns for col in keys):
        return out
    return out.drop_duplicates(subset=keys, keep="first").reset_index(drop=True)


async def _fetch_outcomes(match_ids: list[str], concurrency: int) -> list[dict[str, Any]]:
    if not match_ids:
        return []
    timeout = aiohttp.ClientTimeout(total=15)
    sem = asyncio.Semaphore(max(concurrency, 1))
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async def one(match_id: str) -> dict[str, Any]:
            async with sem:
                outcome = await fetch_match_outcome(session, match_id)
                return _outcome_row(match_id, outcome)

        return await asyncio.gather(*(one(match_id) for match_id in match_ids))


def _read_outcome_cache(path: Path) -> dict[str, dict[str, Any]]:
    latest = path / "latest.parquet"
    if not latest.exists():
        return {}
    frame = pd.read_parquet(latest)
    return {str(row["match_id"]): row for row in frame.to_dict(orient="records")}


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    con = duckdb.connect()
    return con.execute(
        "select * from read_parquet(?, union_by_name=true)",
        [str(path / "*.parquet")],
    ).fetchdf()


def _outcome_row(match_id: str, outcome: dict[str, Any] | None) -> dict[str, Any]:
    now_ns = time.time_ns()
    outcome = outcome or {}
    return {
        "match_id": str(match_id),
        "radiant_win": outcome.get("radiant_win"),
        "outcome_source": outcome.get("outcome_source"),
        "status": outcome.get("status") or "pending",
        "error": outcome.get("error"),
        "fetched_at_utc": outcome.get("fetched_at_utc") or utc_from_ns(now_ns),
        "fetched_at_ns": outcome.get("fetched_at_ns") or now_ns,
    }


def _derive_market_scope(row: pd.Series) -> str:
    bucket = _text_upper(row.get("label_market_bucket"))
    market_type = _text_upper(row.get("market_type"))
    if bucket == "MAP_WINNER" or market_type == "MAP_WINNER":
        return MAP_WINNER_EXPLICIT
    if bucket in {"MATCH_WINNER_BO1", "MATCH_WINNER_GAME3_PROXY"}:
        return SERIES_DECIDER_EQUIVALENT
    try:
        map_num = int(str(row.get("current_game_number") or ""))
    except ValueError:
        return UNKNOWN_SCOPE
    return str(_classify_market_for_live_map(row.to_dict(), map_num).get("market_scope") or UNKNOWN_SCOPE)


def _text_upper(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().upper()


def _num_or_none(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def add_settle_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--output-name", default="live_settled_side_snapshots")
    parser.add_argument("--outcomes-name", default="live_outcomes")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=120.0)
