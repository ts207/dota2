from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from .strategy_contract import PAPER_DECISION_SPECS


@dataclass(frozen=True)
class ExposureLimit:
    strategy_name: str
    max_entries_per_map: int = 1
    min_seconds_between_entries: int = 300
    max_shares_per_entry: float = 1.0
    max_total_shares_per_map: float = 3.0
    max_total_notional_per_map: float = 100.0
    allow_add_to_winner: bool = False
    block_opposite_side_strategy: bool = True
    block_opposite_side_portfolio: bool = True
    exposure_limit_version: str = "v2"

def canonical_game_number(val: Any) -> str:
    if pd.isna(val) or val == "":
        return "MAPEQUIV"
    try:
        f = float(val)
        if f.is_integer():
            return str(int(f))
        return str(f)
    except (ValueError, TypeError):
        s = str(val).strip()
        if not s or s == "nan":
            return "MAPEQUIV"
        return s

def canonical_map_exposure_id(row: Mapping[str, Any]) -> str:
    match = str(row.get("match_id", ""))
    game = canonical_game_number(row.get("current_game_number"))
    return f"{match}::{game}"

def _generate_default_limits() -> dict[str, ExposureLimit]:
    limits = {}
    for spec in PAPER_DECISION_SPECS:
        strat = spec.strategy_name
        group = getattr(spec, "candidate_group", "")
        if group == "control":
            # No execution for control group
            limits[strat] = ExposureLimit(strategy_name=strat, max_entries_per_map=0)
        elif group in ("primary", "gettoplive_candidate"):
            limits[strat] = ExposureLimit(strategy_name=strat, max_entries_per_map=1, block_opposite_side_portfolio=True)
        elif group == "benchmark":
            limits[strat] = ExposureLimit(strategy_name=strat, max_entries_per_map=1, block_opposite_side_portfolio=False)
        else:
            limits[strat] = ExposureLimit(strategy_name=strat, max_entries_per_map=1)
    return limits

DEFAULT_LIMITS = _generate_default_limits()


