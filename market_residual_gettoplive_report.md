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
- Walk-forward 1c slippage PnL, enhanced vs market-only: +2.2700 vs -0.5300
- Walk-forward 2c slippage PnL, enhanced vs market-only: +2.0700 vs -0.6100
- Lockbox 1c slippage PnL, enhanced vs market-only: +2.9000 vs +0.0000
- Lockbox 2c slippage PnL, enhanced vs market-only: +2.7900 vs +0.0000
- Best walk-forward ablation by 1c slippage PnL: `market_nw_kill_momentum_logistic` (+5.0100 / +4.8200 after 1c/2c)
- Best lockbox ablation by 1c slippage PnL: `market_momentum_logistic__with_bucket` (+3.3100 / +3.1700 after 1c/2c)
- Positive 60s future-bid CLV events with at least 3 matches: 0
- Best 60s average future-bid CLV: -0.0124

## Candidate Board (Post-Fix, Canonical Dedupe)

Pass conditions: walk positive 1c+2c, lockbox positive 1c+2c, folds_with_trades>=4, folds_positive_1c>=3.
artifact_risk: no_bucket version fails but __with_bucket twin passes — relying on label provenance.

| model_name | with_bucket | raw_trades | canonical_exposures | win_rate | avg_ask | pnl_raw | pnl_1c | pnl_2c | folds_with_trades | folds_positive_1c | lockbox_pnl_1c | candidate_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| market_nw_kill_momentum_logistic | False | 19 | n/a | 68.9% | 0.445 | +5.2000 | +5.0100 | +4.8200 | 4 | 4 | +1.5400 | candidate |
| market_momentum_logistic | False | 24 | n/a | 72.0% | 0.485 | +4.6400 | +4.4000 | +4.1600 | 5 | 5 | +2.3200 | candidate |
| market_gettoplive_logistic | False | 20 | n/a | 66.4% | 0.541 | +2.4700 | +2.2700 | +2.0700 | 4 | 3 | +2.9000 | candidate |
| market_nw_logistic | False | 18 | n/a | 63.3% | 0.559 | +1.2300 | +1.0500 | +0.8700 | 4 | 3 | +2.7100 | candidate |
| market_score_logistic | False | 28 | n/a | 57.8% | 0.559 | +1.0900 | +0.8100 | +0.5300 | 5 | 3 | +1.0600 | candidate |
| market_transition_kill_logistic | False | 25 | n/a | 67.7% | 0.540 | +1.0400 | +0.7900 | +0.5400 | 5 | 4 | +0.3300 | candidate |
| market_kill_momentum_logistic | False | 25 | n/a | 54.2% | 0.510 | +0.9500 | +0.7000 | +0.4500 | 4 | 2 | +0.2300 | research_only |
| market_transition_nw_logistic | False | 30 | n/a | 59.4% | 0.554 | +0.4100 | +0.1100 | -0.1900 | 5 | 2 | +2.0600 | artifact_risk |
| market_transition_nw_kill_logistic | False | 28 | n/a | 54.4% | 0.514 | -0.1900 | -0.4700 | -0.7500 | 5 | 3 | +1.0300 | artifact_risk |
| market_only_logistic | False | 8 | n/a | 62.5% | 0.681 | -0.4500 | -0.5300 | -0.6100 | 1 | 0 | +0.0000 | reject |
| market_transition_catchup_logistic | False | 28 | n/a | 56.9% | 0.546 | -0.2700 | -0.5500 | -0.8300 | 5 | 3 | +2.1100 | artifact_risk |
| market_structure_logistic | False | 10 | n/a | 47.9% | 0.599 | -1.0600 | -1.1600 | -1.2600 | 4 | 0 | +1.0100 | reject |
| market_nw_kill_momentum_logistic__with_bucket | True | 20 | n/a | 64.8% | 0.446 | +4.6600 | +4.4600 | +4.2600 | 4 | 3 | +2.7000 | candidate |
| market_momentum_logistic__with_bucket | True | 25 | n/a | 69.4% | 0.511 | +3.3000 | +3.0500 | +2.8000 | 5 | 5 | +3.3100 | candidate |
| market_gettoplive_logistic__with_bucket | True | 20 | n/a | 66.4% | 0.544 | +2.4800 | +2.2800 | +2.0800 | 4 | 3 | +2.8200 | candidate |
| market_nw_logistic__with_bucket | True | 22 | n/a | 64.2% | 0.536 | +2.0500 | +1.8300 | +1.6100 | 4 | 4 | +1.6600 | candidate |
| market_transition_nw_kill_logistic__with_bucket | True | 36 | n/a | 64.2% | 0.553 | +2.1000 | +1.7400 | +1.3800 | 5 | 4 | +2.4200 | candidate |
| market_transition_catchup_logistic__with_bucket | True | 32 | n/a | 65.4% | 0.576 | +1.6900 | +1.3700 | +1.0500 | 5 | 4 | +1.6100 | candidate |
| market_score_logistic__with_bucket | True | 27 | n/a | 57.7% | 0.542 | +0.7800 | +0.5100 | +0.2400 | 5 | 3 | +0.5800 | candidate |
| market_transition_nw_logistic__with_bucket | True | 29 | n/a | 63.3% | 0.567 | +0.7800 | +0.4900 | +0.2000 | 5 | 3 | +1.4600 | candidate |
| market_transition_kill_logistic__with_bucket | True | 24 | n/a | 59.6% | 0.552 | +0.3500 | +0.1100 | -0.1300 | 5 | 4 | +0.5600 | reject |
| market_kill_momentum_logistic__with_bucket | True | 22 | n/a | 54.4% | 0.542 | +0.0300 | -0.1900 | -0.4100 | 4 | 1 | +0.4800 | reject |
| market_only_logistic__with_bucket | True | 7 | n/a | 71.4% | 0.767 | -0.3700 | -0.4400 | -0.5100 | 1 | 0 | +0.0000 | reject |
| market_structure_logistic__with_bucket | True | 12 | n/a | 43.8% | 0.570 | -1.5400 | -1.6600 | -1.7800 | 4 | 0 | +0.5000 | reject |

## Bucket Artifact Check (No-Bucket vs With-Bucket)

artifact_flag=True means the base (no-bucket) model fails but __with_bucket passes — downgrade that family.

| base_model | no_bucket_pnl_1c | with_bucket_pnl_1c | delta_pnl_1c | artifact_flag |
| --- | --- | --- | --- | --- |
| market_transition_nw_kill_logistic | -0.4700 | +1.7400 | +2.2100 | True |
| market_transition_catchup_logistic | -0.5500 | +1.3700 | +1.9200 | True |
| market_nw_logistic | +1.0500 | +1.8300 | +0.7800 | False |
| market_transition_nw_logistic | +0.1100 | +0.4900 | +0.3800 | False |
| market_only_logistic | -0.5300 | -0.4400 | +0.0900 | False |
| market_gettoplive_logistic | +2.2700 | +2.2800 | +0.0100 | False |
| market_score_logistic | +0.8100 | +0.5100 | -0.3000 | False |
| market_structure_logistic | -1.1600 | -1.6600 | -0.5000 | False |
| market_nw_kill_momentum_logistic | +5.0100 | +4.4600 | -0.5500 | False |
| market_transition_kill_logistic | +0.7900 | +0.1100 | -0.6800 | False |
| market_kill_momentum_logistic | +0.7000 | -0.1900 | -0.8900 | False |
| market_momentum_logistic | +4.4000 | +3.0500 | -1.3500 | False |

## Duplicate Exposure Impact

pnl_removed_by_dedupe: PnL that was present before canonical deduplication. If large, the strategy was double-counting equivalent contracts.

