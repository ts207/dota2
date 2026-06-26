from __future__ import annotations

import pandas as pd
import pytest

from dota2bot.gettoplive_markout_report import (
    add_future_markouts,
    bootstrap_match_pnl,
    chronological_candidate_details,
    chronological_candidate_summary,
    chronological_match_split,
    chronological_settlement_candidate_details,
    chronological_settlement_candidate_summary,
    concentration_metrics,
    eligible_markout_rows,
    first_candidate_event_per_map,
    format_gettoplive_markout_report,
    match_level_pnl,
    parse_horizons,
    select_gettoplive_events,
    settlement_strategy_metrics,
)


def test_select_gettoplive_events_dedupes_first_event_per_map_side_event():
    frame = pd.DataFrame(
        [
            _row(received_at_ns=100, side_mom_100=1200),
            _row(received_at_ns=200, side_mom_100=5000),
            _row(received_at_ns=300, side="NO", token_id="tok2", side_mom_100=1400),
        ]
    )

    events = select_gettoplive_events(frame)
    mom = events[events["event_name"] == "mom100_up_1k"]

    assert mom["received_at_ns"].tolist() == [100, 300]
    assert len(mom) == 2


def test_add_future_markouts_uses_same_token_and_round_trip_cost():
    events = pd.DataFrame([_row(received_at_ns=100_000_000_000, ask=0.40, bid=0.38)])
    frame = pd.DataFrame(
        [
            _row(received_at_ns=100_000_000_000, ask=0.40, bid=0.38),
            _row(received_at_ns=129_000_000_000, ask=0.50, bid=0.48),
            _row(received_at_ns=130_000_000_000, ask=0.60, bid=0.57),
            _row(received_at_ns=131_000_000_000, token_id="other", ask=0.99, bid=0.98),
        ]
    )

    marked = add_future_markouts(events, frame, horizons_sec=[30])

    assert marked.loc[0, "future_bid_30"] == 0.57
    assert marked.loc[0, "bid_markout_30"] == pytest.approx(0.17)
    assert marked.loc[0, "sell_bid_pnl_30"] == pytest.approx(0.57 - 0.40 - 0.03)


def test_eligible_markout_rows_filters_scope_and_tradability():
    frame = pd.DataFrame(
        [
            _row(match_id="m1", market_scope="map_winner_explicit", tradable=True),
            _row(match_id="m2", market_scope="series", tradable=True),
            _row(match_id="m3", market_scope="map_winner_explicit", tradable=False),
            _row(match_id="m4", market_scope="map_winner_explicit", tradable=True, game_time_sec=500),
        ]
    )

    eligible = eligible_markout_rows(frame, min_game_time_sec=600)

    assert eligible["match_id"].tolist() == ["m1"]


