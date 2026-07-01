import pandas as pd
import numpy as np
import pytest
from pathlib import Path
from dota2bot.paper_sizing_report import run_sizing_report

def mock_positions():
    return pd.DataFrame([
        {
            "position_id": "1",
            "candidate_group": "primary",
            "strategy_name": "strat_1",
            "match_id": "match_1",
            "blocked_reason": None, "map_exposure_id": "m1",
            "entry_received_at_ns": 1000,
            "entry_ask": 0.50,
            "edge": 0.05,
            "fair_prob": 0.55,
            "book_ask_size": 100,
            "blocked_reason": None,
            "settled_win": True,
            "pnl_per_share_2c": 1.0,
            "position_pnl_2c": 1.0,
        },
        {
            "position_id": "2",
            "candidate_group": "gettoplive_candidate",
            "strategy_name": "strat_2",
            "match_id": "match_1",
            "blocked_reason": None, "map_exposure_id": "m1",
            "entry_received_at_ns": 2000,
            "entry_ask": 0.50,
            "edge": 0.15,
            "fair_prob": 0.65,
            "book_ask_size": 10,  # 10 * 0.25 = 2.5 liq cap
            "blocked_reason": None,
            "settled_win": False,
            "pnl_per_share_2c": -1.0,
            "position_pnl_2c": -1.0,
        },
        {
            "position_id": "3",
            "candidate_group": "primary",
            "strategy_name": "strat_1",
            "match_id": "match_1",
            "blocked_reason": None, "map_exposure_id": "m1",
            "entry_received_at_ns": 3000,
            "entry_ask": 0.50,
            "edge": 0.10,
            "fair_prob": 0.51, # fair_prob <= ask + 0.02
            "book_ask_size": np.nan,
            "blocked_reason": None,
            "settled_win": True,
            "pnl_per_share_2c": 1.0,
            "position_pnl_2c": 1.0,
        },
        {
            "position_id": "4",
            "candidate_group": "benchmark",
            "strategy_name": "strat_3",
            "match_id": "match_2",
            "blocked_reason": None, "map_exposure_id": "m2",
            "entry_received_at_ns": 4000,
            "entry_ask": 0.50,
            "edge": 0.05,
            "fair_prob": 0.55,
            "book_ask_size": 100,
            "blocked_reason": None,
            "settled_win": True,
            "pnl_per_share_2c": 1.0,
            "position_pnl_2c": 1.0,
        },
        {
            "position_id": "5",
            "candidate_group": "control",
            "strategy_name": "strat_4",
            "match_id": "match_3",
            "blocked_reason": None, "map_exposure_id": "m3",
            "entry_received_at_ns": 5000,
            "entry_ask": 0.50,
            "edge": 0.05,
            "fair_prob": 0.55,
            "book_ask_size": 100,
            "blocked_reason": None,
            "settled_win": True,
            "pnl_per_share_2c": 1.0,
            "position_pnl_2c": 1.0,
        },
        {
            "position_id": "6",
            "candidate_group": "primary",
            "strategy_name": "strat_1",
            "match_id": "match_4",
            "blocked_reason": None, "map_exposure_id": "m4",
            "entry_received_at_ns": 6000,
            "entry_ask": 0.50,
            "edge": 0.05,
            "fair_prob": 0.55,
            "book_ask_size": 100,
            "blocked_reason": None,
            "settled_win": None, # pending
            "pnl_per_share_2c": None,
            "position_pnl_2c": None,
        }
    ])

