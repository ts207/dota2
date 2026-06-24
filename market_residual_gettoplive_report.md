# Market Residual GetTopLive Analysis

Scope: executable backtest side snapshots only. This report tests whether GetTopLive state adds residual edge after anchoring on Polymarket ask price.

## Data

- Source rows: 34,254
- Tradable rows: 9,981
- Matches: 135
- Development matches: 108
- Lockbox matches: 27
- Minimum game time: 600s
- Future-price max lag for CLV: 20s
- Robust residual bucket gate: rows >= 25, matches >= 10, positive residual, positive PnL

## Verdict

- Settlement residual test: PASS
- CLV / short-horizon future-bid test: FAIL
- Walk-forward 1c slippage PnL, enhanced vs market-only: +0.3900 vs -0.4400
- Walk-forward 2c slippage PnL, enhanced vs market-only: +0.2600 vs -0.5100
- Lockbox 1c slippage PnL, enhanced vs market-only: +2.3300 vs +0.0000
- Lockbox 2c slippage PnL, enhanced vs market-only: +2.2100 vs +0.0000
- Best walk-forward ablation by 1c slippage PnL: `market_transition_nw_kill_logistic` (+3.6000 / +3.3800 after 1c/2c)
- Best lockbox ablation by 1c slippage PnL: `market_nw_kill_momentum_logistic` (+2.7100 / +2.6200 after 1c/2c)
- Positive 60s future-bid CLV events with at least 3 matches: 0
- Best 60s average future-bid CLV: -0.0168

## Market Calibration

| ask_bucket | rows | matches | avg_ask | win_rate | win_rate_minus_avg_ask | avg_pnl | total_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 00_20 | 2015 | 79 | 0.123 | 9.0% | -3.3% | -0.0333 | -67.0800 |
| 20_35 | 1542 | 85 | 0.280 | 25.1% | -2.9% | -0.0288 | -44.3700 |
| 35_50 | 1415 | 65 | 0.435 | 38.3% | -5.2% | -0.0519 | -73.4000 |
| 50_65 | 1295 | 57 | 0.585 | 55.1% | -3.4% | -0.0342 | -44.3400 |
| 65_80 | 1510 | 81 | 0.736 | 71.1% | -2.6% | -0.0257 | -38.8700 |
| 80_100 | 2204 | 90 | 0.888 | 87.2% | -1.6% | -0.0162 | -35.7580 |

## Strongest Price-Bucket State Residuals

| ask_bucket | state_bucket_type | state_bucket | rows | matches | avg_ask | win_rate | win_rate_minus_avg_ask | avg_pnl | robust_residual_bucket | robust_gate_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 35_50 | transition_signal_type | first_nw_change | 2 | 1 | 0.360 | 100.0% | 64.0% | +0.6400 | False | too_few_rows |
| 35_50 | game_time_bucket | 0000_0600 | 2 | 1 | 0.365 | 100.0% | 63.5% | +0.6350 | False | too_few_rows |
| 20_35 | side_nw_bucket | nw_ge_8k | 41 | 4 | 0.274 | 87.8% | 60.4% | +0.6044 | False | too_few_matches |
| 00_20 | side_transition_nw_delta_bucket | transition_nw_ge_5k | 5 | 4 | 0.100 | 60.0% | 50.0% | +0.5000 | False | too_few_rows |
| 20_35 | side_score_bucket | score_ge_6 | 77 | 16 | 0.283 | 74.0% | 45.7% | +0.4571 | True | pass |
| 00_20 | side_nw_bucket | nw_3k_8k | 41 | 5 | 0.140 | 56.1% | 42.1% | +0.4207 | False | too_few_matches |
| 20_35 | transition_signal_type | score_then_nw_catchup | 3 | 2 | 0.260 | 66.7% | 40.7% | +0.4067 | False | too_few_rows |
| 20_35 | score_nw_lag_type | score_then_nw | 6 | 5 | 0.262 | 66.7% | 40.5% | +0.4050 | False | too_few_rows |
| 20_35 | side_mom_100_bucket | mom_ge_5k | 20 | 8 | 0.269 | 65.0% | 38.1% | +0.3805 | False | too_few_rows |
| 20_35 | structure_score_bucket | struct_1_2 | 15 | 5 | 0.289 | 66.7% | 37.8% | +0.3780 | False | too_few_rows |
| 00_20 | side_mom_100_bucket | mom_ge_5k | 24 | 5 | 0.132 | 50.0% | 36.8% | +0.3679 | False | too_few_rows |
| 00_20 | transition_signal_type | score_then_nw_catchup | 2 | 2 | 0.140 | 50.0% | 36.0% | +0.3600 | False | too_few_rows |
| 20_35 | side_nw_bucket | nw_3k_8k | 38 | 9 | 0.298 | 57.9% | 28.1% | +0.2805 | False | too_few_matches |
| 00_20 | side_score_bucket | score_2_6 | 79 | 17 | 0.138 | 36.7% | 22.9% | +0.2295 | True | pass |
| 20_35 | transition_signal_type | nw_then_score_catchup | 8 | 7 | 0.280 | 50.0% | 22.0% | +0.2200 | False | too_few_rows |
| 00_20 | side_score_bucket | score_ge_6 | 40 | 8 | 0.137 | 35.0% | 21.3% | +0.2130 | False | too_few_matches |
| 35_50 | side_score_bucket | score_2_6 | 182 | 32 | 0.442 | 64.3% | 20.1% | +0.2007 | True | pass |
| 20_35 | side_transition_nw_delta_bucket | transition_nw_1k_5k | 59 | 26 | 0.284 | 47.5% | 19.1% | +0.1907 | True | pass |
| 35_50 | side_nw_bucket | nw_ge_8k | 30 | 8 | 0.455 | 63.3% | 17.8% | +0.1783 | False | too_few_matches |
| 20_35 | structure_score_bucket | struct_ge_2 | 161 | 18 | 0.284 | 46.0% | 17.6% | +0.1760 | True | pass |
| 80_100 | game_time_bucket | 0000_0600 | 2 | 1 | 0.840 | 100.0% | 16.0% | +0.1600 | False | too_few_rows |
| 00_20 | side_nw_bucket | nw_ge_8k | 11 | 3 | 0.127 | 27.3% | 14.5% | +0.1455 | False | too_few_rows |
| 20_35 | side_transition_nw_delta_bucket | transition_nw_le_-5k | 12 | 7 | 0.274 | 41.7% | 14.2% | +0.1425 | False | too_few_rows |
| 65_80 | side_score_bucket | score_2_6 | 278 | 58 | 0.737 | 87.8% | 14.1% | +0.1409 | True | pass |
| 20_35 | side_mom_100_bucket | mom_1k_5k | 192 | 34 | 0.282 | 42.2% | 14.0% | +0.1402 | True | pass |
| 20_35 | game_time_bucket | 2400_plus | 149 | 18 | 0.281 | 41.6% | 13.5% | +0.1349 | True | pass |
| 80_100 | transition_signal_type | score_then_nw_catchup | 10 | 9 | 0.873 | 100.0% | 12.7% | +0.1270 | False | too_few_rows |
| 65_80 | side_transition_nw_delta_bucket | transition_nw_le_-5k | 7 | 5 | 0.741 | 85.7% | 11.6% | +0.1157 | False | too_few_rows |
| 00_20 | game_time_bucket | 2400_plus | 237 | 24 | 0.121 | 23.2% | 11.1% | +0.1114 | True | pass |
| 35_50 | side_transition_nw_delta_bucket | transition_nw_1k_5k | 84 | 36 | 0.425 | 53.6% | 11.1% | +0.1112 | True | pass |
| 35_50 | game_time_bucket | 2400_plus | 172 | 16 | 0.432 | 54.1% | 10.9% | +0.1092 | True | pass |
| 50_65 | game_time_bucket | 1200_1800 | 311 | 36 | 0.591 | 69.5% | 10.4% | +0.1036 | True | pass |
| 50_65 | side_transition_nw_delta_bucket | transition_nw_ge_5k | 6 | 5 | 0.568 | 66.7% | 9.8% | +0.0983 | False | too_few_rows |
| 50_65 | side_score_bucket | score_lt_-6 | 111 | 19 | 0.581 | 67.6% | 9.5% | +0.0945 | True | pass |
| 35_50 | side_mom_100_bucket | mom_ge_5k | 38 | 10 | 0.437 | 52.6% | 8.9% | +0.0892 | True | pass |
| 65_80 | structure_score_bucket | struct_ge_2 | 270 | 38 | 0.741 | 82.6% | 8.5% | +0.0847 | True | pass |
| 35_50 | score_nw_lag_type | nw_only | 6 | 4 | 0.418 | 50.0% | 8.2% | +0.0817 | False | too_few_rows |
| 50_65 | structure_score_bucket | struct_-2_-1 | 91 | 26 | 0.582 | 65.9% | 7.7% | +0.0774 | True | pass |
| 35_50 | transition_signal_type | first_score_change | 44 | 22 | 0.447 | 52.3% | 7.6% | +0.0757 | True | pass |
| 50_65 | side_kill_mom_bucket | kill_mom_le_-3 | 437 | 48 | 0.583 | 65.7% | 7.4% | +0.0737 | True | pass |