def test_format_gettoplive_markout_report_outputs_markdown_and_json():
    result = {
        "report": "gettoplive_markout",
        "include_live": False,
        "input_rows": 10,
        "eligible_rows": 8,
        "eligible_matches": 3,
        "event_rows": 2,
        "event_matches": 2,
        "horizons_sec": [30],
        "min_game_time_sec": 600,
        "min_events": 1,
        "horizon_summary": [
            {
                "event": "mom100_up_1k",
                "horizon_sec": 30,
                "events_with_future": 2,
                "matches": 2,
                "avg_entry_ask": 0.4,
                "avg_bid_markout": 0.05,
                "avg_mid_markout": 0.04,
                "positive_sell_rate": 0.5,
                "total_sell_bid_pnl": 0.04,
                "avg_sell_bid_pnl": 0.02,
            }
        ],
        "event_summary": [
            {
                "event": "mom100_up_1k",
                "events": 2,
                "matches": 2,
                "map_exposures": 2,
                "avg_ask": 0.4,
                "settled": 2,
                "settlement_win_rate": 0.5,
                "settlement_pnl_2c": 0.1,
            }
        ],
        "candidate_summary": [
            {
                "event": "mom100_up_1k",
                "filter": "ask20_50_gt900",
                "horizon_sec": 30,
                "events_with_future": 2,
                "matches": 2,
                "avg_entry_ask": 0.4,
                "positive_sell_rate": 0.5,
                "total_sell_bid_pnl": 0.04,
                "avg_sell_bid_pnl": 0.02,
                "settlement_pnl_2c": 0.1,
            }
        ],
        "chronological_candidate_summary": [
            {
                "event": "mom100_up_1k",
                "filter": "ask20_50_gt900",
                "horizon_sec": 30,
                "dev": {
                    "events": 1,
                    "matches": 1,
                    "avg_ask": 0.4,
                    "positive_sell_rate": 1.0,
                    "sell_bid_pnl": 0.04,
                    "avg_sell_bid_pnl": 0.04,
                    "settlement_pnl_2c": 0.1,
                },
                "lockbox": {
                    "events": 1,
                    "matches": 1,
                    "avg_ask": 0.4,
                    "positive_sell_rate": 1.0,
                    "sell_bid_pnl": 0.04,
                    "avg_sell_bid_pnl": 0.04,
                    "settlement_pnl_2c": 0.1,
                },
                "combined": {
                    "events": 2,
                    "matches": 2,
                    "avg_ask": 0.4,
                    "positive_sell_rate": 1.0,
                    "sell_bid_pnl": 0.08,
                    "avg_sell_bid_pnl": 0.04,
                    "settlement_pnl_2c": 0.2,
                },
                "recommendation": "research_candidate",
            }
        ],
        "chronological_candidate_details": [
            {
                "event": "mom100_up_1k",
                "filter": "ask20_50_gt900",
                "horizon_sec": 30,
                "split": "dev",
                "match_id": "m1",
                "current_game_number": 1,
                "side": "YES",
                "received_at_utc": None,
                "game_time_sec": 900,
                "entry_ask": 0.4,
                "entry_bid": 0.39,
                "future_bid": 0.47,
                "sell_bid_pnl": 0.04,
                "settled_win": True,
                "settlement_pnl_2c": 0.58,
                "source_update_age_sec": 0.0,
                "side_nw": 1000.0,
                "side_mom_100": 1200.0,
                "side_mom_300": 0.0,
                "side_kill_mom": 1.0,
            }
        ],
        "chronological_settlement_candidate_summary": [
            {
                "event": "mom100_up_1k",
                "filter": "ask20_50_gt900",
                "dev": {
                    "events": 1,
                    "matches": 1,
                    "avg_ask": 0.4,
                    "win_rate": 1.0,
                    "settlement_pnl_2c": 0.58,
                    "avg_settlement_pnl_2c": 0.58,
                },
                "lockbox": {
                    "events": 1,
                    "matches": 1,
                    "avg_ask": 0.4,
                    "win_rate": 1.0,
                    "settlement_pnl_2c": 0.58,
                    "avg_settlement_pnl_2c": 0.58,
                },
                "combined": {
                    "events": 2,
                    "matches": 2,
                    "avg_ask": 0.4,
                    "win_rate": 1.0,
                    "settlement_pnl_2c": 1.16,
                    "avg_settlement_pnl_2c": 0.58,
                },
                "recommendation": "research_candidate",
            }
        ],
        "chronological_settlement_candidate_details": [
            {
                "event": "mom100_up_1k",
                "filter": "ask20_50_gt900",
                "split": "dev",
                "match_id": "m1",
                "current_game_number": 1,
                "side": "YES",
                "received_at_utc": None,
                "game_time_sec": 900,
                "entry_ask": 0.4,
                "entry_bid": 0.39,
                "settled_win": True,
                "settlement_pnl_2c": 0.58,
                "source_update_age_sec": 0.0,
                "side_nw": 1000.0,
                "side_mom_100": 1200.0,
                "side_mom_300": 0.0,
                "side_kill_mom": 1.0,
            }
        ],
        "details": [],
    }

    text = format_gettoplive_markout_report(result)
    json_text = format_gettoplive_markout_report(result, output_format="json")

    assert "# GetTopLive Markout Report" in text
    assert "## Candidate Subsets" in text
    assert "## Chronological Candidate Split" in text
    assert "## Research Candidate Trades" in text
    assert "## Chronological Settlement Candidate Split" in text
    assert "## Settlement Candidate Trades" in text
    assert "mom100_up_1k" in text
    assert '"report": "gettoplive_markout"' in json_text


def test_parse_horizons_rejects_empty_and_negative_values():
    assert parse_horizons("30,60") == [30, 60]
    with pytest.raises(ValueError, match="positive"):
        parse_horizons("30,-1")
    with pytest.raises(ValueError, match="empty"):
        parse_horizons("")


