from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dota2bot.decision_reports import first_global_signal_trades, first_signal_trades, run_report_decisions, run_settle_decisions
from dota2bot.paper_strategy_logger import (
    PAPER_MODEL_SPECS,
    PaperModelBundle,
    add_model_scores,
    load_paper_model_bundle,
    run_paper_log,
    save_paper_model_bundle,
    score_paper_decisions,
    validate_paper_model_artifact,
)
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
    assert len(PAPER_MODEL_SPECS) == 3
    assert PAPER_MODEL_SPECS[0].model_name == "winprob_logistic_evfilter"
    assert PAPER_MODEL_SPECS[0].entry_threshold == 0.05
    assert PAPER_MODEL_SPECS[0].score_kind == "win_prob_2c"
    assert PAPER_MODEL_SPECS[0].market_scopes == ("map_winner_explicit", "series_decider_equivalent")
    assert PAPER_MODEL_SPECS[0].min_ask == 0.20
    assert PAPER_MODEL_SPECS[0].max_ask == 0.50
    assert list(PAPER_MODEL_SPECS[1:2]) == list(BENCHMARK_MARKET_ANCHOR_SPECS)
    assert list(PAPER_MODEL_SPECS[2:]) == list(CONTROL_MARKET_ANCHOR_SPECS)
    assert BENCHMARK_MARKET_ANCHOR_SPECS[0].model_name == "market_gettoplive_logistic"
    assert ACTIVE_MARKET_ANCHOR_MODEL_VERSION == "winprob_evfilter_paper_v1_mapequiv_ask20_50_e05"
    assert ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE == "live_executable"


def test_win_prob_2c_edge_subtracts_ask_and_two_cent_cost():
    frame = pd.DataFrame({"book_best_ask": [0.50]})
    scored = add_model_scores(frame, FixedProbModel(0.75), ["book_best_ask"], score_kind="win_prob_2c")

    assert scored.loc[0, "fair_prob"] == 0.75
    assert scored.loc[0, "edge"] == pytest.approx(0.23)


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
    decisions["match_id"] = ["m1", "m2"]
    decisions["current_game_number"] = [1, 1]
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


def test_report_global_exposure_excludes_control_models(tmp_path: Path):
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS} for _ in range(2)])
    decisions["decision_id"] = ["control_first", "primary_second"]
    decisions["model_name"] = ["market_only_logistic", "winprob_logistic_evfilter"]
    decisions["candidate_group"] = ["control", "primary"]
    decisions["match_id"] = ["m1", "m1"]
    decisions["current_game_number"] = [1, 1]
    decisions["received_at_ns"] = [100, 200]
    decisions["signal"] = [True, True]
    decisions["settled_win"] = [False, True]
    decisions["ask"] = [0.30, 0.40]
    decisions["paper_pnl_per_share"] = [-0.30, 0.60]
    decisions["pnl_slip_1c"] = [-0.31, 0.59]
    decisions["pnl_slip_2c"] = [-0.32, 0.58]
    out_dir = tmp_path / "settled_strategy_decisions"
    out_dir.mkdir()
    decisions.to_parquet(out_dir / "latest.parquet", index=False)

    summary = run_report_decisions(logs_root=tmp_path, output_format="json")

    assert '"global_trade_rows": 1' in summary
    assert '"pnl_slip_2c": 0.58' in summary
    assert '"trade_rows": 2' in summary


def test_global_exposure_tie_break_prefers_primary_over_benchmark():
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS} for _ in range(2)])
    decisions["decision_id"] = ["benchmark", "primary"]
    decisions["model_name"] = ["market_gettoplive_logistic", "winprob_logistic_evfilter"]
    decisions["candidate_group"] = ["benchmark", "primary"]
    decisions["match_id"] = ["m1", "m1"]
    decisions["current_game_number"] = [1, 1]
    decisions["received_at_ns"] = [100, 100]
    decisions["signal"] = [True, True]

    trades = first_global_signal_trades(decisions)

    assert trades["decision_id"].tolist() == ["primary"]