## Robust Price-Bucket State Residuals

| ask_bucket | state_bucket_type | state_bucket | rows | matches | avg_ask | win_rate | win_rate_minus_avg_ask | avg_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 20_35 | side_score_bucket | score_ge_6 | 77 | 16 | 0.283 | 74.0% | 45.7% | +0.4571 |
| 00_20 | side_score_bucket | score_2_6 | 79 | 17 | 0.138 | 36.7% | 22.9% | +0.2295 |
| 35_50 | side_score_bucket | score_2_6 | 182 | 32 | 0.442 | 64.3% | 20.1% | +0.2007 |
| 20_35 | side_transition_nw_delta_bucket | transition_nw_1k_5k | 59 | 26 | 0.284 | 47.5% | 19.1% | +0.1907 |
| 20_35 | structure_score_bucket | struct_ge_2 | 161 | 18 | 0.284 | 46.0% | 17.6% | +0.1760 |
| 65_80 | side_score_bucket | score_2_6 | 278 | 58 | 0.737 | 87.8% | 14.1% | +0.1409 |
| 20_35 | side_mom_100_bucket | mom_1k_5k | 192 | 34 | 0.282 | 42.2% | 14.0% | +0.1402 |
| 20_35 | game_time_bucket | 2400_plus | 149 | 18 | 0.281 | 41.6% | 13.5% | +0.1349 |
| 00_20 | game_time_bucket | 2400_plus | 237 | 24 | 0.121 | 23.2% | 11.1% | +0.1114 |
| 35_50 | side_transition_nw_delta_bucket | transition_nw_1k_5k | 84 | 36 | 0.425 | 53.6% | 11.1% | +0.1112 |
| 35_50 | game_time_bucket | 2400_plus | 172 | 16 | 0.432 | 54.1% | 10.9% | +0.1092 |
| 50_65 | game_time_bucket | 1200_1800 | 311 | 36 | 0.591 | 69.5% | 10.4% | +0.1036 |
| 50_65 | side_score_bucket | score_lt_-6 | 111 | 19 | 0.581 | 67.6% | 9.5% | +0.0945 |
| 35_50 | side_mom_100_bucket | mom_ge_5k | 38 | 10 | 0.437 | 52.6% | 8.9% | +0.0892 |
| 65_80 | structure_score_bucket | struct_ge_2 | 270 | 38 | 0.741 | 82.6% | 8.5% | +0.0847 |
| 50_65 | structure_score_bucket | struct_-2_-1 | 91 | 26 | 0.582 | 65.9% | 7.7% | +0.0774 |
| 35_50 | transition_signal_type | first_score_change | 44 | 22 | 0.447 | 52.3% | 7.6% | +0.0757 |
| 50_65 | side_kill_mom_bucket | kill_mom_le_-3 | 437 | 48 | 0.583 | 65.7% | 7.4% | +0.0737 |
| 80_100 | side_score_bucket | score_2_6 | 501 | 67 | 0.889 | 95.8% | 6.9% | +0.0693 |
| 20_35 | score_nw_lag_type | nw_then_score | 146 | 46 | 0.280 | 34.9% | 6.9% | +0.0693 |
| 50_65 | side_score_bucket | score_2_6 | 218 | 41 | 0.593 | 65.6% | 6.3% | +0.0629 |
| 20_35 | side_score_bucket | score_2_6 | 118 | 22 | 0.277 | 33.9% | 6.2% | +0.0615 |
| 00_20 | structure_score_bucket | struct_ge_2 | 204 | 16 | 0.129 | 18.1% | 5.3% | +0.0527 |
| 50_65 | structure_score_bucket | struct_1_2 | 53 | 17 | 0.593 | 64.2% | 4.9% | +0.0489 |
| 65_80 | side_nw_bucket | nw_ge_8k | 260 | 35 | 0.748 | 79.2% | 4.5% | +0.0446 |
| 80_100 | game_time_bucket | 0900_1200 | 374 | 48 | 0.881 | 92.2% | 4.1% | +0.0414 |
| 35_50 | score_nw_lag_type | nw_then_score | 100 | 42 | 0.430 | 47.0% | 4.0% | +0.0399 |
| 35_50 | side_mom_100_bucket | mom_1k_5k | 286 | 45 | 0.437 | 47.6% | 3.9% | +0.0388 |
| 65_80 | game_time_bucket | 0600_0900 | 252 | 44 | 0.730 | 76.6% | 3.6% | +0.0360 |
| 20_35 | score_nw_lag_type | no_change | 303 | 68 | 0.281 | 31.7% | 3.5% | +0.0354 |
| 20_35 | side_kill_mom_bucket | kill_mom_-2_-1 | 160 | 35 | 0.272 | 30.6% | 3.5% | +0.0346 |
| 65_80 | game_time_bucket | 0900_1200 | 307 | 51 | 0.738 | 77.2% | 3.4% | +0.0343 |
| 20_35 | side_transition_kill_delta_bucket | transition_kill_0 | 397 | 73 | 0.282 | 31.5% | 3.3% | +0.0327 |
| 20_35 | transition_signal_type | post_transition_close | 267 | 67 | 0.284 | 31.5% | 3.1% | +0.0311 |
| 50_65 | side_transition_nw_delta_bucket | transition_nw_1k_5k | 96 | 37 | 0.585 | 61.5% | 3.0% | +0.0298 |
| 65_80 | side_score_bucket | score_ge_6 | 274 | 36 | 0.742 | 77.0% | 2.8% | +0.0284 |
| 35_50 | game_time_bucket | 0600_0900 | 352 | 45 | 0.437 | 46.3% | 2.6% | +0.0262 |
| 65_80 | transition_signal_type | first_score_change | 57 | 32 | 0.729 | 75.4% | 2.5% | +0.0251 |
| 80_100 | side_nw_bucket | nw_ge_8k | 1091 | 70 | 0.899 | 92.4% | 2.5% | +0.0251 |
| 65_80 | structure_score_bucket | struct_1_2 | 124 | 25 | 0.741 | 76.6% | 2.5% | +0.0249 |

## Folds

| fold | fit_matches | validation_matches | test_matches | training_cutoff_match_time |
| --- | --- | --- | --- | --- |
| 1 | 38 | 12 | 11 | 2026-05-30T17:20:46.978+00:00 |
| 2 | 46 | 15 | 11 | 2026-05-31T18:17:58.840+00:00 |
| 3 | 54 | 18 | 11 | 2026-06-01T15:55:39.100+00:00 |
| 4 | 62 | 21 | 11 | 2026-06-02T13:14:29.781+00:00 |
| 5 | 70 | 24 | 11 | 2026-06-03T01:22:10.007+00:00 |

## Market-Anchored Walk-Forward Models

All rows below use the same chronological folds, threshold search, first-trade dedupe, and slippage accounting. The component models are ablations of GetTopLive feature families on top of the same market-price anchor.

