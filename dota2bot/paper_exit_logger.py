"""Paper validation for exit rules applied to active paper entries."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from .active_strategy_backtest import _add_map_exposure_id
from .logging_store import ParquetAppendLog
from .paper_strategy_logger import prepare_paper_feature_frame
from .schemas import EXIT_DECISION_COLUMNS
from .strategy_contract import (
    ACTIVE_MARKET_ANCHOR_MODEL_NAMES,
    ACTIVE_PAPER_DECISIONS_NAME,
    ACTIVE_SETTLED_PAPER_DECISIONS_NAME,
)


DEFAULT_INPUT_NAME = "paper_positions"
DEFAULT_SIDE_NAME = "live_settled_side_snapshots"
DEFAULT_OUTPUT_NAME = "paper_exit_decisions_late_mom100_neg_bid70"
DEFAULT_EXIT_STRATEGY_NAME = "late_mom100_neg_bid70"
ENTRY_COST = 0.02
EXIT_COST = 0.01
DEFAULT_MIN_GAME_TIME_SEC = 1200
DEFAULT_MIN_EXIT_BID = 0.70


def run_paper_exit_log(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = DEFAULT_INPUT_NAME,
    side_name: str = DEFAULT_SIDE_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    exit_strategy_name: str = DEFAULT_EXIT_STRATEGY_NAME,
    min_game_time_sec: float = DEFAULT_MIN_GAME_TIME_SEC,
    min_exit_bid: float = DEFAULT_MIN_EXIT_BID,
    require_mom300_negative: bool = False,
    batch_rows: int = 5000,
    source: str = "primary",
) -> dict[str, Any]:
    entries = _filter_entries(_read_latest_or_dir(logs_root / input_name), source)
    sides = _read_latest_or_dir(logs_root / side_name)
    exits = build_exit_decisions(
        entries=entries,
        sides=sides,
        exit_strategy_name=exit_strategy_name,
        min_game_time_sec=min_game_time_sec,
        min_exit_bid=min_exit_bid,
        require_mom300_negative=require_mom300_negative,
    )
    existing_ids = _read_existing_exit_ids(logs_root / output_name)
    before = len(exits)
    if existing_ids and not exits.empty:
        exits = exits[~exits["exit_decision_id"].astype(str).isin(existing_ids)].copy()
    log = ParquetAppendLog(logs_root, output_name, EXIT_DECISION_COLUMNS, batch_rows=batch_rows)
    log.extend(exits.to_dict(orient="records"))
    output_path = log.flush()
    return {
        "entry_rows": int(len(entries)),
        "exit_decision_rows": int(before),
        "written_rows": int(len(exits)),
        "exit_signal_rows": int(exits["exit_signal"].fillna(False).astype(bool).sum()) if not exits.empty else 0,
        "skipped_existing_rows": int(before - len(exits)),
        "output_name": output_name,
        "output_path": str(output_path) if output_path else None,
        "exit_strategy_name": exit_strategy_name,
    }


def run_paper_exit_log_loop(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = DEFAULT_INPUT_NAME,
    side_name: str = DEFAULT_SIDE_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    interval_sec: float = 300.0,
    source: str = "primary",
) -> None:
    while True:
        result = run_paper_exit_log(
            logs_root=logs_root,
            input_name=input_name,
            side_name=side_name,
            output_name=output_name,
            source=source,
        )
        print(result, flush=True)
        time.sleep(interval_sec)


def build_exit_decisions(
    *,
    entries: pd.DataFrame,
    sides: pd.DataFrame,
    exit_strategy_name: str = DEFAULT_EXIT_STRATEGY_NAME,
    min_game_time_sec: float = DEFAULT_MIN_GAME_TIME_SEC,
    min_exit_bid: float = DEFAULT_MIN_EXIT_BID,
    require_mom300_negative: bool = False,
) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame(columns=EXIT_DECISION_COLUMNS)
    featured_sides = _prepare_side_frame(sides)
    rows = [
        _exit_row(
            entry,
            featured_sides,
            exit_strategy_name=exit_strategy_name,
            min_game_time_sec=min_game_time_sec,
            min_exit_bid=min_exit_bid,
            require_mom300_negative=require_mom300_negative,
        )
        for _, entry in entries.iterrows()
    ]
    return pd.DataFrame(rows, columns=EXIT_DECISION_COLUMNS)


def run_paper_exit_report(
    *,
    logs_root: Path = Path("logs"),
    exit_name: str = DEFAULT_OUTPUT_NAME,
    output_format: str = "markdown",
    source: str = "primary",
) -> str:
    exits = _read_latest_or_dir(logs_root / exit_name)
    summary = summarize_exit_decisions(exits, source=source)
    if output_format == "json":
        return json.dumps(summary, indent=2, sort_keys=True)
    return format_exit_report(summary)


def summarize_exit_decisions(exits: pd.DataFrame, source: str = "primary") -> dict[str, Any]:
    if exits.empty:
        return {
            "rows": 0,
            "exit_signal_rows": 0,
            "pending_rows": 0,
            "hold_pnl_2c": 0.0,
            "exit_pnl_2c": 0.0,
            "delta_vs_hold": 0.0,
            "exit_status": [],
            "outcome": [],
            "source": [],
            "entry_ask_buckets": [],
            "exit_bid_buckets": [],
            "exit_game_time_buckets": [],
            "match_concentration": [],
            "exits": [],
        }
    if "exit_decision_id" in exits.columns:
        exits = exits.drop_duplicates(["exit_decision_id"], keep="last").reset_index(drop=True)
    exits = _annotate_report_frame(exits)
    signal = exits["exit_signal"].fillna(False).astype(bool)
    hold = pd.to_numeric(exits["hold_pnl_2c"], errors="coerce")
    pnl = pd.to_numeric(exits["exit_pnl_2c"], errors="coerce")
    settled_win = exits["settled_win"].map(_bool_or_none)
    exit_rows = exits[signal].copy()
    return {
        "source_name": source,
        "rows": len(exits),
        "exit_signal_rows": int(signal.sum()),
        "settled_rows": int(settled_win.notna().sum()),
        "pending_rows": int(settled_win.isna().sum()),
        "win_rate": float(settled_win.dropna().astype(bool).mean()) if settled_win.notna().any() else None,
        "hold_pnl_2c": float(hold.sum()) if not hold.empty else 0.0,
        "exit_pnl_2c": float(pnl.sum()) if not pnl.empty else 0.0,
        "delta_vs_hold": float((pnl - hold).sum()) if not pnl.empty else 0.0,
        "winners_exited": int((exit_rows["settled_win"].map(_bool_or_none).fillna(False).astype(bool)).sum()) if not exit_rows.empty else 0,
        "losers_exited": int((~exit_rows["settled_win"].map(_bool_or_none).fillna(False).astype(bool)).sum()) if not exit_rows.empty else 0,
        "avg_exit_bid": _mean_num(exit_rows, "exit_bid"),
        "exit_status": _group_metrics(exits, "exit_status"),
        "outcome": _group_metrics(exits, "outcome"),
        "source": _group_metrics(exits, "source_group"),
        "entry_ask_buckets": _group_metrics(exits, "entry_ask_bucket"),
        "exit_bid_buckets": _group_metrics(exits[signal].copy(), "exit_bid_bucket"),
        "exit_game_time_buckets": _group_metrics(exits[signal].copy(), "exit_game_time_bucket"),
        "match_concentration": _group_metrics(exits, "match_id", limit=10),
        "exits": _limited_records(
            exit_rows,
            [
                "match_id",
                "current_game_number",
                "side",
                "source_group",
                "entry_ask",
                "entry_game_time_sec",
                "exit_bid",
                "exit_bid_size",
                "exit_book_spread",
                "exit_book_age_ms",
                "exit_game_time_sec",
                "exit_side_mom_100",
                "settled_win",
                "hold_pnl_2c",
                "exit_pnl_2c",
                "pnl_delta_vs_hold",
            ],
            20,
        ),
    }


def format_exit_report(summary: dict[str, Any]) -> str:
    source_name = summary.get('source_name', 'primary')
    lines = [
        "# Paper Exit Report",
        "",
        f"- source: {source_name} controlled positions",
        f"- active entries: {summary['rows']}",
        f"- exit signals: {summary['exit_signal_rows']}",
        f"- pending rows: {summary.get('pending_rows', 0)}",
        "",
        "| active entries | exits | entry win | hold pnl 2c | exit pnl 2c | delta vs hold | avg exit bid | winners exited | losers exited |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| "
        + " | ".join(
            [
                str(summary["rows"]),
                str(summary["exit_signal_rows"]),
                _pct(summary.get("win_rate")),
                _signed(summary["hold_pnl_2c"]),
                _signed(summary["exit_pnl_2c"]),
                _signed(summary["delta_vs_hold"]),
                _num(summary.get("avg_exit_bid")),
                str(summary.get("winners_exited", 0)),
                str(summary.get("losers_exited", 0)),
            ]
        )
        + " |",
        "",
        "## Exit Status",
        "",
        _group_table(summary.get("exit_status", []), "status"),
        "",
        "## Outcome",
        "",
        _group_table(summary.get("outcome", []), "outcome"),
        "",
        "## Exposure Type",
        "",
        _group_table(summary.get("source", []), "type"),
        "",
        "## Entry Ask Buckets",
        "",
        _group_table(summary.get("entry_ask_buckets", []), "bucket"),
        "",
        "## Exit Bid Buckets",
        "",
        _group_table(summary.get("exit_bid_buckets", []), "bucket"),
        "",
        "## Exit Game-Time Buckets",
        "",
        _group_table(summary.get("exit_game_time_buckets", []), "bucket"),
        "",
        "## Match Concentration",
        "",
        _group_table(summary.get("match_concentration", []), "match"),
        "",
        "## Exits",
        "",
        "| match | game | side | type | entry ask | entry time | exit bid | bid size | spread | age ms | exit time | mom100 | win | hold pnl | exit pnl | delta |",
        "| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for row in summary["exits"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("match_id", "")),
                    str(row.get("current_game_number", "")),
                    str(row.get("side", "")),
                    str(row.get("source_group", "")),
                    _num(row.get("entry_ask")),
                    _num(row.get("entry_game_time_sec")),
                    _num(row.get("exit_bid")),
                    _num(row.get("exit_bid_size")),
                    _num(row.get("exit_book_spread")),
                    _num(row.get("exit_book_age_ms")),
                    _num(row.get("exit_game_time_sec")),
                    _num(row.get("exit_side_mom_100")),
                    str(row.get("settled_win", "")),
                    _signed(row.get("hold_pnl_2c")),
                    _signed(row.get("exit_pnl_2c")),
                    _signed(row.get("pnl_delta_vs_hold")),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _filter_entries(positions: pd.DataFrame, source: str) -> pd.DataFrame:
    if positions.empty:
        return positions.iloc[0:0].copy()
    allowed = positions["blocked_reason"].isna()
    model = positions["model_name"].astype("string").isin(ACTIVE_MARKET_ANCHOR_MODEL_NAMES)
    
    if source == "primary":
        group = positions["candidate_group"].astype("string").str.lower().eq("primary")
        work = positions[allowed & model & group].copy()
    elif source == "gettoplive":
        group = positions["candidate_group"].astype("string").str.lower().eq("gettoplive_candidate")
        work = positions[allowed & group].copy()
    elif source == "active":
        group = positions["candidate_group"].astype("string").str.lower().isin(["primary", "gettoplive_candidate"])
        work = positions[allowed & group].copy()
    else:
        work = positions[allowed].copy()

    if work.empty:
        return work
    
    # Rename columns so that down-stream logic matches
    work = work.rename(columns={
        "entry_received_at_ns": "received_at_ns",
        "entry_ask": "ask",
        "pnl_per_share_2c": "pnl_slip_2c",
    })
    
    if "map_exposure_id" not in work.columns:
        work = _add_map_exposure_id(work)
    
    return work.sort_values(["map_exposure_id", "received_at_ns"]).drop_duplicates(["map_exposure_id"], keep="first").reset_index(drop=True)


def _prepare_side_frame(sides: pd.DataFrame) -> pd.DataFrame:
    if sides.empty:
        return sides
    featured = prepare_paper_feature_frame(sides, eligibility_mode="live_executable")
    featured = _add_map_exposure_id(featured)
    for col in [
        "received_at_ns",
        "game_time_sec",
        "book_best_bid",
        "book_bid_size",
        "book_spread",
        "book_age_ms",
        "side_mom_100",
        "side_mom_300",
    ]:
        featured[f"{col}_num"] = pd.to_numeric(featured[col], errors="coerce") if col in featured.columns else pd.NA
    return featured


def _exit_row(
    entry: pd.Series,
    sides: pd.DataFrame,
    *,
    exit_strategy_name: str,
    min_game_time_sec: float,
    min_exit_bid: float,
    require_mom300_negative: bool,
) -> dict[str, Any]:
    future = _future_rows(sides, entry)
    condition = (
        (future["game_time_sec_num"] >= min_game_time_sec)
        & (future["side_mom_100_num"] < 0)
        & (future["book_best_bid_num"] >= min_exit_bid)
    ) if not future.empty else pd.Series(False, index=future.index)
    if require_mom300_negative and not future.empty:
        condition &= future["side_mom_300_num"] < 0
    hit = future[condition].head(1) if not future.empty else future
    exit_snapshot = None if hit.empty else hit.iloc[0]

    entry_ask = _float(entry.get("ask"))
    settled_win = _bool_or_none(entry.get("settled_win"))
    hold_pnl = _hold_pnl(entry_ask, settled_win)
    exit_signal = exit_snapshot is not None
    exit_bid = _float(exit_snapshot.get("book_best_bid")) if exit_signal else None
    exit_pnl = _exit_pnl(entry_ask, exit_bid) if exit_signal else hold_pnl
    delta = None if hold_pnl is None or exit_pnl is None else exit_pnl - hold_pnl

    row = {
        "exit_decision_id": _exit_decision_id(entry, exit_strategy_name),
        "entry_decision_id": entry.get("decision_id"),
        "exit_strategy_name": exit_strategy_name,
        "model_name": entry.get("model_name"),
        "model_version": entry.get("model_version"),
        "match_id": entry.get("match_id"),
        "market_id": entry.get("market_id"),
        "label_market_bucket": entry.get("label_market_bucket"),
        "current_game_number": entry.get("current_game_number"),
        "map_exposure_id": entry.get("map_exposure_id"),
        "canonical_exposure_id": entry.get("canonical_exposure_id"),
        "token_id": entry.get("token_id"),
        "side": entry.get("side"),
        "entry_received_at_utc": entry.get("received_at_utc"),
        "entry_received_at_ns": entry.get("received_at_ns"),
        "entry_game_time_sec": entry.get("game_time_sec"),
        "entry_ask": entry_ask,
        "entry_bid": _float(entry.get("bid")),
        "entry_edge": _float(entry.get("edge")),
        "entry_side_mom_100": _float(entry.get("side_mom_100")),
        "exit_signal": exit_signal,
        "exit_reason": _exit_reason(exit_signal, min_game_time_sec, min_exit_bid, require_mom300_negative),
        "exit_received_at_utc": exit_snapshot.get("received_at_utc") if exit_signal else None,
        "exit_received_at_ns": exit_snapshot.get("received_at_ns") if exit_signal else None,
        "exit_game_time_sec": _float(exit_snapshot.get("game_time_sec")) if exit_signal else None,
        "exit_bid": exit_bid,
        "exit_bid_size": _float(exit_snapshot.get("book_bid_size")) if exit_signal else None,
        "exit_book_spread": _float(exit_snapshot.get("book_spread")) if exit_signal else None,
        "exit_book_age_ms": _float(exit_snapshot.get("book_age_ms")) if exit_signal else None,
        "exit_side_mom_100": _float(exit_snapshot.get("side_mom_100")) if exit_signal else None,
        "exit_side_mom_300": _float(exit_snapshot.get("side_mom_300")) if exit_signal else None,
        "settled_win": settled_win,
        "hold_pnl_2c": hold_pnl,
        "exit_pnl_2c": exit_pnl,
        "pnl_delta_vs_hold": delta,
    }
    return {col: row.get(col) for col in EXIT_DECISION_COLUMNS}


def _future_rows(sides: pd.DataFrame, entry: pd.Series) -> pd.DataFrame:
    if sides.empty:
        return sides
    match_id = str(entry.get("match_id"))
    map_exposure_id = str(entry.get("map_exposure_id"))
    received_at_ns = pd.to_numeric(pd.Series([entry.get("received_at_ns")]), errors="coerce").iloc[0]
    future = sides[
        (sides["match_id"].astype(str) == match_id)
        & (sides["map_exposure_id"].astype(str) == map_exposure_id)
        & (sides["received_at_ns_num"] > received_at_ns)
        & sides["book_best_bid_num"].notna()
    ].copy()
    token_id = entry.get("token_id")
    if token_id is not None and not pd.isna(token_id):
        future = future[future["token_id"].astype(str) == str(token_id)]
    else:
        future = future[future["side"].astype(str) == str(entry.get("side"))]
    return future.sort_values("received_at_ns_num").reset_index(drop=True)


def _exit_decision_id(entry: pd.Series, exit_strategy_name: str) -> str:
    return "::".join(
        [
            str(exit_strategy_name),
            str(entry.get("decision_id")),
            str(entry.get("match_id")),
            str(entry.get("current_game_number")),
            str(entry.get("token_id")),
        ]
    )


def _exit_reason(exit_signal: bool, min_game_time_sec: float, min_exit_bid: float, require_mom300_negative: bool) -> str:
    if not exit_signal:
        return "hold_no_exit_signal"
    parts = [f"game_time>={min_game_time_sec:g}", "side_mom_100<0", f"bid>={min_exit_bid:.2f}"]
    if require_mom300_negative:
        parts.append("side_mom_300<0")
    return " ".join(parts)


def _hold_pnl(entry_ask: float | None, settled_win: bool | None) -> float | None:
    if entry_ask is None or settled_win is None:
        return None
    return 1.0 - entry_ask - ENTRY_COST if settled_win else -(entry_ask + ENTRY_COST)


def _exit_pnl(entry_ask: float | None, exit_bid: float | None) -> float | None:
    if entry_ask is None or exit_bid is None:
        return None
    return exit_bid - entry_ask - ENTRY_COST - EXIT_COST


def _read_latest_or_dir(path: Path) -> pd.DataFrame:
    latest = path / "latest.parquet"
    if latest.exists():
        return pd.read_parquet(latest)
    return _read_parquet_dir(path)


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return duckdb.execute(
        "select * from read_parquet(?, union_by_name=true)",
        [str(path / "*.parquet")],
    ).df()


def _read_existing_exit_ids(path: Path) -> set[str]:
    files = sorted(path.glob("*.parquet"))
    if not files:
        return set()
    try:
        frame = duckdb.execute(
            "select exit_decision_id from read_parquet(?, union_by_name=true)",
            [str(path / "*.parquet")],
        ).df()
    except Exception:
        return set()
    if "exit_decision_id" not in frame.columns:
        return set()
    return set(frame["exit_decision_id"].dropna().astype(str))


def _limited_records(frame: pd.DataFrame, columns: list[str], limit: int) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    cols = [col for col in columns if col in frame.columns]
    return frame[cols].head(limit).where(pd.notna(frame[cols]), None).to_dict(orient="records")


def _annotate_report_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    exit_signal = out["exit_signal"].fillna(False).astype(bool) if "exit_signal" in out.columns else pd.Series(False, index=out.index)
    out["exit_status"] = exit_signal.map({True: "exited", False: "held"})
    settled = out["settled_win"].map(_bool_or_none) if "settled_win" in out.columns else pd.Series(None, index=out.index)
    out["outcome"] = settled.map({True: "winner", False: "loser"}).fillna("pending")
    out["source_group"] = out.apply(_source_group, axis=1)
    out["entry_ask_bucket"] = _numeric_col(out, "entry_ask").map(_entry_ask_bucket)
    out["exit_bid_bucket"] = _numeric_col(out, "exit_bid").map(_exit_bid_bucket)
    out["exit_game_time_bucket"] = _numeric_col(out, "exit_game_time_sec").map(_exit_game_time_bucket)
    return out


def _numeric_col(frame: pd.DataFrame, col: str) -> pd.Series:
    if col not in frame.columns:
        return pd.Series(pd.NA, index=frame.index, dtype="Float64")
    return pd.to_numeric(frame[col], errors="coerce")


def _group_metrics(frame: pd.DataFrame, group_col: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    if frame.empty or group_col not in frame.columns:
        return []
    rows: list[dict[str, Any]] = []
    for group, sub in frame.groupby(group_col, dropna=False):
        exit_signal = sub["exit_signal"].fillna(False).astype(bool) if "exit_signal" in sub.columns else pd.Series(False, index=sub.index)
        settled = sub["settled_win"].map(_bool_or_none) if "settled_win" in sub.columns else pd.Series(None, index=sub.index)
        wins = settled.dropna().astype(bool)
        hold = pd.to_numeric(sub["hold_pnl_2c"], errors="coerce")
        pnl = pd.to_numeric(sub["exit_pnl_2c"], errors="coerce")
        row = {
            "group": str(group),
            "rows": int(len(sub)),
            "exits": int(exit_signal.sum()),
            "settled": int(settled.notna().sum()),
            "pending": int(settled.isna().sum()),
            "win_rate": float(wins.mean()) if len(wins) else None,
            "hold_pnl_2c": float(hold.sum()),
            "exit_pnl_2c": float(pnl.sum()),
            "delta_vs_hold": float((pnl - hold).sum()),
        }
        rows.append(row)
    rows = sorted(rows, key=lambda row: (row["delta_vs_hold"], row["rows"]), reverse=True)
    return rows[:limit] if limit is not None else rows


def _group_table(rows: list[dict[str, Any]], name: str) -> str:
    lines = [
        f"| {name} | rows | exits | settled | pending | win | hold pnl 2c | exit pnl 2c | delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row["group"]),
                    str(row["rows"]),
                    str(row["exits"]),
                    str(row["settled"]),
                    str(row["pending"]),
                    _pct(row["win_rate"]),
                    _signed(row["hold_pnl_2c"]),
                    _signed(row["exit_pnl_2c"]),
                    _signed(row["delta_vs_hold"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _source_group(row: pd.Series) -> str:
    value = row.get("map_exposure_id")
    text = "" if value is None or pd.isna(value) else str(value)
    if "::MAPEQUIV" in text:
        return "map_equivalent"
    return "explicit_map"


def _entry_ask_bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "unknown"
    if value < 0.30:
        return "0.20-0.30"
    if value < 0.40:
        return "0.30-0.40"
    return "0.40-0.50"


def _exit_bid_bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "held"
    if value < 0.75:
        return "0.70-0.75"
    if value < 0.85:
        return "0.75-0.85"
    return ">=0.85"


def _exit_game_time_bucket(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "held"
    if value < 1800:
        return "1200-1800"
    if value < 2400:
        return "1800-2400"
    return ">=2400"


def _float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


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


def _mean_num(frame: pd.DataFrame, col: str) -> float | None:
    if frame.empty or col not in frame.columns:
        return None
    value = pd.to_numeric(frame[col], errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def _pct(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value * 100:.1f}%"


def _num(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:.4f}"


def _signed(value: float | None) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{value:+.4f}"


def add_paper_exit_log_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME)
    parser.add_argument("--side-name", default=DEFAULT_SIDE_NAME)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--source", choices=["primary", "gettoplive", "active"], default="primary")
    parser.add_argument("--batch-rows", type=int, default=5000)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=300.0)


def add_paper_exit_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--exit-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--source", choices=["primary", "gettoplive", "active"], default="primary")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
