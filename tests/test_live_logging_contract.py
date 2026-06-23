from __future__ import annotations

import json

import pandas as pd

from dota2bot.audit_logs import run_audit_logs
from dota2bot.live_logger import (
    SERIES_DECIDER_EQUIVALENT,
    _annotate_state_changes,
    _bind_discovered_markets,
    _classify_market_for_live_map,
    _filter_games_for_markets,
    _infer_market_side_mapping,
    _side_rows_for_game,
)
from dota2bot.live_sources import normalize_top_live_game
from dota2bot.logging_store import BotLogs
from dota2bot.schemas import LIVE_BINDING_REJECT_COLUMNS, LIVE_HEALTH_COLUMNS, SIDE_SNAPSHOT_COLUMNS
from dota2bot.settle_live import dedupe_side_snapshots, enrich_side_snapshots, normalize_side_snapshot_frame
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
    assert rows[0]["has_two_sided_book"] is True


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


def test_bo3_map3_series_moneyline_binds_as_decider_equivalent():
    markets = pd.DataFrame(
        [
            {
                "match_id": "",
                "market_name": "Dota 2: Rune Eaters vs MODUS (BO3) - The International Europe Closed Qualifier Playoffs",
                "market_type": "moneyline",
                "side": "RUNE EATERS",
                "token_id": "yes-token",
                "yes_token_id": "yes-token",
                "no_token_id": "no-token",
                "yes_team": "RUNE EATERS",
                "no_team": "MODUS",
            }
        ]
    )

    rejects = _bind_discovered_markets(
        markets,
        [
            {
                "match_id": "8863187227",
                "radiant_team": "Rune Eaters",
                "dire_team": "MODUS",
            }
        ],
        {"8863187227": 3},
    )

    assert rejects == []
    assert markets.loc[0, "match_id"] == "8863187227"
    assert markets.loc[0, "market_scope"] == SERIES_DECIDER_EQUIVALENT
    assert markets.loc[0, "parsed_series_length"] == 3


def test_series_moneyline_only_binds_on_deciding_map():
    bo3_map2 = _classify_market_for_live_map(
        {
            "market_name": "Dota 2: Rune Eaters vs MODUS (BO3) - The International Europe Closed Qualifier Playoffs",
            "market_type": "moneyline",
        },
        2,
    )
    bo5_map3 = _classify_market_for_live_map(
        {
            "market_name": "Dota 2: OG vs Grind Back (BO5) - The International Southeast Asia Closed Qualifier Playoffs",
            "market_type": "moneyline",
        },
        3,
    )
    bo5_map5 = _classify_market_for_live_map(
        {
            "market_name": "Dota 2: OG vs Grind Back (BO5) - The International Southeast Asia Closed Qualifier Playoffs",
            "market_type": "moneyline",
        },
        5,
    )

    assert bo3_map2["bind"] is False
    assert bo3_map2["reason"] == "series_market_not_decider"
    assert bo5_map3["bind"] is False
    assert bo5_map3["reason"] == "series_market_not_decider"
    assert bo5_map5["bind"] is True
    assert bo5_map5["market_scope"] == SERIES_DECIDER_EQUIVALENT


def test_explicit_game_winner_binds_only_matching_live_game():
    game2 = {
        "market_name": "Dota 2: Rune Eaters vs MODUS - Game 2 Winner",
        "market_type": "child_moneyline",
    }

    assert _classify_market_for_live_map(game2, 2)["bind"] is True
    wrong = _classify_market_for_live_map(game2, 3)
    assert wrong["bind"] is False
    assert wrong["reason"] == "wrong_game_number"


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


def test_audit_logs_reports_map_equivalent_rows(tmp_path):
    logs = BotLogs(root=tmp_path, batch_rows=1)
    logs.live_health.append({"cycle_id": "c1", "fetched_games": 1, "games": 1, "live_side_rows": 1})
    logs.live_binding_rejects.append(
        {
            "cycle_id": "c1",
            "reason": "series_market_not_decider",
            "reject_bucket": "expected_non_target_market",
        }
    )
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row.update(
        {
            "match_id": "m1",
            "market_id": "mk1",
            "token_id": "tok",
            "market_type": "moneyline",
            "market_scope": SERIES_DECIDER_EQUIVALENT,
            "received_at_utc": "2026-01-01T00:00:00+00:00",
            "received_at_ns": 1_000_000_000,
            "source_update_age_sec": 1.0,
            "book_age_ms": 100.0,
            "book_best_bid": 0.49,
            "book_best_ask": 0.51,
            "book_ask_size": 200.0,
            "book_spread": 0.02,
        }
    )
    logs.live_side_snapshots.append(row)

    report = json.loads(run_audit_logs(logs_root=tmp_path, output_format="json"))

    assert report["side_snapshots"]["summary"]["map_equivalent_rows"] == 1
    assert report["side_snapshots"]["summary"]["series_decider_equivalent_rows"] == 1
    assert report["side_snapshots"]["summary"]["executable_rows"] == 1