| stage | model_name | folds | median_threshold | pred_rows | auc | log_loss | brier | trade_trades | trade_win_rate | trade_avg_ask | trade_avg_edge | trade_total_pnl | trade_total_pnl_slip_1c | trade_total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_nw_kill_momentum_logistic | 1 | 0.080 | 1968 | 82.9% | 0.511 | 0.171 | 9 | 77.8% | 0.467 | +0.1156 | +2.8000 | +2.7100 | +2.6200 |
| lockbox | market_momentum_logistic | 1 | 0.100 | 1968 | 83.1% | 0.509 | 0.170 | 8 | 75.0% | 0.438 | +0.1508 | +2.5000 | +2.4200 | +2.3400 |
| lockbox | market_gettoplive_logistic | 1 | 0.080 | 1968 | 84.3% | 0.493 | 0.164 | 12 | 75.0% | 0.546 | +0.1136 | +2.4500 | +2.3300 | +2.2100 |
| lockbox | market_transition_nw_kill_logistic | 1 | 0.020 | 1968 | 80.6% | 0.547 | 0.185 | 16 | 68.8% | 0.562 | +0.0668 | +2.0000 | +1.8400 | +1.6800 |
| lockbox | market_transition_nw_logistic | 1 | 0.050 | 1968 | 80.5% | 0.548 | 0.186 | 13 | 69.2% | 0.565 | +0.1003 | +1.6500 | +1.5200 | +1.3900 |
| lockbox | market_nw_logistic | 1 | 0.150 | 1968 | 83.8% | 0.499 | 0.167 | 5 | 60.0% | 0.360 | +0.1810 | +1.2000 | +1.1500 | +1.1000 |
| lockbox | market_transition_catchup_logistic | 1 | 0.020 | 1968 | 80.6% | 0.547 | 0.185 | 15 | 66.7% | 0.585 | +0.0772 | +1.2300 | +1.0800 | +0.9300 |
| lockbox | market_structure_logistic | 1 | 0.100 | 1968 | 80.7% | 0.544 | 0.184 | 2 | 100.0% | 0.495 | +0.1623 | +1.0100 | +0.9900 | +0.9700 |
| lockbox | market_only_logistic | 1 | 0.200 | 1968 | 80.1% | 0.553 | 0.188 | 0 | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| lockbox | market_transition_kill_logistic | 1 | 0.020 | 1968 | 80.2% | 0.552 | 0.187 | 12 | 50.0% | 0.493 | +0.0766 | +0.0800 | -0.0400 | -0.1600 |
| lockbox | market_kill_momentum_logistic | 1 | 0.020 | 1968 | 79.8% | 0.555 | 0.189 | 5 | 20.0% | 0.274 | +0.0260 | -0.3700 | -0.4200 | -0.4700 |
| lockbox | market_score_logistic | 1 | 0.020 | 1968 | 82.3% | 0.525 | 0.177 | 12 | 33.3% | 0.372 | +0.0263 | -0.4600 | -0.5800 | -0.7000 |
| walk_forward | market_transition_nw_kill_logistic | 5 | 0.020 | 2627 | 82.7% | 0.474 | 0.156 | 22 | 82.5% | 0.611 | +0.0429 | +3.8200 | +3.6000 | +3.3800 |
| walk_forward | market_transition_catchup_logistic | 5 | 0.020 | 2627 | 82.7% | 0.475 | 0.156 | 25 | 72.7% | 0.564 | +0.0384 | +3.1400 | +2.8900 | +2.6400 |
| walk_forward | market_transition_kill_logistic | 5 | 0.020 | 2627 | 82.5% | 0.476 | 0.156 | 19 | 69.0% | 0.546 | +0.0500 | +1.7600 | +1.5700 | +1.3800 |
| walk_forward | market_transition_nw_logistic | 5 | 0.020 | 2627 | 82.6% | 0.475 | 0.156 | 21 | 66.0% | 0.550 | +0.0694 | +1.6100 | +1.4000 | +1.1900 |
| walk_forward | market_momentum_logistic | 5 | 0.020 | 2627 | 83.8% | 0.461 | 0.151 | 24 | 48.9% | 0.439 | +0.0546 | +0.9300 | +0.6900 | +0.4500 |
| walk_forward | market_nw_kill_momentum_logistic | 5 | 0.080 | 2627 | 84.2% | 0.459 | 0.150 | 21 | 51.7% | 0.475 | +0.0934 | +0.8500 | +0.6400 | +0.4300 |
| walk_forward | market_gettoplive_logistic | 5 | 0.100 | 2627 | 83.5% | 0.461 | 0.153 | 13 | 66.7% | 0.574 | +0.1417 | +0.5200 | +0.3900 | +0.2600 |
| walk_forward | market_nw_logistic | 5 | 0.050 | 2627 | 83.0% | 0.467 | 0.155 | 20 | 55.0% | 0.563 | +0.0882 | +0.4600 | +0.2600 | +0.0600 |
| walk_forward | market_score_logistic | 5 | 0.020 | 2627 | 82.3% | 0.477 | 0.157 | 23 | 54.6% | 0.521 | +0.0266 | -0.1200 | -0.3500 | -0.5800 |
| walk_forward | market_only_logistic | 5 | 0.200 | 2627 | 82.4% | 0.477 | 0.157 | 7 | 71.4% | 0.767 | +0.0280 | -0.3700 | -0.4400 | -0.5100 |
| walk_forward | market_structure_logistic | 5 | 0.020 | 2627 | 82.6% | 0.477 | 0.156 | 9 | 56.2% | 0.552 | +0.1402 | -0.4200 | -0.5100 | -0.6000 |
| walk_forward | market_kill_momentum_logistic | 5 | 0.020 | 2627 | 82.7% | 0.476 | 0.156 | 19 | 41.7% | 0.502 | +0.0307 | -1.2200 | -1.4100 | -1.6000 |

## Model Summary Verdicts

| stage | model_name | folds | pred_rows | auc | trade_trades | trade_win_rate | trade_total_pnl_slip_1c | trade_total_pnl_slip_2c | folds_with_trades | folds_positive_1c | folds_positive_2c | win_rate_ci_low | win_rate_ci_high | uncertainty_reason | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_nw_kill_momentum_logistic | 1 | 1968 | 82.9% | 9 | 77.8% | +2.7100 | +2.6200 | 1 | 1 | 1 | 45.3% | 93.7% | ci_low_not_above_breakeven | research_only |
| lockbox | market_momentum_logistic | 1 | 1968 | 83.1% | 8 | 75.0% | +2.4200 | +2.3400 | 1 | 1 | 1 | 40.9% | 92.9% | ci_low_not_above_breakeven | research_only |
| lockbox | market_gettoplive_logistic | 1 | 1968 | 84.3% | 12 | 75.0% | +2.3300 | +2.2100 | 1 | 1 | 1 | 46.8% | 91.1% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_nw_kill_logistic | 1 | 1968 | 80.6% | 16 | 68.8% | +1.8400 | +1.6800 | 1 | 1 | 1 | 44.4% | 85.8% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_nw_logistic | 1 | 1968 | 80.5% | 13 | 69.2% | +1.5200 | +1.3900 | 1 | 1 | 1 | 42.4% | 87.3% | ci_low_not_above_breakeven | research_only |
| lockbox | market_nw_logistic | 1 | 1968 | 83.8% | 5 | 60.0% | +1.1500 | +1.1000 | 1 | 1 | 1 | 23.1% | 88.2% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_catchup_logistic | 1 | 1968 | 80.6% | 15 | 66.7% | +1.0800 | +0.9300 | 1 | 1 | 1 | 41.7% | 84.8% | ci_low_not_above_breakeven | research_only |
| lockbox | market_structure_logistic | 1 | 1968 | 80.7% | 2 | 100.0% | +0.9900 | +0.9700 | 1 | 1 | 1 | 34.2% | 100.0% | ci_low_not_above_breakeven | research_only |
| lockbox | market_only_logistic | 1 | 1968 | 80.1% | 0 | n/a | +0.0000 | +0.0000 | 0 | 0 | 0 | n/a | n/a | no_trades | reject |
| lockbox | market_transition_kill_logistic | 1 | 1968 | 80.2% | 12 | 50.0% | -0.0400 | -0.1600 | 1 | 0 | 0 | 25.4% | 74.6% | ci_low_not_above_breakeven | reject |
| lockbox | market_kill_momentum_logistic | 1 | 1968 | 79.8% | 5 | 20.0% | -0.4200 | -0.4700 | 1 | 0 | 0 | 3.6% | 62.4% | ci_low_not_above_breakeven | reject |
| lockbox | market_score_logistic | 1 | 1968 | 82.3% | 12 | 33.3% | -0.5800 | -0.7000 | 1 | 0 | 0 | 13.8% | 60.9% | ci_low_not_above_breakeven | reject |
| walk_forward | market_transition_nw_kill_logistic | 5 | 2627 | 82.7% | 22 | 82.5% | +3.6000 | +3.3800 | 4 | 4 | 4 | 56.6% | 89.9% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_catchup_logistic | 5 | 2627 | 82.7% | 25 | 72.7% | +2.8900 | +2.6400 | 5 | 4 | 4 | 48.4% | 82.8% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_kill_logistic | 5 | 2627 | 82.5% | 19 | 69.0% | +1.5700 | +1.3800 | 5 | 3 | 3 | 36.3% | 76.9% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_nw_logistic | 5 | 2627 | 82.6% | 21 | 66.0% | +1.4000 | +1.1900 | 5 | 4 | 4 | 40.9% | 79.2% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_momentum_logistic | 5 | 2627 | 83.8% | 24 | 48.9% | +0.6900 | +0.4500 | 4 | 3 | 3 | 31.4% | 68.6% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_nw_kill_momentum_logistic | 5 | 2627 | 84.2% | 21 | 51.7% | +0.6400 | +0.4300 | 4 | 3 | 3 | 32.4% | 71.7% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_gettoplive_logistic | 5 | 2627 | 83.5% | 13 | 66.7% | +0.3900 | +0.2600 | 4 | 3 | 3 | 35.5% | 82.3% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_nw_logistic | 5 | 2627 | 83.0% | 20 | 55.0% | +0.2600 | +0.0600 | 5 | 2 | 2 | 38.7% | 78.1% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_score_logistic | 5 | 2627 | 82.3% | 23 | 54.6% | -0.3500 | -0.5800 | 5 | 3 | 3 | 33.0% | 70.8% | ci_low_not_above_breakeven | reject |
| walk_forward | market_only_logistic | 5 | 2627 | 82.4% | 7 | 71.4% | -0.4400 | -0.5100 | 1 | 0 | 0 | 35.9% | 91.8% | ci_low_not_above_breakeven | reject |
| walk_forward | market_structure_logistic | 5 | 2627 | 82.6% | 9 | 56.2% | -0.5100 | -0.6000 | 4 | 1 | 1 | 26.7% | 81.1% | ci_low_not_above_breakeven | reject |
| walk_forward | market_kill_momentum_logistic | 5 | 2627 | 82.7% | 19 | 41.7% | -1.4100 | -1.6000 | 4 | 1 | 1 | 27.3% | 68.3% | ci_low_not_above_breakeven | reject |

