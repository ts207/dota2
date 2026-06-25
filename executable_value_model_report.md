# Executable Value Model Research

Final accounting: historical executable research gate, map-equivalent, one trade per match/map, 2c slippage.

## Inventory

| step | rows | matches | map exposures |
| --- | ---: | ---: | ---: |
| raw_clean_artifact | 34317 | 135 | 137 |
| raw_live_settled | 21978 | 19 | 21 |
| raw_combined | 56295 | 154 | 158 |
| dedup_identity_combined | 53787 | 154 | 158 |
| feature_frame | 53787 | 154 | 158 |
| settled | 53787 | 154 | 158 |
| map_equivalent_scope | 46597 | 154 | 156 |
| executable_snapshot | 9308 | 118 | 118 |
| tradable_research | 17840 | 122 | 124 |
| live_executable_and_research_same_row | 5414 | 95 | 95 |
| final_historical_executable_universe | 16015 | 122 | 123 |

Rows: 16015 total, 8703 development, 7312 lockbox.
Matches: 122 total, 98 development, 24 lockbox.

## Promotion Verdict

Promote candidate: `value_logistic` / `ask_20_50` / threshold `0.50`.

## Development Selection

## Selected Candidate

`value_logistic` / `ask_20_50` / threshold `0.50`.

| split | trades | win | avg ask | pnl | pnl 1c | pnl 2c |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| lockbox | 11 | 63.6% | 0.467 | +1.8600 | +1.7500 | +1.6400 |

## Top Lockbox Candidates

| model | kind | ask filter | threshold | trades | win | avg ask | pnl 2c |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| winprob_hgb | win_prob | ask_25_55 | 0.10 | 14 | 71.4% | 0.431 | +3.6800 |
| winprob_hgb | win_prob | ask_20_50 | 0.06 | 15 | 66.7% | 0.405 | +3.6200 |
| winprob_hgb | win_prob | ask_20_50 | 0.10 | 13 | 69.2% | 0.401 | +3.5300 |
| winprob_hgb | win_prob | ask_25_55 | 0.08 | 15 | 66.7% | 0.426 | +3.3100 |
| winprob_hgb | win_prob | ask_15_70 | 0.08 | 19 | 63.2% | 0.445 | +3.1600 |
| winprob_hgb | win_prob | ask_20_50 | 0.08 | 14 | 64.3% | 0.404 | +3.0600 |
| winprob_hgb | win_prob | ask_20_60 | 0.08 | 15 | 66.7% | 0.444 | +3.0400 |
| value_hgb | value_class | ask_20_50 | 0.60 | 9 | 77.8% | 0.424 | +3.0000 |
| winprob_hgb | win_prob | ask_25_55 | 0.06 | 16 | 62.5% | 0.419 | +2.9700 |
| winprob_hgb | win_prob | ask_15_70 | 0.10 | 19 | 63.2% | 0.458 | +2.9100 |
| winprob_hgb | win_prob | ask_20_60 | 0.10 | 15 | 66.7% | 0.453 | +2.9100 |
| value_hgb | value_class | ask_20_50 | 0.62 | 9 | 77.8% | 0.438 | +2.8800 |
| value_hgb | value_class | ask_20_50 | 0.65 | 9 | 77.8% | 0.442 | +2.8400 |
| winprob_hgb | win_prob | ask_20_60 | 0.06 | 16 | 62.5% | 0.436 | +2.7000 |
| winprob_logistic | win_prob | ask_25_55 | 0.02 | 11 | 72.7% | 0.462 | +2.7000 |
| value_hgb | value_class | ask_25_55 | 0.62 | 11 | 72.7% | 0.470 | +2.6100 |
| value_hgb | value_class | ask_25_55 | 0.65 | 11 | 72.7% | 0.472 | +2.5900 |
| winprob_hgb | win_prob | ask_20_50 | 0.04 | 15 | 60.0% | 0.409 | +2.5700 |
| winprob_logistic | win_prob | ask_25_55 | 0.04 | 7 | 85.7% | 0.486 | +2.4600 |
| value_hgb | value_class | ask_20_50 | 0.55 | 13 | 61.5% | 0.409 | +2.4200 |

