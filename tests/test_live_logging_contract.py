from __future__ import annotations

import pandas as pd

from dota2bot.live_logger import _annotate_state_changes, _bind_discovered_markets, _filter_games_for_markets, _infer_market_side_mapping, _side_rows_for_game
from dota2bot.live_sources import normalize_top_live_game
from dota2bot.logging_store import BotLogs
from dota2bot.schemas import LIVE_BINDING_REJECT_COLUMNS, LIVE_HEALTH_COLUMNS, SIDE_SNAPSHOT_COLUMNS
from dota2bot.strategies import LeaderMidgameProbe


def test_live_side_rows_use_clean_schema():
    game = {
        "match_id": "m1",
        "received_at_utc": "2026-01-01T00:00:01+00:00",
        "received_at_ns": 1_000_000_000,
        "game_time_sec": 100,
        "radiant_lead": 1000,
        "radiant_score": 3,
        "dire_score": 1,
        "data_source": "steam_top_live",
    }
    markets = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "market_id": "mk1",
                "condition_id": "c1",
                "market_name": "M",
                "market_type": "MAP_WINNER",
                "label_market_bucket": "MAP_WINNER",
                "current_game_number": "",
                "side": "YES",
                "token_id": "yes",
                "opposing_token_id": "no",
                "yes_token_id": "yes",
                "no_token_id": "no",
                "yes_team": "A",
                "no_team": "B",
                "yes_is_radiant": True,
                "confidence": "1.0",
            }
        ]
    )
    books = {
        "yes": {
            "asset_id": "yes",
            "received_at_utc": "2026-01-01T00:00:00+00:00",
            "received_at_ns": 900_000_000,
            "best_bid": 0.49,
            "best_ask": 0.51,
            "bid_size": 100,
            "ask_size": 100,
            "mid": 0.5,
            "spread": 0.02,
        }
    }
    rows = _side_rows_for_game(game, markets, books)
    assert len(rows) == 1
    assert list(rows[0].keys()) == SIDE_SNAPSHOT_COLUMNS
    assert rows[0]["book_best_ask"] == 0.51
    assert rows[0]["settled_win"] is None


def test_live_discovered_team_outcomes_map_to_radiant_and_dire():
    game = {
        "match_id": "8862817169",
        "radiant_team": "REKONIX",
        "dire_team": "TEAM GRIND",
        "received_at_utc": "2026-06-23T05:53:30+00:00",
        "received_at_ns": 1_000_000_000,
    }
    yes_row = {
        "side": "REKONIX",
        "token_id": "yes-token",
        "yes_token_id": "yes-token",
        "no_token_id": "no-token",
        "yes_team": "REKONIX",
        "no_team": "GRIND BACK",
    }
    no_row = {
        "side": "GRIND BACK",
        "token_id": "no-token",
        "yes_token_id": "yes-token",
        "no_token_id": "no-token",
        "yes_team": "REKONIX",
        "no_team": "GRIND BACK",
    }

    yes_mapping = _infer_market_side_mapping(yes_row, game)
    no_mapping = _infer_market_side_mapping(no_row, game)

    assert yes_mapping == {
        "side_is_radiant": True,
        "yes_is_radiant": True,
        "steam_side_mapping": "normal",
        "confidence": "1.0",
    }
    assert no_mapping == {
        "side_is_radiant": False,
        "yes_is_radiant": True,
        "steam_side_mapping": "normal",
        "confidence": "1.0",
    }


def test_probe_rejects_missing_side_mapping():
    decision = LeaderMidgameProbe().evaluate(
        {
            "game_time_sec": 1200,
            "radiant_lead": -9000,
            "radiant_score": 7,
            "dire_score": 12,
            "side_is_radiant": None,
        }
    )
    assert decision.signal is False
    assert decision.reason == "missing_side_mapping"


def test_top_live_normalization_logs_broadcast_delay_and_source_age():
    row = normalize_top_live_game(
        {
            "match_id": "m1",
            "game_time": 100,
            "radiant_lead": 2500,
            "radiant_score": 4,
            "dire_score": 2,
            "delay": 900,
            "last_update_time": 1_700_000_000.0,
            "building_state": 123,
        },
        received_at_ns=1_700_000_017_500_000_000,
    )

    assert row["stream_delay_s"] == 900
    assert row["broadcast_delay_s"] == 900
    assert row["source_last_update_utc"] == "2023-11-14T22:13:20+00:00"
    assert row["source_update_age_sec"] == 17.5
    assert row["source_clock_skew_sec"] == 0.0
    assert row["state_hash"]