## Fold Robustness

| model_name | folds | folds_with_trades | folds_positive_raw | folds_positive_1c | folds_positive_2c | total_trades | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| market_transition_nw_kill_logistic | 5 | 4 | 4 | 4 | 4 | 22 | +3.8200 | +3.6000 | +3.3800 |
| market_transition_catchup_logistic | 5 | 5 | 4 | 4 | 4 | 25 | +3.1400 | +2.8900 | +2.6400 |
| market_transition_kill_logistic | 5 | 5 | 3 | 3 | 3 | 19 | +1.7600 | +1.5700 | +1.3800 |
| market_transition_nw_logistic | 5 | 5 | 4 | 4 | 4 | 21 | +1.6100 | +1.4000 | +1.1900 |
| market_momentum_logistic | 5 | 4 | 3 | 3 | 3 | 24 | +0.9300 | +0.6900 | +0.4500 |
| market_nw_kill_momentum_logistic | 5 | 4 | 3 | 3 | 3 | 21 | +0.8500 | +0.6400 | +0.4300 |
| market_gettoplive_logistic | 5 | 4 | 3 | 3 | 3 | 13 | +0.5200 | +0.3900 | +0.2600 |
| market_nw_logistic | 5 | 5 | 2 | 2 | 2 | 20 | +0.4600 | +0.2600 | +0.0600 |
| market_score_logistic | 5 | 5 | 3 | 3 | 3 | 23 | -0.1200 | -0.3500 | -0.5800 |
| market_only_logistic | 5 | 1 | 0 | 0 | 0 | 7 | -0.3700 | -0.4400 | -0.5100 |
| market_structure_logistic | 5 | 4 | 1 | 1 | 1 | 9 | -0.4200 | -0.5100 | -0.6000 |
| market_kill_momentum_logistic | 5 | 4 | 1 | 1 | 1 | 19 | -1.2200 | -1.4100 | -1.6000 |

## Trade Win-Rate Uncertainty

| stage | model_name | trades | wins | win_rate | win_rate_ci_low | win_rate_ci_high | avg_ask | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_nw_kill_momentum_logistic | 9 | 7 | 77.8% | 45.3% | 93.7% | 0.467 | +2.8000 | +2.7100 | +2.6200 |
| lockbox | market_momentum_logistic | 8 | 6 | 75.0% | 40.9% | 92.9% | 0.438 | +2.5000 | +2.4200 | +2.3400 |
| lockbox | market_gettoplive_logistic | 12 | 9 | 75.0% | 46.8% | 91.1% | 0.546 | +2.4500 | +2.3300 | +2.2100 |
| lockbox | market_transition_nw_kill_logistic | 16 | 11 | 68.8% | 44.4% | 85.8% | 0.562 | +2.0000 | +1.8400 | +1.6800 |
| lockbox | market_transition_nw_logistic | 13 | 9 | 69.2% | 42.4% | 87.3% | 0.565 | +1.6500 | +1.5200 | +1.3900 |
| lockbox | market_nw_logistic | 5 | 3 | 60.0% | 23.1% | 88.2% | 0.360 | +1.2000 | +1.1500 | +1.1000 |
| lockbox | market_transition_catchup_logistic | 15 | 10 | 66.7% | 41.7% | 84.8% | 0.585 | +1.2300 | +1.0800 | +0.9300 |
| lockbox | market_structure_logistic | 2 | 2 | 100.0% | 34.2% | 100.0% | 0.495 | +1.0100 | +0.9900 | +0.9700 |
| lockbox | market_transition_kill_logistic | 12 | 6 | 50.0% | 25.4% | 74.6% | 0.493 | +0.0800 | -0.0400 | -0.1600 |
| lockbox | market_kill_momentum_logistic | 5 | 1 | 20.0% | 3.6% | 62.4% | 0.274 | -0.3700 | -0.4200 | -0.4700 |
| lockbox | market_score_logistic | 12 | 4 | 33.3% | 13.8% | 60.9% | 0.372 | -0.4600 | -0.5800 | -0.7000 |
| walk_forward | market_transition_nw_kill_logistic | 22 | 17 | 77.3% | 56.6% | 89.9% | 0.599 | +3.8200 | +3.6000 | +3.3800 |
| walk_forward | market_transition_catchup_logistic | 25 | 17 | 68.0% | 48.4% | 82.8% | 0.554 | +3.1400 | +2.8900 | +2.6400 |
| walk_forward | market_transition_kill_logistic | 19 | 11 | 57.9% | 36.3% | 76.9% | 0.486 | +1.7600 | +1.5700 | +1.3800 |
| walk_forward | market_transition_nw_logistic | 21 | 13 | 61.9% | 40.9% | 79.2% | 0.542 | +1.6100 | +1.4000 | +1.1900 |
| walk_forward | market_momentum_logistic | 24 | 12 | 50.0% | 31.4% | 68.6% | 0.461 | +0.9300 | +0.6900 | +0.4500 |
| walk_forward | market_nw_kill_momentum_logistic | 21 | 11 | 52.4% | 32.4% | 71.7% | 0.483 | +0.8500 | +0.6400 | +0.4300 |
| walk_forward | market_gettoplive_logistic | 13 | 8 | 61.5% | 35.5% | 82.3% | 0.575 | +0.5200 | +0.3900 | +0.2600 |
| walk_forward | market_nw_logistic | 20 | 12 | 60.0% | 38.7% | 78.1% | 0.577 | +0.4600 | +0.2600 | +0.0600 |
| walk_forward | market_score_logistic | 23 | 12 | 52.2% | 33.0% | 70.8% | 0.527 | -0.1200 | -0.3500 | -0.5800 |
| walk_forward | market_only_logistic | 7 | 5 | 71.4% | 35.9% | 91.8% | 0.767 | -0.3700 | -0.4400 | -0.5100 |
| walk_forward | market_structure_logistic | 9 | 5 | 55.6% | 26.7% | 81.1% | 0.602 | -0.4200 | -0.5100 | -0.6000 |
| walk_forward | market_kill_momentum_logistic | 19 | 9 | 47.4% | 27.3% | 68.3% | 0.538 | -1.2200 | -1.4100 | -1.6000 |

## CLV Event Study At 60s

| event | rows | matches | avg_ask | avg_clv_mid | avg_clv_bid | avg_future_delay_s | positive_bid_clv_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| side_nw_crosses_5000 | 56 | 55 | 0.774 | +0.0102 | -0.0168 | 62.268 | 37.5% |
| side_mom_100_ge_5000 | 34 | 33 | 0.695 | -0.0022 | -0.0403 | 61.971 | 41.2% |
| side_nw_crosses_8000 | 51 | 50 | 0.813 | -0.0111 | -0.0457 | 62.549 | 31.4% |
| side_mom_100_ge_3000 | 61 | 59 | 0.710 | -0.0262 | -0.0685 | 61.525 | 32.8% |
| building_state_changes | 71 | 67 | 0.406 | -0.0399 | -0.0704 | 61.761 | 12.7% |
| score_changes | 69 | 66 | 0.402 | -0.0465 | -0.0777 | 61.667 | 11.6% |

## Transition Entry-Timing Event Study

