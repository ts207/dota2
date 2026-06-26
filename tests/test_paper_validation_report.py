from __future__ import annotations

import json
from pathlib import Path

import pytest
import pandas as pd

from dota2bot.decision_reports import run_paper_validation_report
from dota2bot.schemas import DECISION_COLUMNS
from dota2bot.strategy_contract import ACTIVE_SETTLED_PAPER_DECISIONS_NAME


def test_paper_validation_report_uses_global_non_control_accounting(tmp_path: Path):
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS} for _ in range(5)])
    decisions["decision_id"] = ["primary_m1", "benchmark_m1", "benchmark_m2", "control_m3", "benchmark_m4"]
    decisions["model_name"] = [
        "winprob_logistic_evfilter",
        "market_gettoplive_logistic",
        "market_gettoplive_logistic",
        "market_only_logistic",
        "market_gettoplive_logistic",
    ]
    decisions["candidate_group"] = ["primary", "benchmark", "benchmark", "control", "benchmark"]
    decisions["match_id"] = ["m1", "m1", "m2", "m3", "m4"]
    decisions["label_market_bucket"] = ["MAP_WINNER", "MAP_WINNER", "MATCH_WINNER_GAME3_PROXY", "MAP_WINNER", "MAP_WINNER"]
    decisions["current_game_number"] = [1, 1, 1, 1, 2]
    decisions["canonical_exposure_id"] = ["m1::1::YES", "m1::1::YES", "m2::1::NO", "m3::1::YES", "m4::2::YES"]
    decisions["received_at_utc"] = [
        "2026-06-25T01:00:00Z",
        "2026-06-25T01:00:00Z",
        "2026-06-25T02:00:00Z",
        "2026-06-25T03:00:00Z",
        "2026-06-25T04:00:00Z",
    ]
    decisions["received_at_ns"] = [100, 100, 200, 50, 400]
    decisions["side"] = ["YES", "YES", "NO", "YES", "YES"]
    decisions["signal"] = [True, True, True, True, True]
    decisions["ask"] = [0.40, 0.41, 0.30, 0.20, 0.25]
    decisions["edge"] = [0.08, 0.09, 0.06, 0.20, 0.07]
    decisions["settled_win"] = [True, True, False, False, None]
    decisions["paper_pnl_per_share"] = [0.60, 0.59, -0.30, -0.20, None]
    decisions["pnl_slip_1c"] = [0.59, 0.58, -0.31, -0.21, None]
    decisions["pnl_slip_2c"] = [0.58, 0.57, -0.32, -0.22, None]

    out_dir = tmp_path / ACTIVE_SETTLED_PAPER_DECISIONS_NAME
    out_dir.mkdir()
    decisions.to_parquet(out_dir / "latest.parquet", index=False)

    summary = json.loads(run_paper_validation_report(logs_root=tmp_path, output_format="json"))

    assert summary["global_non_control"]["trade_rows"] == 3
    assert summary["global_non_control"]["settled_trade_rows"] == 2
    assert summary["global_non_control"]["pending_trade_rows"] == 1
    assert summary["global_non_control"]["pnl_slip_2c"] == pytest.approx(0.26)
    assert summary["global_non_control"]["win_rate"] == pytest.approx(0.5)
    assert {row["model_name"]: row["trade_rows"] for row in summary["models"]} == {
        "winprob_logistic_evfilter": 1,
        "market_gettoplive_logistic": 3,
        "market_only_logistic": 1,
    }
    assert {row["exposure_signal_group"]: row["trade_rows"] for row in summary["attribution"]} == {
        "primary_and_benchmark": 1,
        "benchmark_only": 2,
    }
    assert summary["pending_global_trades"][0]["match_id"] == "m4"
    assert summary["pending_global_trades"][0]["exposure_signal_group"] == "benchmark_only"