| model_name | raw_trade_count | canonical_trade_count | duplicate_exposures | raw_pnl_1c | canonical_pnl_1c | pnl_removed_by_dedupe |
| --- | --- | --- | --- | --- | --- | --- |
| market_momentum_logistic__with_bucket | 193 | 25 | 168 | +26.5000 | +3.0500 | +23.4500 |
| market_nw_kill_momentum_logistic | 132 | 19 | 113 | +26.1700 | +5.0100 | +21.1600 |
| market_momentum_logistic | 196 | 24 | 172 | +23.9500 | +4.4000 | +19.5500 |
| market_kill_momentum_logistic | 175 | 25 | 150 | +18.9900 | +0.7000 | +18.2900 |
| market_nw_kill_momentum_logistic__with_bucket | 128 | 20 | 108 | +22.1700 | +4.4600 | +17.7100 |
| market_only_logistic | 89 | 8 | 81 | +13.6900 | -0.5300 | +14.2200 |
| market_gettoplive_logistic | 145 | 20 | 125 | +15.2300 | +2.2700 | +12.9600 |
| market_gettoplive_logistic__with_bucket | 133 | 20 | 113 | +13.0400 | +2.2800 | +10.7600 |
| market_score_logistic | 208 | 28 | 180 | +10.2900 | +0.8100 | +9.4800 |
| market_nw_logistic | 162 | 18 | 144 | +8.8400 | +1.0500 | +7.7900 |
| market_transition_nw_logistic | 81 | 30 | 51 | +4.9700 | +0.1100 | +4.8600 |
| market_score_logistic__with_bucket | 156 | 27 | 129 | +5.3400 | +0.5100 | +4.8300 |
| market_structure_logistic | 39 | 10 | 29 | +3.3000 | -1.1600 | +4.4600 |
| market_transition_nw_kill_logistic | 73 | 28 | 45 | +2.9600 | -0.4700 | +3.4300 |
| market_structure_logistic__with_bucket | 60 | 12 | 48 | +0.9200 | -1.6600 | +2.5800 |
| market_nw_logistic__with_bucket | 192 | 22 | 170 | +3.8600 | +1.8300 | +2.0300 |
| market_transition_nw_logistic__with_bucket | 74 | 29 | 45 | +2.3400 | +0.4900 | +1.8500 |
| market_transition_kill_logistic | 70 | 25 | 45 | +2.5400 | +0.7900 | +1.7500 |
| market_only_logistic__with_bucket | 58 | 7 | 51 | +0.9800 | -0.4400 | +1.4200 |
| market_transition_catchup_logistic | 79 | 28 | 51 | +0.7100 | -0.5500 | +1.2600 |
| market_transition_catchup_logistic__with_bucket | 102 | 32 | 70 | +2.5800 | +1.3700 | +1.2100 |
| market_kill_momentum_logistic__with_bucket | 144 | 22 | 122 | +0.3800 | -0.1900 | +0.5700 |
| market_transition_nw_kill_logistic__with_bucket | 103 | 36 | 67 | +2.2700 | +1.7400 | +0.5300 |
| market_transition_kill_logistic__with_bucket | 74 | 24 | 50 | +0.0600 | +0.1100 | -0.0500 |

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
| lockbox | market_momentum_logistic__with_bucket | 1 | 0.050 | 1968 | 83.1% | 0.509 | 0.170 | 14 | 71.4% | 0.468 | +0.0810 | +3.4500 | +3.3100 | +3.1700 |
| lockbox | market_gettoplive_logistic | 1 | 0.080 | 1968 | 84.6% | 0.488 | 0.162 | 11 | 81.8% | 0.545 | +0.1097 | +3.0100 | +2.9000 | +2.7900 |
| lockbox | market_gettoplive_logistic__with_bucket | 1 | 0.080 | 1968 | 84.3% | 0.493 | 0.164 | 11 | 81.8% | 0.552 | +0.1163 | +2.9300 | +2.8200 | +2.7100 |
| lockbox | market_nw_logistic | 1 | 0.050 | 1968 | 84.2% | 0.495 | 0.165 | 11 | 81.8% | 0.562 | +0.0693 | +2.8200 | +2.7100 | +2.6000 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 1 | 0.080 | 1968 | 82.9% | 0.511 | 0.171 | 9 | 77.8% | 0.468 | +0.1281 | +2.7900 | +2.7000 | +2.6100 |
| lockbox | market_transition_nw_kill_logistic__with_bucket | 1 | 0.020 | 1968 | 80.6% | 0.547 | 0.185 | 20 | 65.0% | 0.519 | +0.0497 | +2.6200 | +2.4200 | +2.2200 |
| lockbox | market_momentum_logistic | 1 | 0.100 | 1968 | 83.5% | 0.505 | 0.168 | 8 | 75.0% | 0.450 | +0.1458 | +2.4000 | +2.3200 | +2.2400 |
| lockbox | market_transition_catchup_logistic | 1 | 0.050 | 1968 | 81.1% | 0.541 | 0.183 | 14 | 71.4% | 0.554 | +0.0941 | +2.2500 | +2.1100 | +1.9700 |
| lockbox | market_transition_nw_logistic | 1 | 0.050 | 1968 | 81.0% | 0.542 | 0.184 | 14 | 71.4% | 0.557 | +0.0906 | +2.2000 | +2.0600 | +1.9200 |
| lockbox | market_nw_logistic__with_bucket | 1 | 0.050 | 1968 | 83.8% | 0.499 | 0.167 | 11 | 63.6% | 0.475 | +0.0692 | +1.7700 | +1.6600 | +1.5500 |
| lockbox | market_transition_catchup_logistic__with_bucket | 1 | 0.020 | 1968 | 80.6% | 0.547 | 0.185 | 19 | 63.2% | 0.537 | +0.0575 | +1.8000 | +1.6100 | +1.4200 |
| lockbox | market_nw_kill_momentum_logistic | 1 | 0.050 | 1968 | 83.3% | 0.507 | 0.170 | 17 | 58.8% | 0.488 | +0.0751 | +1.7100 | +1.5400 | +1.3700 |
| lockbox | market_transition_nw_logistic__with_bucket | 1 | 0.050 | 1968 | 80.5% | 0.548 | 0.186 | 13 | 69.2% | 0.570 | +0.0864 | +1.5900 | +1.4600 | +1.3300 |
| lockbox | market_score_logistic | 1 | 0.020 | 1968 | 82.8% | 0.521 | 0.175 | 20 | 50.0% | 0.437 | +0.0271 | +1.2600 | +1.0600 | +0.8600 |
| lockbox | market_transition_nw_kill_logistic | 1 | 0.020 | 1968 | 81.2% | 0.541 | 0.183 | 22 | 54.5% | 0.489 | +0.0455 | +1.2500 | +1.0300 | +0.8100 |
| lockbox | market_structure_logistic | 1 | 0.080 | 1968 | 81.3% | 0.539 | 0.182 | 2 | 100.0% | 0.485 | +0.1002 | +1.0300 | +1.0100 | +0.9900 |
| lockbox | market_score_logistic__with_bucket | 1 | 0.020 | 1968 | 82.3% | 0.525 | 0.177 | 14 | 50.0% | 0.449 | +0.0327 | +0.7200 | +0.5800 | +0.4400 |
| lockbox | market_transition_kill_logistic__with_bucket | 1 | 0.020 | 1968 | 80.2% | 0.552 | 0.187 | 17 | 52.9% | 0.486 | +0.0520 | +0.7300 | +0.5600 | +0.3900 |
| lockbox | market_structure_logistic__with_bucket | 1 | 0.050 | 1968 | 80.7% | 0.544 | 0.184 | 7 | 57.1% | 0.490 | +0.0683 | +0.5700 | +0.5000 | +0.4300 |
| lockbox | market_kill_momentum_logistic__with_bucket | 1 | 0.020 | 1968 | 79.8% | 0.555 | 0.189 | 8 | 50.0% | 0.430 | +0.0293 | +0.5600 | +0.4800 | +0.4000 |
| lockbox | market_transition_kill_logistic | 1 | 0.020 | 1968 | 80.8% | 0.546 | 0.185 | 19 | 42.1% | 0.394 | +0.0602 | +0.5200 | +0.3300 | +0.1400 |
| lockbox | market_kill_momentum_logistic | 1 | 0.020 | 1968 | 80.4% | 0.550 | 0.187 | 6 | 33.3% | 0.285 | +0.0306 | +0.2900 | +0.2300 | +0.1700 |
| lockbox | market_only_logistic | 1 | 0.200 | 1968 | 80.7% | 0.547 | 0.186 | 0 | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| lockbox | market_only_logistic__with_bucket | 1 | 0.200 | 1968 | 80.1% | 0.553 | 0.188 | 0 | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| walk_forward | market_nw_kill_momentum_logistic | 5 | 0.100 | 2627 | 84.2% | 0.457 | 0.150 | 19 | 68.9% | 0.445 | +0.1122 | +5.2000 | +5.0100 | +4.8200 |
| walk_forward | market_nw_kill_momentum_logistic__with_bucket | 5 | 0.100 | 2627 | 84.2% | 0.459 | 0.150 | 20 | 64.8% | 0.446 | +0.1159 | +4.6600 | +4.4600 | +4.2600 |
| walk_forward | market_momentum_logistic | 5 | 0.050 | 2627 | 83.8% | 0.459 | 0.151 | 24 | 72.0% | 0.485 | +0.0871 | +4.6400 | +4.4000 | +4.1600 |
| walk_forward | market_momentum_logistic__with_bucket | 5 | 0.050 | 2627 | 83.8% | 0.461 | 0.151 | 25 | 69.4% | 0.511 | +0.0889 | +3.3000 | +3.0500 | +2.8000 |
| walk_forward | market_gettoplive_logistic__with_bucket | 5 | 0.100 | 2627 | 83.5% | 0.461 | 0.153 | 20 | 66.4% | 0.544 | +0.1199 | +2.4800 | +2.2800 | +2.0800 |
| walk_forward | market_gettoplive_logistic | 5 | 0.100 | 2627 | 83.5% | 0.459 | 0.152 | 20 | 66.4% | 0.541 | +0.1193 | +2.4700 | +2.2700 | +2.0700 |
| walk_forward | market_nw_logistic__with_bucket | 5 | 0.050 | 2627 | 83.0% | 0.467 | 0.155 | 22 | 64.2% | 0.536 | +0.0861 | +2.0500 | +1.8300 | +1.6100 |
| walk_forward | market_transition_nw_kill_logistic__with_bucket | 5 | 0.020 | 2627 | 82.7% | 0.474 | 0.156 | 36 | 64.2% | 0.553 | +0.0615 | +2.1000 | +1.7400 | +1.3800 |
| walk_forward | market_transition_catchup_logistic__with_bucket | 5 | 0.020 | 2627 | 82.7% | 0.475 | 0.156 | 32 | 65.4% | 0.576 | +0.0652 | +1.6900 | +1.3700 | +1.0500 |
| walk_forward | market_nw_logistic | 5 | 0.080 | 2627 | 83.0% | 0.466 | 0.154 | 18 | 63.3% | 0.559 | +0.1067 | +1.2300 | +1.0500 | +0.8700 |
| walk_forward | market_score_logistic | 5 | 0.020 | 2627 | 82.4% | 0.475 | 0.156 | 28 | 57.8% | 0.559 | +0.0268 | +1.0900 | +0.8100 | +0.5300 |
| walk_forward | market_transition_kill_logistic | 5 | 0.020 | 2627 | 82.6% | 0.475 | 0.156 | 25 | 67.7% | 0.540 | +0.0682 | +1.0400 | +0.7900 | +0.5400 |
| walk_forward | market_kill_momentum_logistic | 5 | 0.020 | 2627 | 82.8% | 0.474 | 0.155 | 25 | 54.2% | 0.510 | +0.0290 | +0.9500 | +0.7000 | +0.4500 |
| walk_forward | market_score_logistic__with_bucket | 5 | 0.020 | 2627 | 82.3% | 0.477 | 0.157 | 27 | 57.7% | 0.542 | +0.0253 | +0.7800 | +0.5100 | +0.2400 |
| walk_forward | market_transition_nw_logistic__with_bucket | 5 | 0.020 | 2627 | 82.6% | 0.475 | 0.156 | 29 | 63.3% | 0.567 | +0.0747 | +0.7800 | +0.4900 | +0.2000 |
| walk_forward | market_transition_nw_logistic | 5 | 0.020 | 2627 | 82.7% | 0.473 | 0.155 | 30 | 59.4% | 0.554 | +0.0608 | +0.4100 | +0.1100 | -0.1900 |
| walk_forward | market_transition_kill_logistic__with_bucket | 5 | 0.020 | 2627 | 82.5% | 0.476 | 0.156 | 24 | 59.6% | 0.552 | +0.0640 | +0.3500 | +0.1100 | -0.1300 |
| walk_forward | market_kill_momentum_logistic__with_bucket | 5 | 0.020 | 2627 | 82.7% | 0.476 | 0.156 | 22 | 54.4% | 0.542 | +0.0308 | +0.0300 | -0.1900 | -0.4100 |
| walk_forward | market_only_logistic__with_bucket | 5 | 0.200 | 2627 | 82.4% | 0.477 | 0.157 | 7 | 71.4% | 0.767 | +0.0280 | -0.3700 | -0.4400 | -0.5100 |
| walk_forward | market_transition_nw_kill_logistic | 5 | 0.020 | 2627 | 82.7% | 0.473 | 0.155 | 28 | 54.4% | 0.514 | +0.0864 | -0.1900 | -0.4700 | -0.7500 |
| walk_forward | market_only_logistic | 5 | 0.020 | 2627 | 82.5% | 0.475 | 0.156 | 8 | 62.5% | 0.681 | +0.0236 | -0.4500 | -0.5300 | -0.6100 |
| walk_forward | market_transition_catchup_logistic | 5 | 0.020 | 2627 | 82.7% | 0.473 | 0.155 | 28 | 56.9% | 0.546 | +0.0830 | -0.2700 | -0.5500 | -0.8300 |
| walk_forward | market_structure_logistic | 5 | 0.050 | 2627 | 82.7% | 0.474 | 0.156 | 10 | 47.9% | 0.599 | +0.1361 | -1.0600 | -1.1600 | -1.2600 |
| walk_forward | market_structure_logistic__with_bucket | 5 | 0.020 | 2627 | 82.6% | 0.477 | 0.156 | 12 | 43.8% | 0.570 | +0.0909 | -1.5400 | -1.6600 | -1.7800 |

## Model Summary Verdicts

