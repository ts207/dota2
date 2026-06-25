from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dota2bot.decision_reports import run_report_decisions, run_settle_decisions
from dota2bot.paper_strategy_logger import PAPER_MODEL_SPECS, PaperModelBundle, run_paper_log, score_paper_decisions
from dota2bot.schemas import DECISION_COLUMNS, SIDE_SNAPSHOT_COLUMNS
from dota2bot.strategy_contract import (
    ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE,
    ACTIVE_MARKET_ANCHOR_MODEL_VERSION,
    ACTIVE_MARKET_ANCHOR_SPECS,
    BENCHMARK_MARKET_ANCHOR_SPECS,
    CONTROL_MARKET_ANCHOR_SPECS,
    PAPER_MARKET_ANCHOR_SPECS,
)


class FixedProbModel:
    def __init__(self, probability: float):
        self.probability = probability

    def predict_proba(self, frame: pd.DataFrame):
        return np.array([[1.0 - self.probability, self.probability] for _ in range(len(frame))])


def test_score_paper_decisions_logs_paper_validation_suite():
    frame = pd.DataFrame([_side_row()])
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )

    decisions = score_paper_decisions(frame, bundle)

    assert list(decisions.columns) == DECISION_COLUMNS
    assert len(decisions) == len(PAPER_MODEL_SPECS)
    assert decisions["signal"].all()
    assert decisions["signal_group"].unique().tolist() == ["primary_benchmark_control"]
    assert set(decisions["model_name"]) == {spec.model_name for spec in PAPER_MODEL_SPECS}
    assert decisions["entry_threshold"].notna().all()


def test_paper_specs_use_active_strategy_contract():
    assert PAPER_MODEL_SPECS == list(PAPER_MARKET_ANCHOR_SPECS)
    assert len(PAPER_MODEL_SPECS) == 4
    assert PAPER_MODEL_SPECS[0].model_name == "market_nw_kill_momentum_logistic"
    assert PAPER_MODEL_SPECS[0].entry_threshold == 0.18
    assert list(PAPER_MODEL_SPECS[1:3]) == list(BENCHMARK_MARKET_ANCHOR_SPECS)
    assert list(PAPER_MODEL_SPECS[3:]) == list(CONTROL_MARKET_ANCHOR_SPECS)
    assert ACTIVE_MARKET_ANCHOR_MODEL_VERSION == "market_anchor_paper_v4_edge18_live_exec_benchmarks"
    assert ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE == "live_executable"


def test_default_paper_gate_requires_live_executable_snapshot():
    row = _side_row()
    row["executable_snapshot"] = False
    row["quality_reason"] = "small_ask_size"
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )

    default_gate = score_paper_decisions(pd.DataFrame([row]), bundle)

    assert not default_gate["signal"].any()
    assert set(default_gate["reason"]) == {"small_ask_size"}
    with pytest.raises(ValueError, match="unknown eligibility_mode"):
        score_paper_decisions(pd.DataFrame([row]), bundle, eligibility_mode="research")


def test_settle_decisions_fills_pnl_from_settled_side_rows(tmp_path: Path):
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS}])
    decisions.loc[0, ["decision_id", "strategy_name", "model_name", "match_id", "market_id", "token_id", "received_at_ns", "ask", "signal"]] = [
        "d1",
        "paper_market_momentum",
        "market_momentum_logistic",
        "m1",
        "mk1",
        "tok1",
        1000,
        0.40,
        True,
    ]
    decision_dir = tmp_path / "strategy_decisions"
    decision_dir.mkdir()
    decisions.to_parquet(decision_dir / "part.parquet", index=False)

    side = pd.DataFrame([{col: None for col in SIDE_SNAPSHOT_COLUMNS}])
    side.loc[0, ["match_id", "market_id", "token_id", "received_at_ns", "settled_win"]] = [
        "m1",
        "mk1",
        "tok1",
        1000,
        True,
    ]
    side_dir = tmp_path / "live_settled_side_snapshots"
    side_dir.mkdir()
    side.to_parquet(side_dir / "latest.parquet", index=False)

    result = run_settle_decisions(logs_root=tmp_path)
    settled = pd.read_parquet(tmp_path / "settled_strategy_decisions" / "latest.parquet")

    assert result["settled_signal_rows"] == 1
    assert bool(settled.loc[0, "settled_win"]) is True
    assert settled.loc[0, "paper_pnl_per_share"] == 0.60
    assert settled.loc[0, "pnl_slip_1c"] == 0.59


