from __future__ import annotations

import pandas as pd

from dota2bot.live_logger import _side_rows_for_game
from dota2bot.schemas import SIDE_SNAPSHOT_COLUMNS


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