| stage | model_name | folds | pred_rows | auc | trade_trades | trade_win_rate | trade_total_pnl_slip_1c | trade_total_pnl_slip_2c | folds_with_trades | folds_positive_1c | folds_positive_2c | win_rate_ci_low | win_rate_ci_high | uncertainty_reason | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_momentum_logistic__with_bucket | 1 | 1968 | 83.1% | 14 | 71.4% | +3.3100 | +3.1700 | 1 | 1 | 1 | 45.4% | 88.3% | ci_low_not_above_breakeven | research_only |
| lockbox | market_gettoplive_logistic | 1 | 1968 | 84.6% | 11 | 81.8% | +2.9000 | +2.7900 | 1 | 1 | 1 | 52.3% | 94.9% | ci_low_not_above_breakeven | research_only |
| lockbox | market_gettoplive_logistic__with_bucket | 1 | 1968 | 84.3% | 11 | 81.8% | +2.8200 | +2.7100 | 1 | 1 | 1 | 52.3% | 94.9% | ci_low_not_above_breakeven | research_only |
| lockbox | market_nw_logistic | 1 | 1968 | 84.2% | 11 | 81.8% | +2.7100 | +2.6000 | 1 | 1 | 1 | 52.3% | 94.9% | ci_low_not_above_breakeven | research_only |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 1 | 1968 | 82.9% | 9 | 77.8% | +2.7000 | +2.6100 | 1 | 1 | 1 | 45.3% | 93.7% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_nw_kill_logistic__with_bucket | 1 | 1968 | 80.6% | 20 | 65.0% | +2.4200 | +2.2200 | 1 | 1 | 1 | 43.3% | 81.9% | ci_low_not_above_breakeven | research_only |
| lockbox | market_momentum_logistic | 1 | 1968 | 83.5% | 8 | 75.0% | +2.3200 | +2.2400 | 1 | 1 | 1 | 40.9% | 92.9% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_catchup_logistic | 1 | 1968 | 81.1% | 14 | 71.4% | +2.1100 | +1.9700 | 1 | 1 | 1 | 45.4% | 88.3% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_nw_logistic | 1 | 1968 | 81.0% | 14 | 71.4% | +2.0600 | +1.9200 | 1 | 1 | 1 | 45.4% | 88.3% | ci_low_not_above_breakeven | research_only |
| lockbox | market_nw_logistic__with_bucket | 1 | 1968 | 83.8% | 11 | 63.6% | +1.6600 | +1.5500 | 1 | 1 | 1 | 35.4% | 84.8% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_catchup_logistic__with_bucket | 1 | 1968 | 80.6% | 19 | 63.2% | +1.6100 | +1.4200 | 1 | 1 | 1 | 41.0% | 80.9% | ci_low_not_above_breakeven | research_only |
| lockbox | market_nw_kill_momentum_logistic | 1 | 1968 | 83.3% | 17 | 58.8% | +1.5400 | +1.3700 | 1 | 1 | 1 | 36.0% | 78.4% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_nw_logistic__with_bucket | 1 | 1968 | 80.5% | 13 | 69.2% | +1.4600 | +1.3300 | 1 | 1 | 1 | 42.4% | 87.3% | ci_low_not_above_breakeven | research_only |
| lockbox | market_score_logistic | 1 | 1968 | 82.8% | 20 | 50.0% | +1.0600 | +0.8600 | 1 | 1 | 1 | 29.9% | 70.1% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_nw_kill_logistic | 1 | 1968 | 81.2% | 22 | 54.5% | +1.0300 | +0.8100 | 1 | 1 | 1 | 34.7% | 73.1% | ci_low_not_above_breakeven | research_only |
| lockbox | market_structure_logistic | 1 | 1968 | 81.3% | 2 | 100.0% | +1.0100 | +0.9900 | 1 | 1 | 1 | 34.2% | 100.0% | ci_low_not_above_breakeven | research_only |
| lockbox | market_score_logistic__with_bucket | 1 | 1968 | 82.3% | 14 | 50.0% | +0.5800 | +0.4400 | 1 | 1 | 1 | 26.8% | 73.2% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_kill_logistic__with_bucket | 1 | 1968 | 80.2% | 17 | 52.9% | +0.5600 | +0.3900 | 1 | 1 | 1 | 31.0% | 73.8% | ci_low_not_above_breakeven | research_only |
| lockbox | market_structure_logistic__with_bucket | 1 | 1968 | 80.7% | 7 | 57.1% | +0.5000 | +0.4300 | 1 | 1 | 1 | 25.0% | 84.2% | ci_low_not_above_breakeven | research_only |
| lockbox | market_kill_momentum_logistic__with_bucket | 1 | 1968 | 79.8% | 8 | 50.0% | +0.4800 | +0.4000 | 1 | 1 | 1 | 21.5% | 78.5% | ci_low_not_above_breakeven | research_only |
| lockbox | market_transition_kill_logistic | 1 | 1968 | 80.8% | 19 | 42.1% | +0.3300 | +0.1400 | 1 | 1 | 1 | 23.1% | 63.7% | ci_low_not_above_breakeven | research_only |
| lockbox | market_kill_momentum_logistic | 1 | 1968 | 80.4% | 6 | 33.3% | +0.2300 | +0.1700 | 1 | 1 | 1 | 9.7% | 70.0% | ci_low_not_above_breakeven | research_only |
| lockbox | market_only_logistic | 1 | 1968 | 80.7% | 0 | n/a | +0.0000 | +0.0000 | 0 | 0 | 0 | n/a | n/a | no_trades | reject |
| lockbox | market_only_logistic__with_bucket | 1 | 1968 | 80.1% | 0 | n/a | +0.0000 | +0.0000 | 0 | 0 | 0 | n/a | n/a | no_trades | reject |
| walk_forward | market_nw_kill_momentum_logistic | 5 | 2627 | 84.2% | 19 | 68.9% | +5.0100 | +4.8200 | 4 | 4 | 4 | 51.2% | 88.2% | concentrated_pnl | research_only |
| walk_forward | market_nw_kill_momentum_logistic__with_bucket | 5 | 2627 | 84.2% | 20 | 64.8% | +4.4600 | +4.2600 | 4 | 3 | 3 | 48.1% | 85.5% | concentrated_pnl | research_only |
| walk_forward | market_momentum_logistic | 5 | 2627 | 83.8% | 24 | 72.0% | +4.4000 | +4.1600 | 5 | 5 | 5 | 46.7% | 82.0% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_momentum_logistic__with_bucket | 5 | 2627 | 83.8% | 25 | 69.4% | +3.0500 | +2.8000 | 5 | 5 | 4 | 44.5% | 79.8% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_gettoplive_logistic__with_bucket | 5 | 2627 | 83.5% | 20 | 66.4% | +2.2800 | +2.0800 | 4 | 3 | 3 | 48.1% | 85.5% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_gettoplive_logistic | 5 | 2627 | 83.5% | 20 | 66.4% | +2.2700 | +2.0700 | 4 | 3 | 3 | 48.1% | 85.5% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_nw_logistic__with_bucket | 5 | 2627 | 83.0% | 22 | 64.2% | +1.8300 | +1.6100 | 4 | 4 | 4 | 43.0% | 80.3% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_nw_kill_logistic__with_bucket | 5 | 2627 | 82.7% | 36 | 64.2% | +1.7400 | +1.3800 | 5 | 4 | 4 | 42.2% | 72.9% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_catchup_logistic__with_bucket | 5 | 2627 | 82.7% | 32 | 65.4% | +1.3700 | +1.0500 | 5 | 4 | 3 | 42.3% | 74.5% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_nw_logistic | 5 | 2627 | 83.0% | 18 | 63.3% | +1.0500 | +0.8700 | 4 | 3 | 3 | 43.7% | 83.7% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_score_logistic | 5 | 2627 | 82.4% | 28 | 57.8% | +0.8100 | +0.5300 | 5 | 3 | 3 | 39.1% | 73.5% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_kill_logistic | 5 | 2627 | 82.6% | 25 | 67.7% | +0.7900 | +0.5400 | 5 | 4 | 4 | 33.5% | 70.0% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_kill_momentum_logistic | 5 | 2627 | 82.8% | 25 | 54.2% | +0.7000 | +0.4500 | 4 | 2 | 1 | 37.1% | 73.3% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_score_logistic__with_bucket | 5 | 2627 | 82.3% | 27 | 57.7% | +0.5100 | +0.2400 | 5 | 3 | 3 | 37.3% | 72.4% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_nw_logistic__with_bucket | 5 | 2627 | 82.6% | 29 | 63.3% | +0.4900 | +0.2000 | 5 | 3 | 2 | 40.7% | 74.5% | ci_low_not_above_breakeven | research_only |
| walk_forward | market_transition_nw_logistic | 5 | 2627 | 82.7% | 30 | 59.4% | +0.1100 | -0.1900 | 5 | 2 | 2 | 36.1% | 69.8% | ci_low_not_above_breakeven | reject |
| walk_forward | market_transition_kill_logistic__with_bucket | 5 | 2627 | 82.5% | 24 | 59.6% | +0.1100 | -0.1300 | 5 | 4 | 4 | 31.4% | 68.6% | ci_low_not_above_breakeven | reject |
| walk_forward | market_kill_momentum_logistic__with_bucket | 5 | 2627 | 82.7% | 22 | 54.4% | -0.1900 | -0.4100 | 4 | 1 | 1 | 34.7% | 73.1% | ci_low_not_above_breakeven | reject |
| walk_forward | market_only_logistic__with_bucket | 5 | 2627 | 82.4% | 7 | 71.4% | -0.4400 | -0.5100 | 1 | 0 | 0 | 35.9% | 91.8% | ci_low_not_above_breakeven | reject |
| walk_forward | market_transition_nw_kill_logistic | 5 | 2627 | 82.7% | 28 | 54.4% | -0.4700 | -0.7500 | 5 | 3 | 3 | 29.5% | 64.2% | ci_low_not_above_breakeven | reject |
| walk_forward | market_only_logistic | 5 | 2627 | 82.5% | 8 | 62.5% | -0.5300 | -0.6100 | 1 | 0 | 0 | 30.6% | 86.3% | ci_low_not_above_breakeven | reject |
| walk_forward | market_transition_catchup_logistic | 5 | 2627 | 82.7% | 28 | 56.9% | -0.5500 | -0.8300 | 5 | 3 | 2 | 32.6% | 67.4% | ci_low_not_above_breakeven | reject |
| walk_forward | market_structure_logistic | 5 | 2627 | 82.7% | 10 | 47.9% | -1.1600 | -1.2600 | 4 | 0 | 0 | 31.3% | 83.2% | ci_low_not_above_breakeven | reject |
| walk_forward | market_structure_logistic__with_bucket | 5 | 2627 | 82.6% | 12 | 43.8% | -1.6600 | -1.7800 | 4 | 0 | 0 | 25.4% | 74.6% | ci_low_not_above_breakeven | reject |

## Fold Robustness

| model_name | folds | folds_with_trades | folds_positive_raw | folds_positive_1c | folds_positive_2c | total_trades | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| market_nw_kill_momentum_logistic | 5 | 4 | 4 | 4 | 4 | 19 | +5.2000 | +5.0100 | +4.8200 |
| market_nw_kill_momentum_logistic__with_bucket | 5 | 4 | 4 | 3 | 3 | 20 | +4.6600 | +4.4600 | +4.2600 |
| market_momentum_logistic | 5 | 5 | 5 | 5 | 5 | 24 | +4.6400 | +4.4000 | +4.1600 |
| market_momentum_logistic__with_bucket | 5 | 5 | 5 | 5 | 4 | 25 | +3.3000 | +3.0500 | +2.8000 |
| market_gettoplive_logistic__with_bucket | 5 | 4 | 3 | 3 | 3 | 20 | +2.4800 | +2.2800 | +2.0800 |
| market_gettoplive_logistic | 5 | 4 | 3 | 3 | 3 | 20 | +2.4700 | +2.2700 | +2.0700 |
| market_nw_logistic__with_bucket | 5 | 4 | 4 | 4 | 4 | 22 | +2.0500 | +1.8300 | +1.6100 |
| market_transition_nw_kill_logistic__with_bucket | 5 | 5 | 4 | 4 | 4 | 36 | +2.1000 | +1.7400 | +1.3800 |
| market_transition_catchup_logistic__with_bucket | 5 | 5 | 5 | 4 | 3 | 32 | +1.6900 | +1.3700 | +1.0500 |
| market_nw_logistic | 5 | 4 | 3 | 3 | 3 | 18 | +1.2300 | +1.0500 | +0.8700 |
| market_score_logistic | 5 | 5 | 3 | 3 | 3 | 28 | +1.0900 | +0.8100 | +0.5300 |
| market_transition_kill_logistic | 5 | 5 | 4 | 4 | 4 | 25 | +1.0400 | +0.7900 | +0.5400 |
| market_kill_momentum_logistic | 5 | 4 | 3 | 2 | 1 | 25 | +0.9500 | +0.7000 | +0.4500 |
| market_score_logistic__with_bucket | 5 | 5 | 3 | 3 | 3 | 27 | +0.7800 | +0.5100 | +0.2400 |
| market_transition_nw_logistic__with_bucket | 5 | 5 | 3 | 3 | 2 | 29 | +0.7800 | +0.4900 | +0.2000 |
| market_transition_nw_logistic | 5 | 5 | 3 | 2 | 2 | 30 | +0.4100 | +0.1100 | -0.1900 |
| market_transition_kill_logistic__with_bucket | 5 | 5 | 4 | 4 | 4 | 24 | +0.3500 | +0.1100 | -0.1300 |
| market_kill_momentum_logistic__with_bucket | 5 | 4 | 2 | 1 | 1 | 22 | +0.0300 | -0.1900 | -0.4100 |
| market_only_logistic__with_bucket | 5 | 1 | 0 | 0 | 0 | 7 | -0.3700 | -0.4400 | -0.5100 |
| market_transition_nw_kill_logistic | 5 | 5 | 3 | 3 | 3 | 28 | -0.1900 | -0.4700 | -0.7500 |
| market_only_logistic | 5 | 1 | 0 | 0 | 0 | 8 | -0.4500 | -0.5300 | -0.6100 |
| market_transition_catchup_logistic | 5 | 5 | 3 | 3 | 2 | 28 | -0.2700 | -0.5500 | -0.8300 |
| market_structure_logistic | 5 | 4 | 0 | 0 | 0 | 10 | -1.0600 | -1.1600 | -1.2600 |
| market_structure_logistic__with_bucket | 5 | 4 | 0 | 0 | 0 | 12 | -1.5400 | -1.6600 | -1.7800 |