def test_audit_logs_does_not_promote_legacy_child_moneyline_without_map_number(tmp_path):
    logs = BotLogs(root=tmp_path, batch_rows=1)
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row.update(
        {
            "match_id": "m1",
            "market_id": "mk1",
            "token_id": "tok",
            "market_name": "Dota 2: REKONIX vs Grind Back - Game 2 Winner",
            "market_type": "child_moneyline",
            "received_at_utc": "2026-01-01T00:00:00+00:00",
            "received_at_ns": 1_000_000_000,
            "source_update_age_sec": 1.0,
            "book_age_ms": 100.0,
            "book_best_bid": 0.49,
            "book_best_ask": 0.51,
            "book_ask_size": 200.0,
            "book_spread": 0.02,
        }
    )
    logs.live_side_snapshots.append(row)

    report = json.loads(run_audit_logs(logs_root=tmp_path, output_format="json"))

    assert report["side_snapshots"]["summary"]["map_equivalent_rows"] == 0
    assert report["side_snapshots"]["by_scope"][0]["market_scope"] == "unknown_scope"


def test_settle_live_enriches_side_rows_with_outcome_and_pnl():
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row.update(
        {
            "match_id": "m1",
            "side": "RADIANT",
            "side_is_radiant": True,
            "yes_is_radiant": True,
            "book_best_ask": 0.40,
            "market_scope": "map_winner_explicit",
        }
    )
    outcomes = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "radiant_win": True,
                "outcome_source": "test",
                "status": "settled",
            }
        ]
    )

    enriched = enrich_side_snapshots(pd.DataFrame([row]), outcomes)

    assert enriched.loc[0, "radiant_win"] is True
    assert enriched.loc[0, "settled_win"] is True
    assert enriched.loc[0, "yes_won"] is True
    assert enriched.loc[0, "hold_to_settlement_pnl_per_share"] == 0.60
    assert round(enriched.loc[0, "hold_to_settlement_roi"], 6) == 1.5


def test_settle_live_infers_missing_side_mapping_from_side_name():
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row.update(
        {
            "match_id": "8862817169",
            "side": "GRIND BACK",
            "radiant_team": "REKONIX",
            "dire_team": "TEAM GRIND",
            "book_best_ask": 0.31,
            "market_scope": "map_winner_explicit",
        }
    )
    outcomes = pd.DataFrame(
        [
            {
                "match_id": "8862817169",
                "radiant_win": False,
                "outcome_source": "test",
                "status": "settled",
            }
        ]
    )

    enriched = enrich_side_snapshots(pd.DataFrame([row]), outcomes)

    assert enriched.loc[0, "side_is_radiant"] is False
    assert enriched.loc[0, "settled_win"] is True
    assert enriched.loc[0, "hold_to_settlement_pnl_per_share"] == 0.69


def test_settle_live_dedupes_exact_snapshot_keys_only():
    rows = []
    for received_at_ns in [100, 100, 105]:
        row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
        row.update(
            {
                "match_id": "m1",
                "market_id": "mk1",
                "token_id": "tok1",
                "received_at_ns": received_at_ns,
            }
        )
        rows.append(row)

    deduped = dedupe_side_snapshots(pd.DataFrame(rows))

    assert len(deduped) == 2
    assert deduped["received_at_ns"].tolist() == [100, 105]


def test_normalize_side_snapshot_frame_derives_legacy_map_equivalent_scope():
    frame = pd.DataFrame(
        [
            {
                "match_id": "m1",
                "market_name": "Dota 2: A vs B (BO3) - Final",
                "market_type": "moneyline",
                "current_game_number": "3",
                "source_update_age_sec": 1.0,
                "book_age_ms": 100.0,
                "book_best_bid": 0.49,
                "book_best_ask": 0.51,
                "book_ask_size": 200.0,
                "book_spread": 0.02,
            }
        ]
    )

    normalized = normalize_side_snapshot_frame(frame)

    assert normalized.loc[0, "market_scope"] == SERIES_DECIDER_EQUIVALENT
    assert normalized.loc[0, "executable_snapshot"] is True
