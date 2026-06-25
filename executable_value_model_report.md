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

Do not switch the running paper bot to a retrained model from this run.

Promotion requires folds >= 4, development trades >= 15, lockbox trades >= 4, and positive 2c PnL on both development and lockbox.
No retrained candidate passed that combined test.

## Development Selection

## Selected Candidate

`winprob_logistic_evfilter` / `ask_25_55` / threshold `0.18`.

| split | trades | win | avg ask | pnl | pnl 1c | pnl 2c |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| lockbox | 3 | 66.7% | 0.400 | +0.8000 | +0.7700 | +0.7400 |

## Top Lockbox Candidates

| model | kind | ask filter | threshold | trades | win | avg ask | pnl 2c |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| winprob_hgb_evfilter | win_prob | ask_25_55 | 0.10 | 14 | 71.4% | 0.431 | +3.6800 |
| pnl_hgb_regression | pnl_regression | ask_20_60 | 0.10 | 15 | 73.3% | 0.468 | +3.6800 |
| pnl_hgb_regression | pnl_regression | ask_25_55 | 0.10 | 12 | 75.0% | 0.427 | +3.6400 |
| winprob_hgb_evfilter | win_prob | ask_20_50 | 0.20 | 11 | 72.7% | 0.378 | +3.6200 |
| winprob_hgb_evfilter | win_prob | ask_20_50 | 0.18 | 11 | 72.7% | 0.380 | +3.6000 |
| winprob_hgb_evfilter | win_prob | ask_20_50 | 0.10 | 13 | 69.2% | 0.401 | +3.5300 |
| pnl_hgb_regression | pnl_regression | ask_15_70 | 0.10 | 18 | 66.7% | 0.459 | +3.3700 |
| winprob_hgb_evfilter | win_prob | ask_25_55 | 0.08 | 15 | 66.7% | 0.426 | +3.3100 |
| winprob_hgb_evfilter | win_prob | ask_15_70 | 0.08 | 19 | 63.2% | 0.445 | +3.1600 |
| winprob_hgb_evfilter | win_prob | ask_25_55 | 0.12 | 13 | 69.2% | 0.432 | +3.1200 |
| winprob_hgb_evfilter | win_prob | ask_20_50 | 0.08 | 14 | 64.3% | 0.404 | +3.0600 |
| winprob_hgb_evfilter | win_prob | ask_25_55 | 0.20 | 12 | 66.7% | 0.393 | +3.0500 |
| winprob_hgb_evfilter | win_prob | ask_20_60 | 0.20 | 12 | 66.7% | 0.393 | +3.0400 |
| winprob_hgb_evfilter | win_prob | ask_20_60 | 0.08 | 15 | 66.7% | 0.444 | +3.0400 |
| winprob_hgb_evfilter | win_prob | ask_25_55 | 0.18 | 12 | 66.7% | 0.394 | +3.0300 |
| winprob_logistic_evfilter | win_prob | ask_25_55 | 0.05 | 6 | 100.0% | 0.478 | +3.0100 |
| winprob_hgb_evfilter | win_prob | ask_20_50 | 0.15 | 12 | 66.7% | 0.398 | +2.9800 |
| winprob_hgb_evfilter | win_prob | ask_20_50 | 0.12 | 12 | 66.7% | 0.402 | +2.9400 |
| pnl_ridge_regression | pnl_regression | ask_20_50 | 0.00 | 11 | 72.7% | 0.442 | +2.9200 |
| winprob_hgb_evfilter | win_prob | ask_15_70 | 0.10 | 19 | 63.2% | 0.458 | +2.9100 |

## Top Development Candidates

| model | kind | ask filter | threshold | folds | trades | win | avg ask | pnl 2c |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| winprob_logistic_evfilter | win_prob | ask_25_55 | 0.18 | 1 | 6 | 66.7% | 0.478 | +1.0100 |
| winprob_logistic_evfilter | win_prob | ask_20_50 | 0.18 | 1 | 5 | 60.0% | 0.454 | +0.6300 |
| winprob_logistic_evfilter | win_prob | ask_25_55 | 0.15 | 2 | 7 | 57.1% | 0.469 | +0.5800 |
| pnl_ridge_regression | pnl_regression | ask_25_55 | 0.10 | 2 | 7 | 57.1% | 0.476 | +0.5300 |
| pnl_ridge_regression | pnl_regression | ask_20_60 | 0.10 | 2 | 7 | 57.1% | 0.484 | +0.4700 |
| winprob_logistic_evfilter | win_prob | ask_20_60 | 0.18 | 1 | 7 | 57.1% | 0.501 | +0.3500 |
| winprob_logistic_evfilter | win_prob | ask_20_50 | 0.15 | 2 | 6 | 50.0% | 0.443 | +0.2200 |
| winprob_logistic_evfilter | win_prob | ask_20_60 | 0.15 | 3 | 9 | 55.6% | 0.512 | +0.2100 |
| pnl_ridge_regression | pnl_regression | ask_20_50 | 0.08 | 2 | 6 | 50.0% | 0.452 | +0.1700 |
| winprob_logistic_evfilter | win_prob | ask_20_50 | 0.20 | 1 | 4 | 50.0% | 0.465 | +0.0600 |
| pnl_ridge_regression | pnl_regression | ask_25_55 | 0.08 | 3 | 8 | 50.0% | 0.482 | -0.0200 |
| pnl_ridge_regression | pnl_regression | ask_15_70 | 0.15 | 3 | 8 | 62.5% | 0.619 | -0.1100 |
| winprob_logistic_evfilter | win_prob | ask_20_50 | 0.12 | 2 | 7 | 42.9% | 0.429 | -0.1400 |
| pnl_ridge_regression | pnl_regression | ask_20_50 | 0.10 | 2 | 5 | 40.0% | 0.438 | -0.2900 |
| pnl_hgb_regression | pnl_regression | ask_25_55 | -0.02 | 5 | 48 | 43.8% | 0.424 | -0.3100 |
| pnl_ridge_regression | pnl_regression | ask_20_50 | 0.12 | 2 | 5 | 40.0% | 0.450 | -0.3500 |
| pnl_ridge_regression | pnl_regression | ask_25_55 | 0.12 | 2 | 5 | 40.0% | 0.450 | -0.3500 |
| pnl_ridge_regression | pnl_regression | ask_20_50 | 0.15 | 1 | 3 | 33.3% | 0.447 | -0.4000 |
| winprob_logistic_evfilter | win_prob | ask_25_55 | 0.20 | 1 | 5 | 40.0% | 0.478 | -0.4900 |
| pnl_ridge_regression | pnl_regression | ask_25_55 | 0.15 | 1 | 3 | 33.3% | 0.490 | -0.5300 |