## Trade Win-Rate Uncertainty

| stage | model_name | trades | wins | win_rate | win_rate_ci_low | win_rate_ci_high | avg_ask | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_momentum_logistic__with_bucket | 14 | 10 | 71.4% | 45.4% | 88.3% | 0.468 | +3.4500 | +3.3100 | +3.1700 |
| lockbox | market_gettoplive_logistic | 11 | 9 | 81.8% | 52.3% | 94.9% | 0.545 | +3.0100 | +2.9000 | +2.7900 |
| lockbox | market_gettoplive_logistic__with_bucket | 11 | 9 | 81.8% | 52.3% | 94.9% | 0.552 | +2.9300 | +2.8200 | +2.7100 |
| lockbox | market_nw_logistic | 11 | 9 | 81.8% | 52.3% | 94.9% | 0.562 | +2.8200 | +2.7100 | +2.6000 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 9 | 7 | 77.8% | 45.3% | 93.7% | 0.468 | +2.7900 | +2.7000 | +2.6100 |
| lockbox | market_transition_nw_kill_logistic__with_bucket | 20 | 13 | 65.0% | 43.3% | 81.9% | 0.519 | +2.6200 | +2.4200 | +2.2200 |
| lockbox | market_momentum_logistic | 8 | 6 | 75.0% | 40.9% | 92.9% | 0.450 | +2.4000 | +2.3200 | +2.2400 |
| lockbox | market_transition_catchup_logistic | 14 | 10 | 71.4% | 45.4% | 88.3% | 0.554 | +2.2500 | +2.1100 | +1.9700 |
| lockbox | market_transition_nw_logistic | 14 | 10 | 71.4% | 45.4% | 88.3% | 0.557 | +2.2000 | +2.0600 | +1.9200 |
| lockbox | market_nw_logistic__with_bucket | 11 | 7 | 63.6% | 35.4% | 84.8% | 0.475 | +1.7700 | +1.6600 | +1.5500 |
| lockbox | market_transition_catchup_logistic__with_bucket | 19 | 12 | 63.2% | 41.0% | 80.9% | 0.537 | +1.8000 | +1.6100 | +1.4200 |
| lockbox | market_nw_kill_momentum_logistic | 17 | 10 | 58.8% | 36.0% | 78.4% | 0.488 | +1.7100 | +1.5400 | +1.3700 |
| lockbox | market_transition_nw_logistic__with_bucket | 13 | 9 | 69.2% | 42.4% | 87.3% | 0.570 | +1.5900 | +1.4600 | +1.3300 |
| lockbox | market_score_logistic | 20 | 10 | 50.0% | 29.9% | 70.1% | 0.437 | +1.2600 | +1.0600 | +0.8600 |
| lockbox | market_transition_nw_kill_logistic | 22 | 12 | 54.5% | 34.7% | 73.1% | 0.489 | +1.2500 | +1.0300 | +0.8100 |
| lockbox | market_structure_logistic | 2 | 2 | 100.0% | 34.2% | 100.0% | 0.485 | +1.0300 | +1.0100 | +0.9900 |
| lockbox | market_score_logistic__with_bucket | 14 | 7 | 50.0% | 26.8% | 73.2% | 0.449 | +0.7200 | +0.5800 | +0.4400 |
| lockbox | market_transition_kill_logistic__with_bucket | 17 | 9 | 52.9% | 31.0% | 73.8% | 0.486 | +0.7300 | +0.5600 | +0.3900 |
| lockbox | market_structure_logistic__with_bucket | 7 | 4 | 57.1% | 25.0% | 84.2% | 0.490 | +0.5700 | +0.5000 | +0.4300 |
| lockbox | market_kill_momentum_logistic__with_bucket | 8 | 4 | 50.0% | 21.5% | 78.5% | 0.430 | +0.5600 | +0.4800 | +0.4000 |
| lockbox | market_transition_kill_logistic | 19 | 8 | 42.1% | 23.1% | 63.7% | 0.394 | +0.5200 | +0.3300 | +0.1400 |
| lockbox | market_kill_momentum_logistic | 6 | 2 | 33.3% | 9.7% | 70.0% | 0.285 | +0.2900 | +0.2300 | +0.1700 |
| walk_forward | market_nw_kill_momentum_logistic | 19 | 14 | 73.7% | 51.2% | 88.2% | 0.463 | +5.2000 | +5.0100 | +4.8200 |
| walk_forward | market_nw_kill_momentum_logistic__with_bucket | 20 | 14 | 70.0% | 48.1% | 85.5% | 0.467 | +4.6600 | +4.4600 | +4.2600 |
| walk_forward | market_momentum_logistic | 24 | 16 | 66.7% | 46.7% | 82.0% | 0.473 | +4.6400 | +4.4000 | +4.1600 |
| walk_forward | market_momentum_logistic__with_bucket | 25 | 16 | 64.0% | 44.5% | 79.8% | 0.508 | +3.3000 | +3.0500 | +2.8000 |
| walk_forward | market_gettoplive_logistic__with_bucket | 20 | 14 | 70.0% | 48.1% | 85.5% | 0.576 | +2.4800 | +2.2800 | +2.0800 |
| walk_forward | market_gettoplive_logistic | 20 | 14 | 70.0% | 48.1% | 85.5% | 0.576 | +2.4700 | +2.2700 | +2.0700 |
| walk_forward | market_nw_logistic__with_bucket | 22 | 14 | 63.6% | 43.0% | 80.3% | 0.543 | +2.0500 | +1.8300 | +1.6100 |
| walk_forward | market_transition_nw_kill_logistic__with_bucket | 36 | 21 | 58.3% | 42.2% | 72.9% | 0.525 | +2.1000 | +1.7400 | +1.3800 |
| walk_forward | market_transition_catchup_logistic__with_bucket | 32 | 19 | 59.4% | 42.3% | 74.5% | 0.541 | +1.6900 | +1.3700 | +1.0500 |
| walk_forward | market_nw_logistic | 18 | 12 | 66.7% | 43.7% | 83.7% | 0.598 | +1.2300 | +1.0500 | +0.8700 |
| walk_forward | market_score_logistic | 28 | 16 | 57.1% | 39.1% | 73.5% | 0.532 | +1.0900 | +0.8100 | +0.5300 |
| walk_forward | market_transition_kill_logistic | 25 | 13 | 52.0% | 33.5% | 70.0% | 0.478 | +1.0400 | +0.7900 | +0.5400 |
| walk_forward | market_kill_momentum_logistic | 25 | 14 | 56.0% | 37.1% | 73.3% | 0.522 | +0.9500 | +0.7000 | +0.4500 |
| walk_forward | market_score_logistic__with_bucket | 27 | 15 | 55.6% | 37.3% | 72.4% | 0.527 | +0.7800 | +0.5100 | +0.2400 |
| walk_forward | market_transition_nw_logistic__with_bucket | 29 | 17 | 58.6% | 40.7% | 74.5% | 0.559 | +0.7800 | +0.4900 | +0.2000 |
| walk_forward | market_transition_kill_logistic__with_bucket | 24 | 12 | 50.0% | 31.4% | 68.6% | 0.485 | +0.3500 | +0.1100 | -0.1300 |
| walk_forward | market_transition_nw_logistic | 30 | 16 | 53.3% | 36.1% | 69.8% | 0.520 | +0.4100 | +0.1100 | -0.1900 |
| walk_forward | market_kill_momentum_logistic__with_bucket | 22 | 12 | 54.5% | 34.7% | 73.1% | 0.544 | +0.0300 | -0.1900 | -0.4100 |
| walk_forward | market_only_logistic__with_bucket | 7 | 5 | 71.4% | 35.9% | 91.8% | 0.767 | -0.3700 | -0.4400 | -0.5100 |
| walk_forward | market_transition_nw_kill_logistic | 28 | 13 | 46.4% | 29.5% | 64.2% | 0.471 | -0.1900 | -0.4700 | -0.7500 |
| walk_forward | market_only_logistic | 8 | 5 | 62.5% | 30.6% | 86.3% | 0.681 | -0.4500 | -0.5300 | -0.6100 |
| walk_forward | market_transition_catchup_logistic | 28 | 14 | 50.0% | 32.6% | 67.4% | 0.510 | -0.2700 | -0.5500 | -0.8300 |
| walk_forward | market_structure_logistic | 10 | 6 | 60.0% | 31.3% | 83.2% | 0.706 | -1.0600 | -1.1600 | -1.2600 |
| walk_forward | market_structure_logistic__with_bucket | 12 | 6 | 50.0% | 25.4% | 74.6% | 0.628 | -1.5400 | -1.6600 | -1.7800 |

## CLV Event Study At 60s

| event | rows | matches | avg_ask | avg_clv_mid | avg_clv_bid | avg_future_delay_s | positive_bid_clv_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| side_nw_crosses_5000 | 62 | 59 | 0.749 | +0.0141 | -0.0124 | 62.145 | 38.7% |
| side_mom_100_ge_5000 | 40 | 34 | 0.674 | +0.0012 | -0.0358 | 61.750 | 42.5% |
| side_nw_crosses_8000 | 51 | 50 | 0.809 | -0.0080 | -0.0404 | 62.549 | 31.4% |
| score_changes | 124 | 75 | 0.520 | -0.0304 | -0.0549 | 61.565 | 16.9% |
| building_state_changes | 127 | 75 | 0.517 | -0.0304 | -0.0554 | 61.724 | 13.4% |
| side_mom_100_ge_3000 | 77 | 61 | 0.651 | -0.0203 | -0.0596 | 61.532 | 32.5% |

## Transition Entry-Timing Event Study