def test_first_candidate_event_per_map_dedupes_opposite_sides():
    events = pd.DataFrame(
        [
            _row(match_id="m1", side="YES", token_id="tok1", received_at_ns=200),
            _row(match_id="m1", side="NO", token_id="tok2", received_at_ns=100),
            _row(match_id="m2", side="YES", token_id="tok3", received_at_ns=300),
        ]
    )

    trades = first_candidate_event_per_map(events)

    assert trades["match_id"].tolist() == ["m1", "m2"]
    assert trades["side"].tolist() == ["NO", "YES"]


def test_chronological_match_split_keeps_later_matches_in_lockbox():
    events = pd.DataFrame(
        [
            _row(match_id="m1", received_at_ns=100),
            _row(match_id="m2", received_at_ns=200),
            _row(match_id="m3", received_at_ns=300),
            _row(match_id="m4", received_at_ns=400),
        ]
    )

    dev, lockbox = chronological_match_split(events, lockbox_fraction=0.25)

    assert dev["match_id"].tolist() == ["m1", "m2", "m3"]
    assert lockbox["match_id"].tolist() == ["m4"]


def test_chronological_candidate_summary_requires_dev_and_lockbox_positive():
    rows = []
    for idx, match_id in enumerate(["m1", "m2", "m3", "m4"]):
        row = _row(match_id=match_id, received_at_ns=(idx + 1) * 100, side_mom_100=4000, ask=0.40, bid=0.39)
        row["event_name"] = "mom100_up_3k"
        row["sell_bid_pnl_300"] = 0.10 if match_id != "m4" else 0.20
        row["settlement_pnl_2c"] = 0.10
        rows.append(row)

    summary = chronological_candidate_summary(pd.DataFrame(rows), horizons_sec=[300], min_events=1)

    candidate = next(row for row in summary if row["event"] == "mom100_up_3k" and row["filter"] == "ask20_50_gt900")
    assert candidate["dev"]["events"] == 2
    assert candidate["lockbox"]["events"] == 2
    assert candidate["recommendation"] == "research_candidate"


def test_chronological_candidate_details_returns_exact_research_trades():
    rows = []
    for idx, match_id in enumerate(["m1", "m2", "m3", "m4"]):
        row = _row(
            match_id=match_id,
            received_at_ns=(idx + 1) * 100,
            side_mom_100=4000,
            ask=0.60,
            bid=0.58,
        )
        row["event_name"] = "kill_mom_up"
        row["side_kill_mom_num"] = 2.0
        row["sell_bid_pnl_300"] = 0.10
        row["future_bid_300"] = 0.73
        row["settlement_pnl_2c"] = 0.20
        rows.append(row)
    events = pd.DataFrame(rows)
    candidates = [
        {
            "event": "kill_mom_up",
            "filter": "ask50_80_src_age5",
            "horizon_sec": 300,
            "recommendation": "research_candidate",
        }
    ]

    details = chronological_candidate_details(events, candidates, limit=10)

    assert [row["match_id"] for row in details] == ["m1", "m2", "m3", "m4"]
    assert details[-1]["split"] == "lockbox"
    assert details[0]["future_bid"] == 0.73
    assert details[0]["sell_bid_pnl"] == 0.10


def test_chronological_settlement_candidate_summary_scores_hold_to_settlement():
    rows = []
    for idx, match_id in enumerate(["m1", "m2", "m3", "m4"]):
        row = _row(match_id=match_id, received_at_ns=(idx + 1) * 100, side_mom_100=4000, ask=0.60)
        row["event_name"] = "kill_mom_up"
        row["side_kill_mom_num"] = 2.0
        row["settlement_pnl_2c"] = 0.20
        rows.append(row)

    summary = chronological_settlement_candidate_summary(pd.DataFrame(rows), min_events=1)

    candidate = next(row for row in summary if row["event"] == "kill_mom_up" and row["filter"] == "ask50_80_src_age5")
    assert candidate["dev"]["settlement_pnl_2c"] == pytest.approx(0.40)
    assert candidate["lockbox"]["settlement_pnl_2c"] == pytest.approx(0.40)
    assert candidate["recommendation"] == "research_candidate"