def test_settle_decisions_handles_no_settled_signals(tmp_path: Path):
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS}])
    decisions.loc[0, ["decision_id", "strategy_name", "model_name", "match_id", "market_id", "token_id", "received_at_ns", "ask", "signal"]] = [
        "d1",
        "paper_market_momentum",
        "market_momentum_logistic",
        "m1",
        "mk1",
        "tok1",
        1000,
        0.40,
        True,
    ]
    decision_dir = tmp_path / "forward_strategy_decisions"
    decision_dir.mkdir()
    decisions.to_parquet(decision_dir / "part.parquet", index=False)
    side_dir = tmp_path / "live_settled_side_snapshots"
    side_dir.mkdir()
    pd.DataFrame([{col: None for col in SIDE_SNAPSHOT_COLUMNS}]).to_parquet(side_dir / "latest.parquet", index=False)

    result = run_settle_decisions(
        logs_root=tmp_path,
        decisions_name="forward_strategy_decisions",
        output_name="forward_settled_strategy_decisions",
    )

    assert result["decision_rows"] == 1
    assert result["settled_signal_rows"] == 0


def test_report_decisions_summarizes_model_and_signal_group(tmp_path: Path):
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS} for _ in range(2)])
    decisions["model_name"] = ["market_momentum_logistic", "market_momentum_logistic"]
    decisions["signal"] = [True, True]
    decisions["settled_win"] = [True, False]
    decisions["ask"] = [0.40, 0.30]
    decisions["paper_pnl_per_share"] = [0.60, -0.30]
    decisions["pnl_slip_1c"] = [0.59, -0.31]
    decisions["pnl_slip_2c"] = [0.58, -0.32]
    decisions["signal_group"] = ["momentum_only", "momentum_only"]
    decisions["canonical_exposure_id"] = ["m1::1::YES", "m2::1::NO"]
    out_dir = tmp_path / "settled_strategy_decisions"
    out_dir.mkdir()
    decisions.to_parquet(out_dir / "latest.parquet", index=False)

    report = run_report_decisions(logs_root=tmp_path)

    assert "market_momentum_logistic" in report
    assert "momentum_only" in report
    assert "+0.2800" in report
    assert "Global Exposure" in report


def test_run_paper_log_respects_min_received_at_ns(tmp_path: Path, monkeypatch):
    live_dir = tmp_path / "live_side_snapshots"
    live_dir.mkdir()
    pd.DataFrame([_side_row(received_at_ns=100), _side_row(received_at_ns=200)]).to_parquet(
        live_dir / "part.parquet",
        index=False,
    )
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )
    monkeypatch.setattr("dota2bot.paper_strategy_logger.train_paper_model_bundle", lambda **_: bundle)

    result = run_paper_log(logs_root=tmp_path, min_received_at_ns=200)
    decisions = pd.read_parquet(next((tmp_path / "strategy_decisions").glob("*.parquet")))

    assert result["input_rows"] == 1
    assert set(decisions["received_at_ns"]) == {200}


def _side_row(received_at_ns: int = 1000) -> dict:
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row.update(
        {
            "match_id": "m1",
            "market_id": "mk1",
            "label_market_bucket": "MAP_WINNER",
            "market_scope": "map_winner_explicit",
            "current_game_number": 1,
            "token_id": "tok1",
            "side": "YES",
            "received_at_utc": "2026-06-24T00:00:00+00:00",
            "received_at_ns": received_at_ns,
            "game_time_sec": 900,
            "book_received_at_ns": 900,
            "book_age_ms": 1000.0,
            "book_best_bid": 0.49,
            "book_best_ask": 0.50,
            "book_ask_size": 200.0,
            "book_spread": 0.01,
            "executable_snapshot": True,
            "quality_reason": "ok",
            "side_is_radiant": True,
            "radiant_lead": 5000,
            "net_worth_diff": 5000,
            "radiant_score": 20,
            "dire_score": 15,
            "building_state": None,
            "tower_state": None,
        }
    )
    return row