| entry_timing | trades | matches | avg_ask | settlement_win_rate | raw_pnl | pnl_1c | pnl_2c | future_bid_clv_15s | future_bid_clv_30s | future_bid_clv_60s | future_bid_clv_120s | positive_bid_clv_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| score_then_nw_catchup | 43 | 26 | 0.514 | 48.8% | -1.0900 | -1.5200 | -1.9500 | -0.0200 | -0.0486 | -0.0670 | -0.0444 | 5.0% |
| first_nw_change | 62 | 38 | 0.515 | 50.0% | -0.9600 | -1.5800 | -2.2000 | -0.0288 | -0.0447 | -0.0790 | -0.0507 | 16.1% |
| nw_then_score_catchup | 152 | 87 | 0.506 | 46.7% | -5.9800 | -7.5000 | -9.0200 | -0.0790 | -0.0465 | -0.0520 | -0.0785 | 14.4% |
| post_transition_close | 181 | 94 | 0.524 | 49.2% | -5.9100 | -7.7200 | -9.5300 | -0.0530 | -0.0629 | -0.0483 | -0.0563 | 15.1% |
| first_score_change | 194 | 102 | 0.524 | 49.0% | -6.6600 | -8.6000 | -10.5400 | -0.0415 | -0.0493 | -0.0481 | -0.0611 | 20.2% |
| confirmed_transition | 196 | 103 | 0.529 | 49.5% | -6.6980 | -8.6580 | -10.6180 | -0.0486 | -0.0773 | -0.0585 | -0.0439 | 22.2% |
| score_nw_same_snapshot | 184 | 100 | 0.527 | 48.4% | -7.9880 | -9.8280 | -11.6680 | -0.0475 | -0.0544 | -0.0593 | -0.0615 | 24.8% |

## Provenance Diagnostic (Unified Map-Equivalent Exposure)

NOTE: MAP_WINNER and MATCH_WINNER_GAME3_PROXY are economically the same map-equivalent exposure.
Trade ledgers are deduped by `canonical_exposure_id = match_id + current_game_number + side`, collapsing both into one exposure.
The table below is a DATA-QUALITY diagnostic only. It answers: does one provenance source produce worse liquidity/binding artifacts?
It does NOT split strategy PnL into separate buckets.

_No rows._

## Trade PnL Concentration

Provenance breakdown by market label (data-quality diagnostic — NOT a strategy PnL split):

| stage | model_name | label_market_bucket | trades | matches | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_gettoplive_logistic | MAP_WINNER | 8 | 8 | 87.5% | +2.3700 | +2.2900 | +2.2100 |
| lockbox | market_gettoplive_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6400 | +0.6100 | +0.5800 |
| lockbox | market_gettoplive_logistic__with_bucket | MAP_WINNER | 8 | 8 | 87.5% | +2.2900 | +2.2100 | +2.1300 |
| lockbox | market_gettoplive_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6400 | +0.6100 | +0.5800 |
| lockbox | market_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 1 | 1 | 100.0% | +0.6700 | +0.6600 | +0.6500 |
| lockbox | market_kill_momentum_logistic | MAP_WINNER | 5 | 5 | 20.0% | -0.3800 | -0.4300 | -0.4800 |
| lockbox | market_kill_momentum_logistic__with_bucket | MAP_WINNER | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_kill_momentum_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 7 | 4 | 42.9% | -0.2500 | -0.3200 | -0.3900 |
| lockbox | market_momentum_logistic | MAP_WINNER | 5 | 4 | 80.0% | +1.7600 | +1.7100 | +1.6600 |
| lockbox | market_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6400 | +0.6100 | +0.5800 |
| lockbox | market_momentum_logistic__with_bucket | MAP_WINNER | 11 | 9 | 72.7% | +2.7000 | +2.5900 | +2.4800 |
| lockbox | market_momentum_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.7500 | +0.7200 | +0.6900 |
| lockbox | market_nw_kill_momentum_logistic | MAP_WINNER | 16 | 11 | 56.2% | +1.5400 | +1.3800 | +1.2200 |
| lockbox | market_nw_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | MAP_WINNER | 6 | 5 | 83.3% | +2.1500 | +2.0900 | +2.0300 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6400 | +0.6100 | +0.5800 |
| lockbox | market_nw_logistic | MAP_WINNER | 8 | 8 | 87.5% | +2.2000 | +2.1200 | +2.0400 |
| lockbox | market_nw_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.6200 | +0.5900 | +0.5600 |
| lockbox | market_nw_logistic__with_bucket | MAP_WINNER | 6 | 6 | 83.3% | +1.4400 | +1.3800 | +1.3200 |
| lockbox | market_nw_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 5 | 4 | 40.0% | +0.3300 | +0.2800 | +0.2300 |
| lockbox | market_score_logistic | MAP_WINNER | 18 | 14 | 50.0% | +1.2900 | +1.1100 | +0.9300 |
| lockbox | market_score_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 50.0% | -0.0300 | -0.0500 | -0.0700 |
| lockbox | market_score_logistic__with_bucket | MAP_WINNER | 7 | 6 | 57.1% | +0.9200 | +0.8500 | +0.7800 |
| lockbox | market_score_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 7 | 4 | 42.9% | -0.2000 | -0.2700 | -0.3400 |
| lockbox | market_structure_logistic | MAP_WINNER | 2 | 2 | 100.0% | +1.0300 | +1.0100 | +0.9900 |
| lockbox | market_structure_logistic__with_bucket | MAP_WINNER | 4 | 4 | 75.0% | +0.7800 | +0.7400 | +0.7000 |
| lockbox | market_structure_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 2 | 33.3% | -0.2100 | -0.2400 | -0.2700 |
| lockbox | market_transition_catchup_logistic | MAP_WINNER | 12 | 11 | 83.3% | +3.2600 | +3.1400 | +3.0200 |
| lockbox | market_transition_catchup_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 0.0% | -1.0100 | -1.0300 | -1.0500 |
| lockbox | market_transition_catchup_logistic__with_bucket | MAP_WINNER | 12 | 10 | 75.0% | +2.5700 | +2.4500 | +2.3300 |
| lockbox | market_transition_catchup_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 7 | 4 | 42.9% | -0.7700 | -0.8400 | -0.9100 |
| lockbox | market_transition_kill_logistic | MAP_WINNER | 18 | 13 | 44.4% | +0.5800 | +0.4000 | +0.2200 |
| lockbox | market_transition_kill_logistic | MATCH_WINNER_GAME3_PROXY | 1 | 1 | 0.0% | -0.0600 | -0.0700 | -0.0800 |
| lockbox | market_transition_kill_logistic__with_bucket | MAP_WINNER | 10 | 7 | 60.0% | +1.5100 | +1.4100 | +1.3100 |
| lockbox | market_transition_kill_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 7 | 4 | 42.9% | -0.7800 | -0.8500 | -0.9200 |
| lockbox | market_transition_nw_kill_logistic | MAP_WINNER | 19 | 13 | 57.9% | +1.9800 | +1.7900 | +1.6000 |
| lockbox | market_transition_nw_kill_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 33.3% | -0.7300 | -0.7600 | -0.7900 |
| lockbox | market_transition_nw_kill_logistic__with_bucket | MAP_WINNER | 13 | 11 | 76.9% | +3.3900 | +3.2600 | +3.1300 |
| lockbox | market_transition_nw_kill_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 7 | 4 | 42.9% | -0.7700 | -0.8400 | -0.9100 |
| lockbox | market_transition_nw_logistic | MAP_WINNER | 12 | 11 | 83.3% | +3.2100 | +3.0900 | +2.9700 |
| lockbox | market_transition_nw_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 0.0% | -1.0100 | -1.0300 | -1.0500 |
| lockbox | market_transition_nw_logistic__with_bucket | MAP_WINNER | 10 | 9 | 80.0% | +2.3000 | +2.2000 | +2.1000 |
| lockbox | market_transition_nw_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 33.3% | -0.7100 | -0.7400 | -0.7700 |
| walk_forward | market_gettoplive_logistic | MAP_WINNER | 17 | 13 | 70.6% | +1.6300 | +1.4600 | +1.2900 |
| walk_forward | market_gettoplive_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.8400 | +0.8100 | +0.7800 |
| walk_forward | market_gettoplive_logistic__with_bucket | MAP_WINNER | 17 | 13 | 70.6% | +1.6800 | +1.5100 | +1.3400 |
| walk_forward | market_gettoplive_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.8000 | +0.7700 | +0.7400 |
| walk_forward | market_kill_momentum_logistic | MAP_WINNER | 23 | 16 | 60.9% | +1.1200 | +0.8900 | +0.6600 |
| walk_forward | market_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 0.0% | -0.1700 | -0.1900 | -0.2100 |
| walk_forward | market_kill_momentum_logistic__with_bucket | MAP_WINNER | 19 | 15 | 63.2% | +0.6400 | +0.4500 | +0.2600 |
| walk_forward | market_kill_momentum_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 0.0% | -0.6100 | -0.6400 | -0.6700 |
| walk_forward | market_momentum_logistic | MAP_WINNER | 21 | 16 | 71.4% | +4.7100 | +4.5000 | +4.2900 |
| walk_forward | market_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 3 | 2 | 33.3% | -0.0700 | -0.1000 | -0.1300 |
| walk_forward | market_momentum_logistic__with_bucket | MAP_WINNER | 22 | 17 | 68.2% | +3.5700 | +3.3500 | +3.1300 |
| walk_forward | market_momentum_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 2 | 33.3% | -0.2700 | -0.3000 | -0.3300 |
| walk_forward | market_nw_kill_momentum_logistic | MAP_WINNER | 17 | 14 | 76.5% | +4.7700 | +4.6000 | +4.4300 |
| walk_forward | market_nw_kill_momentum_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 50.0% | +0.4300 | +0.4100 | +0.3900 |
| walk_forward | market_nw_kill_momentum_logistic__with_bucket | MAP_WINNER | 17 | 14 | 76.5% | +4.6000 | +4.4300 | +4.2600 |
| walk_forward | market_nw_kill_momentum_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 33.3% | +0.0600 | +0.0300 | +0.0000 |
| walk_forward | market_nw_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 50.0% | +0.6900 | +0.6700 | +0.6500 |
| walk_forward | market_nw_logistic | MAP_WINNER | 16 | 14 | 68.8% | +0.5400 | +0.3800 | +0.2200 |
| walk_forward | market_nw_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +1.0000 | +0.9700 | +0.9400 |
| walk_forward | market_nw_logistic__with_bucket | MAP_WINNER | 19 | 15 | 63.2% | +1.0500 | +0.8600 | +0.6700 |
| walk_forward | market_only_logistic | MAP_WINNER | 8 | 6 | 62.5% | -0.4500 | -0.5300 | -0.6100 |
| walk_forward | market_only_logistic__with_bucket | MAP_WINNER | 6 | 6 | 83.3% | +0.0300 | -0.0300 | -0.0900 |
| walk_forward | market_only_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 1 | 1 | 0.0% | -0.4000 | -0.4100 | -0.4200 |
| walk_forward | market_score_logistic | MATCH_WINNER_GAME3_PROXY | 1 | 1 | 100.0% | +0.6600 | +0.6500 | +0.6400 |
| walk_forward | market_score_logistic | MAP_WINNER | 27 | 20 | 55.6% | +0.4300 | +0.1600 | -0.1100 |
| walk_forward | market_score_logistic__with_bucket | MAP_WINNER | 26 | 20 | 57.7% | +0.8500 | +0.5900 | +0.3300 |
| walk_forward | market_score_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 1 | 1 | 0.0% | -0.0700 | -0.0800 | -0.0900 |
| walk_forward | market_structure_logistic | MATCH_WINNER_GAME3_PROXY | 2 | 2 | 50.0% | +0.2400 | +0.2200 | +0.2000 |
| walk_forward | market_structure_logistic | MAP_WINNER | 8 | 8 | 62.5% | -1.3000 | -1.3800 | -1.4600 |
| walk_forward | market_structure_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 4 | 3 | 25.0% | -0.3200 | -0.3600 | -0.4000 |
| walk_forward | market_structure_logistic__with_bucket | MAP_WINNER | 8 | 8 | 62.5% | -1.2200 | -1.3000 | -1.3800 |
| walk_forward | market_transition_catchup_logistic | MATCH_WINNER_GAME3_PROXY | 6 | 3 | 50.0% | +0.1200 | +0.0600 | +0.0000 |
| walk_forward | market_transition_catchup_logistic | MAP_WINNER | 22 | 15 | 50.0% | -0.3900 | -0.6100 | -0.8300 |
| walk_forward | market_transition_catchup_logistic__with_bucket | MAP_WINNER | 28 | 19 | 60.7% | +1.6000 | +1.3200 | +1.0400 |
| walk_forward | market_transition_catchup_logistic__with_bucket | MATCH_WINNER_GAME3_PROXY | 4 | 3 | 50.0% | +0.0900 | +0.0500 | +0.0100 |
| walk_forward | market_transition_kill_logistic | MAP_WINNER | 20 | 13 | 50.0% | +0.8000 | +0.6000 | +0.4000 |
| walk_forward | market_transition_kill_logistic | MATCH_WINNER_GAME3_PROXY | 5 | 3 | 60.0% | +0.2400 | +0.1900 | +0.1400 |