def test_first_signal_trades_dedupes_opposite_sides_per_model_map():
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS} for _ in range(3)])
    decisions["decision_id"] = ["d1", "d2", "d3"]
    decisions["model_name"] = ["m", "m", "m"]
    decisions["match_id"] = ["match1", "match1", "match1"]
    decisions["current_game_number"] = [1, 1, 2]
    decisions["side"] = ["YES", "NO", "YES"]
    decisions["canonical_exposure_id"] = ["match1::1::YES", "match1::1::NO", "match1::2::YES"]
    decisions["received_at_ns"] = [100, 200, 300]
    decisions["signal"] = [True, True, True]

    trades = first_signal_trades(decisions)

    assert trades["decision_id"].tolist() == ["d1", "d3"]


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
    monkeypatch.setattr("dota2bot.paper_strategy_logger.load_paper_model_bundle", lambda **_: bundle)

    result = run_paper_log(logs_root=tmp_path, min_received_at_ns=200)
    decisions = pd.read_parquet(next((tmp_path / "strategy_decisions").glob("*.parquet")))

    assert result["input_rows"] == 1
    assert set(decisions["received_at_ns"]) == {200}


def test_run_paper_log_refuses_full_rescore_into_existing_ledger(tmp_path: Path, monkeypatch):
    live_dir = tmp_path / "live_side_snapshots"
    live_dir.mkdir()
    pd.DataFrame([_side_row(received_at_ns=100)]).to_parquet(live_dir / "part.parquet", index=False)
    out_dir = tmp_path / "strategy_decisions"
    out_dir.mkdir()
    pd.DataFrame([{col: None for col in DECISION_COLUMNS}]).to_parquet(out_dir / "part-old.parquet", index=False)
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )
    monkeypatch.setattr("dota2bot.paper_strategy_logger.load_paper_model_bundle", lambda **_: bundle)

    with pytest.raises(ValueError, match="refusing full paper-log rescore"):
        run_paper_log(logs_root=tmp_path)


def test_force_full_rescore_dedupes_against_all_existing_parts(tmp_path: Path, monkeypatch):
    live_dir = tmp_path / "live_side_snapshots"
    live_dir.mkdir()
    pd.DataFrame([_side_row(received_at_ns=100)]).to_parquet(live_dir / "part.parquet", index=False)
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )
    monkeypatch.setattr("dota2bot.paper_strategy_logger.load_paper_model_bundle", lambda **_: bundle)

    first = run_paper_log(logs_root=tmp_path, force_full_rescore=True)
    second = run_paper_log(logs_root=tmp_path, force_full_rescore=True)

    assert first["written_rows"] == len(PAPER_MODEL_SPECS)
    assert second["written_rows"] == 0
    assert second["skipped_existing_rows"] == len(PAPER_MODEL_SPECS)


def test_save_and_load_paper_model_bundle_round_trips(tmp_path: Path):
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )

    result = save_paper_model_bundle(bundle, artifact_dir=tmp_path / "artifact")
    loaded = load_paper_model_bundle(artifact_dir=tmp_path / "artifact")

    assert Path(result["bundle_path"]).exists()
    assert Path(result["manifest_path"]).exists()
    assert loaded.model_version == bundle.model_version
    assert loaded.specs == bundle.specs


def test_validate_paper_model_artifact_checks_manifest_contract(tmp_path: Path):
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )
    artifact_dir = tmp_path / "artifact"
    save_paper_model_bundle(bundle, artifact_dir=artifact_dir)

    result = validate_paper_model_artifact(artifact_dir=artifact_dir)

    assert result["valid"] is True
    assert result["model_version"] == ACTIVE_MARKET_ANCHOR_MODEL_VERSION

    manifest_path = artifact_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["model_version"] = "stale"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="model_version"):
        validate_paper_model_artifact(artifact_dir=artifact_dir)


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
