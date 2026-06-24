from __future__ import annotations

import pandas as pd

from walk_forward_model_research import first_trade_rows, make_folds, split_development_lockbox


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


def test_first_trade_rows_dedupes_by_match_and_bucket_only():
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