Largest match contributions by absolute 1c-slippage PnL:

| stage | model_name | match_id | trades | buckets | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_gettoplive_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_gettoplive_logistic | 8837869969 | 1 | 1 | 0.0% | -0.6500 | -0.6600 | -0.6700 |
| lockbox | market_gettoplive_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_gettoplive_logistic | 8837725916 | 1 | 1 | 100.0% | +0.5900 | +0.5800 | +0.5700 |
| lockbox | market_gettoplive_logistic | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_gettoplive_logistic | 8836897842 | 1 | 1 | 100.0% | +0.4500 | +0.4400 | +0.4300 |
| lockbox | market_gettoplive_logistic | 8839123109 | 1 | 1 | 100.0% | +0.2800 | +0.2700 | +0.2600 |
| lockbox | market_gettoplive_logistic | 8837690631 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |
| lockbox | market_gettoplive_logistic | 8836916511 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_gettoplive_logistic | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_gettoplive_logistic | 8837288943 | 1 | 1 | 0.0% | -0.1400 | -0.1500 | -0.1600 |
| lockbox | market_gettoplive_logistic__with_bucket | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_gettoplive_logistic__with_bucket | 8837869969 | 1 | 1 | 0.0% | -0.6500 | -0.6600 | -0.6700 |
| lockbox | market_gettoplive_logistic__with_bucket | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_gettoplive_logistic__with_bucket | 8837725916 | 1 | 1 | 100.0% | +0.5900 | +0.5800 | +0.5700 |
| lockbox | market_gettoplive_logistic__with_bucket | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_gettoplive_logistic__with_bucket | 8836897842 | 1 | 1 | 100.0% | +0.3700 | +0.3600 | +0.3500 |
| lockbox | market_gettoplive_logistic__with_bucket | 8839123109 | 1 | 1 | 100.0% | +0.2800 | +0.2700 | +0.2600 |
| lockbox | market_gettoplive_logistic__with_bucket | 8837690631 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |
| lockbox | market_gettoplive_logistic__with_bucket | 8836916511 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_gettoplive_logistic__with_bucket | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_gettoplive_logistic__with_bucket | 8837288943 | 1 | 1 | 0.0% | -0.1400 | -0.1500 | -0.1600 |
| lockbox | market_kill_momentum_logistic | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_kill_momentum_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6700 | +0.6600 | +0.6500 |
| lockbox | market_kill_momentum_logistic | 8836897842 | 1 | 1 | 0.0% | -0.4600 | -0.4700 | -0.4800 |
| lockbox | market_kill_momentum_logistic | 8839123109 | 1 | 1 | 0.0% | -0.3300 | -0.3400 | -0.3500 |
| lockbox | market_kill_momentum_logistic | 8837690631 | 1 | 1 | 0.0% | -0.2100 | -0.2200 | -0.2300 |
| lockbox | market_kill_momentum_logistic | 8839193447 | 1 | 1 | 0.0% | -0.1900 | -0.2000 | -0.2100 |
| lockbox | market_kill_momentum_logistic__with_bucket | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_kill_momentum_logistic__with_bucket | 8837052943 | 2 | 1 | 50.0% | -0.1200 | -0.1400 | -0.1600 |
| lockbox | market_kill_momentum_logistic__with_bucket | 8837692542 | 2 | 1 | 50.0% | -0.1200 | -0.1400 | -0.1600 |
| lockbox | market_kill_momentum_logistic__with_bucket | 8837724891 | 1 | 1 | 0.0% | -0.1000 | -0.1100 | -0.1200 |
| lockbox | market_kill_momentum_logistic__with_bucket | 8837288943 | 2 | 1 | 50.0% | +0.0900 | +0.0700 | +0.0500 |
| lockbox | market_momentum_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_momentum_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_momentum_logistic | 8837725916 | 1 | 1 | 100.0% | +0.5900 | +0.5800 | +0.5700 |
| lockbox | market_momentum_logistic | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_momentum_logistic | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_momentum_logistic | 8837288943 | 1 | 1 | 0.0% | -0.1400 | -0.1500 | -0.1600 |
| lockbox | market_momentum_logistic | 8836897842 | 2 | 1 | 50.0% | -0.1200 | -0.1400 | -0.1600 |
| lockbox | market_momentum_logistic__with_bucket | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_momentum_logistic__with_bucket | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_momentum_logistic__with_bucket | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_momentum_logistic__with_bucket | 8837889126 | 1 | 1 | 100.0% | +0.6000 | +0.5900 | +0.5800 |
| lockbox | market_momentum_logistic__with_bucket | 8839123109 | 1 | 1 | 100.0% | +0.2800 | +0.2700 | +0.2600 |
| lockbox | market_momentum_logistic__with_bucket | 8837560468 | 1 | 1 | 0.0% | -0.2300 | -0.2400 | -0.2500 |
| lockbox | market_momentum_logistic__with_bucket | 8837690631 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |
| lockbox | market_momentum_logistic__with_bucket | 8837692542 | 1 | 1 | 100.0% | +0.2000 | +0.1900 | +0.1800 |
| lockbox | market_momentum_logistic__with_bucket | 8836916511 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_momentum_logistic__with_bucket | 8837869969 | 2 | 1 | 50.0% | +0.1100 | +0.0900 | +0.0700 |
| lockbox | market_momentum_logistic__with_bucket | 8837288943 | 1 | 1 | 0.0% | -0.0600 | -0.0700 | -0.0800 |
| lockbox | market_momentum_logistic__with_bucket | 8836897842 | 2 | 1 | 50.0% | -0.0100 | -0.0300 | -0.0500 |
| lockbox | market_nw_kill_momentum_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_nw_kill_momentum_logistic | 8837889126 | 1 | 1 | 100.0% | +0.6000 | +0.5900 | +0.5800 |
| lockbox | market_nw_kill_momentum_logistic | 8837690631 | 1 | 1 | 100.0% | +0.2800 | +0.2700 | +0.2600 |
| lockbox | market_nw_kill_momentum_logistic | 8836916511 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_kill_momentum_logistic | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_kill_momentum_logistic | 8837288943 | 1 | 1 | 0.0% | -0.1200 | -0.1300 | -0.1400 |
| lockbox | market_nw_kill_momentum_logistic | 8837560468 | 1 | 1 | 0.0% | -0.1200 | -0.1300 | -0.1400 |
| lockbox | market_nw_kill_momentum_logistic | 8839123109 | 2 | 1 | 50.0% | -0.0900 | -0.1100 | -0.1300 |
| lockbox | market_nw_kill_momentum_logistic | 8837725916 | 2 | 1 | 50.0% | -0.0400 | -0.0600 | -0.0800 |
| lockbox | market_nw_kill_momentum_logistic | 8837869969 | 2 | 1 | 50.0% | +0.0600 | +0.0400 | +0.0200 |
| lockbox | market_nw_kill_momentum_logistic | 8836897842 | 2 | 1 | 50.0% | +0.0500 | +0.0300 | +0.0100 |
| lockbox | market_nw_kill_momentum_logistic | 8837052943 | 2 | 1 | 50.0% | +0.0200 | +0.0000 | -0.0200 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8837725916 | 1 | 1 | 100.0% | +0.8100 | +0.8000 | +0.7900 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8837052943 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8839123109 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8837288943 | 1 | 1 | 0.0% | -0.1400 | -0.1500 | -0.1600 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 8836897842 | 2 | 1 | 50.0% | -0.1200 | -0.1400 | -0.1600 |
| lockbox | market_nw_logistic | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_nw_logistic | 8837869969 | 1 | 1 | 0.0% | -0.6500 | -0.6600 | -0.6700 |
| lockbox | market_nw_logistic | 8837052943 | 1 | 1 | 100.0% | +0.6700 | +0.6600 | +0.6500 |
| lockbox | market_nw_logistic | 8837889126 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| lockbox | market_nw_logistic | 8836897842 | 1 | 1 | 100.0% | +0.4500 | +0.4400 | +0.4300 |
| lockbox | market_nw_logistic | 8837725916 | 1 | 1 | 100.0% | +0.3800 | +0.3700 | +0.3600 |
| lockbox | market_nw_logistic | 8836916511 | 1 | 1 | 100.0% | +0.2900 | +0.2800 | +0.2700 |
| lockbox | market_nw_logistic | 8837690631 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |

By league:

