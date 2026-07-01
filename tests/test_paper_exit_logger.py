from __future__ import annotations

import pandas as pd
import pytest

from dota2bot.paper_exit_logger import build_exit_decisions, format_exit_report, run_paper_exit_log, summarize_exit_decisions
from dota2bot.schemas import DECISION_COLUMNS, SIDE_SNAPSHOT_COLUMNS


def test_build_exit_decisions_uses_first_future_rich_bid_momentum_reversal():
    entries = pd.DataFrame([_entry_row()])
    sides = pd.DataFrame(
        [
            _side_row(received_at_ns=90, game_time_sec=1300, bid=0.80, radiant_lead=8000),
            _side_row(received_at_ns=110, game_time_sec=1199, bid=0.80, radiant_lead=7000),
            _side_row(received_at_ns=120, game_time_sec=1300, bid=0.69, radiant_lead=6000),
            _side_row(received_at_ns=130, game_time_sec=1400, bid=0.72, radiant_lead=5000),
            _side_row(received_at_ns=140, game_time_sec=1500, bid=0.90, radiant_lead=4000),
        ]
    )

    exits = build_exit_decisions(entries=entries, sides=sides)

    assert len(exits) == 1
    row = exits.iloc[0]
    assert bool(row["exit_signal"]) is True
    assert row["exit_received_at_ns"] == 130
    assert row["exit_bid"] == 0.72
    assert row["hold_pnl_2c"] == pytest.approx(-0.42)
    assert row["exit_pnl_2c"] == pytest.approx(0.72 - 0.40 - 0.03)
    assert row["pnl_delta_vs_hold"] == pytest.approx(0.71)


def test_build_exit_decisions_holds_when_no_exit_signal():
    entries = pd.DataFrame([_entry_row(settled_win=True)])
    sides = pd.DataFrame(
        [
            _side_row(received_at_ns=120, game_time_sec=1300, bid=0.69, radiant_lead=5000),
            _side_row(received_at_ns=130, game_time_sec=1400, bid=0.80, radiant_lead=6000),
        ]
    )

    exits = build_exit_decisions(entries=entries, sides=sides)

    row = exits.iloc[0]
    assert bool(row["exit_signal"]) is False
    assert row["hold_pnl_2c"] == pytest.approx(0.58)
    assert row["exit_pnl_2c"] == pytest.approx(0.58)
    assert row["pnl_delta_vs_hold"] == pytest.approx(0.0)


def test_summarize_exit_decisions_reports_delta():
    exits = pd.DataFrame(
        [
            {"exit_signal": True, "settled_win": False, "hold_pnl_2c": -0.42, "exit_pnl_2c": 0.29, "exit_bid": 0.72},
            {"exit_signal": False, "settled_win": True, "hold_pnl_2c": 0.58, "exit_pnl_2c": 0.58, "exit_bid": None},
        ]
    )

    summary = summarize_exit_decisions(exits)

    assert summary["rows"] == 2
    assert summary["exit_signal_rows"] == 1
    assert summary["hold_pnl_2c"] == pytest.approx(0.16)
    assert summary["exit_pnl_2c"] == pytest.approx(0.87)
    assert summary["delta_vs_hold"] == pytest.approx(0.71)
    assert summary["losers_exited"] == 1
    assert {row["group"]: row["rows"] for row in summary["exit_status"]} == {"exited": 1, "held": 1}
    assert {row["group"]: row["rows"] for row in summary["outcome"]} == {"loser": 1, "winner": 1}


def test_format_exit_report_has_breakdown_sections():
    summary = summarize_exit_decisions(
        pd.DataFrame(
            [
                {
                    "exit_signal": True,
                    "settled_win": False,
                    "hold_pnl_2c": -0.42,
                    "exit_pnl_2c": 0.29,
                    "exit_bid": 0.72,
                    "entry_ask": 0.40,
                    "exit_game_time_sec": 1400,
                    "match_id": "m1",
                    "map_exposure_id": "m1::1",
                }
            ]
        )
    )

    report = format_exit_report(summary)

    assert "## Exit Status" in report
    assert "## Exposure Type" in report
    assert "## Entry Ask Buckets" in report
    assert "## Exit Bid Buckets" in report
    assert "## Match Concentration" in report


def test_run_paper_exit_log_dedupes_existing_decisions(tmp_path):
    decision_dir = tmp_path / "settled_decisions"
    decision_dir.mkdir()
    pd.DataFrame([_entry_row()]).to_parquet(decision_dir / "latest.parquet", index=False)
    side_dir = tmp_path / "live_settled_side_snapshots"
    side_dir.mkdir()
    pd.DataFrame(
        [
            _side_row(received_at_ns=90, game_time_sec=1300, bid=0.80, radiant_lead=8000),
            _side_row(received_at_ns=130, game_time_sec=1400, bid=0.72, radiant_lead=5000),
        ]
    ).to_parquet(side_dir / "latest.parquet", index=False)

    first = run_paper_exit_log(logs_root=tmp_path, input_name="settled_decisions")
    second = run_paper_exit_log(logs_root=tmp_path, input_name="settled_decisions")

    assert first["written_rows"] == 1
    assert second["written_rows"] == 0
    assert second["skipped_existing_rows"] == 1


def _entry_row(*, settled_win: bool = False) -> dict:
    row = {col: None for col in DECISION_COLUMNS}
    row.update(
        {
            "decision_id": "entry1",
            "model_name": "winprob_logistic_evfilter",
            "model_version": "v1",
            "candidate_group": "primary",
            "strategy_name": "entry",
            "match_id": "m1",
            "market_id": "mk1",
            "label_market_bucket": "MAP_WINNER",
            "current_game_number": 1,
            "map_exposure_id": "m1::1",
            "canonical_exposure_id": "m1::1::YES",
            "token_id": "tok1",
            "side": "YES",
            "received_at_utc": "2026-06-24T00:00:00+00:00",
            "received_at_ns": 100,
            "game_time_sec": 900,
            "ask": 0.40,
            "bid": 0.39,
            "edge": 0.08,
            "side_mom_100": 1000,
            "signal": True,
            "settled_win": settled_win,
            "blocked_reason": None,
        }
    )
    return row


def _side_row(*, received_at_ns: int, game_time_sec: int, bid: float, radiant_lead: int) -> dict:
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row.update(
        {
            "match_id": "m1",
            "market_id": "mk1",
            "market_scope": "map_winner_explicit",
            "label_market_bucket": "MAP_WINNER",
            "current_game_number": 1,
            "token_id": "tok1",
            "side": "YES",
            "received_at_utc": "2026-06-24T00:00:00+00:00",
            "received_at_ns": received_at_ns,
            "game_time_sec": game_time_sec,
            "book_received_at_ns": received_at_ns,
            "book_age_ms": 1000,
            "book_best_bid": bid,
            "book_best_ask": bid + 0.01,
            "book_bid_size": 100,
            "book_ask_size": 100,
            "book_spread": 0.01,
            "executable_snapshot": True,
            "quality_reason": "ok",
            "side_is_radiant": True,
            "radiant_lead": radiant_lead,
            "net_worth_diff": radiant_lead,
            "radiant_score": 20,
            "dire_score": 15,
            "settled_win": False,
        }
    )
    return row