def test_top_live_future_source_timestamp_logs_clock_skew():
    row = normalize_top_live_game(
        {
            "match_id": "m1",
            "game_time": 100,
            "last_update_time": 1_700_000_020.0,
        },
        received_at_ns=1_700_000_017_500_000_000,
    )

    assert row["source_update_age_sec"] == 0.0
    assert row["source_clock_skew_sec"] == 2.5


def test_state_change_annotation_tracks_unchanged_polls():
    games = [
        {"match_id": "m1", "state_hash": "a", "received_at_ns": 1_000_000_000},
        {"match_id": "m1", "state_hash": "a", "received_at_ns": 6_000_000_000},
        {"match_id": "m1", "state_hash": "b", "received_at_ns": 8_000_000_000},
    ]
    last_hash = {}
    last_change = {}

    for game in games:
        _annotate_state_changes([game], last_hash, last_change)

    assert games[0]["state_changed"] is True
    assert games[0]["seconds_since_state_change"] == 0.0
    assert games[1]["state_changed"] is False
    assert games[1]["seconds_since_state_change"] == 5.0
    assert games[2]["state_changed"] is True
    assert games[2]["seconds_since_state_change"] == 0.0


def test_discovered_binding_skips_when_map_number_unknown():
    markets = pd.DataFrame(
        [
            {
                "match_id": "",
                "market_name": "Dota 2: REKONIX vs Grind Back - Game 2 Winner",
                "side": "REKONIX",
                "token_id": "yes-token",
                "yes_token_id": "yes-token",
                "no_token_id": "no-token",
                "yes_team": "REKONIX",
                "no_team": "GRIND BACK",
            }
        ]
    )
    _bind_discovered_markets(
        markets,
        [
            {
                "match_id": "8862817169",
                "radiant_team": "REKONIX",
                "dire_team": "TEAM GRIND",
            }
        ],
        {},
    )

    assert markets.loc[0, "match_id"] == ""


def test_live_filter_keeps_only_games_matching_polymarket_markets():
    markets = pd.DataFrame(
        [
            {
                "market_name": "Dota 2: REKONIX vs Grind Back - Game 2 Winner",
            }
        ]
    )
    games = [
        {
            "match_id": "8862817169",
            "radiant_team": "REKONIX",
            "dire_team": "TEAM GRIND",
        },
        {
            "match_id": "irrelevant",
            "radiant_team": "ALPHA",
            "dire_team": "BETA",
        },
        {
            "match_id": "missing-teams",
            "radiant_team": "",
            "dire_team": "",
        },
    ]

    filtered, rejects = _filter_games_for_markets(games, markets)

    assert [game["match_id"] for game in filtered] == ["8862817169"]
    assert [reject["reason"] for reject in rejects] == ["not_polymarket_match", "missing_team_names"]


def test_future_deactivate_time_is_not_game_over():
    row = normalize_top_live_game(
        {
            "match_id": "m1",
            "game_time": 100,
            "deactivate_time": 1_700_000_100,
            "last_update_time": 1_700_000_000,
        },
        received_at_ns=1_700_000_017_000_000_000,
    )
    assert row["game_over"] is False

    row = normalize_top_live_game(
        {
            "match_id": "m1",
            "game_time": 100,
            "deactivate_time": 1_700_000_010,
            "last_update_time": 1_700_000_000,
        },
        received_at_ns=1_700_000_017_000_000_000,
    )
    assert row["game_over"] is True


def test_live_health_and_binding_reject_logs_use_exact_schema(tmp_path):
    logs = BotLogs(root=tmp_path, batch_rows=1)
    logs.live_health.append({"cycle_id": "c1", "fetched_games": 2, "irrelevant_games": 1, "games": 1})
    logs.live_binding_rejects.append({"cycle_id": "c1", "reason": "no_map_number"})

    health_file = next((tmp_path / "live_health").glob("*.parquet"))
    rejects_file = next((tmp_path / "live_binding_rejects").glob("*.parquet"))

    assert list(pd.read_parquet(health_file).columns) == LIVE_HEALTH_COLUMNS
    assert list(pd.read_parquet(rejects_file).columns) == LIVE_BINDING_REJECT_COLUMNS