| stage | model_name | league_id | trades | matches | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | market_gettoplive_logistic | 19699 | 8 | 8 | 87.5% | +2.6500 | +2.5700 | +2.4900 |
| lockbox | market_gettoplive_logistic | 19101 | 3 | 3 | 66.7% | +0.3600 | +0.3300 | +0.3000 |
| lockbox | market_gettoplive_logistic__with_bucket | 19699 | 8 | 8 | 87.5% | +2.5700 | +2.4900 | +2.4100 |
| lockbox | market_gettoplive_logistic__with_bucket | 19101 | 3 | 3 | 66.7% | +0.3600 | +0.3300 | +0.3000 |
| lockbox | market_kill_momentum_logistic | 19699 | 4 | 4 | 50.0% | +0.8100 | +0.7700 | +0.7300 |
| lockbox | market_kill_momentum_logistic | 19101 | 2 | 2 | 0.0% | -0.5200 | -0.5400 | -0.5600 |
| lockbox | market_kill_momentum_logistic__with_bucket | 19699 | 8 | 5 | 50.0% | +0.5600 | +0.4800 | +0.4000 |
| lockbox | market_momentum_logistic | 19699 | 7 | 6 | 71.4% | +1.6700 | +1.6000 | +1.5300 |
| lockbox | market_momentum_logistic | 19101 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_momentum_logistic__with_bucket | 19699 | 10 | 9 | 70.0% | +2.3300 | +2.2300 | +2.1300 |
| lockbox | market_momentum_logistic__with_bucket | 19101 | 4 | 3 | 75.0% | +1.1200 | +1.0800 | +1.0400 |
| lockbox | market_nw_kill_momentum_logistic | 19699 | 12 | 9 | 58.3% | +1.0100 | +0.8900 | +0.7700 |
| lockbox | market_nw_kill_momentum_logistic | 19101 | 5 | 3 | 60.0% | +0.7000 | +0.6500 | +0.6000 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 19699 | 7 | 6 | 71.4% | +1.8900 | +1.8200 | +1.7500 |
| lockbox | market_nw_kill_momentum_logistic__with_bucket | 19101 | 2 | 2 | 100.0% | +0.9000 | +0.8800 | +0.8600 |
| lockbox | market_nw_logistic | 19699 | 8 | 8 | 87.5% | +2.5400 | +2.4600 | +2.3800 |
| lockbox | market_nw_logistic | 19101 | 3 | 3 | 66.7% | +0.2800 | +0.2500 | +0.2200 |
| lockbox | market_nw_logistic__with_bucket | 19699 | 8 | 7 | 62.5% | +1.4600 | +1.3800 | +1.3000 |
| lockbox | market_nw_logistic__with_bucket | 19101 | 3 | 3 | 66.7% | +0.3100 | +0.2800 | +0.2500 |
| lockbox | market_score_logistic | 19101 | 6 | 4 | 66.7% | +1.3900 | +1.3300 | +1.2700 |
| lockbox | market_score_logistic | 19699 | 14 | 12 | 42.9% | -0.1300 | -0.2700 | -0.4100 |
| lockbox | market_score_logistic__with_bucket | 19101 | 4 | 3 | 75.0% | +1.4500 | +1.4100 | +1.3700 |
| lockbox | market_score_logistic__with_bucket | 19699 | 10 | 7 | 40.0% | -0.7300 | -0.8300 | -0.9300 |
| lockbox | market_structure_logistic | 19101 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| lockbox | market_structure_logistic | 19699 | 1 | 1 | 100.0% | +0.3000 | +0.2900 | +0.2800 |
| lockbox | market_structure_logistic__with_bucket | 19699 | 5 | 3 | 60.0% | +0.4900 | +0.4400 | +0.3900 |
| lockbox | market_structure_logistic__with_bucket | 19101 | 2 | 2 | 50.0% | +0.0800 | +0.0600 | +0.0400 |
| lockbox | market_transition_catchup_logistic | 19699 | 10 | 8 | 70.0% | +1.4000 | +1.3000 | +1.2000 |
| lockbox | market_transition_catchup_logistic | 19101 | 4 | 3 | 75.0% | +0.8500 | +0.8100 | +0.7700 |
| lockbox | market_transition_catchup_logistic__with_bucket | 19699 | 14 | 10 | 64.3% | +1.3700 | +1.2300 | +1.0900 |
| lockbox | market_transition_catchup_logistic__with_bucket | 19101 | 5 | 3 | 60.0% | +0.4300 | +0.3800 | +0.3300 |
| lockbox | market_transition_kill_logistic | 19101 | 6 | 4 | 50.0% | +0.2500 | +0.1900 | +0.1300 |
| lockbox | market_transition_kill_logistic | 19699 | 13 | 10 | 38.5% | +0.2700 | +0.1400 | +0.0100 |
| lockbox | market_transition_kill_logistic__with_bucket | 19101 | 5 | 3 | 60.0% | +0.4400 | +0.3900 | +0.3400 |
| lockbox | market_transition_kill_logistic__with_bucket | 19699 | 12 | 7 | 50.0% | +0.2900 | +0.1700 | +0.0500 |
| lockbox | market_transition_nw_kill_logistic | 19699 | 16 | 10 | 56.2% | +0.9000 | +0.7400 | +0.5800 |
| lockbox | market_transition_nw_kill_logistic | 19101 | 6 | 4 | 50.0% | +0.3500 | +0.2900 | +0.2300 |
| lockbox | market_transition_nw_kill_logistic__with_bucket | 19699 | 15 | 11 | 66.7% | +2.1000 | +1.9500 | +1.8000 |
| lockbox | market_transition_nw_kill_logistic__with_bucket | 19101 | 5 | 3 | 60.0% | +0.5200 | +0.4700 | +0.4200 |
| lockbox | market_transition_nw_logistic | 19699 | 10 | 8 | 70.0% | +1.3500 | +1.2500 | +1.1500 |
| lockbox | market_transition_nw_logistic | 19101 | 4 | 3 | 75.0% | +0.8500 | +0.8100 | +0.7700 |
| lockbox | market_transition_nw_logistic__with_bucket | 19101 | 4 | 3 | 75.0% | +0.8500 | +0.8100 | +0.7700 |
| lockbox | market_transition_nw_logistic__with_bucket | 19699 | 9 | 8 | 66.7% | +0.7400 | +0.6500 | +0.5600 |
| walk_forward | market_gettoplive_logistic | 19699 | 20 | 16 | 70.0% | +2.4700 | +2.2700 | +2.0700 |
| walk_forward | market_gettoplive_logistic__with_bucket | 19699 | 20 | 16 | 70.0% | +2.4800 | +2.2800 | +2.0800 |
| walk_forward | market_kill_momentum_logistic | 19699 | 23 | 17 | 56.5% | +1.0100 | +0.7800 | +0.5500 |
| walk_forward | market_kill_momentum_logistic | 19101 | 2 | 1 | 50.0% | -0.0600 | -0.0800 | -0.1000 |
| walk_forward | market_kill_momentum_logistic__with_bucket | 19101 | 2 | 1 | 50.0% | -0.0600 | -0.0800 | -0.1000 |
| walk_forward | market_kill_momentum_logistic__with_bucket | 19699 | 20 | 16 | 55.0% | +0.0900 | -0.1100 | -0.3100 |
| walk_forward | market_momentum_logistic | 19699 | 24 | 18 | 66.7% | +4.6400 | +4.4000 | +4.1600 |
| walk_forward | market_momentum_logistic__with_bucket | 19699 | 25 | 19 | 64.0% | +3.3000 | +3.0500 | +2.8000 |
| walk_forward | market_nw_kill_momentum_logistic | 19699 | 19 | 16 | 73.7% | +5.2000 | +5.0100 | +4.8200 |
| walk_forward | market_nw_kill_momentum_logistic__with_bucket | 19699 | 20 | 16 | 70.0% | +4.6600 | +4.4600 | +4.2600 |
| walk_forward | market_nw_logistic | 19699 | 18 | 16 | 66.7% | +1.2300 | +1.0500 | +0.8700 |
| walk_forward | market_nw_logistic__with_bucket | 19699 | 22 | 18 | 63.6% | +2.0500 | +1.8300 | +1.6100 |
| walk_forward | market_only_logistic | 19699 | 8 | 6 | 62.5% | -0.4500 | -0.5300 | -0.6100 |
| walk_forward | market_only_logistic__with_bucket | 19699 | 7 | 6 | 71.4% | -0.3700 | -0.4400 | -0.5100 |
| walk_forward | market_score_logistic | 19699 | 27 | 20 | 59.3% | +1.5900 | +1.3200 | +1.0500 |
| walk_forward | market_score_logistic | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| walk_forward | market_score_logistic__with_bucket | 19699 | 26 | 20 | 57.7% | +1.2800 | +1.0200 | +0.7600 |
| walk_forward | market_score_logistic__with_bucket | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| walk_forward | market_structure_logistic | 19699 | 10 | 10 | 60.0% | -1.0600 | -1.1600 | -1.2600 |
| walk_forward | market_structure_logistic__with_bucket | 19699 | 12 | 11 | 50.0% | -1.5400 | -1.6600 | -1.7800 |
| walk_forward | market_transition_catchup_logistic | 19101 | 2 | 1 | 50.0% | +0.1700 | +0.1500 | +0.1300 |
| walk_forward | market_transition_catchup_logistic | 19699 | 26 | 17 | 50.0% | -0.4400 | -0.7000 | -0.9600 |
| walk_forward | market_transition_catchup_logistic__with_bucket | 19699 | 30 | 20 | 60.0% | +1.5200 | +1.2200 | +0.9200 |
| walk_forward | market_transition_catchup_logistic__with_bucket | 19101 | 2 | 1 | 50.0% | +0.1700 | +0.1500 | +0.1300 |
| walk_forward | market_transition_kill_logistic | 19699 | 24 | 15 | 54.2% | +1.5600 | +1.3200 | +1.0800 |
| walk_forward | market_transition_kill_logistic | 19101 | 1 | 1 | 0.0% | -0.5200 | -0.5300 | -0.5400 |
| walk_forward | market_transition_kill_logistic__with_bucket | 19699 | 23 | 15 | 52.2% | +0.8700 | +0.6400 | +0.4100 |
| walk_forward | market_transition_kill_logistic__with_bucket | 19101 | 1 | 1 | 0.0% | -0.5200 | -0.5300 | -0.5400 |
| walk_forward | market_transition_nw_kill_logistic | 19101 | 1 | 1 | 0.0% | -0.2200 | -0.2300 | -0.2400 |
| walk_forward | market_transition_nw_kill_logistic | 19699 | 27 | 18 | 48.1% | +0.0300 | -0.2400 | -0.5100 |
| walk_forward | market_transition_nw_kill_logistic__with_bucket | 19699 | 35 | 23 | 60.0% | +2.6200 | +2.2700 | +1.9200 |
| walk_forward | market_transition_nw_kill_logistic__with_bucket | 19101 | 1 | 1 | 0.0% | -0.5200 | -0.5300 | -0.5400 |
| walk_forward | market_transition_nw_logistic | 19699 | 28 | 19 | 53.6% | +0.4000 | +0.1200 | -0.1600 |
| walk_forward | market_transition_nw_logistic | 19101 | 2 | 1 | 50.0% | +0.0100 | -0.0100 | -0.0300 |
| walk_forward | market_transition_nw_logistic__with_bucket | 19699 | 27 | 20 | 59.3% | +0.7700 | +0.5000 | +0.2300 |
| walk_forward | market_transition_nw_logistic__with_bucket | 19101 | 2 | 1 | 50.0% | +0.0100 | -0.0100 | -0.0300 |

## Threshold Search

