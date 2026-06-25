"""Single source of truth for active paper strategy definitions."""

from __future__ import annotations

from dataclasses import dataclass


ACTIVE_MARKET_ANCHOR_MODEL_VERSION = "market_anchor_paper_v4_edge18_live_exec_benchmarks"
ACTIVE_MARKET_ANCHOR_ELIGIBILITY_MODE = "live_executable"


@dataclass(frozen=True)
class StrategySpec:
    model_name: str
    strategy_name: str
    candidate_group: str
    entry_threshold: float


ACTIVE_MARKET_ANCHOR_SPECS = (
    StrategySpec(
        model_name="market_nw_kill_momentum_logistic",
        strategy_name="paper_market_nw_kill_momentum",
        candidate_group="primary",
        entry_threshold=0.18,
    ),
)


BENCHMARK_MARKET_ANCHOR_SPECS = (
    StrategySpec(
        model_name="market_momentum_logistic",
        strategy_name="paper_market_momentum",
        candidate_group="benchmark",
        entry_threshold=0.12,
    ),
    StrategySpec(
        model_name="market_gettoplive_logistic",
        strategy_name="paper_market_gettoplive",
        candidate_group="full_state_benchmark",
        entry_threshold=0.10,
    ),
)


CONTROL_MARKET_ANCHOR_SPECS = (
    StrategySpec(
        model_name="market_only_logistic",
        strategy_name="paper_market_only",
        candidate_group="control",
        entry_threshold=0.10,
    ),
)


PAPER_MARKET_ANCHOR_SPECS = (
    *ACTIVE_MARKET_ANCHOR_SPECS,
    *BENCHMARK_MARKET_ANCHOR_SPECS,
    *CONTROL_MARKET_ANCHOR_SPECS,
)


ACTIVE_MARKET_ANCHOR_MODEL_NAMES = tuple(spec.model_name for spec in ACTIVE_MARKET_ANCHOR_SPECS)
