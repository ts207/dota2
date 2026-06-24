"""Shared side-relative features for research and paper decisions."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


RESEARCH_MIN_GAME_TIME_SEC = 600


def bit_count(value: object, bits: Iterable[int]) -> float:
    if pd.isna(value):
        return np.nan
    mask = int(value)
    return float(sum(1 for bit in bits if mask & (1 << bit)))


def side_from_signed(series: pd.Series, threshold: float) -> pd.Series:
    return pd.Series(
        np.select([series >= threshold, series <= -threshold], ["radiant", "dire"], default=""),
        index=series.index,
    )


def add_time_delta(frame: pd.DataFrame, value_col: str, seconds: int, out_col: str) -> pd.DataFrame:
    out = frame.copy()
    out[out_col] = np.nan
    key_cols = ["match_id", "received_at_ns", "game_time_sec"]
    missing = [col for col in key_cols + [value_col] if col not in out.columns]
    if missing:
        return out
    snap = (
        out.drop_duplicates(key_cols)
        .sort_values(["match_id", "game_time_sec", "received_at_ns"])
        [key_cols + [value_col]]
        .copy()
    )
    snap[out_col] = np.nan
    for _, idx in snap.groupby("match_id").groups.items():
        sub = snap.loc[idx].sort_values(["game_time_sec", "received_at_ns"])
        times = sub["game_time_sec"].to_numpy(dtype=float)
        values = sub[value_col].to_numpy(dtype=float)
        pos = np.searchsorted(times, times - seconds, side="right") - 1
        valid = pos >= 0
        deltas = np.full(len(sub), np.nan)
        deltas[valid] = values[valid] - values[pos[valid]]
        snap.loc[sub.index, out_col] = deltas
    merged = out.merge(snap[key_cols + [out_col]], on=key_cols, how="left", suffixes=("", "_new"))
    out[out_col] = merged[f"{out_col}_new"].to_numpy()
    return out


def add_base_state_features(rows: pd.DataFrame) -> pd.DataFrame:
    frame = rows.copy()
    if "net_worth_diff" not in frame.columns:
        frame["net_worth_diff"] = np.nan
    if "radiant_lead" not in frame.columns:
        frame["radiant_lead"] = np.nan
    if "radiant_score" not in frame.columns:
        frame["radiant_score"] = np.nan
    if "dire_score" not in frame.columns:
        frame["dire_score"] = np.nan
    if "tower_state" not in frame.columns:
        frame["tower_state"] = np.nan
    if "building_state" not in frame.columns:
        frame["building_state"] = np.nan

    frame["nw_lead_clean"] = frame["radiant_lead"].fillna(frame["net_worth_diff"])
    frame["abs_nw_lead"] = frame["nw_lead_clean"].abs()
    frame["score_diff"] = frame["radiant_score"] - frame["dire_score"]
    frame["abs_score_diff"] = frame["score_diff"].abs()
    frame["total_kills"] = frame["radiant_score"] + frame["dire_score"]
    frame["nw_leader"] = side_from_signed(frame["nw_lead_clean"], 0.000001).replace("", "tied")
    frame["kill_leader"] = side_from_signed(frame["score_diff"], 0.000001).replace("", "tied")
    frame["leaders_agree"] = frame["nw_leader"] == frame["kill_leader"]

    frame["towers_alive_radiant"] = frame["tower_state"].apply(lambda value: bit_count(value, range(0, 11)))
    frame["towers_alive_dire"] = frame["tower_state"].apply(lambda value: bit_count(value, range(11, 22)))
    frame["tower_advantage"] = frame["towers_alive_radiant"] - frame["towers_alive_dire"]

    build_int = frame["building_state"].fillna(0).astype("int64").to_numpy()
    for side, offsets in {"radiant": [0, 3, 6], "dire": [16, 19, 22]}.items():
        lane_cols = []
        for lane_num, offset in enumerate(offsets):
            col = f"{side}_building_lane_{lane_num}_state"
            frame[col] = np.where(
                frame["building_state"].notna(),
                ((build_int >> offset) & 0b111).astype("float64"),
                np.nan,
            )
            lane_cols.append(col)
        frame[f"{side}_rax_lanes_down"] = (frame[lane_cols] >= 4).sum(axis=1).astype("float64")
        frame.loc[frame["building_state"].isna(), f"{side}_rax_lanes_down"] = np.nan

    frame["rax_lane_advantage"] = frame["dire_rax_lanes_down"] - frame["radiant_rax_lanes_down"]
    frame = frame.sort_values(["match_id", "label_market_bucket", "received_at_ns", "side"]).reset_index(drop=True)
    frame = add_time_delta(frame, "nw_lead_clean", 100, "nw_change_100s")
    frame = add_time_delta(frame, "nw_lead_clean", 300, "nw_change_300s")
    frame = add_time_delta(frame, "total_kills", 100, "kills_change_100s")
    return frame


def add_side_features(rows: pd.DataFrame, *, min_game_time_sec: int = RESEARCH_MIN_GAME_TIME_SEC) -> pd.DataFrame:
    frame = add_base_state_features(rows)
    side_is_radiant = frame["side_is_radiant"].map(_bool_or_none)
    sign = np.where(side_is_radiant == True, 1.0, np.where(side_is_radiant == False, -1.0, np.nan))  # noqa: E712
    frame["book_age_s"] = frame["book_age_ms"] / 1000.0 if "book_age_ms" in frame.columns else np.nan
    frame["side_nw"] = sign * frame["nw_lead_clean"]
    frame["side_score"] = sign * frame["score_diff"]
    frame["side_tower"] = sign * frame["tower_advantage"]
    frame["side_rax"] = sign * frame["rax_lane_advantage"]
    frame["side_mom_100"] = sign * frame["nw_change_100s"]
    frame["side_mom_300"] = sign * frame["nw_change_300s"]
    frame["side_kill_mom"] = sign * frame["kills_change_100s"]
    if "seconds_since_state_change" not in frame.columns:
        frame["seconds_since_state_change"] = np.nan
    if frame["seconds_since_state_change"].isna().all():
        frame["seconds_since_state_change"] = 0.0

    frame["structure_score"] = frame["side_tower"].fillna(0) + 2 * frame["side_rax"].fillna(0)
    frame["state_score"] = (
        0.00012 * frame["side_nw"].clip(-30000, 30000)
        + 0.08 * frame["side_score"].clip(-25, 25)
        + 0.00006 * frame["side_mom_100"].fillna(0).clip(-15000, 15000)
        + 0.18 * frame["side_tower"].fillna(0).clip(-8, 8)
        + 0.45 * frame["side_rax"].fillna(0).clip(-3, 3)
    )
    frame["state_prob_proxy"] = 1 / (1 + np.exp(-frame["state_score"]))
    frame["state_edge_proxy"] = frame["state_prob_proxy"] - frame["book_best_ask"]
    frame["nw_price_gap"] = frame["side_nw"] / 1000.0 - 10 * (frame["book_best_ask"] - 0.5)
    frame["scoreboard_lag"] = (frame["side_nw"] >= 3000) & (frame["side_score"] <= 3)
    frame["momentum_lag"] = (frame["side_mom_100"] >= 3000) & (frame["side_nw"] <= 10000)
    frame["structure_confirms"] = (frame["side_tower"].fillna(0) >= 1) | (frame["side_rax"].fillna(0) >= 1)
    frame["fresh"] = frame["book_age_s"] <= 60
    frame["sane_ask"] = frame["book_best_ask"].between(0.05, 0.95)
    frame["liquid"] = frame["book_ask_size"] >= 25
    frame["tradable_research"] = (
        frame["sane_ask"]
        & frame["book_best_bid"].notna()
        & (frame["book_age_ms"] <= 60_000)
        & frame["liquid"]
        & (frame["game_time_sec"] >= min_game_time_sec)
    )
    return frame


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
