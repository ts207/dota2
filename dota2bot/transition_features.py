"""Sparse game-state transition features for executable Dota side snapshots."""

from __future__ import annotations

import numpy as np
import pandas as pd


MAX_CONFIRM_GAP_SEC = 45
MIN_NW_TRANSITION = 1000
LARGE_NW_TRANSITION = 3000
LARGE_KILL_TRANSITION = 2


TRANSITION_COLUMNS = [
    "transition_dt_sec",
    "radiant_lead_delta",
    "score_diff_delta",
    "total_kill_delta",
    "radiant_score_delta",
    "dire_score_delta",
    "building_state_changed",
    "side_transition_nw_delta",
    "side_transition_score_delta",
    "side_transition_kill_delta",
    "side_transition_nw_per_sec",
    "side_transition_kill_per_sec",
    "side_transition_building_changed",
    "nw_changed",
    "score_changed",
    "building_changed",
    "last_nw_change_game_time",
    "last_score_change_game_time",
    "last_building_change_game_time",
    "seconds_since_nw_change",
    "seconds_since_score_change",
    "seconds_since_building_change",
    "score_changed_without_nw",
    "nw_changed_without_score",
    "score_nw_changed_together",
    "score_leads_nw_sec",
    "nw_leads_score_sec",
    "score_nw_lag_type",
    "transition_signal_type",
]


def add_transition_features(rows: pd.DataFrame, *, max_confirm_gap_sec: int = MAX_CONFIRM_GAP_SEC) -> pd.DataFrame:
    """Add side-relative sparse transition features without double-counting token rows.

    The input is expected to be side snapshots. Multiple rows can share the same
    game-state timestamp because both token sides and multiple markets are logged.
    Transition deltas are computed once per unique match/game snapshot and merged
    back to every side row at that snapshot.
    """

    frame = rows.copy()
    for col in TRANSITION_COLUMNS:
        if col not in frame.columns:
            frame[col] = np.nan

    required = ["match_id", "received_at_ns", "game_time_sec", "radiant_score", "dire_score", "side_is_radiant"]
    missing = [col for col in required if col not in frame.columns]
    if missing:
        frame["score_nw_lag_type"] = "missing_input"
        frame["transition_signal_type"] = "missing_input"
        return frame

    if "nw_lead_clean" not in frame.columns:
        if "radiant_lead" in frame.columns and "net_worth_diff" in frame.columns:
            frame["nw_lead_clean"] = frame["radiant_lead"].fillna(frame["net_worth_diff"])
        elif "radiant_lead" in frame.columns:
            frame["nw_lead_clean"] = frame["radiant_lead"]
        elif "net_worth_diff" in frame.columns:
            frame["nw_lead_clean"] = frame["net_worth_diff"]
        else:
            frame["nw_lead_clean"] = np.nan
    if "building_state" not in frame.columns:
        frame["building_state"] = np.nan

    key_cols = ["match_id", "received_at_ns", "game_time_sec"]
    state_cols = key_cols + ["nw_lead_clean", "radiant_score", "dire_score", "building_state"]
    stream = (
        frame[state_cols]
        .drop_duplicates(key_cols)
        .sort_values(["match_id", "game_time_sec", "received_at_ns"])
        .reset_index(drop=True)
    )
    if stream.empty:
        frame["score_nw_lag_type"] = "no_change"
        frame["transition_signal_type"] = "no_transition"
        return frame

    stream["score_diff"] = stream["radiant_score"] - stream["dire_score"]
    stream["total_kills"] = stream["radiant_score"] + stream["dire_score"]

    pieces = []
    for _, sub in stream.groupby("match_id", sort=False):
        pieces.append(_add_match_transitions(sub.copy(), max_confirm_gap_sec=max_confirm_gap_sec))
    transition_stream = pd.concat(pieces, ignore_index=True)

    merge_cols = key_cols + [
        "transition_dt_sec",
        "radiant_lead_delta",
        "score_diff_delta",
        "total_kill_delta",
        "radiant_score_delta",
        "dire_score_delta",
        "building_state_changed",
        "nw_changed",
        "score_changed",
        "building_changed",
        "last_nw_change_game_time",
        "last_score_change_game_time",
        "last_building_change_game_time",
        "seconds_since_nw_change",
        "seconds_since_score_change",
        "seconds_since_building_change",
        "score_changed_without_nw",
        "nw_changed_without_score",
        "score_nw_changed_together",
        "score_leads_nw_sec",
        "nw_leads_score_sec",
        "score_nw_lag_type",
    ]
    frame = frame.drop(columns=[c for c in merge_cols if c in frame.columns and c not in key_cols], errors="ignore")
    frame = frame.merge(transition_stream[merge_cols], on=key_cols, how="left")

    sign = _side_sign(frame["side_is_radiant"])
    dt = frame["transition_dt_sec"].replace(0, np.nan)
    frame["side_transition_nw_delta"] = sign * frame["radiant_lead_delta"]
    frame["side_transition_score_delta"] = sign * frame["score_diff_delta"]
    side_is_radiant = frame["side_is_radiant"].map(_bool_or_none)
    frame["side_transition_kill_delta"] = np.where(
        side_is_radiant == True,  # noqa: E712
        frame["radiant_score_delta"],
        np.where(side_is_radiant == False, frame["dire_score_delta"], np.nan),  # noqa: E712
    )
    frame["side_transition_nw_per_sec"] = frame["side_transition_nw_delta"] / dt
    frame["side_transition_kill_per_sec"] = frame["side_transition_kill_delta"] / dt
    frame["side_transition_building_changed"] = frame["building_state_changed"]
    frame["transition_signal_type"] = _transition_signal_type(frame, max_confirm_gap_sec=max_confirm_gap_sec)
    return frame


