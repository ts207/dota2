from __future__ import annotations

import pandas as pd

from dota2bot.side_features import add_side_features
from walk_forward_model_research import first_trade_rows, make_folds, split_development_lockbox, trade_output


def test_split_development_lockbox_keeps_last_matches_for_lockbox():
    frame = pd.DataFrame(
        [
            {"match_id": f"m{i}", "received_at_ns": i, "received_at_utc": f"t{i}"}
            for i in range(10)
        ]
    )

    split = split_development_lockbox(frame, lockbox_fraction=0.2)

    assert split.development_matches == [f"m{i}" for i in range(8)]
    assert split.lockbox_matches == ["m8", "m9"]


def test_make_folds_uses_past_matches_only():
    frame = pd.DataFrame(
        [
            {"match_id": f"m{i}", "received_at_ns": i, "received_at_utc": f"t{i}"}
            for i in range(12)
        ]
    )

    folds = make_folds(frame, initial_train_matches=6, n_folds=3)

    assert len(folds) == 3
    for fold in folds:
        fit = {int(m[1:]) for m in fold.fit_matches}
        validation = {int(m[1:]) for m in fold.validation_matches}
        test = {int(m[1:]) for m in fold.test_matches}
        assert fit.isdisjoint(validation)
        assert fit.isdisjoint(test)
        assert validation.isdisjoint(test)
        assert max(fit | validation) < min(test)


def test_first_trade_rows_dedupes_by_canonical_exposure_when_columns_present():
    """With current_game_number + side columns, MAP_WINNER and MATCH_WINNER_GAME3_PROXY
    for the same game/side collapse into a single canonical exposure (correct behaviour)."""
    frame = pd.DataFrame(
        [
            # Same match, same game, same side, different label buckets -> ONE canonical exposure
            {"match_id": "m1", "current_game_number": 3, "side": "NO", "label_market_bucket": "MAP_WINNER", "received_at_ns": 2, "book_best_ask": 0.40},
            {"match_id": "m1", "current_game_number": 3, "side": "NO", "label_market_bucket": "MATCH_WINNER_GAME3_PROXY", "received_at_ns": 1, "book_best_ask": 0.50},
            # Same match, same game, different side -> separate exposure
            {"match_id": "m1", "current_game_number": 3, "side": "YES", "label_market_bucket": "MAP_WINNER", "received_at_ns": 1, "book_best_ask": 0.60},
            # Different match -> separate exposure
            {"match_id": "m2", "current_game_number": 3, "side": "NO", "label_market_bucket": "MAP_WINNER", "received_at_ns": 1, "book_best_ask": 0.70},
        ]
    )

    deduped = first_trade_rows(frame)

    # 3 canonical exposures: (m1,3,NO), (m1,3,YES), (m2,3,NO)
    assert len(deduped) == 3
    # For (m1,3,NO): earliest received_at_ns=1 (MATCH_WINNER_GAME3_PROXY row) wins
    m1_no = deduped[(deduped["match_id"] == "m1") & (deduped["side"] == "NO")]
    assert len(m1_no) == 1
    assert m1_no.iloc[0]["received_at_ns"] == 1


def test_first_trade_rows_fallback_dedupes_by_match_and_bucket_without_canonical_cols():
    """Without current_game_number/side columns, falls back to match_id+label_market_bucket."""
    frame = pd.DataFrame(
        [
            {"match_id": "m1", "label_market_bucket": "MAP_WINNER", "received_at_ns": 2, "book_best_ask": 0.40},
            {"match_id": "m1", "label_market_bucket": "MAP_WINNER", "received_at_ns": 1, "book_best_ask": 0.60},
            {"match_id": "m1", "label_market_bucket": "MATCH_WINNER", "received_at_ns": 1, "book_best_ask": 0.50},
            {"match_id": "m2", "label_market_bucket": "MAP_WINNER", "received_at_ns": 1, "book_best_ask": 0.70},
        ]
    )

    deduped = first_trade_rows(frame)

    assert len(deduped) == 3
    assert deduped[["match_id", "label_market_bucket", "received_at_ns"]].values.tolist() == [
        ["m1", "MAP_WINNER", 1],
        ["m1", "MATCH_WINNER", 1],
        ["m2", "MAP_WINNER", 1],
    ]


def test_side_features_require_min_game_time_for_research_tradability():
    frame = _snapshot_frame([500, 700])

    featured = add_side_features(frame, min_game_time_sec=600)

    assert featured.loc[featured["game_time_sec"] == 500, "tradable_research"].tolist() == [False]
    assert featured.loc[featured["game_time_sec"] == 700, "tradable_research"].tolist() == [True]


def test_side_features_handle_missing_tower_and_building_columns():
    frame = _snapshot_frame([700]).drop(columns=["tower_state", "building_state"])

    featured = add_side_features(frame, min_game_time_sec=600)

    assert "side_tower" in featured.columns
    assert "side_rax" in featured.columns
    assert featured["side_tower"].isna().all()
    assert featured["side_rax"].isna().all()
    assert featured["tradable_research"].tolist() == [True]


def test_trade_output_empty_uses_fixed_ledger_columns():
    out = trade_output(pd.DataFrame())

    assert "stage" in out.columns
    assert "pnl_slip_1c" in out.columns
    assert "condition_id" not in out.columns


def _snapshot_frame(game_times: list[int]) -> pd.DataFrame:
    rows = []
    for idx, game_time in enumerate(game_times, start=1):
        rows.append(
            {
                "match_id": "m1",
                "market_id": "market1",
                "label_market_bucket": "MAP_WINNER",
                "token_id": "token_yes",
                "side": "YES",
                "received_at_utc": f"t{idx}",
                "received_at_ns": idx * 1_000,
                "game_time_sec": game_time,
                "league_id": "league1",
                "book_best_ask": 0.80,
                "book_best_bid": 0.79,
                "book_spread": 0.01,
                "book_ask_size": 200,
                "book_age_ms": 1000,
                "executable_snapshot": True,
                "quality_reason": "ok",
                "settled_win": None,
                "side_is_radiant": True,
                "radiant_lead": 10000,
                "net_worth_diff": 10000,
                "radiant_score": 20,
                "dire_score": 10,
                "tower_state": None,
                "building_state": None,
            }
        )
    return pd.DataFrame(rows)
