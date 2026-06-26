from __future__ import annotations

import json

import pandas as pd
import pytest

from dota2bot.entry_quality_report import (
    active_entries_for_filter,
    ask_bucket,
    candidate_row,
    edge_bucket,
    format_entry_quality_report,
    game_time_bucket,
    sign_bucket,
    trade_metrics,
)


def test_bucket_boundaries_are_stable():
    assert edge_bucket(0.05) == "0.05-0.10"
    assert edge_bucket(0.10) == "0.10-0.15"
    assert edge_bucket(0.15) == "0.15-0.20"
    assert edge_bucket(0.20) == ">=0.20"
    assert ask_bucket(0.20) == "0.20-0.30"
    assert ask_bucket(0.30) == "0.30-0.40"
    assert ask_bucket(0.40) == "0.40-0.50"
    assert game_time_bucket(600) == "600-900"
    assert game_time_bucket(900) == "900-1200"
    assert game_time_bucket(1200) == "1200-1800"
    assert game_time_bucket(1800) == ">=1800"
    assert sign_bucket(1) == "positive"
    assert sign_bucket(-1) == "negative"
    assert sign_bucket(0) == "zero"


def test_active_entries_for_filter_uses_first_qualifying_signal_per_map():
    scored = pd.DataFrame(
        [
            _row(match_id="m1", game=1, received_at_ns=100, edge=0.04),
            _row(match_id="m1", game=1, received_at_ns=200, edge=0.06),
            _row(match_id="m1", game=1, received_at_ns=300, edge=0.20),
            _row(match_id="m1", game=2, received_at_ns=400, edge=0.06),
        ]
    )

    entries = active_entries_for_filter(scored, lambda frame: frame["edge_num"] >= 0.05)

    assert entries["received_at_ns"].tolist() == [200, 400]


def test_trade_metrics_uses_two_cent_pnl_and_worst_trade():
    trades = pd.DataFrame(
        [
            _row(ask=0.40, settled_win=True),
            _row(ask=0.30, settled_win=False),
        ]
    )

    metrics = trade_metrics(trades)

    assert metrics["trades"] == 2
    assert metrics["win_rate"] == 0.5
    assert metrics["pnl_2c"] == pytest.approx((1 - 0.42) - 0.32)
    assert metrics["worst_trade"] == -0.32


def test_candidate_promotion_requires_better_pnl_and_min_trades():
    scored = pd.DataFrame(
        [
            _row(match_id="m1", game=1, ask=0.40, settled_win=True),
            _row(match_id="m2", game=1, ask=0.40, settled_win=True),
        ]
    )

    promoted = candidate_row(scored, "all", baseline_pnl=0.50, min_trades=2, filter_fn=lambda frame: pd.Series(True, index=frame.index))
    too_few = candidate_row(scored, "all", baseline_pnl=0.50, min_trades=3, filter_fn=lambda frame: pd.Series(True, index=frame.index))
    not_better = candidate_row(scored, "all", baseline_pnl=2.0, min_trades=2, filter_fn=lambda frame: pd.Series(True, index=frame.index))

    assert promoted["recommendation"] == "promote_candidate"
    assert too_few["recommendation"] == "keep_active"
    assert not_better["recommendation"] == "keep_active"


def test_format_entry_quality_report_markdown_and_json():
    result = {
        "strategy": "winprob_logistic_evfilter",
        "entry_threshold": 0.05,
        "include_live": False,
        "input_rows": 10,
        "min_trades": 10,
        "baseline": {"trades": 1, "matches": 1, "win_rate": 1.0, "avg_ask": 0.4, "pnl_2c": 0.58, "worst_trade": 0.58},
        "buckets": {"edge": [], "ask": [], "game_time": [], "side_mom_100": [], "side_mom_300": [], "side_kill_mom": []},
        "candidates": [
            {
                "filter": "edge>=0.05",
                "trades": 1,
                "win_rate": 1.0,
                "avg_ask": 0.4,
                "pnl_2c": 0.58,
                "delta_vs_baseline": 0.0,
                "recommendation": "keep_active",
            }
        ],
        "agreement": [
            {
                "exposure_signal_group": "primary_only",
                "trades": 1,
                "settled": 1,
                "win_rate": 1.0,
                "avg_ask": 0.4,
                "pnl_2c": 0.58,
            }
        ],
    }

    markdown = format_entry_quality_report(result)
    parsed = json.loads(format_entry_quality_report(result, output_format="json"))

    assert "# Entry Quality Report" in markdown
    assert "## Candidate Filters" in markdown
    assert parsed["strategy"] == "winprob_logistic_evfilter"


def _row(
    *,
    match_id: str = "m1",
    game: int = 1,
    received_at_ns: int = 100,
    ask: float = 0.40,
    edge: float = 0.06,
    settled_win: bool = True,
) -> dict:
    return {
        "match_id": match_id,
        "current_game_number": game,
        "map_exposure_id": f"{match_id}::{game}",
        "received_at_ns": received_at_ns,
        "book_best_ask": ask,
        "book_best_ask_num": ask,
        "edge": edge,
        "edge_num": edge,
        "game_time_sec": 900,
        "game_time_sec_num": 900,
        "side_mom_100": 0,
        "side_mom_100_num": 0,
        "side_mom_300": 0,
        "side_mom_300_num": 0,
        "side_kill_mom": 0,
        "side_kill_mom_num": 0,
        "active_backtest_tradable": True,
        "market_scope": "map_winner_explicit",
        "settled_win": settled_win,
    }