| entry_timing | trades | matches | avg_ask | settlement_win_rate | raw_pnl | pnl_1c | pnl_2c | future_bid_clv_15s | future_bid_clv_30s | future_bid_clv_60s | future_bid_clv_120s | positive_bid_clv_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_nw_change | 39 | 38 | 0.385 | 38.5% | -0.0300 | -0.4200 | -0.8100 | -0.0620 | -0.0767 | -0.0964 | -0.0682 | 18.2% |
| score_then_nw_catchup | 27 | 26 | 0.384 | 37.0% | -0.3800 | -0.6500 | -0.9200 | -0.0267 | -0.0663 | -0.0808 | -0.0710 | 7.7% |
| nw_then_score_catchup | 93 | 87 | 0.378 | 33.3% | -4.1700 | -5.1000 | -6.0300 | -0.0832 | -0.0809 | -0.0629 | -0.1057 | 9.6% |
| post_transition_close | 102 | 94 | 0.398 | 33.3% | -6.5900 | -7.6100 | -8.6300 | -0.0817 | -0.0816 | -0.0615 | -0.0867 | 8.5% |
| score_nw_same_snapshot | 107 | 100 | 0.403 | 32.7% | -8.1700 | -9.2400 | -10.3100 | -0.0560 | -0.0968 | -0.0857 | -0.0824 | 18.8% |
| confirmed_transition | 111 | 103 | 0.458 | 36.9% | -9.8800 | -10.9900 | -12.1000 | -0.0558 | -0.0657 | -0.0757 | -0.0628 | 21.5% |
| first_score_change | 110 | 102 | 0.408 | 30.9% | -10.8500 | -11.9500 | -13.0500 | -0.0529 | -0.0741 | -0.0700 | -0.0790 | 14.7% |

## Trade PnL Concentration

By market bucket:

| stage | model_name | label_market_bucket | trades | matches | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_gettoplive_logistic | MAP_WINNER | 9 | 9 | 77.8% | +1.8100 | +1.7200 | +1.6300 |
| lockbox | market_gettoplive_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6400 | +0.6100 | +0.5800 |
| lockbox | market_kill_momentum_logistic | MAP_WINNER | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 0.0% | -1.1800 | -1.2200 | -1.2600 |
| lockbox | market_momentum_logistic | MAP_WINNER | 5 | 5 | 80.0% | +1.8600 | +1.8100 | +1.7600 |
| lockbox | market_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6400 | +0.6100 | +0.5800 |
| lockbox | market_nw_kill_momentum_logistic | MAP_WINNER | 6 | 6 | 83.3% | +2.1600 | +2.1000 | +2.0400 |
| lockbox | market_nw_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6400 | +0.6100 | +0.5800 |
| lockbox | market_nw_logistic | MAP_WINNER | 3 | 3 | 66.7% | +0.7300 | +0.7000 | +0.6700 |
| lockbox | market_nw_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 50.0% | +0.4700 | +0.4500 | +0.4300 |
| lockbox | market_score_logistic | MAP_WINNER | 8 | 8 | 50.0% | +0.6700 | +0.5900 | +0.5100 |
| lockbox | market_score_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 0.0% | -1.1300 | -1.1700 | -1.2100 |
| lockbox | market_structure_logistic | MAP_WINNER | 2 | 2 | 100.0% | +1.0100 | +0.9900 | +0.9700 |
| lockbox | market_transition_catchup_logistic | MAP_WINNER | 11 | 11 | 72.7% | +1.7600 | +1.6500 | +1.5400 |
| lockbox | market_transition_catchup_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 50.0% | -0.5300 | -0.5700 | -0.6100 |
| lockbox | market_transition_kill_logistic | MAP_WINNER | 8 | 8 | 50.0% | +0.6100 | +0.5300 | +0.4500 |
| lockbox | market_transition_kill_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 50.0% | -0.5300 | -0.5700 | -0.6100 |
| lockbox | market_transition_nw_kill_logistic | MAP_WINNER | 12 | 12 | 75.0% | +2.5300 | +2.4100 | +2.2900 |
| lockbox | market_transition_nw_kill_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 50.0% | -0.5300 | -0.5700 | -0.6100 |
| lockbox | market_transition_nw_logistic | MAP_WINNER | 10 | 10 | 70.0% | +1.0700 | +0.9700 | +0.8700 |
| lockbox | market_transition_nw_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.5800 | +0.5500 | +0.5200 |
| walk_forward | market_gettoplive_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 75.0% | +1.0200 | +0.9800 | +0.9400 |
| walk_forward | market_gettoplive_logistic | MAP_WINNER | 9 | 9 | 55.6% | -0.5000 | -0.5900 | -0.6800 |
| walk_forward | market_kill_momentum_logistic | MAP_WINNER | 15 | 15 | 60.0% | -0.2400 | -0.3900 | -0.5400 |
| walk_forward | market_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 0.0% | -0.9800 | -1.0200 | -1.0600 |
| walk_forward | market_momentum_logistic | MAP_WINNER | 19 | 19 | 52.6% | +1.2200 | +1.0300 | +0.8400 |
| walk_forward | market_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 5 | 5 | 40.0% | -0.2900 | -0.3400 | -0.3900 |
| walk_forward | market_nw_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 5 | 5 | 60.0% | +0.7800 | +0.7300 | +0.6800 |
| walk_forward | market_nw_kill_momentum_logistic | MAP_WINNER | 16 | 16 | 50.0% | +0.0700 | -0.0900 | -0.2500 |
| walk_forward | market_nw_logistic | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 75.0% | +1.2200 | +1.1800 | +1.1400 |
| walk_forward | market_nw_logistic | MAP_WINNER | 16 | 16 | 56.2% | -0.7600 | -0.9200 | -1.0800 |
| walk_forward | market_only_logistic | MAP_WINNER | 6 | 6 | 83.3% | +0.0300 | -0.0300 | -0.0900 |
| walk_forward | market_only_logistic | MATCH_WINNER_GAME3_PROXY | 1 | 1 | 0.0% | -0.4000 | -0.4100 | -0.4200 |
| walk_forward | market_score_logistic | MAP_WINNER | 20 | 20 | 55.0% | +0.0800 | -0.1200 | -0.3200 |
| walk_forward | market_score_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 33.3% | -0.2000 | -0.2300 | -0.2600 |
| walk_forward | market_structure_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 33.3% | +0.1200 | +0.0900 | +0.0600 |
| walk_forward | market_structure_logistic | MAP_WINNER | 6 | 6 | 66.7% | -0.5400 | -0.6000 | -0.6600 |
| walk_forward | market_transition_catchup_logistic | MAP_WINNER | 22 | 22 | 72.7% | +3.0800 | +2.8600 | +2.6400 |
| walk_forward | market_transition_catchup_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 33.3% | +0.0600 | +0.0300 | -0.0000 |
| walk_forward | market_transition_kill_logistic | MAP_WINNER | 17 | 17 | 58.8% | +1.4400 | +1.2700 | +1.1000 |
| walk_forward | market_transition_kill_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 50.0% | +0.3200 | +0.3000 | +0.2800 |
| walk_forward | market_transition_nw_kill_logistic | MAP_WINNER | 20 | 20 | 80.0% | +3.6900 | +3.4900 | +3.2900 |
| walk_forward | market_transition_nw_kill_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 50.0% | +0.1300 | +0.1100 | +0.0900 |
| walk_forward | market_transition_nw_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.8600 | +0.8300 | +0.8000 |
| walk_forward | market_transition_nw_logistic | MAP_WINNER | 18 | 18 | 61.1% | +0.7500 | +0.5700 | +0.3900 |

Largest match contributions by absolute 1c-slippage PnL:

