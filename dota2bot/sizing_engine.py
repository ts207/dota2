from collections import defaultdict
import pandas as pd
import numpy as np

def _clamp(val, min_val, max_val):
    return max(min_val, min(val, max_val))

def simulate_sizing(
    positions: pd.DataFrame,
    sizing: str,
    bankroll: float = 1000.0,
    max_shares: float = 25.0,
    max_position_notional: float = 100.0,
    max_map_notional: float = 200.0,
) -> pd.DataFrame:
    if positions.empty:
        return positions.copy()
    
    df = positions.copy()

    # Calculate liquidity cap
    if "book_ask_size" not in df.columns:
        df["book_ask_size"] = np.nan
    df["book_ask_size"] = pd.to_numeric(df["book_ask_size"], errors="coerce")
    df["liquidity_unknown"] = df["book_ask_size"].isna()
    df["liquidity_cap"] = np.where(
        df["liquidity_unknown"],
        max_shares,
        df["book_ask_size"] * 0.25
    )

    if "source_update_age_sec" not in df.columns:
        if "book_age_ms" in df.columns:
            df["source_update_age_sec"] = pd.to_numeric(df["book_age_ms"], errors="coerce") / 1000.0
        else:
            df["source_update_age_sec"] = np.nan

    map_used_notional = defaultdict(float)
    sim_shares_list = []
    liq_capped_list = []

    for idx, row in df.iterrows():
        entry_ask = float(row.get("entry_ask", 0.0))
        if entry_ask <= 0:
            entry_ask = 1.0
            
        liq_cap = float(row["liquidity_cap"])
        edge = float(row.get("edge", 0.0))
        fair_prob = float(row.get("fair_prob", 0.0))
        map_id = row.get("map_exposure_id", "unknown")
        side_kill_mom = float(row.get("side_kill_mom", 0.0))
        if pd.isna(side_kill_mom): side_kill_mom = 0.0
        source_age = float(row.get("source_update_age_sec", 0.0))
        if pd.isna(source_age): source_age = 5.0
        group = row.get("candidate_group", "")

        desired_shares = 0.0

        if sizing == "flat_1":
            desired_shares = 1.0
        elif sizing == "flat_5":
            desired_shares = 5.0
        elif sizing == "flat_25_liquidity_unchecked":
            desired_shares = min(25.0, liq_cap)
        elif sizing == "edge_scaled" or sizing == "edge_scaled_0.5pct_bankroll_cap25":
            base_notional = bankroll * 0.005
            multiplier = _clamp(edge / 0.10, 0.25, 2.0) if not pd.isna(edge) else 0.25
            target_notional = base_notional * multiplier
            desired_shares = target_notional / entry_ask
        elif sizing == "kill_mom_scaled" or sizing == "kill_mom_scaled_0.5pct_cap25":
            base_notional = bankroll * 0.005
            kill_multiplier = _clamp(side_kill_mom / 3.0, 0.5, 2.0)
            age_multiplier = _clamp((5.0 - source_age) / 5.0, 0.25, 1.0)
            target_notional = base_notional * kill_multiplier * age_multiplier
            desired_shares = target_notional / entry_ask
        elif sizing == "kelly_05_cap25":
            effective_price = entry_ask + 0.02
            kelly_fraction = max(0.0, (fair_prob - effective_price) / (1 - effective_price) if effective_price < 1 and not pd.isna(fair_prob) else 0.0)
            target_notional = bankroll * 0.05 * kelly_fraction
            desired_shares = target_notional / entry_ask
        elif sizing == "kelly_10_cap25":
            effective_price = entry_ask + 0.02
            kelly_fraction = max(0.0, (fair_prob - effective_price) / (1 - effective_price) if effective_price < 1 and not pd.isna(fair_prob) else 0.0)
            target_notional = bankroll * 0.10 * kelly_fraction
            desired_shares = target_notional / entry_ask
        elif sizing == "group_specific_default":
            if group == "primary":
                base_notional = bankroll * 0.005
                multiplier = _clamp(edge / 0.10, 0.25, 2.0) if not pd.isna(edge) else 0.25
                target_notional = base_notional * multiplier
                desired_shares = target_notional / entry_ask
            elif group == "gettoplive_candidate":
                base_notional = bankroll * 0.005
                kill_multiplier = _clamp(side_kill_mom / 3.0, 0.5, 2.0)
                age_multiplier = _clamp((5.0 - source_age) / 5.0, 0.25, 1.0)
                target_notional = base_notional * kill_multiplier * age_multiplier
                desired_shares = target_notional / entry_ask
            else:
                desired_shares = 1.0
        elif sizing == "conservative_group_default":
            if group == "primary":
                desired_shares = 1.0
            elif group == "gettoplive_candidate":
                base_notional = bankroll * 0.005
                kill_multiplier = _clamp(side_kill_mom / 3.0, 0.5, 2.0)
                age_multiplier = _clamp((5.0 - source_age) / 5.0, 0.25, 1.0)
                target_notional = base_notional * kill_multiplier * age_multiplier
                desired_shares = target_notional / entry_ask
            else:
                desired_shares = 1.0
        else:
            desired_shares = 1.0

        # Apply caps
        capped_shares = min(desired_shares, max_shares)
        capped_shares = min(capped_shares, max_position_notional / entry_ask)
        
        # Apply liquidity cap to non-flat_1/5
        if sizing not in ["flat_1", "flat_5"]:
            capped_shares = min(capped_shares, liq_cap)

        desired_notional = capped_shares * entry_ask
        remaining_map_notional = max_map_notional - map_used_notional[map_id]
        final_notional = min(desired_notional, remaining_map_notional)
        
        final_shares = final_notional / entry_ask
        map_used_notional[map_id] += final_notional
        
        sim_shares_list.append(final_shares)
        
        capped_by_liq = (capped_shares == liq_cap and desired_shares > liq_cap)
        liq_capped_list.append(capped_by_liq)

    df["sim_shares"] = sim_shares_list
    df["liq_capped"] = liq_capped_list
    
    df["sim_stake"] = df["sim_shares"] * pd.to_numeric(df["entry_ask"], errors="coerce").fillna(0.0)
    df["sim_pnl_2c"] = df["sim_shares"] * pd.to_numeric(df.get("pnl_per_share_2c", 0.0), errors="coerce").fillna(0.0)

    return df