def test_sizing_logic(monkeypatch, capsys):
    df = mock_positions()
    monkeypatch.setattr("dota2bot.paper_sizing_report._read_parquet_dir", lambda _: df)
    
    results = run_sizing_report(
        input_name="paper_positions",
        source="active",
        bankroll=1000.0,
        max_shares=25.0,
        max_position_notional=100.0,
        max_map_notional=25.0, # force map cap for m1
    )
    
    out = capsys.readouterr().out
    
    r_map = {r["sizing"]: r for r in results}
    
    f1 = r_map["flat_1"]
    f5 = r_map["flat_5"]
    f25 = r_map["flat_25_liquidity_unchecked"]
    es = r_map["edge_scaled_0.5pct_bankroll_cap25"]
    k5 = r_map["kelly_05_cap25"]
    
    # Check 1: flat_1 equals current position_pnl_2c sum for active settled
    # positions 1, 2, 3 are active. 1 and 3 won (1.0), 2 lost (-1.0). Total pnl = 1.0
    assert f1["pnl_2c"] == 1.0
    
    # Check 2: flat_5 equals 5x per-share PnL
    assert f5["pnl_2c"] == 5.0
    
    # Check 3: edge_scaled increases shares with edge
    # pos 1 edge 0.05 -> shares = (1000 * 0.005 * 0.5) / 0.5 = 5.0
    # pos 2 edge 0.15 -> shares = (1000 * 0.005 * 1.5) / 0.5 = 15.0 (but capped)
    # let's look at the underlying df
    es_df = es["df"]
    pos1_shares = es_df[es_df["position_id"] == "1"]["sim_shares"].iloc[0]
    pos2_shares_raw = (1000 * 0.005 * 1.5) / 0.5
    # pos2 has liq cap = 2.5
    pos2_shares = es_df[es_df["position_id"] == "2"]["sim_shares"].iloc[0]
    assert pos1_shares == 5.0
    
    # Check 4: edge_scaled never exceeds max_shares
    assert es["df"]["sim_shares"].max() <= 25.0
    
    # Check 5: liquidity cap reduces shares
    # pos2 desired is 15.0, liq cap is 2.5
    assert pos2_shares == 2.5
    
    # Check 6: map notional cap reduces later same-map positions
    # max_map_notional = 25.0
    # pos 1: 5.0 shares * 0.5 = 2.5 notional (used: 2.5)
    # pos 2: 2.5 shares * 0.5 = 1.25 notional (used: 3.75)
    # pos 3: desired = (1000 * 0.005 * 1.0) / 0.5 = 10.0 shares = 5.0 notional
    # In another scheme (e.g. flat_25) we'd hit map cap:
    # flat_25_liq_capped:
    # pos 1: 25 shares * 0.5 = 12.5 notional
    # pos 2: 2.5 shares * 0.5 = 1.25 notional
    # pos 3: desired 25 shares * 0.5 = 12.5 notional
    # total would be 26.25, but cap is 25.0, so pos 3 should get 11.25 notional = 22.5 shares
    f25_df = f25["df"]
    pos3_shares_f25 = f25_df[f25_df["position_id"] == "3"]["sim_shares"].iloc[0]
    assert pos3_shares_f25 == 22.5
    
    # Check 7: Kelly returns 0 when fair_prob <= ask + 0.02
    k5_df = k5["df"]
    pos3_shares_k5 = k5_df[k5_df["position_id"] == "3"]["sim_shares"].iloc[0]
    assert pos3_shares_k5 == 0.0
    
    # Check 8: pending positions counted but excluded from realized PnL
    assert es["positions"] == 4 # 1, 2, 3, 6 (all active)
    assert es["settled"] == 3 # 1, 2, 3
    assert len(es["settled_df"]) == 3
    
    # Check 9: source=active excludes benchmark and control
    assert "4" not in es_df["position_id"].values # benchmark
    assert "5" not in es_df["position_id"].values # control

def test_source_all_non_control(monkeypatch, capsys):
    df = mock_positions()
    monkeypatch.setattr("dota2bot.paper_sizing_report._read_parquet_dir", lambda _: df)
    
    results = run_sizing_report(
        input_name="paper_positions",
        source="all_non_control",
        bankroll=1000.0,
        max_shares=25.0,
        max_position_notional=100.0,
        max_map_notional=25.0,
    )
    
    out = capsys.readouterr().out
    
    es = results[3]
    es_df = es["df"]
    
    # Check 10: source=all_non_control includes benchmark but warns
    assert "4" in es_df["position_id"].values # benchmark is included
    assert "5" not in es_df["position_id"].values # control is still excluded
    assert "benchmark included in source" in out

def test_paper_sizing_report_strategy_name_filter_isolates_ask65_shadow(tmp_path: Path):
    from dota2bot.paper_sizing_report import run_sizing_report
    
    frame = pd.DataFrame([
        {"position_id": "1", "strategy_name": "paper_gettoplive_kill_mom_favorite_hold_v1", "candidate_group": "gettoplive_candidate", "settled_win": True, "entry_ask": 0.5, "book_ask_size_log": 2, "sim_pnl_2c": 0.5, "sim_stake": 1, "blocked_reason": None, "map_exposure_id": "1", "pnl_per_share_2c": 0.5, "entry_received_at_ns": 1000, "sim_shares": 1, "liquidity_unknown": False, "liq_capped": False, "match_id": "m1"},
        {"position_id": "2", "strategy_name": "paper_gettoplive_kill_mom_favorite_ask65_gt600_shadow_v1", "candidate_group": "gettoplive_candidate", "settled_win": True, "entry_ask": 0.5, "book_ask_size_log": 2, "sim_pnl_2c": 0.3, "sim_stake": 1, "blocked_reason": None, "map_exposure_id": "2", "pnl_per_share_2c": 0.3, "entry_received_at_ns": 1000, "sim_shares": 1, "liquidity_unknown": False, "liq_capped": False, "match_id": "m1"},
    ])
    
    input_dir = tmp_path / "paper_positions"
    input_dir.mkdir()
    frame.to_parquet(input_dir / "latest.parquet", index=False)
    
    import io
    import sys
    captured = io.StringIO()
    sys.stdout = captured
    run_sizing_report(
        logs_root=tmp_path,
        input_name="paper_positions",
        source="gettoplive",
        strategy_name="paper_gettoplive_kill_mom_favorite_ask65_gt600_shadow_v1"
    )
    sys.stdout = sys.__stdout__
    output = captured.getvalue()
    print("OUTPUT IS:", output)
    assert "Strategy: paper_gettoplive_kill_mom_favorite_ask65_gt600_shadow_v1" in output
    assert "| 1 " in output
