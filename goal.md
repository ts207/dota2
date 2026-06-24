
Yes. Your instinct is right.

You should **not trust the hand-selected strategies yet**. They were useful for hypothesis discovery, but the next serious step should be a **walk-forward model framework**, not hardcoding those rules as if they are already real alpha.

The correct goal is:

> Train only on past matches, predict future matches, compare model fair probability to executable ask, and measure forward EV fold by fold.

## Why you should not trust the current strategies

The current multifactor rules came from a large rule search. The script generates many variants across market buckets, edge thresholds, ask caps, net-worth thresholds, momentum thresholds, scoreboard lag thresholds, structure thresholds, and reversal conditions.

That creates data-snooping risk:

```text
many rules tested
small samples
best-looking rules selected
reported results can be inflated
```

The report itself shows promising but small samples. Example: the top structure rule has only 11 test trades; the top momentum rule has 19 test trades.

So yes: treat those as **hypotheses**, not strategies.

## But do not “train once” either

The model should not be trained once on one train/test split and trusted.

Current model code uses a single chronological 60/40 match split:

```text
first 60% matches = train
last 40% matches = test
```

That is better than random splitting, but still not enough.

You want **walk-forward validation**:

```text
Fold 1: train early matches       → test next block
Fold 2: train early + block 1     → test next block
Fold 3: train early + blocks 1-2  → test next block
...
```

The unit must be **match-level**, not row-level, because rows inside the same match are highly correlated.

## Correct model-first workflow

Use this order:

```text
1. Audit executable dataset
2. Build side-relative features
3. Build walk-forward model evaluator
4. Train probability models fold by fold
5. Convert model probability to trade decisions
6. Compare model edge to rule edge
7. Only then implement live paper logging
```

So yes, model before runtime strategy deployment. But still audit first, because bad data makes any model useless.

## The model objective

The model should estimate:

```text
P(side token wins | game state at this timestamp)
```

Then trading edge is:

```text
edge = model_prob - book_best_ask
```

Expected value per share is approximately the same:

```text
EV = model_prob - ask
```

Trade only when:

```text
model_prob - ask >= threshold
```

Example:

```text
model_prob = 0.74
ask = 0.62
edge = +0.12
```

That is the actual trading thesis.

## Important: separate state model from price model

Your current research model includes features like:

```text
book_best_ask
state_prob_proxy
state_edge_proxy
```

inside `MODEL_FEATURES`.

That is okay for a **trade classifier**, but not ideal for a clean fair-probability model.

Build two models:

### Model A — fair probability model

Uses only game state:

```text
side_nw
side_score
side_mom_100
side_mom_300
side_tower
side_rax
game_time_sec
total_kills
seconds_since_state_change
market bucket / map type if needed
```

Output:

```text
fair_prob = P(side wins)
```

### Model B — trade/residual model

Uses market features too:

```text
fair_prob
ask
bid
spread
ask_size
book_age_ms
source_update_age_sec
market bucket
```

Output:

```text
trade / no trade
or expected pnl
```

Do **not** mix these concepts too early. First build the clean fair model.

## What walk-forward should measure

For each fold, report:

```text
AUC
log loss
Brier score
calibration by probability bucket
avg predicted probability
realized win rate
avg ask
avg edge
trade count
win rate
avg pnl/share
total pnl
max drawdown
PnL after +1c slippage
PnL after +2c slippage
```

The model is only useful if it is both:

```text
predictive: probabilities match outcomes
tradable: model_prob > ask produces positive PnL
```

A high AUC alone is not enough.

## Stronger validation design

Use this split structure:

```text
Discovery / dev set:
    Used to design features and model candidates.

Walk-forward validation:
    Used to compare models and thresholds.

Final lockbox:
    Never touched until the end.

Live paper:
    Forward-only proof.
```

The threshold must be selected inside each training fold, not on the test fold.

Bad:

```text
Try thresholds on all data and report best.
```

Good:

```text
For each fold:
    train model on past
    choose threshold on train/validation past only
    apply once to future test block
```

## What to build next instead of hardcoding rules

Build:

```text
walk_forward_model_research.py
```

Outputs:

```text
walk_forward_model_report.md
walk_forward_model_predictions.csv
walk_forward_model_trades.csv
```

Core behavior:

```text
1. Load clean executable side snapshots
2. Compute side-relative features
3. Split by match chronology
4. Train model on past folds
5. Predict future fold
6. Calibrate probabilities
7. Generate trades where model_prob - ask >= threshold
8. Deduplicate first trade per match + market bucket
9. Score PnL
10. Aggregate fold-level results
```

## Models to test first

Use simple models first:

```text
logistic regression
hist gradient boosting
random forest
LightGBM if stable
XGBoost if stable
```

Do not start with deep learning. The dataset is likely too small and too correlated.

Preferred baseline:

```text
LogisticRegression + calibration
```

Preferred nonlinear model:

```text
HistGradientBoostingClassifier or LightGBM
```

Then calibrate with:

```text
isotonic calibration
or sigmoid/Platt calibration
```

## What to do with the existing rules

Keep them as benchmarks only.

Your comparison table should be:

```text
market baseline
hand composite proxy
top hand rules
logistic fair-prob model
gradient boosting fair-prob model
residual trade model
```

If the model cannot beat the hand rules in walk-forward, do not deploy it.
If the hand rules cannot beat the model, do not deploy the rules.
If neither beats breakeven after slippage, do not trade.

## Revised next milestone

The next milestone should not be:

```text
implement top 2 strategies
```

It should be:

```text
build walk-forward model validation and prove whether any edge survives out-of-sample
```

Then, after that:

```text
paper-log should log model decisions, not just rule decisions
```

Minimum live decision fields should include:

```text
model_name
model_version
training_cutoff_match_time
fair_prob
calibrated_prob
book_best_ask
edge
entry_threshold
signal
reason
paper_entry_price
```

## Bottom line

Yes: **do not trust those strategies yet**.

The better plan is:

```text
audit executable data
→ build walk-forward model framework
→ train fair-probability model on past matches
→ test on future matches
→ compare model edge vs ask
→ only then paper-log live model decisions
```

The hand strategies are useful as **baselines and sanity checks**, not as the main system.