def _add_match_transitions(sub: pd.DataFrame, *, max_confirm_gap_sec: int) -> pd.DataFrame:
    sub = sub.sort_values(["game_time_sec", "received_at_ns"]).copy()
    sub["transition_dt_sec"] = sub["game_time_sec"].diff()
    sub["radiant_lead_delta"] = sub["nw_lead_clean"].diff()
    sub["score_diff_delta"] = sub["score_diff"].diff()
    sub["total_kill_delta"] = sub["total_kills"].diff()
    sub["radiant_score_delta"] = sub["radiant_score"].diff()
    sub["dire_score_delta"] = sub["dire_score"].diff()

    prev_building = sub["building_state"].shift(1)
    sub["building_state_changed"] = (
        prev_building.notna()
        & sub["building_state"].notna()
        & (sub["building_state"].astype("float64") != prev_building.astype("float64"))
    )

    sub["nw_changed"] = sub["radiant_lead_delta"].abs() >= MIN_NW_TRANSITION
    sub["score_changed"] = sub["total_kill_delta"].abs() > 0
    sub["building_changed"] = sub["building_state_changed"].fillna(False).astype(bool)
    first_mask = sub["transition_dt_sec"].isna()
    sub.loc[first_mask, ["nw_changed", "score_changed", "building_changed", "building_state_changed"]] = False

    sub["score_changed_without_nw"] = sub["score_changed"] & ~sub["nw_changed"]
    sub["nw_changed_without_score"] = sub["nw_changed"] & ~sub["score_changed"]
    sub["score_nw_changed_together"] = sub["score_changed"] & sub["nw_changed"]

    for source_col, out_col in [
        ("nw_changed", "last_nw_change_game_time"),
        ("score_changed", "last_score_change_game_time"),
        ("building_changed", "last_building_change_game_time"),
    ]:
        values = sub["game_time_sec"].where(sub[source_col])
        sub[out_col] = values.ffill()

    sub["seconds_since_nw_change"] = sub["game_time_sec"] - sub["last_nw_change_game_time"]
    sub["seconds_since_score_change"] = sub["game_time_sec"] - sub["last_score_change_game_time"]
    sub["seconds_since_building_change"] = sub["game_time_sec"] - sub["last_building_change_game_time"]

    raw_score_lead = sub["last_score_change_game_time"] - sub["last_nw_change_game_time"]
    raw_nw_lead = sub["last_nw_change_game_time"] - sub["last_score_change_game_time"]
    sub["score_leads_nw_sec"] = raw_score_lead.where(raw_score_lead > 0, 0.0)
    sub["nw_leads_score_sec"] = raw_nw_lead.where(raw_nw_lead > 0, 0.0)
    sub.loc[sub["nw_changed_without_score"], "score_leads_nw_sec"] = sub.loc[sub["nw_changed_without_score"], "seconds_since_score_change"]
    sub.loc[sub["score_changed_without_nw"], "nw_leads_score_sec"] = sub.loc[sub["score_changed_without_nw"], "seconds_since_nw_change"]

    lag_type = np.full(len(sub), "no_change", dtype=object)
    same = sub["score_nw_changed_together"].to_numpy(dtype=bool)
    score_only = sub["score_changed_without_nw"].to_numpy(dtype=bool)
    nw_only = sub["nw_changed_without_score"].to_numpy(dtype=bool)
    score_then_nw = (
        sub["nw_changed_without_score"]
        & sub["seconds_since_score_change"].notna()
        & (sub["seconds_since_score_change"] <= max_confirm_gap_sec)
        & (sub["seconds_since_score_change"] > 0)
    ).to_numpy(dtype=bool)
    nw_then_score = (
        sub["score_changed_without_nw"]
        & sub["seconds_since_nw_change"].notna()
        & (sub["seconds_since_nw_change"] <= max_confirm_gap_sec)
        & (sub["seconds_since_nw_change"] > 0)
    ).to_numpy(dtype=bool)
    lag_type[score_only] = "score_only"
    lag_type[nw_only] = "nw_only"
    lag_type[same] = "same_snapshot"
    lag_type[score_then_nw] = "score_then_nw"
    lag_type[nw_then_score] = "nw_then_score"
    sub["score_nw_lag_type"] = lag_type
    return sub


