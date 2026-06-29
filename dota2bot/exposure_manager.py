from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ExposureLimit:
    strategy_name: str
    max_entries_per_map: int = 1
    min_seconds_between_entries: int = 300
    max_shares_per_entry: float = 1.0
    max_total_shares_per_map: float = 3.0
    max_total_notional_per_map: float = 100.0
    allow_add_to_winner: bool = False
    block_opposite_side: bool = True


DEFAULT_LIMITS = {
    "paper_winprob_logistic_evfilter_v1": ExposureLimit(strategy_name="paper_winprob_logistic_evfilter_v1"),
    "paper_gettoplive_kill_mom_favorite_hold_v1": ExposureLimit(strategy_name="paper_gettoplive_kill_mom_favorite_hold_v1"),
    "paper_market_gettoplive_logistic_v1": ExposureLimit(strategy_name="paper_market_gettoplive_logistic_v1"),
    "paper_market_only_logistic_v1": ExposureLimit(strategy_name="paper_market_only_logistic_v1"),
}


class ExposureManager:
    def __init__(self, limits: dict[str, ExposureLimit] | None = None):
        self.limits = limits or DEFAULT_LIMITS
        # State tracking: canonical_exposure_id -> list of position dicts
        self.positions_by_map: dict[str, list[dict[str, Any]]] = {}

    def process_decisions(self, decisions: pd.DataFrame) -> pd.DataFrame:
        """Process raw signal decisions into allowed positions."""
        if decisions.empty:
            return pd.DataFrame()
            
        # Ensure we process chronologically
        if "received_at_ns" in decisions.columns:
            df = decisions.sort_values("received_at_ns").copy()
        else:
            df = decisions.copy()
            
        positions = []
        for row in df.to_dict(orient="records"):
            if not row.get("signal"):
                continue
                
            pos = self._evaluate_decision(row)
            positions.append(pos)
            
            # Update state if allowed
            if not pos.get("blocked_reason"):
                map_id = pos["canonical_exposure_id"]
                if map_id not in self.positions_by_map:
                    self.positions_by_map[map_id] = []
                self.positions_by_map[map_id].append(pos)
                
        return pd.DataFrame(positions)

    def _evaluate_decision(self, row: dict[str, Any]) -> dict[str, Any]:
        strategy = row.get("strategy_name", "")
        limit = self.limits.get(strategy)
        
        map_id = row.get("canonical_exposure_id")
        if not map_id:
            # Fallback if canonical_exposure_id is missing
            match = row.get("match_id", "")
            game = row.get("current_game_number", 1)
            map_id = f"{match}_{game}"
            
        existing = self.positions_by_map.get(map_id, [])
        strat_existing = [p for p in existing if p["strategy_name"] == strategy]
        
        shares = limit.max_shares_per_entry if limit else 1.0
        ask = float(row.get("ask", 0.0)) if row.get("ask") is not None else 0.0
        notional = shares * ask
        
        pos = {
            "position_id": str(uuid.uuid4()),
            "decision_id": row.get("decision_id"),
            "strategy_name": strategy,
            "model_name": row.get("model_name"),
            "candidate_group": row.get("candidate_group"),
            "match_id": row.get("match_id"),
            "current_game_number": row.get("current_game_number"),
            "canonical_exposure_id": map_id,
            "token_id": row.get("token_id"),
            "side": row.get("side"),
            "entry_received_at_ns": row.get("received_at_ns"),
            "entry_ask": row.get("ask"),
            "shares": shares,
            "notional": notional,
            "exposure_count_for_map": len(strat_existing) + 1,
            "blocked_reason": None,
            "settled_win": row.get("settled_win"),
            "pnl_2c": row.get("pnl_slip_2c"),
        }
        
        if not limit:
            pos["blocked_reason"] = "no_limit_configured"
            pos["shares"] = 0.0
            pos["notional"] = 0.0
            return pos

        if len(strat_existing) >= limit.max_entries_per_map:
            pos["blocked_reason"] = f"max_entries_reached ({limit.max_entries_per_map})"
            pos["shares"] = 0.0
            pos["notional"] = 0.0
            return pos
            
        if limit.block_opposite_side:
            for p in strat_existing:
                if p["side"] != pos["side"]:
                    pos["blocked_reason"] = "opposite_side_already_held"
                    pos["shares"] = 0.0
                    pos["notional"] = 0.0
                    return pos

        if strat_existing:
            last_entry_time = max(p["entry_received_at_ns"] for p in strat_existing)
            current_time = pos["entry_received_at_ns"]
            if current_time is not None and last_entry_time is not None:
                seconds_diff = (int(current_time) - int(last_entry_time)) / 1e9
                if seconds_diff < limit.min_seconds_between_entries:
                    pos["blocked_reason"] = f"cooldown_active ({seconds_diff:.1f}s < {limit.min_seconds_between_entries}s)"
                    pos["shares"] = 0.0
                    pos["notional"] = 0.0
                    return pos
                    
            total_shares = sum(p["shares"] for p in strat_existing)
            if total_shares + shares > limit.max_total_shares_per_map:
                pos["blocked_reason"] = f"max_shares_reached ({total_shares + shares} > {limit.max_total_shares_per_map})"
                pos["shares"] = 0.0
                pos["notional"] = 0.0
                return pos
                
            total_notional = sum(p["notional"] for p in strat_existing)
            if total_notional + notional > limit.max_total_notional_per_map:
                pos["blocked_reason"] = f"max_notional_reached ({total_notional + notional} > {limit.max_total_notional_per_map})"
                pos["shares"] = 0.0
                pos["notional"] = 0.0
                return pos

        return pos
