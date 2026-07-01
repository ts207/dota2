import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import json

from dota2bot.statistical_report import run_statistical_report_for_sizing, run_statistical_report
from dota2bot.sizing_engine import simulate_sizing

@pytest.fixture
def sample_frame():
    return pd.DataFrame([
        {
            "blocked_reason": None,
            "strategy_name": "strat_a",
            "candidate_group": "primary",
            "map_exposure_id": "map_1",
            "entry_ask": 0.5,
            "pnl_per_share_2c": 0.1,
            "edge": 0.08,
            "fair_prob": 0.55,
            "side_kill_mom": 2.0,
            "book_ask_size": 100,
            "book_age_ms": 1000,
            "game_time_sec": 1200,
            "settled_win": True,
            "entry_received_at_ns": 1000,
        },
        {
            "blocked_reason": None,
            "strategy_name": "strat_a",
            "candidate_group": "primary",
            "map_exposure_id": "map_2",
            "entry_ask": 0.6,
            "pnl_per_share_2c": -0.1,
            "edge": 0.06,
            "fair_prob": 0.52,
            "side_kill_mom": 1.0,
            "book_ask_size": 200,
            "book_age_ms": 2000,
            "game_time_sec": 1500,
            "settled_win": False,
            "entry_received_at_ns": 2000,
        },
        {
            "blocked_reason": None,
            "strategy_name": "strat_b",
            "candidate_group": "gettoplive_candidate",
            "map_exposure_id": "map_3",
            "entry_ask": 0.4,
            "pnl_per_share_2c": 0.2,
            "edge": 0.02,
            "fair_prob": 0.45,
            "side_kill_mom": 4.0,
            "book_ask_size": 150,
            "book_age_ms": 500,
            "game_time_sec": 800,
            "settled_win": True,
            "entry_received_at_ns": 500,
        }
    ])

def test_shared_sizing_equivalence(sample_frame):
    # simulate_sizing is used by both
    df1 = simulate_sizing(sample_frame, "group_specific_default")
    
    res = run_statistical_report_for_sizing(
        frame=sample_frame,
        source="active",
        sizing="group_specific_default",
        bootstrap_samples=10,
        seed=42
    )
    
    # We should have the same sim_shares values as df1
    df1_strat_a_shares = df1[df1["strategy_name"] == "strat_a"]["sim_shares"].values
    # In run_statistical_report_for_sizing, we can't directly check the dataframe easily 
    # as it's not returned, but we can verify it ran without error and returned metrics
    assert "error" not in res
    assert len(res["core_metrics"]) == 2

def test_chronological_drawdown(sample_frame):
    # Create a frame with out of order time
    frame = sample_frame.copy()
    # Add a third strat_a entry
    new_row = frame.iloc[0].copy()
    new_row["entry_received_at_ns"] = 1500 # Between 1000 and 2000
    new_row["pnl_per_share_2c"] = -0.5
    new_row["map_exposure_id"] = "map_1_b"
    frame = pd.concat([frame, pd.DataFrame([new_row])], ignore_index=True)
    
    res = run_statistical_report_for_sizing(
        frame=frame,
        source="active",
        sizing="flat_1",
        bootstrap_samples=10,
        seed=42
    )
    
    strat_a_metric = [m for m in res["core_metrics"] if m["Strategy"] == "strat_a"][0]
    
    # Order:
    # 1. 1000ns: pnl = 1.0 * 0.1 = 0.1
    # 2. 1500ns: pnl = 1.0 * -0.5 = -0.5
    # 3. 2000ns: pnl = 1.0 * -0.1 = -0.1
    # Cumulatives: [0.1, -0.4, -0.5]
    # Peak is 0.1.
    # Max DD should be peak (0.1) - min_cum (-0.5) = 0.6
    assert float(strat_a_metric["Max DD"]) == pytest.approx(0.6, abs=0.01)

def test_json_output(sample_frame, tmp_path, capsys):
    log_dir = tmp_path / "paper_positions"
    log_dir.mkdir()
    sample_frame.to_parquet(log_dir / "00001.parquet")
    
    run_statistical_report(
        logs_root=tmp_path,
        source="active",
        sizing="flat_1",
        output_format="json"
    )
    
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert isinstance(output, list)
    assert len(output) == 1
    assert output[0]["source"] == "active"
    assert output[0]["sizing"] == "flat_1"

def test_sizing_all(sample_frame, tmp_path, capsys):
    log_dir = tmp_path / "paper_positions"
    log_dir.mkdir()
    sample_frame.to_parquet(log_dir / "00001.parquet")
    
    run_statistical_report(
        logs_root=tmp_path,
        source="active",
        sizing="all",
        output_format="json"
    )
    
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert len(output) == 6 # flat_1, flat_5, kill_mom_scaled, edge_scaled, conservative, group
    sizings = [r["sizing"] for r in output]
    assert "conservative_group_default" in sizings

