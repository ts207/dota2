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
    # compute expected stake and pnl
    df1 = simulate_sizing(sample_frame, "group_specific_default")
    expected_stats = df1.groupby("strategy_name")[["sim_stake", "sim_pnl_2c"]].sum()
    
    res = run_statistical_report_for_sizing(
        frame=sample_frame,
        source="active",
        sizing="group_specific_default",
        bootstrap_samples=10,
        seed=42
    )
    
    assert "error" not in res
    
    metrics = {m["Strategy"]: m for m in res["core_metrics"]}
    assert metrics["strat_a"]["Stake"] == f"{expected_stats.loc['strat_a', 'sim_stake']:.1f}"
    assert metrics["strat_a"]["PnL 2c"] == f"{expected_stats.loc['strat_a', 'sim_pnl_2c']:.2f}"
    assert metrics["strat_b"]["Stake"] == f"{expected_stats.loc['strat_b', 'sim_stake']:.1f}"
    assert metrics["strat_b"]["PnL 2c"] == f"{expected_stats.loc['strat_b', 'sim_pnl_2c']:.2f}"

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

def test_unknown_sizing_raises_value_error(sample_frame):
    with pytest.raises(ValueError, match="unknown sizing scheme"):
        simulate_sizing(sample_frame, "conservtive_group_default")

def test_sizing_order_independence(sample_frame):
    # Cap is 200. Let's make an entry that uses 200 map notional.
    # If order is correct, the earlier one gets the map cap.
    frame = sample_frame.copy()
    
    # 2 rows for the same map
    r1 = frame.iloc[0].copy()
    r1["entry_received_at_ns"] = 1000
    r1["map_exposure_id"] = "map_shared"
    r1["entry_ask"] = 1.0 # price 1.0
    
    r2 = frame.iloc[0].copy()
    r2["entry_received_at_ns"] = 2000
    r2["map_exposure_id"] = "map_shared"
    r2["entry_ask"] = 1.0
    
    # We will use "flat_25_liquidity_unchecked" but with high bankroll / desired shares?
    # Wait, flat_25 uses 25 shares. 25 * 1.0 = 25 notional. Let's set max map notional to 25.
    df_sorted = pd.concat([pd.DataFrame([r1]), pd.DataFrame([r2])], ignore_index=True)
    df_reversed = pd.concat([pd.DataFrame([r2]), pd.DataFrame([r1])], ignore_index=True)
    
    res_sorted = simulate_sizing(df_sorted, "flat_25_liquidity_unchecked", max_map_notional=25.0)
    res_reversed = simulate_sizing(df_reversed, "flat_25_liquidity_unchecked", max_map_notional=25.0)
    
    # In both cases, the row with entry_received_at_ns == 1000 should get the shares (25.0)
    # and the row with entry_received_at_ns == 2000 should get 0 shares.
    assert res_sorted[res_sorted["entry_received_at_ns"] == 1000]["sim_shares"].iloc[0] == 25.0
    assert res_sorted[res_sorted["entry_received_at_ns"] == 2000]["sim_shares"].iloc[0] == 0.0
    
    assert res_reversed[res_reversed["entry_received_at_ns"] == 1000]["sim_shares"].iloc[0] == 25.0
    assert res_reversed[res_reversed["entry_received_at_ns"] == 2000]["sim_shares"].iloc[0] == 0.0

