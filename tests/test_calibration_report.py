from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from dota2bot.calibration_report import run_paper_calibration_report
from dota2bot.paper_strategy_logger import PAPER_MODEL_SPECS, PaperModelBundle, save_paper_model_bundle
from dota2bot.schemas import SIDE_SNAPSHOT_COLUMNS


class FixedProbModel:
    def __init__(self, probability: float):
        self.probability = probability

    def predict_proba(self, frame: pd.DataFrame):
        return np.array([[1.0 - self.probability, self.probability] for _ in range(len(frame))])


def test_paper_calibration_report_outputs_ask_and_edge_buckets(tmp_path: Path):
    rows = [
        _side_row(match_id="m1", received_at_ns=50, game_time_sec=800, radiant_lead=4000),
        _side_row(match_id="m1", received_at_ns=100, game_time_sec=900, radiant_lead=5000),
        _side_row(match_id="m2", received_at_ns=150, game_time_sec=800, radiant_lead=4000),
        _side_row(match_id="m2", received_at_ns=200, game_time_sec=900, radiant_lead=5000),
    ]
    rows[1]["settled_win"] = True
    rows[3]["settled_win"] = False
    rows[3]["executable_snapshot"] = False
    executable_path = tmp_path / "clean.parquet"
    pd.DataFrame(rows).to_parquet(executable_path, index=False)
    bundle = PaperModelBundle(
        models={spec.model_name: (FixedProbModel(0.75), ["book_best_ask"]) for spec in PAPER_MODEL_SPECS},
        specs=PAPER_MODEL_SPECS,
        training_cutoff="2026-06-24T00:00:00+00:00",
    )
    artifact_dir = tmp_path / "artifact"
    save_paper_model_bundle(bundle, artifact_dir=artifact_dir, executable_path=executable_path)

    report = run_paper_calibration_report(
        executable_path=executable_path,
        artifact_dir=artifact_dir,
    )

    assert "# Paper Model Calibration" in report
    assert "eligibility: historical_research" in report
    assert "## Row Ask Buckets" in report
    assert "## Row Edge Buckets" in report
    assert "## Trade Ask Buckets" in report
    assert "## Trade Edge Buckets" in report
    assert "winprob_logistic_evfilter" in report

    historical = json.loads(
        run_paper_calibration_report(
            executable_path=executable_path,
            artifact_dir=artifact_dir,
            output_format="json",
        )
    )
    live = json.loads(
        run_paper_calibration_report(
            executable_path=executable_path,
            artifact_dir=artifact_dir,
            eligibility_mode="live_executable",
            output_format="json",
        )
    )
    historical_primary_rows = [
        row
        for row in historical["rows"]
        if row["table"] == "ask_bucket"
        and row["model_name"] == "winprob_logistic_evfilter"
        and row["bucket"] == "(0.4, 0.5]"
    ]
    live_primary_rows = [
        row
        for row in live["rows"]
        if row["table"] == "ask_bucket"
        and row["model_name"] == "winprob_logistic_evfilter"
        and row["bucket"] == "(0.4, 0.5]"
    ]
    assert historical["eligibility_mode"] == "historical_research"
    assert live["eligibility_mode"] == "live_executable"
    assert historical_primary_rows[0]["rows"] == 2
    assert live_primary_rows[0]["rows"] == 1


def _side_row(
    *,
    match_id: str,
    received_at_ns: int,
    game_time_sec: int,
    radiant_lead: int,
) -> dict:
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row.update(
        {
            "match_id": match_id,
            "market_id": "mk1",
            "label_market_bucket": "MAP_WINNER",
            "market_scope": "map_winner_explicit",
            "current_game_number": 1,
            "token_id": "tok1",
            "side": "YES",
            "received_at_utc": "2026-06-24T00:00:00+00:00",
            "received_at_ns": received_at_ns,
            "game_time_sec": game_time_sec,
            "book_received_at_ns": 900,
            "book_age_ms": 1000.0,
            "book_best_bid": 0.49,
            "book_best_ask": 0.50,
            "book_ask_size": 200.0,
            "book_spread": 0.01,
            "executable_snapshot": True,
            "quality_reason": "ok",
            "side_is_radiant": True,
            "radiant_lead": radiant_lead,
            "net_worth_diff": radiant_lead,
            "radiant_score": 20,
            "dire_score": 15,
            "building_state": None,
            "tower_state": None,
        }
    )
    return row
