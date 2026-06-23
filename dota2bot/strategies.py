"""Small strategy probes for replay and research."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Decision:
    signal: bool
    reason: str
    score: float


class LeaderMidgameProbe:
    """A conservative pattern probe, not a production trading rule."""

    name = "leader_midgame_probe"

    def __init__(
        self,
        min_game_time_sec: int = 900,
        max_game_time_sec: int = 2200,
        min_abs_net_worth_lead: float = 6000,
        min_abs_score_margin: float = 3,
    ):
        self.min_game_time_sec = min_game_time_sec
        self.max_game_time_sec = max_game_time_sec
        self.min_abs_net_worth_lead = min_abs_net_worth_lead
        self.min_abs_score_margin = min_abs_score_margin

    def evaluate(self, row: dict[str, Any]) -> Decision:
        game_time = _num(row.get("game_time_sec"))
        radiant_lead = _num(row.get("radiant_lead") or row.get("net_worth_diff"))
        radiant_score = _num(row.get("radiant_score"))
        dire_score = _num(row.get("dire_score"))
        if game_time is None or radiant_lead is None:
            return Decision(False, "missing_state", 0.0)
        side_is_radiant = _bool_or_none(row.get("side_is_radiant"))
        if side_is_radiant is None:
            return Decision(False, "missing_side_mapping", 0.0)
        if not (self.min_game_time_sec <= game_time <= self.max_game_time_sec):
            return Decision(False, "outside_time_window", 0.0)

        side_lead = radiant_lead if side_is_radiant else -radiant_lead
        score_margin = None
        if radiant_score is not None and dire_score is not None:
            score_margin = (radiant_score - dire_score) if side_is_radiant else (dire_score - radiant_score)

        if side_lead < self.min_abs_net_worth_lead:
            return Decision(False, "side_not_leading_enough", float(side_lead))
        if score_margin is not None and score_margin < self.min_abs_score_margin:
            return Decision(False, "score_margin_too_small", float(side_lead))

        score = float(side_lead) + float(score_margin or 0) * 1000.0
        return Decision(True, "leader_midgame_state", score)


def decision_id(strategy_name: str, row: dict[str, Any]) -> str:
    raw = "|".join(
        [
            strategy_name,
            str(row.get("match_id")),
            str(row.get("token_id")),
            str(row.get("received_at_ns")),
        ]
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None
