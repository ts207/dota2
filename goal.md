Current directive:

> Use only the executable backtest dataset for strategy/model validation now.
> Live logged data is for later forward validation, not for the current proof.

## Active Scope

The active research source is:

```text
datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet
```

Do not consume these live-log datasets for the current strategy proof:

```text
logs/live_side_snapshots
logs/live_settled_side_snapshots
logs/live_book_ticks
logs/live_game_snapshots
logs/strategy_decisions
```

Live logging, live settlement, and live audit code may remain in the repo, but they are not part of the active strategy-validation loop.

## Goal

Prove whether GetTopLive game-state features add tradable residual edge after controlling for Polymarket executable ask price, using only settled executable backtest rows.

The current proof must answer:

```text
1. Is the market broadly calibrated by ask bucket?
2. At the same ask price, do GetTopLive state buckets separate winners from losers?
3. Does a market-anchored model beat a market-only model in chronological walk-forward?
4. Does the edge survive 1c and 2c slippage?
5. Is there positive short-horizon executable future-bid CLV?
6. Is PnL concentrated in one match, bucket, or league?
```

## Already Implemented

The repo now has:

```text
dota2bot/side_features.py
validate_pattern_strategies.py using shared side features
market_residual_gettoplive_analysis.py
market_residual_gettoplive_report.md
price_bucket_state_residuals.csv
market_anchor_model_predictions.csv
market_anchor_model_trades.csv
gettoplive_clv_event_study.csv
```

The residual analysis uses:

```text
minimum game time: 600s
chronological development / lockbox split
walk-forward threshold selection
first qualifying trade dedupe
1c and 2c slippage accounting
future executable bid/mid CLV
residual bucket robustness gates
```

## Current Verdict

The current executable-backtest result is:

```text
Settlement residual test: PASS
Short-horizon future-bid CLV test: FAIL
```

Model comparison:

```text
market_gettoplive_logistic beats market_only_logistic after 1c and 2c slippage
market_momentum_logistic is the best current ablation by 1c-slippage PnL
all positive-slippage model rows are research_only because Wilson lower bounds do not clear breakeven ask
```

But this is still not deployment approval. The CLV result says the signal does not currently prove a short-horizon scalp. The only supported thesis is hold-to-settlement residual edge in the executable backtest.

## Active Build Order

### 1. Keep Research Backtest-Only

Every current strategy/model command must read from:

```text
datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet
```

Do not add or run:

```text
paper-log
settle-decisions
report-decisions
runtime paper logger
live decision loop
```

Those belong to a later phase after the backtest proof is stable.

### 2. Tighten Residual Analysis

Continue improving:

```text
market_residual_gettoplive_analysis.py
market_residual_gettoplive_report.md
price_bucket_state_residuals.csv
market_anchor_model_predictions.csv
market_anchor_model_trades.csv
gettoplive_clv_event_study.csv
```

Required properties:

```text
dedupe first trade per match / market bucket / model
settlement-aware PnL
1c and 2c slippage PnL
future executable bid CLV, not theoretical mid-only CLV
match-count gates on residual buckets
concentration tables by match, market bucket, and league
Wilson confidence intervals for small trade samples
```

### 3. Add A Compact Model Summary Artifact

Create a small CSV summary so the result is machine-readable without parsing the markdown report:

```text
market_anchor_model_summary.csv
```

It should include, per model/stage:

```text
stage
model_name
folds
pred_rows
auc
log_loss
brier
trade_trades
trade_win_rate
trade_avg_ask
trade_total_pnl
trade_total_pnl_slip_1c
trade_total_pnl_slip_2c
folds_with_trades
folds_positive_1c
folds_positive_2c
verdict
```

Verdict rules:

```text
candidate = positive 1c and 2c slippage PnL with trades across multiple folds and Wilson lower bound above breakeven ask
research_only = positive settlement PnL but weak fold coverage or wide uncertainty
reject = negative after slippage or no trades
```

### 4. Do Not Promote To Live Yet

Do not wire runtime paper decisions from live logs yet.

The later live phase will be:

```text
read live side snapshots
apply the frozen backtest-selected model/rule
log decisions
settle decisions
compare forward paper performance to backtest expectations
```

That phase starts only after the executable-backtest candidate is frozen.

## What Not To Do Now

Do not mine live logs for alpha.

Do not use live-settled rows as backtest evidence.

Do not implement the live paper-decision loop yet.

Do not deploy a model because lockbox PnL is positive on a small number of trades.

Do not count repeated snapshots as independent evidence.

Do not treat positive settlement PnL as proof of positive short-horizon CLV.

## Immediate Next Step

Add `market_anchor_model_summary.csv`, regenerate the executable-backtest artifacts, and rerun the test suite.
