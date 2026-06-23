# Dota2 Clean Bot

Small logging-first Dota/Polymarket bot workspace.

The core rule for this project: live/replay data must log in the same shape as
the clean executable backtest dataset:

`clean_backtest_side_snapshots.parquet`

That means every side/snapshot row has mapped market identity, game state,
nearest executable book, and settlement fields when known.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Extract Datasets

```bash
.venv/bin/python -m dota2bot extract
```

This extracts:

- `clean_executable_backtest_dataset_20260623.zip`
- `pattern_discovery_dataset_20260623.zip`

into `datasets/`.

## Replay Smoke Run

```bash
.venv/bin/python -m dota2bot replay --limit 1000
```

Outputs:

- `logs/clean_side_snapshots/part-*.parquet`
- `logs/strategy_decisions/part-*.parquet`

The first log uses the exact executable-backtest schema.

## Data Tiers

- Clean executable dataset: use for ROI/backtest claims.
- Pattern discovery dataset: use for finding state/outcome patterns.
- Any strategy found on pattern data must be validated on the clean executable
  dataset before it is treated as tradable.