def test_chronological_settlement_candidate_details_returns_exact_hold_trades():
    rows = []
    for idx, match_id in enumerate(["m1", "m2", "m3", "m4"]):
        row = _row(match_id=match_id, received_at_ns=(idx + 1) * 100, side_mom_100=4000, ask=0.60)
        row["event_name"] = "kill_mom_up"
        row["side_kill_mom_num"] = 2.0
        row["settlement_pnl_2c"] = 0.20
        rows.append(row)
    events = pd.DataFrame(rows)
    candidates = [{"event": "kill_mom_up", "filter": "ask50_80_src_age5", "recommendation": "research_candidate"}]

    details = chronological_settlement_candidate_details(events, candidates, limit=10)

    assert [row["match_id"] for row in details] == ["m1", "m2", "m3", "m4"]
    assert details[-1]["split"] == "lockbox"
    assert details[0]["settlement_pnl_2c"] == 0.20


def test_match_level_pnl_aggregates_multiple_maps_per_match():
    events = pd.DataFrame(
        [
            {"match_id": "m1", "settlement_pnl_2c": 0.40},
            {"match_id": "m1", "settlement_pnl_2c": -0.20},
            {"match_id": "m2", "settlement_pnl_2c": 0.10},
        ]
    )

    pnl = match_level_pnl(events, pnl_col="settlement_pnl_2c")

    assert pnl.to_dict() == {"m1": pytest.approx(0.20), "m2": pytest.approx(0.10)}


def test_settlement_strategy_metrics_adds_bootstrap_and_concentration():
    events = pd.DataFrame(
        [
            _row(match_id="m1", ask=0.40),
            _row(match_id="m2", ask=0.60),
            _row(match_id="m3", ask=0.50),
            _row(match_id="m4", ask=0.70),
        ]
    )
    events["settlement_pnl_2c"] = [0.58, 0.38, -0.52, 0.28]
    events["settled_win"] = [True, True, False, True]

    metrics = settlement_strategy_metrics(events)

    assert metrics["settlement_pnl_2c"] == pytest.approx(0.72)
    assert metrics["bootstrap_p05"] is not None
    assert metrics["bootstrap_prob_positive"] > 0.5
    assert metrics["max_match_pnl"] == pytest.approx(0.58)
    assert metrics["worst_match_pnl"] == pytest.approx(-0.52)
    assert metrics["max_match_share"] == pytest.approx(0.58 / 0.72)


def test_bootstrap_and_concentration_handle_empty_events():
    empty = pd.DataFrame(columns=["match_id", "settlement_pnl_2c"])

    boot = bootstrap_match_pnl(empty, pnl_col="settlement_pnl_2c")
    concentration = concentration_metrics(empty, pnl_col="settlement_pnl_2c")

    assert boot["bootstrap_p05"] is None
    assert boot["bootstrap_prob_positive"] is None
    assert concentration["max_match_share"] is None


def _row(
    *,
    match_id: str = "m1",
    game: int = 1,
    side: str = "YES",
    token_id: str = "tok1",
    received_at_ns: int = 100,
    game_time_sec: int = 900,
    ask: float = 0.40,
    bid: float = 0.39,
    side_mom_100: float = 0.0,
    market_scope: str = "map_winner_explicit",
    tradable: bool = True,
) -> dict:
    return {
        "match_id": match_id,
        "current_game_number": game,
        "map_exposure_id": f"{match_id}::{game}",
        "canonical_exposure_id": f"{match_id}::{game}::{side}",
        "market_scope": market_scope,
        "side": side,
        "token_id": token_id,
        "received_at_ns": received_at_ns,
        "received_at_ns_num": float(received_at_ns),
        "game_time_sec": game_time_sec,
        "game_time_sec_num": float(game_time_sec),
        "book_best_ask": ask,
        "book_best_ask_num": ask,
        "book_best_bid": bid,
        "book_best_bid_num": bid,
        "book_mid_num": (ask + bid) / 2.0,
        "entry_mid_num": (ask + bid) / 2.0,
        "tradable_research": tradable,
        "side_mom_100_num": side_mom_100,
        "side_mom_300_num": 0.0,
        "side_kill_mom_num": 0.0,
        "side_transition_nw_delta_num": 0.0,
        "side_transition_kill_delta_num": 0.0,
        "transition_signal_type": "no_transition",
        "settled_win": True,
        "source_update_age_sec_num": 0.0,
        "side_nw_num": 1000.0,
        "settlement_pnl_2c": 1.0 - ask - 0.02,
    }