| stage | model_name | match_id | trades | buckets | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_gettoplive_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_gettoplive_logistic | 8837869969 | 1 | 1 | 0.0% | -0.6500 | -0.6600 | -0.6700 |
| lockbox | market_gettoplive_logistic | 8837288943 | 2 | 2 | 0.0% | -0.6200 | -0.6400 | -0.6600 |
| lockbox | market_gettoplive_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_gettoplive_logistic | 8837725916 | 1 | 1 | 100.0% | +0.5900 | +0.5800 | +0.5700 |
| lockbox | market_gettoplive_logistic | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_gettoplive_logistic | 8836897842 | 1 | 1 | 100.0% | +0.3700 | +0.3600 | +0.3500 |
| lockbox | market_gettoplive_logistic | 8839123109 | 1 | 1 | 100.0% | +0.2800 | +0.2700 | +0.2600 |
| lockbox | market_gettoplive_logistic | 8837690631 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |
| lockbox | market_gettoplive_logistic | 8836916511 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_gettoplive_logistic | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_kill_momentum_logistic | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_kill_momentum_logistic | 8837052943 | 1 | 1 | 0.0% | -0.7300 | -0.7400 | -0.7500 |
| lockbox | market_kill_momentum_logistic | 8837692542 | 1 | 1 | 0.0% | -0.2900 | -0.3000 | -0.3100 |
| lockbox | market_kill_momentum_logistic | 8837724891 | 1 | 1 | 0.0% | -0.1000 | -0.1100 | -0.1200 |
| lockbox | market_kill_momentum_logistic | 8837288943 | 1 | 1 | 0.0% | -0.0600 | -0.0700 | -0.0800 |
| lockbox | market_momentum_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_momentum_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_momentum_logistic | 8837725916 | 1 | 1 | 100.0% | +0.5900 | +0.5800 | +0.5700 |
| lockbox | market_momentum_logistic | 8837288943 | 2 | 2 | 0.0% | -0.5300 | -0.5500 | -0.5700 |
| lockbox | market_momentum_logistic | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_momentum_logistic | 8836897842 | 1 | 1 | 100.0% | +0.3700 | +0.3600 | +0.3500 |
| lockbox | market_momentum_logistic | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_kill_momentum_logistic | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_nw_kill_momentum_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_nw_kill_momentum_logistic | 8837288943 | 2 | 2 | 0.0% | -0.6200 | -0.6400 | -0.6600 |
| lockbox | market_nw_kill_momentum_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_nw_kill_momentum_logistic | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_nw_kill_momentum_logistic | 8836897842 | 1 | 1 | 100.0% | +0.3700 | +0.3600 | +0.3500 |
| lockbox | market_nw_kill_momentum_logistic | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_kill_momentum_logistic | 8839123109 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_nw_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6700 | +0.6600 | +0.6500 |
| lockbox | market_nw_logistic | 8837288943 | 2 | 2 | 0.0% | -0.5900 | -0.6100 | -0.6300 |
| lockbox | market_nw_logistic | 8836897842 | 1 | 1 | 100.0% | +0.3900 | +0.3800 | +0.3700 |
| lockbox | market_score_logistic | 8837725916 | 1 | 1 | 0.0% | -0.7800 | -0.7900 | -0.8000 |
| lockbox | market_score_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_score_logistic | 8837869969 | 1 | 1 | 100.0% | +0.7100 | +0.7000 | +0.6900 |
| lockbox | market_score_logistic | 8837288943 | 2 | 2 | 0.0% | -0.5200 | -0.5400 | -0.5600 |
| lockbox | market_score_logistic | 8836897842 | 1 | 1 | 100.0% | +0.3900 | +0.3800 | +0.3700 |
| lockbox | market_score_logistic | 8837052943 | 2 | 2 | 50.0% | -0.3100 | -0.3300 | -0.3500 |
| lockbox | market_score_logistic | 8837692542 | 1 | 1 | 0.0% | -0.2900 | -0.3000 | -0.3100 |
| lockbox | market_score_logistic | 8839123109 | 1 | 1 | 0.0% | -0.1500 | -0.1600 | -0.1700 |
| lockbox | market_score_logistic | 8837560468 | 1 | 1 | 0.0% | -0.1400 | -0.1500 | -0.1600 |
| lockbox | market_score_logistic | 8837724891 | 1 | 1 | 0.0% | -0.1000 | -0.1100 | -0.1200 |
| lockbox | market_structure_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_structure_logistic | 8836897842 | 1 | 1 | 100.0% | +0.2800 | +0.2700 | +0.2600 |
| lockbox | market_transition_catchup_logistic | 8837869969 | 1 | 1 | 0.0% | -0.7100 | -0.7200 | -0.7300 |
| lockbox | market_transition_catchup_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_transition_catchup_logistic | 8837288943 | 2 | 2 | 0.0% | -0.6200 | -0.6400 | -0.6600 |
| lockbox | market_transition_catchup_logistic | 8837889126 | 1 | 1 | 100.0% | +0.6000 | +0.5900 | +0.5800 |
| lockbox | market_transition_catchup_logistic | 8837725916 | 1 | 1 | 100.0% | +0.3800 | +0.3700 | +0.3600 |
| lockbox | market_transition_catchup_logistic | 8836897842 | 1 | 1 | 100.0% | +0.2700 | +0.2600 | +0.2500 |
| lockbox | market_transition_catchup_logistic | 8837052943 | 2 | 2 | 50.0% | -0.2200 | -0.2400 | -0.2600 |
| lockbox | market_transition_catchup_logistic | 8837692542 | 1 | 1 | 100.0% | +0.2500 | +0.2400 | +0.2300 |
| lockbox | market_transition_catchup_logistic | 8837690631 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |
| lockbox | market_transition_catchup_logistic | 8836916511 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_transition_catchup_logistic | 8839123109 | 1 | 1 | 100.0% | +0.1600 | +0.1500 | +0.1400 |
| lockbox | market_transition_catchup_logistic | 8837827200 | 1 | 1 | 0.0% | -0.0900 | -0.1000 | -0.1100 |
| lockbox | market_transition_catchup_logistic | 8837724891 | 1 | 1 | 100.0% | +0.0700 | +0.0600 | +0.0500 |
| lockbox | market_transition_kill_logistic | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_transition_kill_logistic | 8837869969 | 1 | 1 | 0.0% | -0.7100 | -0.7200 | -0.7300 |
| lockbox | market_transition_kill_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_transition_kill_logistic | 8837288943 | 2 | 2 | 0.0% | -0.6200 | -0.6400 | -0.6600 |
| lockbox | market_transition_kill_logistic | 8836916511 | 1 | 1 | 0.0% | -0.3000 | -0.3100 | -0.3200 |
| lockbox | market_transition_kill_logistic | 8837052943 | 2 | 2 | 50.0% | -0.2200 | -0.2400 | -0.2600 |
| lockbox | market_transition_kill_logistic | 8837692542 | 1 | 1 | 100.0% | +0.2500 | +0.2400 | +0.2300 |
| lockbox | market_transition_kill_logistic | 8839123109 | 1 | 1 | 100.0% | +0.1600 | +0.1500 | +0.1400 |
| lockbox | market_transition_kill_logistic | 8837827200 | 1 | 1 | 0.0% | -0.0900 | -0.1000 | -0.1100 |
| lockbox | market_transition_kill_logistic | 8837724891 | 1 | 1 | 100.0% | +0.0700 | +0.0600 | +0.0500 |
| lockbox | market_transition_nw_kill_logistic | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_transition_nw_kill_logistic | 8837869969 | 1 | 1 | 0.0% | -0.7100 | -0.7200 | -0.7300 |
| lockbox | market_transition_nw_kill_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_transition_nw_kill_logistic | 8837288943 | 2 | 2 | 0.0% | -0.6200 | -0.6400 | -0.6600 |
| lockbox | market_transition_nw_kill_logistic | 8837889126 | 1 | 1 | 100.0% | +0.6000 | +0.5900 | +0.5800 |
| lockbox | market_transition_nw_kill_logistic | 8837519479 | 1 | 1 | 100.0% | +0.3000 | +0.2900 | +0.2800 |
| lockbox | market_transition_nw_kill_logistic | 8836897842 | 1 | 1 | 100.0% | +0.2700 | +0.2600 | +0.2500 |
| lockbox | market_transition_nw_kill_logistic | 8837052943 | 2 | 2 | 50.0% | -0.2200 | -0.2400 | -0.2600 |
| lockbox | market_transition_nw_kill_logistic | 8837692542 | 1 | 1 | 100.0% | +0.2500 | +0.2400 | +0.2300 |
| lockbox | market_transition_nw_kill_logistic | 8837690631 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |

By league:

