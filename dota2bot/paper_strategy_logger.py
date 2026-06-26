"""Paper decision logger for live side snapshots.

This is deliberately paper-only. It scores live snapshots with frozen research
candidate definitions and writes a decision ledger; it does not place orders.
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from dataclasses import asdict, dataclass
from dataclasses import field
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
from .executable_value_model import SLIPPAGE_2C, train_winprob_logistic_evfilter_model
from .strategy_contract import (
    ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE,
    ACTIVE_MARKET_ANCHOR_MODEL_VERSION,
    PAPER_DECISION_SPECS,
    PAPER_MARKET_ANCHOR_SPECS,
    PAPER_RULE_SPECS,
    StrategySpec,
)
from .transition_features import add_transition_features


EXECUTABLE_BACKTEST_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
MODEL_VERSION = ACTIVE_MARKET_ANCHOR_MODEL_VERSION
DEFAULT_MODEL_ARTIFACT_DIR = Path("models/market_anchor") / MODEL_VERSION
MODEL_BUNDLE_FILENAME = "model_bundle.pkl"
MODEL_MANIFEST_FILENAME = "manifest.json"
DEFAULT_INPUT_NAME = "live_side_snapshots"
DEFAULT_OUTPUT_NAME = "strategy_decisions"
DEFAULT_ELIGIBILITY_MODE = ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE
HISTORICAL_RESEARCH_ELIGIBILITY_MODE = "historical_research"
ELIGIBILITY_MODES = {DEFAULT_ELIGIBILITY_MODE, HISTORICAL_RESEARCH_ELIGIBILITY_MODE}


PaperModelSpec = StrategySpec


@dataclass
class PaperModelBundle:
    models: dict[str, tuple[Any, list[str]]]
    specs: list[PaperModelSpec]
    training_cutoff: str
    model_version: str = MODEL_VERSION
    score_kinds: dict[str, str] = field(default_factory=dict)


PAPER_MODEL_SPECS = list(PAPER_MARKET_ANCHOR_SPECS)
PAPER_RULE_MODEL_SPECS = list(PAPER_RULE_SPECS)
PAPER_DECISION_MODEL_SPECS = list(PAPER_DECISION_SPECS)


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
    score_kinds: dict[str, str] = {}
    prepared_training = prepare_paper_feature_frame(pd.read_parquet(executable_path))
    for spec in specs:
        if spec.model_name == "winprob_logistic_evfilter":
            model, features = train_winprob_logistic_evfilter_model(prepared_training)
            trained[spec.model_name] = (model, features)
            score_kinds[spec.model_name] = spec.score_kind
            continue
        if spec.model_name not in registry:
            raise KeyError(f"unknown paper model: {spec.model_name}")
        model, features = registry[spec.model_name]
        missing = [col for col in features if col not in frame.columns]
        if missing:
            raise ValueError(f"training frame missing features for {spec.model_name}: {missing}")
        model.fit(frame[features], frame["settled_win"].astype(int))
        trained[spec.model_name] = (model, features)
        score_kinds[spec.model_name] = spec.score_kind

    training_cutoff = str(frame["received_at_utc"].max()) if "received_at_utc" in frame.columns else ""
    return PaperModelBundle(models=trained, specs=specs, training_cutoff=training_cutoff, score_kinds=score_kinds)


def save_paper_model_bundle(
    bundle: PaperModelBundle,
    *,
    artifact_dir: Path = DEFAULT_MODEL_ARTIFACT_DIR,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
) -> dict[str, Any]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = artifact_dir / MODEL_BUNDLE_FILENAME
    manifest_path = artifact_dir / MODEL_MANIFEST_FILENAME
    with bundle_path.open("wb") as fh:
        pickle.dump(bundle, fh)
    manifest = {
        "model_version": bundle.model_version,
        "training_cutoff": bundle.training_cutoff,
        "executable_path": str(executable_path),
        "models": {
            model_name: {
                "features": features,
                "score_kind": bundle.score_kinds.get(model_name),
            }
            for model_name, (_, features) in bundle.models.items()
        },
        "specs": [_spec_manifest(spec) for spec in bundle.specs],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "artifact_dir": str(artifact_dir),
        "bundle_path": str(bundle_path),
        "manifest_path": str(manifest_path),
        "model_version": bundle.model_version,
        "training_cutoff": bundle.training_cutoff,
        "models": sorted(bundle.models),
    }


def train_and_save_paper_model_bundle(
    *,
    executable_path: Path = EXECUTABLE_BACKTEST_PATH,
    artifact_dir: Path = DEFAULT_MODEL_ARTIFACT_DIR,
    specs: list[PaperModelSpec] | None = None,
) -> dict[str, Any]:
    bundle = train_paper_model_bundle(executable_path=executable_path, specs=specs)
    return save_paper_model_bundle(bundle, artifact_dir=artifact_dir, executable_path=executable_path)


def load_paper_model_bundle(*, artifact_dir: Path = DEFAULT_MODEL_ARTIFACT_DIR) -> PaperModelBundle:
    bundle_path = artifact_dir / MODEL_BUNDLE_FILENAME
    if not bundle_path.exists():
        raise FileNotFoundError(
            f"paper model artifact not found: {bundle_path}. "
            "Run `python -m dota2bot freeze-paper-model` before paper logging."
        )
    with bundle_path.open("rb") as fh:
        bundle = pickle.load(fh)
    if bundle.model_version != MODEL_VERSION:
        raise ValueError(f"artifact model_version={bundle.model_version!r} does not match active {MODEL_VERSION!r}")
    return bundle


def validate_paper_model_artifact(*, artifact_dir: Path = DEFAULT_MODEL_ARTIFACT_DIR) -> dict[str, Any]:
    """Fail closed if the frozen paper artifact does not match the active contract."""
    bundle_path = artifact_dir / MODEL_BUNDLE_FILENAME
    manifest_path = artifact_dir / MODEL_MANIFEST_FILENAME
    missing = [str(path) for path in [bundle_path, manifest_path] if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "paper model artifact is incomplete: "
            + ", ".join(missing)
            + ". Run `python -m dota2bot freeze-paper-model` before starting runtime."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("model_version") != MODEL_VERSION:
        raise ValueError(
            f"artifact manifest model_version={manifest.get('model_version')!r} does not match active {MODEL_VERSION!r}"
        )
    expected_specs = [_spec_manifest(spec) for spec in PAPER_MODEL_SPECS]
    manifest_specs = [_normalize_spec_manifest(spec) for spec in manifest.get("specs", [])]
    if manifest_specs != expected_specs:
        raise ValueError("artifact manifest specs do not match active PAPER_MODEL_SPECS")

    bundle = load_paper_model_bundle(artifact_dir=artifact_dir)
    bundle_specs = [_spec_manifest(spec) for spec in bundle.specs]
    if bundle_specs != expected_specs:
        raise ValueError("artifact bundle specs do not match active PAPER_MODEL_SPECS")
    missing_models = [spec.model_name for spec in PAPER_MODEL_SPECS if spec.model_name not in bundle.models]
    if missing_models:
        raise ValueError(f"artifact bundle missing models: {missing_models}")
    for spec in PAPER_MODEL_SPECS:
        if bundle.score_kinds.get(spec.model_name, spec.score_kind) != spec.score_kind:
            raise ValueError(f"artifact score_kind mismatch for {spec.model_name}")

    return {
        "artifact_dir": str(artifact_dir),
        "bundle_path": str(bundle_path),
        "manifest_path": str(manifest_path),
        "model_version": MODEL_VERSION,
        "models": [spec.model_name for spec in PAPER_MODEL_SPECS],
        "valid": True,
    }


def _spec_manifest(spec: PaperModelSpec) -> dict[str, Any]:
    raw = {
        "model_name": getattr(spec, "model_name", None),
        "strategy_name": getattr(spec, "strategy_name", None),
        "candidate_group": getattr(spec, "candidate_group", None),
        "entry_threshold": getattr(spec, "entry_threshold", None),
        "score_kind": getattr(spec, "score_kind", "win_prob"),
        "market_scopes": getattr(spec, "market_scopes", ()),
        "min_ask": getattr(spec, "min_ask", None),
        "max_ask": getattr(spec, "max_ask", None),
        "min_game_time_sec": getattr(spec, "min_game_time_sec", None),
        "min_side_mom_100": getattr(spec, "min_side_mom_100", None),
        "min_side_kill_mom": getattr(spec, "min_side_kill_mom", None),
        "max_source_update_age_sec": getattr(spec, "max_source_update_age_sec", None),
        "deterministic_rule": getattr(spec, "deterministic_rule", False),
    }
    return _normalize_spec_manifest(raw)


def _normalize_spec_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "score_kind": "win_prob",
        "market_scopes": (),
        "min_ask": None,
        "max_ask": None,
        "min_game_time_sec": None,
        "min_side_mom_100": None,
        "min_side_kill_mom": None,
        "max_source_update_age_sec": None,
        "deterministic_rule": False,
    }
    normalized = {**defaults, **spec}
    if isinstance(normalized.get("market_scopes"), list):
        normalized["market_scopes"] = tuple(normalized["market_scopes"])
    keys = [
        "model_name",
        "strategy_name",
        "candidate_group",
        "entry_threshold",
        "score_kind",
        "market_scopes",
        "min_ask",
        "max_ask",
        "min_game_time_sec",
        "min_side_mom_100",
        "min_side_kill_mom",
        "max_source_update_age_sec",
        "deterministic_rule",
    ]
    return {key: normalized.get(key) for key in keys}


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
        score_kind = bundle.score_kinds.get(spec.model_name, spec.score_kind)
        scored = add_model_scores(scored, model, features, score_kind=score_kind)
        scored["strategy_filter"] = strategy_filter_mask(scored, spec)
        scored["signal"] = scored["tradable_paper"] & scored["strategy_filter"] & (scored["edge"] >= spec.entry_threshold)
        scored["reason"] = scored.apply(lambda row: _decision_reason(row, spec.entry_threshold), axis=1)
        for row in scored.to_dict(orient="records"):
            decisions.append(_decision_row(row, spec, bundle))
    for spec in PAPER_RULE_MODEL_SPECS:
        scored = add_rule_scores(featured.copy(), spec)
        scored["strategy_filter"] = strategy_filter_mask(scored, spec)
        scored["signal"] = scored["tradable_paper"] & scored["strategy_filter"] & (scored["edge"] >= spec.entry_threshold)
        scored["reason"] = scored.apply(lambda row: _decision_reason(row, spec.entry_threshold), axis=1)
        for row in scored.to_dict(orient="records"):
            decisions.append(_decision_row(row, spec, bundle))

    out = pd.DataFrame(decisions, columns=DECISION_COLUMNS)
    if out.empty:
        return out
    out["snapshot_signal_group"] = _signal_groups(out, exposure_level=False)
    out["exposure_signal_group"] = _signal_groups(out, exposure_level=True)
    out["signal_group"] = out["exposure_signal_group"]
    return out[DECISION_COLUMNS]


def add_rule_scores(frame: pd.DataFrame, spec: PaperModelSpec) -> pd.DataFrame:
    if spec.score_kind != "rule_binary":
        raise ValueError(f"unknown deterministic rule score_kind={spec.score_kind!r}")
    scored = frame.copy()
    rule_mask = strategy_filter_mask(scored, spec)
    scored["fair_prob"] = np.nan
    scored["edge"] = np.where(rule_mask, 1.0, 0.0)
    return scored


def add_model_scores(frame: pd.DataFrame, model: Any, features: list[str], *, score_kind: str) -> pd.DataFrame:
    scored = frame.copy()
    model_score = model.predict_proba(scored[features])[:, 1]
    scored["fair_prob"] = model_score
    if score_kind == "win_prob_2c":
        scored["edge"] = scored["fair_prob"] - scored["book_best_ask"] - SLIPPAGE_2C
    elif score_kind == "win_prob":
        scored["edge"] = scored["fair_prob"] - scored["book_best_ask"]
    else:
        raise ValueError(f"unknown score_kind={score_kind!r}")
    return scored


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
        "source_update_age_sec",
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


def strategy_filter_mask(frame: pd.DataFrame, spec: PaperModelSpec) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    if spec.market_scopes:
        if "market_scope" not in frame.columns:
            return pd.Series(False, index=frame.index)
        mask &= frame["market_scope"].isin(spec.market_scopes)
    ask = pd.to_numeric(frame["book_best_ask"], errors="coerce") if "book_best_ask" in frame.columns else pd.Series(np.nan, index=frame.index)
    if spec.min_ask is not None:
        mask &= ask >= spec.min_ask
    if spec.max_ask is not None:
        mask &= ask <= spec.max_ask
    if spec.min_game_time_sec is not None:
        if "game_time_sec" not in frame.columns:
            return pd.Series(False, index=frame.index)
        game_time = pd.to_numeric(frame["game_time_sec"], errors="coerce")
        mask &= game_time >= spec.min_game_time_sec
    if spec.min_side_mom_100 is not None:
        if "side_mom_100" not in frame.columns:
            return pd.Series(False, index=frame.index)
        side_mom_100 = pd.to_numeric(frame["side_mom_100"], errors="coerce")
        mask &= side_mom_100 >= spec.min_side_mom_100
    if spec.min_side_kill_mom is not None:
        if "side_kill_mom" not in frame.columns:
            return pd.Series(False, index=frame.index)
        side_kill_mom = pd.to_numeric(frame["side_kill_mom"], errors="coerce")
        mask &= side_kill_mom >= spec.min_side_kill_mom
    if spec.max_source_update_age_sec is not None:
        if "source_update_age_sec" not in frame.columns:
            return pd.Series(False, index=frame.index)
        source_age = pd.to_numeric(frame["source_update_age_sec"], errors="coerce")
        mask &= source_age <= spec.max_source_update_age_sec
    return mask.fillna(False).astype(bool)


def run_paper_log(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = DEFAULT_INPUT_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    artifact_dir: Path = DEFAULT_MODEL_ARTIFACT_DIR,
    batch_rows: int = 5000,
    signals_only: bool = False,
    limit: int | None = None,
    min_received_at_ns: int | None = None,
    eligibility_mode: str = DEFAULT_ELIGIBILITY_MODE,
    force_full_rescore: bool = False,
) -> dict[str, Any]:
    input_dir = logs_root / input_name
    # Push the watermark filter down into DuckDB so only matching row-groups
    # are read from disk — avoids loading the entire (growing) directory.
    frame = _read_parquet_dir(input_dir, min_received_at_ns=min_received_at_ns)
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
            "max_received_at_ns": None,
        }

    bundle = load_paper_model_bundle(artifact_dir=artifact_dir)
    decisions = score_paper_decisions(frame, bundle, eligibility_mode=eligibility_mode)
    if signals_only:
        decisions = decisions[decisions["signal"].fillna(False).astype(bool)].copy()

    if min_received_at_ns is None and not force_full_rescore and _has_existing_decisions(logs_root / output_name):
        raise ValueError(
            "refusing full paper-log rescore into an existing decision ledger without a watermark; "
            "pass --force-full-rescore to dedupe against the full ledger and append only missing rows"
        )

    existing_ids = _read_existing_decision_ids(
        logs_root / output_name,
        mode="all" if min_received_at_ns is None else "latest",
    )
    before = len(decisions)
    if existing_ids:
        decisions = decisions[~decisions["decision_id"].astype(str).isin(existing_ids)].copy()

    # Track max watermark *before* any signals_only filter so the loop can
    # advance past rows that produce no decisions.
    max_ns: int | None = None
    if not frame.empty and "received_at_ns" in frame.columns:
        raw_max = pd.to_numeric(frame["received_at_ns"], errors="coerce").max()
        if not pd.isna(raw_max):
            max_ns = int(raw_max)

    if signals_only:
        decisions = decisions[decisions["signal"].fillna(False).astype(bool)].copy()

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
        "models": [spec.model_name for spec in PAPER_DECISION_MODEL_SPECS],
        "min_received_at_ns": min_received_at_ns,
        "max_received_at_ns": max_ns,
        "eligibility_mode": eligibility_mode,
    }


def run_paper_log_loop(
    *,
    logs_root: Path = Path("logs"),
    input_name: str = DEFAULT_INPUT_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    artifact_dir: Path = DEFAULT_MODEL_ARTIFACT_DIR,
    batch_rows: int = 5000,
    signals_only: bool = False,
    limit: int | None = None,
    interval_sec: float = 30.0,
    min_received_at_ns: int | None = None,
    eligibility_mode: str = DEFAULT_ELIGIBILITY_MODE,
) -> None:
    """Loop that scores only *new* side snapshots each iteration.

    On the first iteration ``min_received_at_ns`` is used as supplied (or
    ``None`` to start from the watermark persisted in the output ledger).
    After each iteration the watermark advances to the highest
    ``received_at_ns`` seen, so subsequent iterations only touch rows that
    arrived since the last cycle.  This prevents the ever-growing
    ``live_side_snapshots/`` directory from being fully loaded into RAM on
    every loop tick.
    """
    # Seed the watermark from the existing decision ledger so restarts don't
    # re-process history.
    watermark = min_received_at_ns
    if watermark is None:
        watermark = _latest_decision_watermark(logs_root / output_name)

    while True:
        result = run_paper_log(
            logs_root=logs_root,
            input_name=input_name,
            output_name=output_name,
            artifact_dir=artifact_dir,
            batch_rows=batch_rows,
            signals_only=signals_only,
            limit=limit,
            min_received_at_ns=watermark,
            eligibility_mode=eligibility_mode,
        )
        # Advance the watermark so next iteration skips already-processed rows.
        new_watermark = result.get("max_received_at_ns")
        if new_watermark is not None:
            # +1 so the boundary row is not re-processed.
            watermark = int(new_watermark) + 1
        print(result, flush=True)
        time.sleep(interval_sec)


def add_paper_log_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_MODEL_ARTIFACT_DIR))
    parser.add_argument("--batch-rows", type=int, default=5000)
    parser.add_argument("--signals-only", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--min-received-at-ns", type=int, default=None)
    parser.add_argument("--force-full-rescore", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval-sec", type=float, default=30.0)


def add_freeze_paper_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executable-path", default=str(EXECUTABLE_BACKTEST_PATH))
    parser.add_argument("--artifact-dir", default=str(DEFAULT_MODEL_ARTIFACT_DIR))


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
    if "strategy_filter" in row and not bool(row.get("strategy_filter")):
        return "outside_strategy_filter"
    if pd.isna(row.get("fair_prob")) or pd.isna(row.get("edge")):
        return "missing_model_score"
    if float(row.get("edge")) < threshold:
        return "below_threshold"
    return "no_signal"


def _signal_groups(decisions: pd.DataFrame, *, exposure_level: bool) -> pd.Series:
    decisions = _add_map_exposure_id(decisions)
    if exposure_level:
        key_cols = ["match_id", "map_exposure_id"]
    else:
        key_cols = ["match_id", "canonical_exposure_id", "received_at_ns", "side"]
    specs_by_model = {spec.model_name: spec for spec in PAPER_DECISION_MODEL_SPECS}
    model_names = list(specs_by_model)
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
    for model_name in model_names:
        if model_name not in signal_map.columns:
            signal_map[model_name] = False

    def group(row: pd.Series) -> str:
        signaled = [
            specs_by_model[model_name].candidate_group
            for model_name in model_names
            if bool(row.get(model_name))
        ]
        if not signaled:
            return "no_signal"
        group_set = set(signaled)
        has_primary = "primary" in group_set
        has_benchmark = bool(group_set.intersection({"benchmark", "full_state_benchmark"}))
        has_gettoplive = "gettoplive_candidate" in group_set
        has_control = "control" in group_set
        if has_primary and has_benchmark and has_control:
            return "primary_benchmark_control"
        if has_primary and has_benchmark:
            return "primary_and_benchmark"
        if has_primary and has_gettoplive and has_control:
            return "primary_gettoplive_control"
        if has_primary and has_gettoplive:
            return "primary_and_gettoplive"
        if has_benchmark and has_gettoplive and has_control:
            return "benchmark_gettoplive_control"
        if has_benchmark and has_gettoplive:
            return "benchmark_and_gettoplive"
        if has_primary and has_control:
            return "primary_and_control"
        if has_primary:
            return "primary_only"
        if has_gettoplive and has_control:
            return "gettoplive_and_control"
        if has_gettoplive:
            return "gettoplive_only"
        if has_benchmark and has_control:
            return "benchmark_and_control"
        if has_benchmark:
            return "benchmark_only"
        if has_control:
            return "control_only"
        return "other_signal"

    signal_map["_signal_group"] = signal_map.apply(group, axis=1)
    return decisions.merge(signal_map[key_cols + ["_signal_group"]], on=key_cols, how="left")["_signal_group"]


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


def _read_parquet_dir(path: Path, min_received_at_ns: int | None = None) -> pd.DataFrame:
    files = sorted(path.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    con = duckdb.connect()
    glob = str(path / "*.parquet")
    if min_received_at_ns is not None:
        # DuckDB pushes the predicate into the parquet reader so only
        # matching row-groups are scanned — orders of magnitude cheaper
        # than loading the full directory into a DataFrame.
        return con.execute(
            "select * from read_parquet(?, union_by_name=true)"
            " where received_at_ns >= ?",
            [glob, min_received_at_ns],
        ).fetchdf()
    return con.execute(
        "select * from read_parquet(?, union_by_name=true)",
        [glob],
    ).fetchdf()


def _has_existing_decisions(path: Path) -> bool:
    return any(path.glob("*.parquet"))


def _read_existing_decision_ids(path: Path, *, mode: str = "latest") -> set[str]:
    # When a watermark is in use the decision IDs within the new window are
    # always fresh, so we only need IDs from the very latest file to guard
    # against the edge-case where a cycle is retried.
    files = sorted(path.glob("*.parquet"))
    if not files:
        return set()
    if mode not in {"latest", "all"}:
        raise ValueError(f"unknown existing decision id mode: {mode!r}")
    if mode == "all":
        con = duckdb.connect()
        frame = con.execute(
            "select decision_id from read_parquet(?, union_by_name=true)",
            [str(path / "*.parquet")],
        ).fetchdf()
    else:
        frame = pd.read_parquet(files[-1], columns=["decision_id"])
    if frame.empty or "decision_id" not in frame.columns:
        return set()
    return set(frame["decision_id"].dropna().astype(str))


def _latest_decision_watermark(path: Path) -> int | None:
    """Return max received_at_ns from the most-recent decision file, or None."""
    files = sorted(path.glob("*.parquet"))
    if not files:
        return None
    try:
        frame = pd.read_parquet(files[-1], columns=["received_at_ns"])
        if frame.empty:
            return None
        raw = pd.to_numeric(frame["received_at_ns"], errors="coerce").max()
        return int(raw) + 1 if not pd.isna(raw) else None
    except Exception:
        return None


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
