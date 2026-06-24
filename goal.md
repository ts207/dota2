# Executable Backtest Research Plan

## Current Directive

Use only the executable backtest dataset for strategy and model validation now.

Live logged data is for later forward validation. It is not evidence for the current strategy proof.

## Active Data Source

All current strategy/model research must read from:

```text
datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet
```

Do not consume these datasets for the current proof:

```text
logs/live_side_snapshots
logs/live_settled_side_snapshots
logs/live_book_ticks
logs/live_game_snapshots
logs/strategy_decisions
```

Live logging, live settlement, and live audit code may remain in the repo, but they are outside the active strategy-validation loop.

## Current Backtest Goal

Prove whether GetTopLive game-state features add tradable residual edge after controlling for Polymarket executable ask price, using only settled executable backtest rows.

The active proof must answer:

```text
1. Is the market broadly calibrated by executable ask bucket?
2. At the same ask price, do GetTopLive state buckets separate winners from losers?
3. Does a market-anchored model beat a market-only model in chronological walk-forward?
4. Does the edge survive 1c and 2c slippage?
5. Is there positive short-horizon executable future-bid CLV?
6. Is PnL concentrated in one match, market bucket, or league?
```

## Current Backtest Verdict

The current executable-backtest result is:

```text
Settlement residual test: PASS
Short-horizon future-bid CLV test: FAIL
```

Current model comparison:

```text
market_gettoplive_logistic beats market_only_logistic after 1c and 2c slippage
market_momentum_logistic is the best current ablation by 1c-slippage PnL
all positive-slippage model rows are research_only because Wilson lower bounds do not clear breakeven ask
```

This is not deployment approval. The current evidence supports hold-to-settlement residual research only, not a short-horizon scalp and not live trading.

## Completed Work

The repo already has:

```text
dota2bot/side_features.py
validate_pattern_strategies.py using shared side features
market_residual_gettoplive_analysis.py
market_residual_gettoplive_report.md
price_bucket_state_residuals.csv
market_anchor_model_predictions.csv
market_anchor_model_trades.csv
gettoplive_clv_event_study.csv
market_anchor_model_summary.csv
```

The residual analysis already uses:

```text
minimum game time: 600s
chronological development / lockbox split
walk-forward threshold selection
first qualifying trade dedupe
1c and 2c slippage accounting
future executable bid/mid CLV
residual bucket robustness gates
concentration tables by match, market bucket, and league
Wilson confidence intervals for small trade samples
```

The current test suite passes.

## Active Next Step

Keep the work backtest-only and add sparse transition research.

The current best thesis is:

```text
Market price is the base.
Static Dota state is mostly priced.
The possible residual edge is in sparse GetTopLive transitions:
- recent net-worth transition
- recent kill transition
- score/net-worth asynchronous update lag
- market underreaction before full repricing
```

Do not model fights as long episodes. GetTopLive snapshots can be sparse and may only expose one or two transitions.

## Backtest Implementation Order

1. Add `dota2bot/transition_features.py`.

   It should compute unique game-state transitions per match without double-counting side/token rows:

   ```text
   transition_dt_sec
   radiant_lead_delta
   score_diff_delta
   total_kill_delta
   radiant_score_delta
   dire_score_delta
   building_state_changed
   side_transition_nw_delta
   side_transition_score_delta
   side_transition_kill_delta
   side_transition_nw_per_sec
   side_transition_kill_per_sec
   side_transition_building_changed
   nw_changed
   score_changed
   building_changed
   score_changed_without_nw
   nw_changed_without_score
   score_nw_changed_together
   score_leads_nw_sec
   nw_leads_score_sec
   score_nw_lag_type
   transition_signal_type
   ```

2. Add transition feature tests.

   Required scenarios:

   ```text
   score-only change detected
   NW-only change detected
   score then NW catch-up detected
   sparse two-snapshot fight produces transition features
   duplicate side/token rows do not double-count game transitions
   first row per match has no fake transition
   ```

3. Extend `market_residual_gettoplive_analysis.py`.

   Keep current baselines:

   ```text
   market_only_logistic
   market_momentum_logistic
   market_gettoplive_logistic
   ```

   Add ablations:

   ```text
   market_kill_momentum_logistic
   market_nw_kill_momentum_logistic
   market_transition_nw_logistic
   market_transition_kill_logistic
   market_transition_nw_kill_logistic
   market_transition_catchup_logistic
   ```