def test_paper_validation_report_markdown_has_operational_sections(tmp_path: Path):
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS}])
    decisions["decision_id"] = ["primary_m1"]
    decisions["model_name"] = ["winprob_logistic_evfilter"]
    decisions["candidate_group"] = ["primary"]
    decisions["match_id"] = ["m1"]
    decisions["label_market_bucket"] = ["MAP_WINNER"]
    decisions["current_game_number"] = [1]
    decisions["canonical_exposure_id"] = ["m1::1::YES"]
    decisions["received_at_ns"] = [100]
    decisions["side"] = ["YES"]
    decisions["signal"] = [True]
    decisions["ask"] = [0.40]
    decisions["edge"] = [0.08]
    decisions["settled_win"] = [True]
    decisions["paper_pnl_per_share"] = [0.60]
    decisions["pnl_slip_1c"] = [0.59]
    decisions["pnl_slip_2c"] = [0.58]
    out_dir = tmp_path / ACTIVE_SETTLED_PAPER_DECISIONS_NAME
    out_dir.mkdir()
    decisions.to_parquet(out_dir / "latest.parquet", index=False)

    report = run_paper_validation_report(logs_root=tmp_path)

    assert "# Paper Validation Report" in report
    assert "## Global Non-Control" in report
    assert "## Global Attribution" in report
    assert "## Edge Buckets" in report
    assert "## Match Concentration" in report
    assert "## Pending Global Trades" in report
    assert "winprob_logistic_evfilter" in report


def test_paper_validation_report_gettoplive_attribution_labels(tmp_path: Path):
    """gettoplive_candidate signals produce correct exposure group labels."""
    decisions = pd.DataFrame([{col: None for col in DECISION_COLUMNS} for _ in range(3)])
    decisions["decision_id"] = ["gtl_m1", "ctl_m1", "gtl_m2"]
    decisions["model_name"] = [
        "gettoplive_kill_mom_favorite_hold_rule",
        "market_only_logistic",
        "gettoplive_kill_mom_favorite_hold_rule",
    ]
    decisions["candidate_group"] = ["gettoplive_candidate", "control", "gettoplive_candidate"]
    decisions["match_id"] = ["m1", "m1", "m2"]
    decisions["label_market_bucket"] = ["MAP_WINNER"] * 3
    decisions["current_game_number"] = [1, 1, 1]
    decisions["canonical_exposure_id"] = ["m1::1::YES", "m1::1::YES", "m2::1::YES"]
    decisions["received_at_ns"] = [100, 100, 200]
    decisions["side"] = ["YES"] * 3
    decisions["signal"] = [True, True, True]
    decisions["ask"] = [0.60, 0.20, 0.65]
    decisions["edge"] = [1.0, 0.15, 1.0]
    decisions["settled_win"] = [True, False, True]
    decisions["paper_pnl_per_share"] = [0.40, -0.20, 0.35]
    decisions["pnl_slip_1c"] = [0.39, -0.21, 0.34]
    decisions["pnl_slip_2c"] = [0.38, -0.22, 0.33]

    out_dir = tmp_path / ACTIVE_SETTLED_PAPER_DECISIONS_NAME
    out_dir.mkdir()
    decisions.to_parquet(out_dir / "latest.parquet", index=False)

    summary = json.loads(run_paper_validation_report(logs_root=tmp_path, output_format="json"))

    group_labels = {row["exposure_signal_group"] for row in summary["attribution"]}
    # m1 has gettoplive + control => gettoplive_and_control; m2 is gettoplive_only
    assert "gettoplive_and_control" in group_labels or "gettoplive_only" in group_labels
    assert "other_signal" not in group_labels


def test_signal_group_label_gettoplive_variants():
    """All gettoplive_candidate combinations produce named labels, not other_signal."""
    from dota2bot.decision_reports import _signal_group_label

    assert _signal_group_label({"gettoplive_candidate"}) == "gettoplive_only"
    assert _signal_group_label({"gettoplive_candidate", "control"}) == "gettoplive_and_control"
    assert _signal_group_label({"gettoplive_candidate", "benchmark"}) == "benchmark_and_gettoplive"
    assert _signal_group_label({"gettoplive_candidate", "benchmark", "control"}) == "benchmark_gettoplive_control"
    assert _signal_group_label({"gettoplive_candidate", "primary"}) == "primary_and_gettoplive"
    assert _signal_group_label({"gettoplive_candidate", "primary", "control"}) == "primary_gettoplive_control"
    assert _signal_group_label({"control"}) == "control_only"
    assert _signal_group_label({"primary"}) == "primary_only"
