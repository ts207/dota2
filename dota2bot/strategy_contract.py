"""Single source of truth for active paper strategy definitions."""

from __future__ import annotations

from dataclasses import dataclass


ACTIVE_MARKET_ANCHOR_MODEL_VERSION = "winprob_evfilter_paper_v1_mapequiv_ask20_50_e05_gt900_mom100nonneg"
ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE = "live_executable"
ACTIVE_MARKET_EQUIVALENT_SCOPES = ("map_winner_explicit", "series_decider_equivalent")
ACTIVE_PAPER_DECISIONS_NAME = "paper_validation_decisions_winprob_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg"
ACTIVE_SETTLED_PAPER_DECISIONS_NAME = "paper_validation_settled_decisions_winprob_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg"


@dataclass(frozen=True)
class StrategySpec:
    model_name: str
    strategy_name: str
    candidate_group: str
    entry_threshold: float
    score_kind: str = "win_prob"
    market_scopes: tuple[str, ...] = ()
    min_ask: float | None = None
    max_ask: float | None = None
    min_game_time_sec: int | None = None
    min_side_mom_100: float | None = None
    min_side_kill_mom: float | None = None
    max_source_update_age_sec: float | None = None
    deterministic_rule: bool = False


ACTIVE_MARKET_ANCHOR_SPECS = (
    StrategySpec(
        model_name="winprob_logistic_evfilter",
        strategy_name="paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg",
        candidate_group="primary",
        entry_threshold=0.05,
        score_kind="win_prob_2c",
        market_scopes=ACTIVE_MARKET_EQUIVALENT_SCOPES,
        min_ask=0.20,
        max_ask=0.50,
        min_game_time_sec=900,
        min_side_mom_100=0.0,
    ),
)


BENCHMARK_MARKET_ANCHOR_SPECS = (
    StrategySpec(
        model_name="market_gettoplive_logistic",
        strategy_name="paper_market_gettoplive_mapequiv_ask20_50",
        candidate_group="benchmark",
        entry_threshold=0.12,
        score_kind="win_prob",
        market_scopes=ACTIVE_MARKET_EQUIVALENT_SCOPES,
        min_ask=0.20,
        max_ask=0.50,
    ),
)


CONTROL_MARKET_ANCHOR_SPECS = (
    StrategySpec(
        model_name="market_only_logistic",
        strategy_name="paper_market_only",
        candidate_group="control",
        entry_threshold=0.10,
        score_kind="win_prob",
        market_scopes=ACTIVE_MARKET_EQUIVALENT_SCOPES,
        min_ask=0.20,
        max_ask=0.50,
    ),
)


PAPER_RULE_SPECS = (
    StrategySpec(
        model_name="gettoplive_kill_mom_favorite_hold_rule",
        strategy_name="paper_gettoplive_kill_mom_favorite_hold_v1",
        candidate_group="gettoplive_candidate",
        entry_threshold=1.0,
        score_kind="rule_binary",
        market_scopes=ACTIVE_MARKET_EQUIVALENT_SCOPES,
        min_ask=0.50,
        max_ask=0.80,
        min_side_kill_mom=1.0,
        max_source_update_age_sec=5.0,
        deterministic_rule=True,
    ),
    StrategySpec(
        model_name="gettoplive_kill_mom_favorite_hold_rule",
        strategy_name="paper_gettoplive_kill_mom_favorite_hold_v2",
        candidate_group="gettoplive_candidate",
        entry_threshold=1.0,
        score_kind="rule_binary",
        market_scopes=ACTIVE_MARKET_EQUIVALENT_SCOPES,
        min_ask=0.50,
        max_ask=0.80,
        min_side_kill_mom=1.0,
        min_side_mom_100=0.0,
        max_source_update_age_sec=5.0,
        deterministic_rule=True,
    ),
    StrategySpec(
        model_name="gettoplive_kill_mom_favorite_hold_rule",
        strategy_name="paper_gettoplive_kill_mom_favorite_ask65_gt600_shadow_v1",
        candidate_group="gettoplive_candidate",
        entry_threshold=1.0,
        score_kind="rule_binary",
        market_scopes=ACTIVE_MARKET_EQUIVALENT_SCOPES,
        min_ask=0.50,
        max_ask=0.65,
        min_side_kill_mom=1.0,
        min_game_time_sec=600,
        max_source_update_age_sec=10.0,
        deterministic_rule=True,
    ),
    StrategySpec(
        model_name="gettoplive_kill_mom_benchmark_confirm_rule",
        strategy_name="paper_gettoplive_kill_mom_benchmark_confirm_shadow_v1",
        candidate_group="gettoplive_candidate",
        entry_threshold=1.0,
        score_kind="rule_binary",
        market_scopes=ACTIVE_MARKET_EQUIVALENT_SCOPES,
        min_ask=0.50,
        max_ask=0.80,
        min_side_kill_mom=1.0,
        max_source_update_age_sec=5.0,
        deterministic_rule=True,
    ),
)


PAPER_MARKET_ANCHOR_SPECS = (
    *ACTIVE_MARKET_ANCHOR_SPECS,
    *BENCHMARK_MARKET_ANCHOR_SPECS,
    *CONTROL_MARKET_ANCHOR_SPECS,
)


PAPER_DECISION_SPECS = (
    *PAPER_MARKET_ANCHOR_SPECS,
    *PAPER_RULE_SPECS,
)


ACTIVE_MARKET_ANCHOR_MODEL_NAMES = tuple(spec.model_name for spec in ACTIVE_MARKET_ANCHOR_SPECS)
