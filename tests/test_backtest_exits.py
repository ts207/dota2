from __future__ import annotations

import pandas as pd
import pytest

from dota2bot.backtest_exits import (
    ExitPolicy,
    active_entry_rows,
    format_exit_backtest,
    future_exit_rows,
    parse_min_hold_values,
    simulate_entry,
    summarize_policy_rows,
)


def test_simulate_entry_exits_at_later_bid_with_round_trip_cost():
    scored = pd.DataFrame(
        [
            _row(received_at_ns=100, token_id="tok1", bid=0.40),
            _row(received_at_ns=200, token_id="tok1", bid=0.62),
        ]
    )
    entry = scored.iloc[0].copy()
    policy = ExitPolicy("take_profit", lambda future, entry: future[future["book_best_bid_num"] >= 0.60])

    result = simulate_entry(scored, entry, policy, min_hold_sec=0)

    assert result["exited"] is True
    assert result["exit_bid"] == 0.62
    assert result["realized_pnl"] == pytest.approx(0.62 - 0.50 - 0.03)


def test_simulate_entry_holds_when_no_exit_fires():
    scored = pd.DataFrame([_row(received_at_ns=100, token_id="tok1", ask=0.40, settled_win=True)])
    entry = scored.iloc[0].copy()
    policy = ExitPolicy("never", lambda future, entry: future)

    result = simulate_entry(scored, entry, policy, min_hold_sec=0)

    assert result["exited"] is False
    assert result["realized_pnl"] == pytest.approx(1.0 - 0.40 - 0.02)


def test_future_exit_rows_requires_same_token_and_min_hold():
    scored = pd.DataFrame(
        [
            _row(received_at_ns=100_000_000_000, token_id="tok1", side="YES", bid=0.40),
            _row(received_at_ns=100_500_000_000, token_id="tok1", side="YES", bid=0.45),
            _row(received_at_ns=101_500_000_000, token_id="tok2", side="YES", bid=0.90),
            _row(received_at_ns=101_600_000_000, token_id="tok1", side="YES", bid=0.60),
        ]
    )
    entry = scored.iloc[0].copy()

    future = future_exit_rows(scored, entry, min_hold_sec=1)

    assert future["token_id"].tolist() == ["tok1"]
    assert future["book_best_bid_num"].tolist() == [0.60]


def test_active_entry_rows_dedupes_first_signal_per_map():
    scored = pd.DataFrame(
        [
            _row(received_at_ns=100, match_id="m1", game=1, ask=0.40, edge=0.06),
            _row(received_at_ns=200, match_id="m1", game=1, ask=0.40, edge=0.20),
            _row(received_at_ns=300, match_id="m1", game=2, ask=0.40, edge=0.06),
        ]
    )
    scored["active_backtest_tradable"] = True
    scored["market_scope"] = "map_winner_explicit"

    entries = active_entry_rows(scored)

    assert entries["received_at_ns"].tolist() == [100, 300]


def test_summarize_policy_rows_recommends_only_when_pnl_beats_hold():
    rows = [
        {"exited": True, "settled_win": False, "realized_pnl": -0.10, "exit_bid": 0.35},
        {"exited": False, "settled_win": True, "realized_pnl": 0.58, "exit_bid": None},
    ]

    better = summarize_policy_rows("candidate", rows, hold_pnl=0.20)
    worse = summarize_policy_rows("candidate", rows, hold_pnl=0.60)

    assert better["recommendation"] == "promote_candidate"
    assert worse["recommendation"] == "keep_hold"
    assert better["losers_exited"] == 1
    assert better["winners_exited"] == 0


def test_parse_min_hold_values_accepts_csv_and_rejects_negative():
    assert parse_min_hold_values("0,60,120") == [0, 60, 120]
    with pytest.raises(ValueError, match="non-negative"):
        parse_min_hold_values("-1")


def test_format_exit_backtest_contains_policy_table():
    result = {
        "strategy": "winprob_logistic_evfilter",
        "entry_threshold": 0.05,
        "include_live": False,
        "input_rows": 10,
        "settled_entry_rows": 1,
        "scenarios": [
            {
                "min_hold_sec": 0,
                "hold_pnl_2c": 0.58,
                "policies": [
                    {
                        "policy": "hold",
                        "entries": 1,
                        "exited_trades": 0,
                        "held_trades": 1,
                        "winners_exited": 0,
                        "losers_exited": 0,
                        "avg_exit_bid": None,
                        "realized_pnl": 0.58,
                        "delta_vs_hold": 0.0,
                        "worst_trade": 0.58,
                        "recommendation": "keep_hold",
                    }
                ],
            }
        ],
    }

    text = format_exit_backtest(result)

    assert "# Exit Backtest" in text
    assert "winprob_logistic_evfilter" in text
    assert "| hold | 1 | 0 | 1" in text


def _row(
    *,
    received_at_ns: int,
    match_id: str = "m1",
    game: int = 1,
    side: str = "YES",
    token_id: str = "tok1",
    ask: float = 0.50,
    bid: float = 0.49,
    edge: float = 0.10,
    settled_win: bool = False,
) -> dict:
    game_text = str(game)
    return {
        "match_id": match_id,
        "current_game_number": game,
        "map_exposure_id": f"{match_id}::{game_text}",
        "side": side,
        "token_id": token_id,
        "received_at_ns": received_at_ns,
        "received_at_ns_num": float(received_at_ns),
        "book_best_ask": ask,
        "book_best_ask_num": ask,
        "book_best_bid": bid,
        "book_best_bid_num": bid,
        "edge": edge,
        "edge_num": edge,
        "game_time_sec": 900,
        "side_mom_100": 0.0,
        "side_mom_100_num": 0.0,
        "side_mom_300": 0.0,
        "side_mom_300_num": 0.0,
        "settled_win": settled_win,
    }