| stage | model_name | league_id | trades | matches | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_gettoplive_logistic | 19699 | 9 | 8 | 77.8% | +2.0900 | +2.0000 | +1.9100 |
| lockbox | market_gettoplive_logistic | 19101 | 3 | 3 | 66.7% | +0.3600 | +0.3300 | +0.3000 |
| lockbox | market_kill_momentum_logistic | 19699 | 5 | 5 | 20.0% | -0.3700 | -0.4200 | -0.4700 |
| lockbox | market_momentum_logistic | 19699 | 7 | 6 | 71.4% | +1.7700 | +1.7000 | +1.6300 |
| lockbox | market_momentum_logistic | 19101 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_nw_kill_momentum_logistic | 19699 | 7 | 6 | 71.4% | +1.9000 | +1.8300 | +1.7600 |
| lockbox | market_nw_kill_momentum_logistic | 19101 | 2 | 2 | 100.0% | +0.9000 | +0.8800 | +0.8600 |
| lockbox | market_nw_logistic | 19101 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_nw_logistic | 19699 | 4 | 3 | 50.0% | +0.4700 | +0.4300 | +0.3900 |
| lockbox | market_score_logistic | 19101 | 3 | 3 | 66.7% | +1.2900 | +1.2600 | +1.2300 |
| lockbox | market_score_logistic | 19699 | 9 | 7 | 22.2% | -1.7500 | -1.8400 | -1.9300 |
| lockbox | market_structure_logistic | 19101 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_structure_logistic | 19699 | 1 | 1 | 100.0% | +0.2800 | +0.2700 | +0.2600 |
| lockbox | market_transition_catchup_logistic | 19699 | 12 | 10 | 66.7% | +1.0500 | +0.9300 | +0.8100 |
| lockbox | market_transition_catchup_logistic | 19101 | 3 | 3 | 66.7% | +0.1800 | +0.1500 | +0.1200 |
| lockbox | market_transition_kill_logistic | 19101 | 3 | 3 | 66.7% | +0.1800 | +0.1500 | +0.1200 |
| lockbox | market_transition_kill_logistic | 19699 | 9 | 7 | 44.4% | -0.1000 | -0.1900 | -0.2800 |
| lockbox | market_transition_nw_kill_logistic | 19699 | 13 | 11 | 69.2% | +1.7800 | +1.6500 | +1.5200 |
| lockbox | market_transition_nw_kill_logistic | 19101 | 3 | 3 | 66.7% | +0.2200 | +0.1900 | +0.1600 |
| lockbox | market_transition_nw_logistic | 19699 | 10 | 8 | 70.0% | +1.4700 | +1.3700 | +1.2700 |
| lockbox | market_transition_nw_logistic | 19101 | 3 | 3 | 66.7% | +0.1800 | +0.1500 | +0.1200 |
| walk_forward | market_gettoplive_logistic | 19699 | 13 | 12 | 61.5% | +0.5200 | +0.3900 | +0.2600 |
| walk_forward | market_kill_momentum_logistic | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| walk_forward | market_kill_momentum_logistic | 19699 | 18 | 16 | 50.0% | -0.7200 | -0.9000 | -1.0800 |
| walk_forward | market_momentum_logistic | 19699 | 24 | 22 | 50.0% | +0.9300 | +0.6900 | +0.4500 |
| walk_forward | market_nw_kill_momentum_logistic | 19699 | 21 | 20 | 52.4% | +0.8500 | +0.6400 | +0.4300 |
| walk_forward | market_nw_logistic | 19699 | 19 | 17 | 63.2% | +0.8600 | +0.6700 | +0.4800 |
| walk_forward | market_nw_logistic | 19101 | 1 | 1 | 0.0% | -0.4000 | -0.4100 | -0.4200 |
| walk_forward | market_only_logistic | 19699 | 7 | 6 | 71.4% | -0.3700 | -0.4400 | -0.5100 |
| walk_forward | market_score_logistic | 19699 | 22 | 20 | 54.5% | +0.3800 | +0.1600 | -0.0600 |
| walk_forward | market_score_logistic | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| walk_forward | market_structure_logistic | 19699 | 9 | 9 | 55.6% | -0.4200 | -0.5100 | -0.6000 |
| walk_forward | market_transition_catchup_logistic | 19699 | 24 | 23 | 66.7% | +2.7000 | +2.4600 | +2.2200 |
| walk_forward | market_transition_catchup_logistic | 19101 | 1 | 1 | 100.0% | +0.4400 | +0.4300 | +0.4200 |
| walk_forward | market_transition_kill_logistic | 19699 | 18 | 18 | 61.1% | +2.2800 | +2.1000 | +1.9200 |
| walk_forward | market_transition_kill_logistic | 19101 | 1 | 1 | 0.0% | -0.5200 | -0.5300 | -0.5400 |
| walk_forward | market_transition_nw_kill_logistic | 19699 | 22 | 21 | 77.3% | +3.8200 | +3.6000 | +3.3800 |
| walk_forward | market_transition_nw_logistic | 19699 | 20 | 20 | 65.0% | +1.8800 | +1.6800 | +1.4800 |
| walk_forward | market_transition_nw_logistic | 19101 | 1 | 1 | 0.0% | -0.2700 | -0.2800 | -0.2900 |

## Threshold Search