| stage | fold | model_name | threshold | trades | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lockbox | 0 | market_gettoplive_logistic | 0.020 | 35 | +1.6600 | +1.3100 | +0.9600 |
| lockbox | 0 | market_gettoplive_logistic | 0.050 | 26 | +3.1200 | +2.8600 | +2.6000 |
| lockbox | 0 | market_gettoplive_logistic | 0.080 | 20 | +3.7200 | +3.5200 | +3.3200 |
| lockbox | 0 | market_gettoplive_logistic | 0.100 | 18 | +3.1000 | +2.9200 | +2.7400 |
| lockbox | 0 | market_gettoplive_logistic | 0.120 | 15 | +3.2300 | +3.0800 | +2.9300 |
| lockbox | 0 | market_gettoplive_logistic | 0.150 | 10 | +1.2700 | +1.1700 | +1.0700 |
| lockbox | 0 | market_gettoplive_logistic | 0.200 | 6 | +0.7500 | +0.6900 | +0.6300 |
| lockbox | 0 | market_gettoplive_logistic__with_bucket | 0.020 | 31 | +2.0800 | +1.7700 | +1.4600 |
| lockbox | 0 | market_gettoplive_logistic__with_bucket | 0.050 | 23 | +2.8200 | +2.5900 | +2.3600 |
| lockbox | 0 | market_gettoplive_logistic__with_bucket | 0.080 | 20 | +3.4100 | +3.2100 | +3.0100 |
| lockbox | 0 | market_gettoplive_logistic__with_bucket | 0.100 | 17 | +2.7700 | +2.6000 | +2.4300 |
| lockbox | 0 | market_gettoplive_logistic__with_bucket | 0.120 | 14 | +2.3100 | +2.1700 | +2.0300 |
| lockbox | 0 | market_gettoplive_logistic__with_bucket | 0.150 | 10 | +1.2700 | +1.1700 | +1.0700 |
| lockbox | 0 | market_gettoplive_logistic__with_bucket | 0.200 | 4 | +0.6500 | +0.6100 | +0.5700 |
| lockbox | 0 | market_kill_momentum_logistic | 0.020 | 14 | +2.6700 | +2.5300 | +2.3900 |
| lockbox | 0 | market_kill_momentum_logistic | 0.050 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.080 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.100 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic__with_bucket | 0.020 | 4 | +1.1700 | +1.1300 | +1.0900 |
| lockbox | 0 | market_kill_momentum_logistic__with_bucket | 0.050 | 2 | -0.0400 | -0.0600 | -0.0800 |
| lockbox | 0 | market_kill_momentum_logistic__with_bucket | 0.080 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_kill_momentum_logistic__with_bucket | 0.100 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic__with_bucket | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic__with_bucket | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_kill_momentum_logistic__with_bucket | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_momentum_logistic | 0.020 | 35 | +1.8200 | +1.4700 | +1.1200 |
| lockbox | 0 | market_momentum_logistic | 0.050 | 26 | +3.9400 | +3.6800 | +3.4200 |
| lockbox | 0 | market_momentum_logistic | 0.080 | 21 | +4.0400 | +3.8300 | +3.6200 |
| lockbox | 0 | market_momentum_logistic | 0.100 | 17 | +4.6600 | +4.4900 | +4.3200 |
| lockbox | 0 | market_momentum_logistic | 0.120 | 17 | +3.9700 | +3.8000 | +3.6300 |
| lockbox | 0 | market_momentum_logistic | 0.150 | 11 | +1.7900 | +1.6800 | +1.5700 |
| lockbox | 0 | market_momentum_logistic | 0.200 | 6 | +0.5100 | +0.4500 | +0.3900 |
| lockbox | 0 | market_momentum_logistic__with_bucket | 0.020 | 34 | +1.9300 | +1.5900 | +1.2500 |
| lockbox | 0 | market_momentum_logistic__with_bucket | 0.050 | 25 | +4.6700 | +4.4200 | +4.1700 |
| lockbox | 0 | market_momentum_logistic__with_bucket | 0.080 | 20 | +3.6100 | +3.4100 | +3.2100 |
| lockbox | 0 | market_momentum_logistic__with_bucket | 0.100 | 17 | +4.2900 | +4.1200 | +3.9500 |
| lockbox | 0 | market_momentum_logistic__with_bucket | 0.120 | 14 | +2.4500 | +2.3100 | +2.1700 |
| lockbox | 0 | market_momentum_logistic__with_bucket | 0.150 | 9 | +0.7000 | +0.6100 | +0.5200 |
| lockbox | 0 | market_momentum_logistic__with_bucket | 0.200 | 5 | +0.1000 | +0.0500 | -0.0000 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.020 | 35 | +1.7400 | +1.3900 | +1.0400 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.050 | 27 | +4.8600 | +4.5900 | +4.3200 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.080 | 22 | +4.7900 | +4.5700 | +4.3500 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.100 | 17 | +4.5200 | +4.3500 | +4.1800 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.120 | 17 | +4.0600 | +3.8900 | +3.7200 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.150 | 14 | +3.0300 | +2.8900 | +2.7500 |
| lockbox | 0 | market_nw_kill_momentum_logistic | 0.200 | 6 | +0.5100 | +0.4500 | +0.3900 |
| lockbox | 0 | market_nw_kill_momentum_logistic__with_bucket | 0.020 | 34 | +1.9100 | +1.5700 | +1.2300 |
| lockbox | 0 | market_nw_kill_momentum_logistic__with_bucket | 0.050 | 25 | +4.4200 | +4.1700 | +3.9200 |
| lockbox | 0 | market_nw_kill_momentum_logistic__with_bucket | 0.080 | 18 | +5.2400 | +5.0600 | +4.8800 |
| lockbox | 0 | market_nw_kill_momentum_logistic__with_bucket | 0.100 | 17 | +4.3500 | +4.1800 | +4.0100 |
| lockbox | 0 | market_nw_kill_momentum_logistic__with_bucket | 0.120 | 16 | +3.6400 | +3.4800 | +3.3200 |
| lockbox | 0 | market_nw_kill_momentum_logistic__with_bucket | 0.150 | 10 | +1.7800 | +1.6800 | +1.5800 |
| lockbox | 0 | market_nw_kill_momentum_logistic__with_bucket | 0.200 | 6 | +0.5100 | +0.4500 | +0.3900 |
| lockbox | 0 | market_nw_logistic | 0.020 | 28 | +1.3900 | +1.1100 | +0.8300 |
| lockbox | 0 | market_nw_logistic | 0.050 | 21 | +2.5700 | +2.3600 | +2.1500 |
| lockbox | 0 | market_nw_logistic | 0.080 | 15 | +0.9000 | +0.7500 | +0.6000 |
| lockbox | 0 | market_nw_logistic | 0.100 | 11 | +0.6500 | +0.5400 | +0.4300 |
| lockbox | 0 | market_nw_logistic | 0.120 | 10 | +1.0500 | +0.9500 | +0.8500 |
| lockbox | 0 | market_nw_logistic | 0.150 | 5 | +1.0500 | +1.0000 | +0.9500 |
| lockbox | 0 | market_nw_logistic | 0.200 | 3 | +1.4900 | +1.4600 | +1.4300 |
| lockbox | 0 | market_nw_logistic__with_bucket | 0.020 | 25 | +1.6600 | +1.4100 | +1.1600 |
| lockbox | 0 | market_nw_logistic__with_bucket | 0.050 | 19 | +2.0900 | +1.9000 | +1.7100 |
| lockbox | 0 | market_nw_logistic__with_bucket | 0.080 | 13 | +0.3200 | +0.1900 | +0.0600 |
| lockbox | 0 | market_nw_logistic__with_bucket | 0.100 | 11 | +0.6600 | +0.5500 | +0.4400 |
| lockbox | 0 | market_nw_logistic__with_bucket | 0.120 | 9 | +1.3800 | +1.2900 | +1.2000 |
| lockbox | 0 | market_nw_logistic__with_bucket | 0.150 | 4 | +1.7100 | +1.6700 | +1.6300 |
| lockbox | 0 | market_nw_logistic__with_bucket | 0.200 | 3 | +1.4900 | +1.4600 | +1.4300 |
| lockbox | 0 | market_only_logistic | 0.020 | 1 | -0.3200 | -0.3300 | -0.3400 |
| lockbox | 0 | market_only_logistic | 0.050 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.080 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.100 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic__with_bucket | 0.020 | 2 | -0.0100 | -0.0300 | -0.0500 |
| lockbox | 0 | market_only_logistic__with_bucket | 0.050 | 2 | -0.0400 | -0.0600 | -0.0800 |
| lockbox | 0 | market_only_logistic__with_bucket | 0.080 | 1 | -0.4300 | -0.4400 | -0.4500 |
| lockbox | 0 | market_only_logistic__with_bucket | 0.100 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic__with_bucket | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic__with_bucket | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_only_logistic__with_bucket | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_score_logistic | 0.020 | 27 | +1.6400 | +1.3700 | +1.1000 |
| lockbox | 0 | market_score_logistic | 0.050 | 10 | -0.9600 | -1.0600 | -1.1600 |
| lockbox | 0 | market_score_logistic | 0.080 | 4 | -0.9200 | -0.9600 | -1.0000 |
| lockbox | 0 | market_score_logistic | 0.100 | 2 | +0.0700 | +0.0500 | +0.0300 |
| lockbox | 0 | market_score_logistic | 0.120 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_score_logistic | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_score_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_score_logistic__with_bucket | 0.020 | 22 | +0.3800 | +0.1600 | -0.0600 |
| lockbox | 0 | market_score_logistic__with_bucket | 0.050 | 8 | -1.7700 | -1.8500 | -1.9300 |
| lockbox | 0 | market_score_logistic__with_bucket | 0.080 | 2 | -0.0400 | -0.0600 | -0.0800 |
| lockbox | 0 | market_score_logistic__with_bucket | 0.100 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_score_logistic__with_bucket | 0.120 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_score_logistic__with_bucket | 0.150 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_score_logistic__with_bucket | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_structure_logistic | 0.020 | 15 | -0.5800 | -0.7300 | -0.8800 |
| lockbox | 0 | market_structure_logistic | 0.050 | 10 | +0.8400 | +0.7400 | +0.6400 |
| lockbox | 0 | market_structure_logistic | 0.080 | 7 | +1.2200 | +1.1500 | +1.0800 |
| lockbox | 0 | market_structure_logistic | 0.100 | 4 | +0.2200 | +0.1800 | +0.1400 |
| lockbox | 0 | market_structure_logistic | 0.120 | 3 | +0.0600 | +0.0300 | -0.0000 |
| lockbox | 0 | market_structure_logistic | 0.150 | 3 | +0.0300 | +0.0000 | -0.0300 |
| lockbox | 0 | market_structure_logistic | 0.200 | 0 | +0.0000 | +0.0000 | +0.0000 |
| lockbox | 0 | market_structure_logistic__with_bucket | 0.020 | 12 | +0.3700 | +0.2500 | +0.1300 |
| lockbox | 0 | market_structure_logistic__with_bucket | 0.050 | 11 | +0.4100 | +0.3000 | +0.1900 |
| lockbox | 0 | market_structure_logistic__with_bucket | 0.080 | 5 | -0.2100 | -0.2600 | -0.3100 |
| lockbox | 0 | market_structure_logistic__with_bucket | 0.100 | 4 | +0.2200 | +0.1800 | +0.1400 |
| lockbox | 0 | market_structure_logistic__with_bucket | 0.120 | 3 | +0.0300 | +0.0000 | -0.0300 |
| lockbox | 0 | market_structure_logistic__with_bucket | 0.150 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_structure_logistic__with_bucket | 0.200 | 1 | +0.3900 | +0.3800 | +0.3700 |
| lockbox | 0 | market_transition_catchup_logistic | 0.020 | 32 | +0.7500 | +0.4300 | +0.1100 |
| lockbox | 0 | market_transition_catchup_logistic | 0.050 | 23 | +1.0800 | +0.8500 | +0.6200 |
| lockbox | 0 | market_transition_catchup_logistic | 0.080 | 22 | +0.5800 | +0.3600 | +0.1400 |
| lockbox | 0 | market_transition_catchup_logistic | 0.100 | 18 | +0.4600 | +0.2800 | +0.1000 |
| lockbox | 0 | market_transition_catchup_logistic | 0.120 | 14 | -0.6800 | -0.8200 | -0.9600 |
| lockbox | 0 | market_transition_catchup_logistic | 0.150 | 12 | -0.5400 | -0.6600 | -0.7800 |
| lockbox | 0 | market_transition_catchup_logistic | 0.200 | 7 | +0.6400 | +0.5700 | +0.5000 |
| lockbox | 0 | market_transition_catchup_logistic__with_bucket | 0.020 | 28 | +1.1900 | +0.9100 | +0.6300 |

## Readout

- Acceptance criterion: enhanced market+GetTopLive must beat market-only after 1c and 2c slippage, including lockbox.
- Current readout: settlement residual passes, but CLV fails; this supports hold-to-settlement residual research, not a short-horizon scalp.
- Trade ledgers dedupe by `canonical_exposure_id = match_id + current_game_number + side`. MAP_WINNER and MATCH_WINNER_GAME3_PROXY rows for the same map/side collapse into one trade — they are economically equivalent (map-equivalent scope).
- `label_market_bucket` is treated as provenance only, NOT as a model feature. Each model family runs twice: base variant (no bucket) and `__with_bucket` ablation. If edge disappears without the bucket feature, flag as provenance/label artifact.
- CLV uses future executable book rows in the same match/market/token stream, within 20s after the target horizon; positive future bid minus current ask is the conservative short-horizon test.

## Files Written

- `market_residual_gettoplive_report.md`
- `price_bucket_state_residuals.csv`
- `market_anchor_model_predictions.csv`
- `market_anchor_model_trades.csv`
- `gettoplive_clv_event_study.csv`
- `transition_entry_event_study.csv`
- `market_anchor_model_summary.csv`
- `market_anchor_provenance_diagnostic.csv`
- `candidate_selection.csv`
- `bucket_artifact_check.csv`
- `duplicate_exposure_impact.csv`
- `instrument_provenance_diagnostic.csv`
