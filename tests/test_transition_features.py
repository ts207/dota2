from __future__ import annotations

import pandas as pd

from dota2bot.transition_features import add_transition_features


def test_transition_features_detect_score_only_change():
    frame = _transition_frame()

    featured = add_transition_features(frame)
    row = _row(featured, game_time=620, side_is_radiant=True)

    assert row["score_changed"]
    assert not row["nw_changed"]
    assert row["score_changed_without_nw"]
    assert row["score_nw_lag_type"] == "score_only"
    assert row["transition_signal_type"] == "first_score_change"
    assert row["side_transition_kill_delta"] == 1


def test_transition_features_detect_nw_only_catchup():
    frame = _transition_frame()

    featured = add_transition_features(frame)
    row = _row(featured, game_time=650, side_is_radiant=True)

    assert row["nw_changed"]
    assert not row["score_changed"]
    assert row["nw_changed_without_score"]
    assert row["score_nw_lag_type"] == "score_then_nw"
    assert row["transition_signal_type"] == "score_then_nw_catchup"
    assert row["side_transition_nw_delta"] == 1500
    assert row["score_leads_nw_sec"] == 30


def test_transition_features_detect_same_snapshot_confirmation():
    frame = _transition_frame()

    featured = add_transition_features(frame)
    row = _row(featured, game_time=690, side_is_radiant=True)

    assert row["score_changed"]
    assert row["nw_changed"]
    assert row["score_nw_changed_together"]
    assert row["score_nw_lag_type"] == "same_snapshot"
    assert row["transition_signal_type"] == "confirmed_transition"
    assert row["side_transition_kill_delta"] == 2
    assert row["side_transition_nw_delta"] == 3500


def test_transition_features_side_relative_values_flip_for_dire():
    frame = _transition_frame()

    featured = add_transition_features(frame)
    dire = _row(featured, game_time=690, side_is_radiant=False)

    assert dire["side_transition_nw_delta"] == -3500
    assert dire["side_transition_score_delta"] == -2
    assert dire["side_transition_kill_delta"] == 0
    assert dire["transition_signal_type"] == "no_transition"


def test_transition_features_do_not_double_count_duplicate_side_rows():
    frame = pd.concat([_transition_frame(), _transition_frame().assign(market_id="market2")], ignore_index=True)

    featured = add_transition_features(frame)
    rows = featured[(featured["game_time_sec"] == 620) & (featured["side_is_radiant"] == True)]  # noqa: E712

    assert rows["radiant_score_delta"].tolist() == [1.0, 1.0]
    assert rows["transition_dt_sec"].tolist() == [20.0, 20.0]
    assert rows["side_transition_kill_delta"].tolist() == [1.0, 1.0]


def test_transition_features_first_row_has_no_fake_transition():
    frame = _transition_frame()

    featured = add_transition_features(frame)
    row = _row(featured, game_time=600, side_is_radiant=True)

    assert pd.isna(row["transition_dt_sec"])
    assert not row["score_changed"]
    assert not row["nw_changed"]
    assert row["score_nw_lag_type"] == "no_change"
    assert row["transition_signal_type"] == "no_transition"


def _row(frame: pd.DataFrame, *, game_time: int, side_is_radiant: bool) -> pd.Series:
    rows = frame[(frame["game_time_sec"] == game_time) & (frame["side_is_radiant"] == side_is_radiant)]
    assert len(rows) == 1
    return rows.iloc[0]


def _transition_frame() -> pd.DataFrame:
    states = [
        {"received_at_ns": 1000, "game_time_sec": 600, "radiant_lead": 0, "radiant_score": 0, "dire_score": 0, "building_state": 1},
        {"received_at_ns": 2000, "game_time_sec": 620, "radiant_lead": 0, "radiant_score": 1, "dire_score": 0, "building_state": 1},
        {"received_at_ns": 3000, "game_time_sec": 650, "radiant_lead": 1500, "radiant_score": 1, "dire_score": 0, "building_state": 1},
        {"received_at_ns": 4000, "game_time_sec": 690, "radiant_lead": 5000, "radiant_score": 3, "dire_score": 0, "building_state": 2},
    ]
    rows = []
    for state in states:
        for side_is_radiant, side in [(True, "YES"), (False, "NO")]:
            rows.append(
                {
                    "match_id": "m1",
                    "market_id": "market1",
                    "label_market_bucket": "MAP_WINNER",
                    "token_id": f"token_{side}",
                    "side": side,
                    "side_is_radiant": side_is_radiant,
                    **state,
                }
            )
    return pd.DataFrame(rows)