| stage | fold | model_name | threshold | trades | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | 0 | market_gettoplive_logistic | 0.020 | 21 | +2.0100 | +1.8000 | +1.5900 |
| lockbox | 0 | market_gettoplive_logistic | 0.050 | 17 | +1.7000 | +1.5300 | +1.3600 |
| lockbox | 0 | market_gettoplive_logistic | 0.080 | 15 | +3.1800 | +3.0300 | +2.8800 |
| lockbox | 0 | market_gettoplive_logistic | 0.100 | 13 | +2.3500 | +2.2200 | +2.0900 |
| lockbox | 0 | market_gettoplive_logistic | 0.120 | 12 | +2.7400 | +2.6200 | +2.5000 |
| lockbox | 0 | market_gettoplive_logistic | 0.150 | 9 | +1.8600 | +1.7700 | +1.6800 |
| lockbox | 0 | market_gettoplive_logistic | 0.200 | 4 | +0.6500 | +0.6100 | +0.5700 |
| lockbox | 0 | market_kill_momentum_logistic | 0.020 | 3 | +0.7800 | +0.7500 | +0.7200 |
| lockbox | 0 | market_kill_momentum_logistic | 0.050 | 1 | -0.4300 | -0.4400 | -0.4500 |
| lockbox | 0 | market_kill_momentum_logistic | 0.080 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_kill_momentum_logistic | 0.100 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_momentum_logistic | 0.020 | 21 | +2.0000 | +1.7900 | +1.5800 |
| lockbox | 0 | market_momentum_logistic | 0.050 | 18 | +2.4100 | +2.2300 | +2.0500 |
| lockbox | 0 | market_momentum_logistic | 0.080 | 16 | +2.8700 | +2.7100 | +2.5500 |
| lockbox | 0 | market_momentum_logistic | 0.100 | 14 | +3.8700 | +3.7300 | +3.5900 |
| lockbox | 0 | market_momentum_logistic | 0.120 | 12 | +2.6800 | +2.5600 | +2.4400 |
| lockbox | 0 | market_momentum_logistic | 0.150 | 7 | +0.9300 | +0.8600 | +0.7900 |
| lockbox | 0 | market_momentum_logistic | 0.200 | 4 | -0.3900 | -0.4300 | -0.4700 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.020 | 21 | +2.7500 | +2.5400 | +2.3300 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.050 | 18 | +3.4000 | +3.2200 | +3.0400 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.080 | 16 | +5.1700 | +5.0100 | +4.8500 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.100 | 15 | +4.2800 | +4.1300 | +3.9800 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.120 | 13 | +3.2200 | +3.0900 | +2.9600 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.150 | 9 | +2.3700 | +2.2800 | +2.1900 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.200 | 5 | +0.0200 | -0.0300 | -0.0800 |
| lockbox | 0 | market_nw_logistic | 0.020 | 19 | -0.6000 | -0.7900 | -0.9800 |
| lockbox | 0 | market_nw_logistic | 0.050 | 15 | +1.3000 | +1.1500 | +1.0000 |
| lockbox | 0 | market_nw_logistic | 0.080 | 11 | +0.3800 | +0.2700 | +0.1600 |
| lockbox | 0 | market_nw_logistic | 0.100 | 10 | +0.5000 | +0.4000 | +0.3000 |
| lockbox | 0 | market_nw_logistic | 0.120 | 9 | +1.3800 | +1.2900 | +1.2000 |
| lockbox | 0 | market_nw_logistic | 0.150 | 4 | +1.7100 | +1.6700 | +1.6300 |
| lockbox | 0 | market_nw_logistic | 0.200 | 3 | +1.4900 | +1.4600 | +1.4300 |
| lockbox | 0 | market_only_logistic | 0.020 | 1 | -0.4000 | -0.4100 | -0.4200 |
| lockbox | 0 | market_only_logistic | 0.050 | 1 | -0.4300 | -0.4400 | -0.4500 |
| lockbox | 0 | market_only_logistic | 0.080 | 1 | -0.4300 | -0.4400 | -0.4500 |
| lockbox | 0 | market_only_logistic | 0.100 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_score_logistic | 0.020 | 17 | +0.7300 | +0.5600 | +0.3900 |
| lockbox | 0 | market_score_logistic | 0.050 | 7 | -2.1600 | -2.2300 | -2.3000 |
| lockbox | 0 | market_score_logistic | 0.080 | 1 | -0.4300 | -0.4400 | -0.4500 |
| lockbox | 0 | market_score_logistic | 0.100 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_score_logistic | 0.120 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_score_logistic | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_score_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_structure_logistic | 0.020 | 11 | -0.0200 | -0.1300 | -0.2400 |
| lockbox | 0 | market_structure_logistic | 0.050 | 10 | +0.0200 | -0.0800 | -0.1800 |
| lockbox | 0 | market_structure_logistic | 0.080 | 4 | -0.6000 | -0.6400 | -0.6800 |
| lockbox | 0 | market_structure_logistic | 0.100 | 4 | +0.2200 | +0.1800 | +0.1400 |
| lockbox | 0 | market_structure_logistic | 0.120 | 3 | +0.0300 | +0.0000 | -0.0300 |
| lockbox | 0 | market_structure_logistic | 0.150 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_structure_logistic | 0.200 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_transition_catchup_logistic | 0.020 | 18 | +2.5000 | +2.3200 | +2.1400 |
| lockbox | 0 | market_transition_catchup_logistic | 0.050 | 14 | +0.7200 | +0.5800 | +0.4400 |
| lockbox | 0 | market_transition_catchup_logistic | 0.080 | 12 | +0.2600 | +0.1400 | +0.0200 |
| lockbox | 0 | market_transition_catchup_logistic | 0.100 | 11 | -1.3100 | -1.4200 | -1.5300 |
| lockbox | 0 | market_transition_catchup_logistic | 0.120 | 11 | -0.9100 | -1.0200 | -1.1300 |
| lockbox | 0 | market_transition_catchup_logistic | 0.150 | 10 | -0.1000 | -0.2000 | -0.3000 |
| lockbox | 0 | market_transition_catchup_logistic | 0.200 | 7 | +0.6800 | +0.6100 | +0.5400 |
| lockbox | 0 | market_transition_kill_logistic | 0.020 | 16 | +2.0200 | +1.8600 | +1.7000 |
| lockbox | 0 | market_transition_kill_logistic | 0.050 | 10 | -0.9400 | -1.0400 | -1.1400 |
| lockbox | 0 | market_transition_kill_logistic | 0.080 | 9 | +0.1900 | +0.1000 | +0.0100 |
| lockbox | 0 | market_transition_kill_logistic | 0.100 | 8 | -0.8400 | -0.9200 | -1.0000 |
| lockbox | 0 | market_transition_kill_logistic | 0.120 | 8 | -0.8400 | -0.9200 | -1.0000 |
| lockbox | 0 | market_transition_kill_logistic | 0.150 | 6 | +0.2600 | +0.2000 | +0.1400 |
| lockbox | 0 | market_transition_kill_logistic | 0.200 | 3 | +0.3400 | +0.3100 | +0.2800 |
| lockbox | 0 | market_transition_nw_kill_logistic | 0.020 | 18 | +3.1500 | +2.9700 | +2.7900 |
| lockbox | 0 | market_transition_nw_kill_logistic | 0.050 | 14 | +0.5800 | +0.4400 | +0.3000 |
| lockbox | 0 | market_transition_nw_kill_logistic | 0.080 | 13 | +0.7400 | +0.6100 | +0.4800 |
| lockbox | 0 | market_transition_nw_kill_logistic | 0.100 | 11 | +0.1700 | +0.0600 | -0.0500 |
| lockbox | 0 | market_transition_nw_kill_logistic | 0.120 | 11 | -1.8300 | -1.9400 | -2.0500 |
| lockbox | 0 | market_transition_nw_kill_logistic | 0.150 | 10 | -0.1000 | -0.2000 | -0.3000 |
| lockbox | 0 | market_transition_nw_kill_logistic | 0.200 | 7 | -0.1100 | -0.1800 | -0.2500 |
| lockbox | 0 | market_transition_nw_logistic | 0.020 | 17 | +0.1600 | -0.0100 | -0.1800 |
| lockbox | 0 | market_transition_nw_logistic | 0.050 | 15 | +1.8800 | +1.7300 | +1.5800 |
| lockbox | 0 | market_transition_nw_logistic | 0.080 | 11 | -1.3100 | -1.4200 | -1.5300 |
| lockbox | 0 | market_transition_nw_logistic | 0.100 | 11 | -0.4900 | -0.6000 | -0.7100 |
| lockbox | 0 | market_transition_nw_logistic | 0.120 | 11 | -1.8300 | -1.9400 | -2.0500 |
| lockbox | 0 | market_transition_nw_logistic | 0.150 | 10 | -0.3700 | -0.4700 | -0.5700 |
| lockbox | 0 | market_transition_nw_logistic | 0.200 | 7 | +1.2800 | +1.2100 | +1.1400 |
| walk_forward | 1 | market_gettoplive_logistic | 0.020 | 6 | -1.0500 | -1.1100 | -1.1700 |
| walk_forward | 1 | market_gettoplive_logistic | 0.050 | 4 | -1.5600 | -1.6000 | -1.6400 |
| walk_forward | 1 | market_gettoplive_logistic | 0.080 | 3 | +1.5800 | +1.5500 | +1.5200 |
| walk_forward | 1 | market_gettoplive_logistic | 0.100 | 3 | +1.6000 | +1.5700 | +1.5400 |
| walk_forward | 1 | market_gettoplive_logistic | 0.120 | 3 | -0.0300 | -0.0600 | -0.0900 |
| walk_forward | 1 | market_gettoplive_logistic | 0.150 | 3 | +0.0000 | -0.0300 | -0.0600 |
| walk_forward | 1 | market_gettoplive_logistic | 0.200 | 1 | -0.5500 | -0.5600 | -0.5700 |
| walk_forward | 1 | market_kill_momentum_logistic | 0.020 | 7 | -0.6800 | -0.7500 | -0.8200 |
| walk_forward | 1 | market_kill_momentum_logistic | 0.050 | 3 | -1.0600 | -1.0900 | -1.1200 |
| walk_forward | 1 | market_kill_momentum_logistic | 0.080 | 3 | -0.8800 | -0.9100 | -0.9400 |
| walk_forward | 1 | market_kill_momentum_logistic | 0.100 | 2 | -0.7800 | -0.8000 | -0.8200 |
| walk_forward | 1 | market_kill_momentum_logistic | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| walk_forward | 1 | market_kill_momentum_logistic | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| walk_forward | 1 | market_kill_momentum_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| walk_forward | 1 | market_momentum_logistic | 0.020 | 7 | -1.9500 | -2.0200 | -2.0900 |
| walk_forward | 1 | market_momentum_logistic | 0.050 | 4 | -0.5600 | -0.6000 | -0.6400 |
| walk_forward | 1 | market_momentum_logistic | 0.080 | 4 | -1.3200 | -1.3600 | -1.4000 |
| walk_forward | 1 | market_momentum_logistic | 0.100 | 4 | -0.0400 | -0.0800 | -0.1200 |
| walk_forward | 1 | market_momentum_logistic | 0.120 | 3 | +0.1100 | +0.0800 | +0.0500 |
| walk_forward | 1 | market_momentum_logistic | 0.150 | 2 | +0.4600 | +0.4400 | +0.4200 |
| walk_forward | 1 | market_momentum_logistic | 0.200 | 1 | -0.3400 | -0.3500 | -0.3600 |
| walk_forward | 1 | market_nw_kill_momentum_logistic | 0.020 | 7 | -0.6300 | -0.7000 | -0.7700 |
| walk_forward | 1 | market_nw_kill_momentum_logistic | 0.050 | 6 | -1.2900 | -1.3500 | -1.4100 |
| walk_forward | 1 | market_nw_kill_momentum_logistic | 0.080 | 4 | -1.3000 | -1.3400 | -1.3800 |
| walk_forward | 1 | market_nw_kill_momentum_logistic | 0.100 | 3 | -0.5900 | -0.6200 | -0.6500 |
| walk_forward | 1 | market_nw_kill_momentum_logistic | 0.120 | 3 | -0.8200 | -0.8500 | -0.8800 |
| walk_forward | 1 | market_nw_kill_momentum_logistic | 0.150 | 3 | -0.9500 | -0.9800 | -1.0100 |
| walk_forward | 1 | market_nw_kill_momentum_logistic | 0.200 | 1 | -0.2600 | -0.2700 | -0.2800 |
| walk_forward | 1 | market_nw_logistic | 0.020 | 7 | -0.7300 | -0.8000 | -0.8700 |
| walk_forward | 1 | market_nw_logistic | 0.050 | 4 | +0.5300 | +0.4900 | +0.4500 |
| walk_forward | 1 | market_nw_logistic | 0.080 | 2 | +0.9600 | +0.9400 | +0.9200 |
| walk_forward | 1 | market_nw_logistic | 0.100 | 2 | +1.3000 | +1.2800 | +1.2600 |
| walk_forward | 1 | market_nw_logistic | 0.120 | 2 | +1.5400 | +1.5200 | +1.5000 |
| walk_forward | 1 | market_nw_logistic | 0.150 | 1 | +0.5700 | +0.5600 | +0.5500 |
| walk_forward | 1 | market_nw_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| walk_forward | 1 | market_only_logistic | 0.020 | 2 | -0.8100 | -0.8300 | -0.8500 |

## Readout

- Acceptance criterion: enhanced market+GetTopLive must beat market-only after 1c and 2c slippage, including lockbox.
- Current readout: settlement residual passes, but CLV fails; this supports hold-to-settlement residual research, not a short-horizon scalp.
- Trade ledgers dedupe to first qualifying row per `match_id` and `label_market_bucket`.
- CLV uses future executable book rows in the same match/market/token stream, within 20s after the target horizon; positive future bid minus current ask is the conservative short-horizon test.

## Files Written

- `market_residual_gettoplive_report.md`
- `price_bucket_state_residuals.csv`
- `market_anchor_model_predictions.csv`
- `market_anchor_model_trades.csv`
- `gettoplive_clv_event_study.csv`
- `transition_entry_event_study.csv`
- `market_anchor_model_summary.csv`