4. Add transition residual bucket tables.

   Extend the residual CSV/report with:

   ```text
   ask_bucket + side_kill_mom_bucket
   ask_bucket + side_transition_kill_delta_bucket
   ask_bucket + side_transition_nw_delta_bucket
   ask_bucket + score_nw_lag_type
   ask_bucket + transition_signal_type
   ```

   A residual bucket is not tradable unless it has:

   ```text
   rows >= 25
   matches >= 10
   avg_pnl > 0
   win_rate_minus_avg_ask > 0
   ```

5. Add a transition entry-timing event study.

   Write:

   ```text
   transition_entry_event_study.csv
   ```

   Compare:

   ```text
   first_score_change
   first_nw_change
   score_nw_same_snapshot
   score_then_nw_catchup
   nw_then_score_catchup
   confirmed_transition
   post_transition_close
   ```

   For each timing, compute:

   ```text
   trades
   matches
   avg_ask
   settlement_win_rate
   raw_pnl
   pnl_1c
   pnl_2c
   future_bid_clv_15s
   future_bid_clv_30s
   future_bid_clv_60s
   future_bid_clv_120s
   positive_bid_clv_rate
   ```

6. Regenerate all executable-backtest artifacts and rerun the full test suite.

## Candidate Promotion Rules

A model can move from `research_only` to `candidate` only if it satisfies all of these:

```text
1. Beats market_only_logistic after 1c and 2c slippage.
2. Positive walk-forward 1c and 2c PnL.
3. Positive lockbox 1c and 2c PnL.
4. Trades in at least 4 of 5 walk-forward folds.
5. At least 3 of 5 folds are positive after 1c slippage.
6. Wilson lower win-rate bound is above average executable ask.
7. PnL is not dominated by one match.
8. PnL is not dominated by one market bucket.
9. PnL is not dominated by one league.
10. Model inputs use only entry-time fields.
11. Future bid/mid CLV labels are never included as model features.
```

If CLV remains negative but settlement PnL passes, the strategy remains hold-to-settlement only.

## What Not To Do Now

Do not mine live logs for alpha.

Do not use live-settled rows as backtest evidence.

Do not implement or run:

```text
paper-log
settle-decisions
report-decisions
runtime paper logger
live decision loop
live-money trading
```

Do not deploy a model because lockbox PnL is positive on a small number of trades.

Do not count repeated snapshots as independent evidence.

Do not treat positive settlement PnL as proof of positive short-horizon CLV.

## Later Phase: Forward Paper Validation

This phase starts only after an executable-backtest candidate is frozen.

Later work will include:

```text
save frozen model artifacts
expand DECISION_COLUMNS
add paper-log CLI
add settle-decisions CLI
add report-decisions CLI
collect forward paper decisions from live_side_snapshots
settle paper decisions
compare forward paper performance to backtest expectations
```

The forward paper phase must use one frozen model/config for the whole validation period. If features, thresholds, model, or eligibility rules change, reset the validation clock.

Forward paper pass criteria:

```text
at least 100 settled paper signals
at least 30 unique matches
positive after 1c and 2c slippage
not dominated by one match
not dominated by one market bucket
not dominated by one league
no unresolved data-quality bugs
```

No live-money trading is in scope until forward paper validation passes.

## Acceptance Criteria

The active backtest phase is done when:

```text
transition features exist and are tested
transition/kill ablations are included in the market residual analysis
transition residual tables are generated
transition entry-timing event study is generated
market_anchor_model_summary.csv includes every model/stage verdict
all artifacts are regenerated from the executable backtest dataset only
full pytest suite passes
git diff --check passes
the final verdict is candidate, research_only, or reject with explicit reasons
```

## Agent Prompt

```text
Work in /home/tstuv/dota2.

Use only:
datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet

Do not use live logs for current strategy/model proof.
Do not implement paper-log, settle-decisions, report-decisions, or live decision loops yet.

Implement sparse transition-feature research on top of the existing market-residual framework.
Keep market_momentum_logistic as the benchmark.
Promote nothing beyond research_only unless it passes the candidate gates above.
After changes, regenerate executable-backtest artifacts, run pytest, and run git diff --check.
```
