import hashlib
from typing import Any

import pandas as pd
import pytest

from dota2bot.exposure_manager import ExposureManager, DEFAULT_LIMITS
from dota2bot.strategy_contract import PAPER_DECISION_SPECS


def _row(
    strategy_name="paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg",
    match_id="test_match",
    current_game_number=1,
    side="team_a",
    entry_ns=1000 * 1000 * 1000,
    decision_id="d1",
    pnl_slip_2c=1.5,
    ask=0.5,
) -> dict[str, Any]:
    return {
        "signal": True,
        "decision_id": decision_id,
        "strategy_name": strategy_name,
        "match_id": match_id,
        "current_game_number": current_game_number,
        "side": side,
        "received_at_ns": entry_ns,
        "pnl_slip_2c": pnl_slip_2c,
        "ask": ask,
    }


def test_current_strategies_get_limits():
    manager = ExposureManager()
    for spec in PAPER_DECISION_SPECS:
        strat = spec.strategy_name
        assert strat in manager.limits
        limit = manager.limits[strat]
        assert limit.strategy_name == strat
        if getattr(spec, "candidate_group", "") == "control":
            assert limit.max_entries_per_map == 0
        else:
            assert limit.max_entries_per_map == 1


def test_opposite_side_blocked():
    manager = ExposureManager()
    decisions = pd.DataFrame([
        _row(side="team_a", decision_id="d1"),
        _row(side="team_b", decision_id="d2", entry_ns=1000 * 1000 * 1000 + 1),
    ])
    pos = manager.process_decisions(decisions)
    assert len(pos) == 2
    assert pd.isna(pos.iloc[0]["blocked_reason"])
    assert pos.iloc[1]["blocked_reason"] == "opposite_side_already_held_strategy"


def test_same_side_repeated_blocked_at_cap_1():
    manager = ExposureManager()
    decisions = pd.DataFrame([
        _row(side="team_a", decision_id="d1"),
        _row(side="team_a", decision_id="d2", entry_ns=1000 * 1000 * 1000 + 400 * 1e9), # after cooldown
    ])
    pos = manager.process_decisions(decisions)
    assert len(pos) == 2
    assert pd.isna(pos.iloc[0]["blocked_reason"])
    assert "max_entries_reached" in pos.iloc[1]["blocked_reason"]


def test_cooldown_blocks_second_entry():
    from dataclasses import replace
    # Need to change cap to 2 to see cooldown block
    mod_limits = {k: replace(v, max_entries_per_map=2) for k, v in DEFAULT_LIMITS.items()}
    manager = ExposureManager(limits=mod_limits)
    
    decisions = pd.DataFrame([
        _row(side="team_a", decision_id="d1"),
        _row(side="team_a", decision_id="d2", entry_ns=1000 * 1000 * 1000 + 200 * 1e9), # < 300s
    ])
    pos = manager.process_decisions(decisions)
    assert len(pos) == 2
    assert pd.isna(pos.iloc[0]["blocked_reason"])
    assert "cooldown_active" in pos.iloc[1]["blocked_reason"]


def test_cap_2_allows_two_blocks_third():
    from dataclasses import replace
    mod_limits = {k: replace(v, max_entries_per_map=2) for k, v in DEFAULT_LIMITS.items()}
    manager = ExposureManager(limits=mod_limits)
    
    decisions = pd.DataFrame([
        _row(side="team_a", decision_id="d1", entry_ns=1000 * 1e9),
        _row(side="team_a", decision_id="d2", entry_ns=2000 * 1e9), # 1000s later
        _row(side="team_a", decision_id="d3", entry_ns=3000 * 1e9), # another 1000s later
    ])
    pos = manager.process_decisions(decisions)
    assert len(pos) == 3
    assert pd.isna(pos.iloc[0]["blocked_reason"])
    assert pd.isna(pos.iloc[1]["blocked_reason"])
    assert "max_entries_reached" in pos.iloc[2]["blocked_reason"]


def test_deterministic_position_id():
    manager1 = ExposureManager()
    manager2 = ExposureManager()
    decisions = pd.DataFrame([_row()])
    
    pos1 = manager1.process_decisions(decisions)
    pos2 = manager2.process_decisions(decisions)
    
    assert pos1.iloc[0]["position_id"] == pos2.iloc[0]["position_id"]
    
    expected_id = hashlib.sha1(b"d1|paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg|test_match::1|v2").hexdigest()
    assert pos1.iloc[0]["position_id"] == expected_id


def test_shares_aware_pnl():
    from dataclasses import replace
    mod_limits = {k: replace(v, max_shares_per_entry=2.5) for k, v in DEFAULT_LIMITS.items()}
    manager = ExposureManager(limits=mod_limits)
    
    decisions = pd.DataFrame([_row(pnl_slip_2c=2.0)])
    pos = manager.process_decisions(decisions)
    
    assert pos.iloc[0]["shares"] == 2.5
    assert pos.iloc[0]["pnl_per_share_2c"] == 2.0
    assert pos.iloc[0]["position_pnl_2c"] == 5.0


def test_load_state_append():
    manager = ExposureManager()
    decisions1 = pd.DataFrame([_row(side="team_a", decision_id="d1")])
    pos1 = manager.process_decisions(decisions1)
    
    # Simulate append by creating a new manager and loading state
    manager2 = ExposureManager()
    manager2.load_state(pos1)
    
    # Try to insert same map again
    decisions2 = pd.DataFrame([_row(side="team_a", decision_id="d2", entry_ns=1000 * 1000 * 1000 + 400 * 1e9)])
    pos2 = manager2.process_decisions(decisions2)
    
    assert "max_entries_reached" in pos2.iloc[0]["blocked_reason"]


def test_portfolio_opposite_side_blocking():
    from dota2bot.exposure_manager import ExposureManager, ExposureLimit
    limits = {
        "primary": ExposureLimit("primary", max_entries_per_map=1, block_opposite_side_portfolio=True),
        "gettoplive_candidate": ExposureLimit("gettoplive_candidate", max_entries_per_map=1, block_opposite_side_portfolio=True)
    }
    mgr = ExposureManager(limits)
    
    # Primary buys radiant
    decisions = pd.DataFrame([{
        "decision_id": "d1",
        "strategy_name": "primary",
        "match_id": "m1",
        "current_game_number": 1,
        "side": "radiant",
        "signal": True
    }])
    pos1 = mgr.process_decisions(decisions)
    assert pos1.iloc[0]["blocked_reason"] is None
    
    # GetTopLive buys dire on same map -> blocked
    decisions2 = pd.DataFrame([{
        "decision_id": "d2",
        "strategy_name": "gettoplive_candidate",
        "match_id": "m1",
        "current_game_number": 1,
        "side": "dire",
        "signal": True
    }])
    pos2 = mgr.process_decisions(decisions2)
    assert pos2.iloc[0]["blocked_reason"] == "opposite_side_already_held_portfolio"