## Robust Development Candidates

| model | kind | ask filter | threshold | folds | trades | win | avg ask | pnl 2c |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| value_logistic | value_class | ask_20_50 | 0.50 | 5 | 19 | 57.9% | 0.472 | +1.6500 |
| value_logistic | value_class | ask_20_50 | 0.52 | 4 | 16 | 56.2% | 0.470 | +1.1600 |
| value_hgb | value_class | ask_25_55 | 0.50 | 5 | 44 | 50.0% | 0.454 | +1.1300 |
| value_logistic | value_class | ask_20_60 | 0.60 | 5 | 23 | 60.9% | 0.555 | +0.7800 |
| value_logistic | value_class | ask_25_55 | 0.48 | 5 | 30 | 53.3% | 0.507 | +0.2000 |
| value_logistic | value_class | ask_20_60 | 0.62 | 5 | 17 | 58.8% | 0.563 | +0.0900 |
| value_logistic | value_class | ask_25_55 | 0.50 | 5 | 28 | 53.6% | 0.514 | +0.0600 |

## Top Development Candidates

| model | kind | ask filter | threshold | folds | trades | win | avg ask | pnl 2c |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| value_logistic | value_class | ask_20_50 | 0.50 | 5 | 19 | 57.9% | 0.472 | +1.6500 |
| value_logistic | value_class | ask_20_50 | 0.60 | 2 | 7 | 71.4% | 0.479 | +1.5100 |
| value_logistic | value_class | ask_25_55 | 0.62 | 2 | 7 | 71.4% | 0.500 | +1.3600 |
| value_logistic | value_class | ask_20_50 | 0.52 | 4 | 16 | 56.2% | 0.470 | +1.1600 |
| value_hgb | value_class | ask_25_55 | 0.50 | 5 | 44 | 50.0% | 0.454 | +1.1300 |
| value_logistic | value_class | ask_25_55 | 0.60 | 4 | 10 | 60.0% | 0.498 | +0.8200 |
| value_logistic | value_class | ask_20_60 | 0.60 | 5 | 23 | 60.9% | 0.555 | +0.7800 |
| value_logistic | value_class | ask_20_50 | 0.62 | 1 | 5 | 60.0% | 0.466 | +0.5700 |
| value_logistic | value_class | ask_20_50 | 0.58 | 3 | 9 | 55.6% | 0.474 | +0.5500 |
| value_logistic | value_class | ask_20_50 | 0.65 | 1 | 5 | 60.0% | 0.486 | +0.4700 |
| value_logistic | value_class | ask_25_55 | 0.65 | 2 | 7 | 57.1% | 0.514 | +0.2600 |
| value_logistic | value_class | ask_25_55 | 0.48 | 5 | 30 | 53.3% | 0.507 | +0.2000 |
| value_logistic | value_class | ask_20_60 | 0.62 | 5 | 17 | 58.8% | 0.563 | +0.0900 |
| value_logistic | value_class | ask_25_55 | 0.50 | 5 | 28 | 53.6% | 0.514 | +0.0600 |
| value_logistic | value_class | ask_20_50 | 0.48 | 5 | 23 | 47.8% | 0.470 | -0.2700 |
| value_logistic | value_class | ask_15_70 | 0.62 | 5 | 41 | 65.9% | 0.645 | -0.2800 |
| value_logistic | value_class | ask_25_55 | 0.52 | 5 | 27 | 51.9% | 0.512 | -0.3700 |
| value_logistic | value_class | ask_25_55 | 0.55 | 5 | 22 | 50.0% | 0.506 | -0.5700 |
| value_logistic | value_class | ask_20_50 | 0.55 | 4 | 12 | 41.7% | 0.467 | -0.8500 |
| value_logistic | value_class | ask_20_60 | 0.65 | 5 | 12 | 50.0% | 0.559 | -0.9500 |