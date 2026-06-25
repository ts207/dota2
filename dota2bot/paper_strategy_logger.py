"""Paper decision logger for live side snapshots.

This is deliberately paper-only. It scores live snapshots with frozen research
candidate definitions and writes a decision ledger; it does not place orders.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from .logging_store import ParquetAppendLog
from .schemas import DECISION_COLUMNS, SIDE_SNAPSHOT_COLUMNS
from .settle_live import normalize_side_snapshot_frame
from .side_features import RESEARCH_MIN_GAME_TIME_SEC, add_side_features
from .strategy_contract import (
    ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE,
    ACTIVE_MARKET_ANCHOR_MODEL_VERSION,
    ACTIVE_MARKET_ANCHOR_SPECS,
    StrategySpec,
)
from .transition_features import add_transition_features


EXECUTABLE_BACKTEST_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
MODEL_VERSION = ACTIVE_MARKET_ANCHOR_MODEL_VERSION
DEFAULT_INPUT_NAME = "live_side_snapshots"
DEFAULT_OUTPUT_NAME = "strategy_decisions"
DEFAULT_ELIGIBILITY_MODE = ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE
ELIGIBILITY_MODES = {"research", "live_executable"}


PaperModelSpec = StrategySpec


@dataclass
class PaperModelBundle:
    models: dict[str, tuple[Any, list[str]]]
    specs: list[PaperModelSpec]
    training_cutoff: str
    model_version: str = MODEL_VERSION


PAPER_MODEL_SPECS = list(ACTIVE_MARKET_ANCHOR_SPECS)


def train_paper_model_bundle(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    specs: list[PaperModelSpec] | None = None,
) -> PaperModelBundle:
    """Train the paper candidates on the executable backtest dataset."""
    specs = specs or PAPER_MODEL_SPECS
    from market_residual_gettoplive_analysis import load_analysis_frame, market_models

    frame = load_analysis_frame(executable_path)
    registry = market_models()
    trained: dict[str, tuple[Any, list[str]]] = {}
    for spec in specs:
        if spec.model_name not in registry:
            raise KeyError(f"unknown paper model: {spec.model_name}")
        model, features = registry[spec.model_name]
        missing = [col for col in features if col not in frame.columns]
        if missing:
            raise ValueError(f"training frame missing features for {spec.model_name}: {missing}")
        model.fit(frame[features], frame["settled_win"].astype(int))
        trained[spec.model_name] = (model, features)

    training_cutoff = str(frame["received_at_utc"].max()) if "received_at_utc" in frame.columns else ""
    return PaperModelBundle(models=trained, specs=specs, training_cutoff=training_cutoff)


def score_paper_decisions(
    frame: pd.DataFrame,
    bundle: PaperModelBundle,
    *,
    eligibility_mode: str = DEFAULT_ELIGIBILITY_MODE,
) -> pd.DataFrame:
    """Score side snapshots for all configured paper candidates."""
    if frame.empty:
        return pd.DataFrame(columns=DECISION_COLUMNS)
    featured = prepare_paper_feature_frame(frame, eligibility_mode=eligibility_mode)
    decisions: list[dict[str, Any]] = []

    for spec in bundle.specs:
        model, features = bundle.models[spec.model_name]
        for col in features:
            if col not in featured.columns:
                featured[col] = np.nan
        scored = featured.copy()
        scored["fair_prob"] = model.predict_proba(scored[features])[:, 1]
        scored["edge"] = scored["fair_prob"] - scored["book_best_ask"]
        scored["signal"] = scored["tradable_paper"] & (scored["edge"] >= spec.entry_threshold)
        scored["reason"] = scored.apply(lambda row: _decision_reason(row, spec.entry_threshold), axis=1)
        for row in scored.to_dict(orient="records"):
            decisions.append(_decision_row(row, spec, bundle))

    out = pd.DataFrame(decisions, columns=DECISION_COLUMNS)
    if out.empty:
        return out
    out["signal_group"] = _signal_groups(out)
    return out[DECISION_COLUMNS]


def prepare_paper_feature_frame(
    frame: pd.DataFrame,
    *,
    eligibility_mode: str = DEFAULT_ELIGIBILITY_MODE,
) -> pd.DataFrame:
    """Normalize and derive the live-paper feature surface."""
    if eligibility_mode not in ELIGIBILITY_MODES:
        raise ValueError(f"unknown eligibility_mode={eligibility_mode!r}; expected one of {sorted(ELIGIBILITY_MODES)}")
    normalized = normalize_side_snapshot_frame(_ensure_side_columns(frame))
    featured = add_transition_features(
        add_side_features(normalized, min_game_time_sec=RESEARCH_MIN_GAME_TIME_SEC)
    )
    featured = _add_canonical_exposure_id(featured)
    for col in [
        "book_best_ask",
        "book_best_bid",
        "book_spread",
        "book_ask_size",
        "book_age_ms",
        "game_time_sec",
    ]:
        if col in featured.columns:
            featured[col] = pd.to_numeric(featured[col], errors="coerce")
    featured["market_prob"] = featured["book_best_ask"].clip(1e-6, 1 - 1e-6)
    featured["logit_market_price"] = np.log(featured["market_prob"] / (1 - featured["market_prob"]))
    featured["book_ask_size_log"] = np.log1p(featured["book_ask_size"])
    featured["book_age_s"] = featured["book_age_ms"] / 1000.0
    executable = featured["executable_snapshot"].map(_bool_or_false)
    research_tradable = featured["tradable_research"].fillna(False).astype(bool)
    featured["tradable_paper"] = research_tradable
    if eligibility_mode == "live_executable":
        featured["tradable_paper"] = executable & research_tradable
    featured["eligibility_mode"] = eligibility_mode
    return featured


def run_paper_log(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = DEFAULT_INPUT_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    batch_rows: int = 5000,
    signals_only: bool = False,
    limit: int | None = None,
    min_received_at_ns: int | None = None,
    eligibility_mode: str = DEFAULT_ELIGIBILITY_MODE,
) -> dict[str, Any]:
    input_dir = logs_root / input_name
    frame = _read_parquet_dir(input_dir)
    if min_received_at_ns is not None and not frame.empty and "received_at_ns" in frame.columns:
        received_at_ns = pd.to_numeric(frame["received_at_ns"], errors="coerce")
        frame = frame[received_at_ns >= min_received_at_ns].copy()
    if limit is not None:
        frame = frame.tail(limit).copy()
    if frame.empty:
        return {
            "input_rows": 0,
            "decision_rows": 0,
            "written_rows": 0,
            "signal_rows": 0,
            "skipped_existing_rows": 0,
            "output_name": output_name,
            "min_received_at_ns": min_received_at_ns,
        }

    bundle = train_paper_model_bundle(executable_path=executable_path)
    decisions = score_paper_decisions(frame, bundle, eligibility_mode=eligibility_mode)
    if signals_only:
        decisions = decisions[decisions["signal"].fillna(False).astype(bool)].copy()

    existing_ids = _read_existing_decision_ids(logs_root / output_name)
    before = len(decisions)
    if existing_ids:
        decisions = decisions[~decisions["decision_id"].astype(str).isin(existing_ids)].copy()

    log = ParquetAppendLog(logs_root, output_name, DECISION_COLUMNS, batch_rows=batch_rows)
    log.extend(decisions.to_dict(orient="records"))
    out_path = log.flush()
    signal_rows = int(decisions["signal"].fillna(False).astype(bool).sum()) if not decisions.empty else 0
    return {
        "input_rows": int(len(frame)),
        "decision_rows": int(before),
        "written_rows": int(len(decisions)),
        "signal_rows": signal_rows,
        "skipped_existing_rows": int(before - len(decisions)),
        "output_name": output_name,
        "output_path": str(out_path) if out_path else None,
        "models": [spec.model_name for spec in PAPER_MODEL_SPECS],
        "min_received_at_ns": min_received_at_ns,
        "eligibility_mode": eligibility_mode,
    }


def run_paper_log_loop(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = DEFAULT_INPUT_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    batch_rows: int = 5000,
    signals_only: bool = False,
    limit: int | None = None,
    interval_sec: float = 30.0,
    min_received_at_ns: int | None = None,
    eligibility_mode: str = DEFAULT_ELIGIBILITY_MODE,
) -> None:
    while True:
        result = run_paper_log(
            logs_root=logs_root,
            input_name=input_name,
            output_name=output_name,
            executable_path=executable_path,
            batch_rows=batch_rows,
            signals_only=signals_only,
            limit=limit,
            min_received_at_ns=min_received_at_ns,
            eligibility_mode=eligibility_mode,
        )
        print(result, flush=True)
        time.sleep(interval_sec)


def add_paper_log_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--batch-rows", type=int, default=5000)
    parser.add_argument("--signals-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-received-at-ns", type=int, default=None)
    parser.add_argument(
        "--eligibility-mode",
        choices=sorted(ELIGIBILITY_MODES),
        default=DEFAULT_ELIGIBILITY_MODE,
        help="research matches the backtest tradability gate; live_executable additionally requires the live executable snapshot gate",
    )
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=30.0)


def _decision_row(row: dict[str, Any], spec: PaperModelSpec, bundle: PaperModelBundle) -> dict[str, Any]:
    signal = bool(row.get("signal"))
    ask = _num_or_none(row.get("book_best_ask"))
    settled_win = _bool_or_none(row.get("settled_win"))
    paper_pnl = _settlement_pnl(ask, settled_win, signal, slippage=0.0)
    pnl_1c = _settlement_pnl(ask, settled_win, signal, slippage=0.01)
    pnl_2c = _settlement_pnl(ask, settled_win, signal, slippage=0.02)
    decision = {
        "decision_id": _decision_id(spec.strategy_name, bundle.model_version, row),
        "strategy_name": spec.strategy_name,
        "model_name": spec.model_name,
        "model_version": bundle.model_version,
        "training_cutoff": bundle.training_cutoff,
        "candidate_group": spec.candidate_group,
        "match_id": row.get("match_id"),
        "market_id": row.get("market_id"),
        "label_market_bucket": row.get("label_market_bucket"),
        "current_game_number": row.get("current_game_number"),
        "canonical_exposure_id": row.get("canonical_exposure_id"),
        "token_id": row.get("token_id"),
        "side": row.get("side"),
        "received_at_utc": row.get("received_at_utc"),
        "received_at_ns": row.get("received_at_ns"),
        "game_time_sec": row.get("game_time_sec"),
        "ask": ask,
        "bid": _num_or_none(row.get("book_best_bid")),
        "book_age_ms": _num_or_none(row.get("book_age_ms")),
        "book_spread": _num_or_none(row.get("book_spread")),
        "book_ask_size": _num_or_none(row.get("book_ask_size")),
        "executable_snapshot": _bool_or_false(row.get("executable_snapshot")),
        "quality_reason": row.get("quality_reason"),
        "signal": signal,
        "reason": row.get("reason"),
        "score": _num_or_none(row.get("edge")),
        "market_prob": _num_or_none(row.get("market_prob")),
        "fair_prob": _num_or_none(row.get("fair_prob")),
        "edge": _num_or_none(row.get("edge")),
        "entry_threshold": spec.entry_threshold,
        "paper_entry_price": ask if signal else None,
        "signal_group": None,
        "side_nw": _num_or_none(row.get("side_nw")),
        "side_score": _num_or_none(row.get("side_score")),
        "side_mom_100": _num_or_none(row.get("side_mom_100")),
        "side_mom_300": _num_or_none(row.get("side_mom_300")),
        "side_kill_mom": _num_or_none(row.get("side_kill_mom")),
        "side_tower": _num_or_none(row.get("side_tower")),
        "side_rax": _num_or_none(row.get("side_rax")),
        "structure_score": _num_or_none(row.get("structure_score")),
        "book_age_s": _num_or_none(row.get("book_age_s")),
        "logit_market_price": _num_or_none(row.get("logit_market_price")),
        "book_ask_size_log": _num_or_none(row.get("book_ask_size_log")),
        "settled_win": settled_win,
        "paper_pnl_per_share": paper_pnl,
        "pnl_slip_1c": pnl_1c,
        "pnl_slip_2c": pnl_2c,
    }
    return {col: decision.get(col) for col in DECISION_COLUMNS}


def _decision_reason(row: pd.Series, threshold: float) -> str:
    if bool(row.get("signal")):
        return "paper_edge_signal"
    if not bool(row.get("tradable_research")):
        return "not_research_tradable"
    if row.get("eligibility_mode") == "live_executable" and not _bool_or_false(row.get("executable_snapshot")):
        return str(row.get("quality_reason") or "not_executable_snapshot")
    if pd.isna(row.get("fair_prob")) or pd.isna(row.get("edge")):
        return "missing_model_score"
    if float(row.get("edge")) < threshold:
        return "below_threshold"
    return "no_signal"


def _signal_groups(decisions: pd.DataFrame) -> pd.Series:
    key_cols = ["match_id", "canonical_exposure_id", "received_at_ns", "side"]
    active_models = [spec.model_name for spec in PAPER_MODEL_SPECS]
    signal_map = (
        decisions.pivot_table(
            index=key_cols,
            columns="model_name",
            values="signal",
            aggfunc="max",
            fill_value=False,
        )
        .reset_index()
    )
    for model_name in active_models:
        if model_name not in signal_map.columns:
            signal_map[model_name] = False
    if len(active_models) == 1:
        signal_map["_signal_group"] = np.where(
            signal_map[active_models[0]].astype(bool),
            "active_strategy_signal",
            "no_signal",
        )
    else:
        any_signal = signal_map[active_models].astype(bool).any(axis=1)
        signal_map["_signal_group"] = np.where(any_signal, "active_strategy_signal", "no_signal")
    return decisions.merge(signal_map[key_cols + ["_signal_group"]], on=key_cols, how="left")["_signal_group"]


def _add_canonical_exposure_id(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    game_num = out["current_game_number"].map(_canonical_game_number) if "current_game_number" in out.columns else "MAPEQUIV"
    side = out["side"].astype(str) if "side" in out.columns else ""
    out["canonical_exposure_id"] = out["match_id"].astype(str) + "::" + game_num.astype(str) + "::" + side
    return out


def _canonical_game_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "MAPEQUIV"
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "?"}:
        return "MAPEQUIV"
    numeric = pd.to_numeric(pd.Series([text]), errors="coerce").iloc[0]
    if pd.notna(numeric) and float(numeric).is_integer():
        return str(int(numeric))
    return text


def _ensure_side_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in SIDE_SNAPSHOT_COLUMNS:
        if col not in out.columns:
            out[col] = None
    return out[SIDE_SNAPSHOT_COLUMNS]


def _read_parquet_dir(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    con = duckdb.connect()
    return con.execute(
        "select * from read_parquet(?, union_by_name=true)",
        [str(path / "*.parquet")],
    ).fetchdf()


def _read_existing_decision_ids(path: Path) -> set[str]:
    frame = _read_parquet_dir(path)
    if frame.empty or "decision_id" not in frame.columns:
        return set()
    return set(frame["decision_id"].dropna().astype(str))


def _decision_id(strategy_name: str, model_version: str, row: dict[str, Any]) -> str:
    raw = "|".join(
        [
            strategy_name,
            model_version,
            str(row.get("match_id")),
            str(row.get("market_id")),
            str(row.get("token_id")),
            str(row.get("received_at_ns")),
        ]
    )
    return sha1(raw.encode("utf-8")).hexdigest()


def _settlement_pnl(ask: float | None, settled_win: bool | None, signal: bool, *, slippage: float) -> float | None:
    if not signal or ask is None or settled_win is None:
        return None
    entry = ask + slippage
    return (1.0 - entry) if settled_win else -entry


def _num_or_none(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_false(value: Any) -> bool:
    parsed = _bool_or_none(value)
    return bool(parsed) if parsed is not None else False


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