class ExposureManager:
    def __init__(self, limits: dict[str, ExposureLimit] | None = None):
        self.limits = limits or DEFAULT_LIMITS
        self.positions_by_map: dict[str, list[dict[str, Any]]] = {}
        
    def load_state(self, existing_positions: pd.DataFrame) -> None:
        if existing_positions.empty:
            return
        # Load state into self.positions_by_map to safely resume append
        df = existing_positions.sort_values("entry_received_at_ns")
        for row in df.to_dict(orient="records"):
            if not row.get("blocked_reason"):
                map_id = row.get("map_exposure_id")
                if map_id:
                    if map_id not in self.positions_by_map:
                        self.positions_by_map[map_id] = []
                    self.positions_by_map[map_id].append(row)

    def process_decisions(self, decisions: pd.DataFrame) -> pd.DataFrame:
        if decisions.empty:
            return pd.DataFrame()
            
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
            
            if not pos.get("blocked_reason"):
                map_id = pos["map_exposure_id"]
                if map_id not in self.positions_by_map:
                    self.positions_by_map[map_id] = []
                self.positions_by_map[map_id].append(pos)
                
        return pd.DataFrame(positions)

    def _evaluate_decision(self, row: dict[str, Any]) -> dict[str, Any]:
        strategy = row.get("strategy_name", "")
        limit = self.limits.get(strategy)
        
        map_id = canonical_map_exposure_id(row)
            
        existing = self.positions_by_map.get(map_id, [])
        strat_existing = [p for p in existing if p["strategy_name"] == strategy]
        
        shares = limit.max_shares_per_entry if limit else 1.0
        ask = float(row.get("ask", 0.0)) if row.get("ask") is not None else 0.0
        notional = shares * ask
        
        # Calculate SHA1 for deterministic position_id
        dec_id = str(row.get("decision_id", ""))
        lim_ver = limit.exposure_limit_version if limit else "v1"
        key_str = f"{dec_id}|{strategy}|{map_id}|{lim_ver}"
        pos_id = hashlib.sha1(key_str.encode("utf-8")).hexdigest()
        
        pnl_per_share_2c = row.get("pnl_slip_2c")
        position_pnl_2c = (shares * pnl_per_share_2c) if pnl_per_share_2c is not None else None
        
        pos = {
            "position_id": pos_id,
            "decision_id": dec_id,
            "strategy_name": strategy,
            "model_name": row.get("model_name"),
            "candidate_group": row.get("candidate_group"),
            "match_id": row.get("match_id"),
            "current_game_number": row.get("current_game_number"),
            "map_exposure_id": map_id,
            "token_id": row.get("token_id"),
            "side": row.get("side"),
            "entry_received_at_ns": row.get("received_at_ns"),
            "entry_received_at_utc": row.get("received_at_utc"),
            "entry_ask": ask,
            "shares": shares,
            "notional": notional,
            "exposure_count_for_map": len(strat_existing) + 1,
            "blocked_reason": None,
            "settled_win": row.get("settled_win"),
            "pnl_per_share_2c": pnl_per_share_2c,
            "position_pnl_2c": position_pnl_2c,
            "edge": row.get("edge"),
            "fair_prob": row.get("fair_prob"),
            "market_prob": row.get("market_prob"),
            "entry_threshold": row.get("entry_threshold"),
            "book_ask_size": row.get("book_ask_size"),
            "book_spread": row.get("book_spread"),
            "book_age_ms": row.get("book_age_ms"),
            "game_time_sec": row.get("game_time_sec"),
            "side_mom_100": row.get("side_mom_100"),
            "side_mom_300": row.get("side_mom_300"),
            "side_kill_mom": row.get("side_kill_mom"),
        }
        
        if not limit:
            pos["blocked_reason"] = "no_limit_configured"
            pos["shares"] = 0.0
            pos["notional"] = 0.0
            pos["position_pnl_2c"] = 0.0
            return pos

        if limit.max_entries_per_map == 0:
            pos["blocked_reason"] = "max_entries_per_map_zero"
            pos["shares"] = 0.0
            pos["notional"] = 0.0
            pos["position_pnl_2c"] = 0.0
            return pos

        if limit.block_opposite_side_strategy:
            for p in strat_existing:
                if p["side"] != pos["side"]:
                    pos["blocked_reason"] = "opposite_side_already_held_strategy"
                    pos["shares"] = 0.0
                    pos["notional"] = 0.0
                    pos["position_pnl_2c"] = 0.0
                    return pos

        if limit.block_opposite_side_portfolio:
            for p in existing:
                if not p.get("blocked_reason") and p["side"] != pos["side"]:
                    pos["blocked_reason"] = "opposite_side_already_held_portfolio"
                    pos["shares"] = 0.0
                    pos["notional"] = 0.0
                    pos["position_pnl_2c"] = 0.0
                    return pos

        if len(strat_existing) >= limit.max_entries_per_map:
            pos["blocked_reason"] = f"max_entries_reached ({limit.max_entries_per_map})"
            pos["shares"] = 0.0
            pos["notional"] = 0.0
            pos["position_pnl_2c"] = 0.0
            return pos

        if strat_existing:
            last_entry_time = max(p.get("entry_received_at_ns", 0) or 0 for p in strat_existing)
            current_time = pos.get("entry_received_at_ns", 0) or 0
            if current_time is not None and last_entry_time is not None:
                seconds_diff = (int(current_time) - int(last_entry_time)) / 1e9
                if seconds_diff < limit.min_seconds_between_entries:
                    pos["blocked_reason"] = f"cooldown_active ({seconds_diff:.1f}s < {limit.min_seconds_between_entries}s)"
                    pos["shares"] = 0.0
                    pos["notional"] = 0.0
                    pos["position_pnl_2c"] = 0.0
                    return pos
                    
            total_shares = sum(p["shares"] for p in strat_existing)
            if total_shares + shares > limit.max_total_shares_per_map:
                pos["blocked_reason"] = f"max_shares_reached ({total_shares + shares} > {limit.max_total_shares_per_map})"
                pos["shares"] = 0.0
                pos["notional"] = 0.0
                pos["position_pnl_2c"] = 0.0
                return pos
                
            total_notional = sum(p["notional"] for p in strat_existing)
            if total_notional + notional > limit.max_total_notional_per_map:
                pos["blocked_reason"] = f"max_notional_reached ({total_notional + notional} > {limit.max_total_notional_per_map})"
                pos["shares"] = 0.0
                pos["notional"] = 0.0
                pos["position_pnl_2c"] = 0.0
                return pos

        return pos