def _side_sign(side_is_radiant: pd.Series) -> np.ndarray:
    parsed = side_is_radiant.map(_bool_or_none)
    return np.where(parsed == True, 1.0, np.where(parsed == False, -1.0, np.nan))  # noqa: E712


def _bool_or_none(value: object) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _transition_signal_type(frame: pd.DataFrame, *, max_confirm_gap_sec: int) -> pd.Series:
    side_nw = frame["side_transition_nw_delta"].fillna(0)
    side_kills = frame["side_transition_kill_delta"].fillna(0)
    favorable_nw = side_nw >= MIN_NW_TRANSITION
    large_nw = side_nw >= LARGE_NW_TRANSITION
    favorable_kills = side_kills > 0
    large_kills = side_kills >= LARGE_KILL_TRANSITION
    confirmed = (favorable_nw & favorable_kills) | large_nw | large_kills
    score_then_nw = (frame["score_nw_lag_type"] == "score_then_nw") & favorable_nw
    nw_then_score = (frame["score_nw_lag_type"] == "nw_then_score") & favorable_kills

    signal = pd.Series("no_transition", index=frame.index, dtype=object)
    signal.loc[frame["score_changed_without_nw"].fillna(False).astype(bool) & favorable_kills] = "first_score_change"
    signal.loc[frame["nw_changed_without_score"].fillna(False).astype(bool) & favorable_nw] = "first_nw_change"
    signal.loc[frame["score_nw_changed_together"].fillna(False).astype(bool) & (favorable_nw | favorable_kills)] = "score_nw_same_snapshot"
    signal.loc[score_then_nw] = "score_then_nw_catchup"
    signal.loc[nw_then_score] = "nw_then_score_catchup"
    signal.loc[confirmed] = "confirmed_transition"

    recent_change = (
        (frame["seconds_since_nw_change"].notna() & (frame["seconds_since_nw_change"] <= max_confirm_gap_sec))
        | (frame["seconds_since_score_change"].notna() & (frame["seconds_since_score_change"] <= max_confirm_gap_sec))
    )
    no_current_change = ~(frame["nw_changed"].fillna(False).astype(bool) | frame["score_changed"].fillna(False).astype(bool))
    signal.loc[(signal == "no_transition") & recent_change & no_current_change] = "post_transition_close"
    return signal
