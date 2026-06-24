# Walk-Forward Model Research

Method: train only on past matches, choose entry thresholds on past validation matches, then score the next future match block once. Trade ledgers dedupe to first qualifying row per `match_id` and `label_market_bucket`.

## Data Audit

- Source rows: 34,254
- Matches: 135
- Development matches: 108
- Lockbox matches: 27
- Markets: 132
- Tradable rows: 14,033
- Rows with tower state: 18,447
- Rows with building state: 14,169
- First timestamp: 2026-05-26T08:56:02.324+00:00
- Last timestamp: 2026-06-05T13:23:44.613+00:00

## Folds

| fold | fit_matches | validation_matches | test_matches | training_cutoff_match_time |
| --- | --- | --- | --- | --- |
| 1 | 38 | 12 | 11 | 2026-05-30T17:20:46.978+00:00 |
| 2 | 46 | 15 | 11 | 2026-05-31T18:17:58.840+00:00 |
| 3 | 54 | 18 | 11 | 2026-06-01T15:55:39.100+00:00 |
| 4 | 62 | 21 | 11 | 2026-06-02T13:14:29.781+00:00 |
| 5 | 70 | 24 | 11 | 2026-06-03T01:22:10.007+00:00 |

## Probability Benchmarks

| model_name | model_type | pred_rows | pred_auc | pred_log_loss | pred_brier | pred_avg_prob | pred_realized_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| market_baseline_ask | benchmark_probability | 14033 | 0.822 | 0.523 | 0.174 | 0.514 | 48.5% |
| hand_composite_proxy | benchmark_probability | 14027 | 0.744 | 0.613 | 0.209 | 0.489 | 48.5% |

## Walk-Forward Comparison

| model_name | model_type | folds | median_threshold | auc | log_loss | brier | trades | win_rate | avg_ask | avg_edge | avg_pnl | total_pnl | max_drawdown | avg_pnl_slip_1c | total_pnl_slip_1c | avg_pnl_slip_2c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | 5 | n/a | 83.8% | 0.493 | 0.163 | 14 | 85.4% | 0.695 | +0.2060 | +0.1592 | +2.1300 | -0.6600 | +0.1492 | +1.9900 | +0.1392 | +1.8500 |
| all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | 5 | n/a | 83.8% | 0.493 | 0.163 | 15 | 61.6% | 0.496 | +0.2325 | +0.1204 | +1.8600 | -0.6500 | +0.1104 | +1.7100 | +0.1004 | +1.5600 |
| all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | 5 | n/a | 83.8% | 0.493 | 0.163 | 9 | 68.8% | 0.547 | +0.3895 | +0.1406 | +0.7600 | -0.6800 | +0.1306 | +0.6700 | +0.1206 | +0.5800 |
| logistic_residual_trade | market_aware_residual | 5 | 0.600 | 82.7% | 0.539 | 0.168 | 42 | 75.5% | 0.753 | +0.1730 | +0.0017 | +0.2820 | -1.7500 | -0.0083 | -0.1380 | -0.0183 | -0.5580 |
| rf_fair_state | fair_probability | 5 | 0.120 | 84.8% | 0.518 | 0.162 | 39 | 32.7% | 0.359 | +0.2398 | -0.0315 | -1.2700 | -2.3600 | -0.0415 | -1.6600 | -0.0515 | -2.0500 |
| hgb_fair_state | fair_probability | 5 | 0.200 | 85.6% | 0.526 | 0.156 | 32 | 37.4% | 0.393 | +0.2666 | -0.0189 | -1.4200 | -1.5200 | -0.0289 | -1.7400 | -0.0389 | -2.0600 |
| logistic_fair_state | fair_probability | 5 | 0.200 | 82.7% | 0.539 | 0.168 | 36 | 30.2% | 0.389 | +0.2375 | -0.0877 | -3.8700 | -2.3600 | -0.0977 | -4.2300 | -0.1077 | -4.5900 |

## Fold Metrics

| fold | model_name | model_type | selected_threshold | pred_auc | pred_log_loss | pred_brier | trade_trades | trade_win_rate | trade_avg_ask | trade_avg_edge | trade_avg_pnl | trade_total_pnl | trade_total_pnl_slip_1c | trade_total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.890 | 0.445 | 0.134 | 0 | n/a | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| 1 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.890 | 0.445 | 0.134 | 0 | n/a | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| 1 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.890 | 0.445 | 0.134 | 0 | n/a | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| 1 | hgb_fair_state | fair_probability | 0.020 | 0.965 | 0.255 | 0.078 | 6 | 16.7% | 0.303 | +0.1648 | -0.1367 | -0.8200 | -0.8800 | -0.9400 |
| 1 | logistic_fair_state | fair_probability | 0.020 | 0.893 | 0.476 | 0.117 | 8 | 12.5% | 0.348 | +0.1716 | -0.2225 | -1.7800 | -1.8600 | -1.9400 |
| 1 | logistic_residual_trade | market_aware_residual | 0.700 | 0.893 | 0.476 | 0.117 | 6 | 50.0% | 0.757 | +0.0654 | -0.2567 | -1.5400 | -1.6000 | -1.6600 |
| 1 | rf_fair_state | fair_probability | 0.020 | 0.921 | 0.351 | 0.112 | 6 | 16.7% | 0.303 | +0.1410 | -0.1367 | -0.8200 | -0.8800 | -0.9400 |
| 2 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.869 | 0.483 | 0.159 | 4 | 75.0% | 0.605 | +0.3064 | +0.1450 | +0.5800 | +0.5400 | +0.5000 |
| 2 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.869 | 0.483 | 0.159 | 2 | 50.0% | 0.335 | +0.3681 | +0.1650 | +0.3300 | +0.3100 | +0.2900 |
| 2 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.869 | 0.483 | 0.159 | 2 | 50.0% | 0.370 | +0.5699 | +0.1300 | +0.2600 | +0.2400 | +0.2200 |
| 2 | hgb_fair_state | fair_probability | 0.200 | 0.875 | 0.693 | 0.151 | 4 | 50.0% | 0.438 | +0.3860 | +0.0625 | +0.2500 | +0.2100 | +0.1700 |
| 2 | logistic_fair_state | fair_probability | 0.200 | 0.839 | 0.506 | 0.163 | 4 | 50.0% | 0.367 | +0.3835 | +0.1325 | +0.5300 | +0.4900 | +0.4500 |
| 2 | logistic_residual_trade | market_aware_residual | 0.500 | 0.839 | 0.506 | 0.163 | 8 | 100.0% | 0.795 | +0.3270 | +0.2050 | +1.6400 | +1.5600 | +1.4800 |
| 2 | rf_fair_state | fair_probability | 0.200 | 0.857 | 0.548 | 0.162 | 7 | 28.6% | 0.307 | +0.3501 | -0.0214 | -0.1500 | -0.2200 | -0.2900 |
| 3 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.759 | 0.598 | 0.201 | 2 | 100.0% | 0.635 | +0.2715 | +0.3650 | +0.7300 | +0.7100 | +0.6900 |
| 3 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.759 | 0.598 | 0.201 | 2 | 50.0% | 0.460 | +0.2103 | +0.0400 | +0.0800 | +0.0600 | +0.0400 |
| 3 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.759 | 0.598 | 0.201 | 1 | 100.0% | 0.470 | +0.4809 | +0.5300 | +0.5300 | +0.5200 | +0.5100 |
| 3 | hgb_fair_state | fair_probability | 0.200 | 0.746 | 0.744 | 0.234 | 7 | 42.9% | 0.430 | +0.3173 | -0.0014 | -0.0100 | -0.0800 | -0.1500 |
| 3 | logistic_fair_state | fair_probability | 0.200 | 0.748 | 0.753 | 0.228 | 6 | 33.3% | 0.473 | +0.2914 | -0.1400 | -0.8400 | -0.9000 | -0.9600 |
| 3 | logistic_residual_trade | market_aware_residual | 0.550 | 0.748 | 0.753 | 0.228 | 9 | 66.7% | 0.784 | +0.2347 | -0.1176 | -1.0580 | -1.1480 | -1.2380 |
| 3 | rf_fair_state | fair_probability | 0.120 | 0.771 | 0.711 | 0.216 | 7 | 57.1% | 0.380 | +0.3018 | +0.1914 | +1.3400 | +1.2700 | +1.2000 |
| 4 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.817 | 0.466 | 0.162 | 3 | 66.7% | 0.760 | +0.1213 | -0.0933 | -0.2800 | -0.3100 | -0.3400 |
| 4 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.817 | 0.466 | 0.162 | 4 | 75.0% | 0.587 | +0.1538 | +0.1625 | +0.6500 | +0.6100 | +0.5700 |
| 4 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.817 | 0.466 | 0.162 | 2 | 50.0% | 0.680 | +0.2473 | -0.1800 | -0.3600 | -0.3800 | -0.4000 |
| 4 | hgb_fair_state | fair_probability | 0.200 | 0.850 | 0.450 | 0.152 | 4 | 50.0% | 0.410 | +0.2121 | +0.0900 | +0.3600 | +0.3200 | +0.2800 |
| 4 | logistic_fair_state | fair_probability | 0.020 | 0.813 | 0.501 | 0.173 | 8 | 25.0% | 0.402 | +0.0979 | -0.1525 | -1.2200 | -1.3000 | -1.3800 |
| 4 | logistic_residual_trade | market_aware_residual | 0.650 | 0.813 | 0.501 | 0.173 | 7 | 85.7% | 0.679 | +0.0639 | +0.1786 | +1.2500 | +1.1800 | +1.1100 |
| 4 | rf_fair_state | fair_probability | 0.050 | 0.848 | 0.446 | 0.153 | 8 | 25.0% | 0.402 | +0.1307 | -0.1525 | -1.2200 | -1.3000 | -1.3800 |
| 5 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.855 | 0.470 | 0.157 | 5 | 100.0% | 0.780 | +0.1248 | +0.2200 | +1.1000 | +1.0500 | +1.0000 |
| 5 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.855 | 0.470 | 0.157 | 7 | 71.4% | 0.600 | +0.1979 | +0.1143 | +0.8000 | +0.7300 | +0.6600 |
| 5 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.855 | 0.470 | 0.157 | 4 | 75.0% | 0.667 | +0.2599 | +0.0825 | +0.3300 | +0.2900 | +0.2500 |
| 5 | hgb_fair_state | fair_probability | 0.200 | 0.844 | 0.486 | 0.164 | 11 | 27.3% | 0.382 | +0.2528 | -0.1091 | -1.2000 | -1.3100 | -1.4200 |
| 5 | logistic_fair_state | fair_probability | 0.200 | 0.844 | 0.462 | 0.158 | 10 | 30.0% | 0.356 | +0.2430 | -0.0560 | -0.5600 | -0.6600 | -0.7600 |
| 5 | logistic_residual_trade | market_aware_residual | 0.600 | 0.844 | 0.462 | 0.158 | 12 | 75.0% | 0.751 | +0.1741 | -0.0008 | -0.0100 | -0.1300 | -0.2500 |
| 5 | rf_fair_state | fair_probability | 0.200 | 0.842 | 0.532 | 0.164 | 11 | 36.4% | 0.402 | +0.2754 | -0.0382 | -0.4200 | -0.5300 | -0.6400 |

## Final Lockbox Check

Selected from walk-forward by 1c-slippage PnL: `all_nw_mom_discount_nw8000_mom5000_ask90`.

| model_name | model_type | selected_threshold | pred_rows | pred_auc | pred_log_loss | pred_brier | trade_trades | trade_win_rate | trade_avg_ask | trade_avg_edge | trade_avg_pnl | trade_total_pnl | trade_total_pnl_slip_1c | trade_total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | lockbox_selected | n/a | 8180 | 0.909 | 0.386 | 0.128 | 8 | 87.5% | 0.644 | +0.2721 | +0.2313 | +1.8500 | +1.7700 | +1.6900 |

## Calibration By Probability Bucket

| model_name | prob_bucket | rows | avg_prob | realized_win_rate |
| --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (-0.001, 0.2] | 2085 | 0.056 | 2.7% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.2, 0.4] | 990 | 0.306 | 25.3% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.4, 0.6] | 2398 | 0.502 | 53.3% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.6, 0.8] | 1014 | 0.692 | 76.2% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.8, 1.0] | 1693 | 0.938 | 96.6% |
| hgb_fair_state | (-0.001, 0.2] | 4352 | 0.061 | 8.8% |
| hgb_fair_state | (0.2, 0.4] | 1519 | 0.290 | 33.2% |
| hgb_fair_state | (0.4, 0.6] | 2685 | 0.509 | 52.3% |
| hgb_fair_state | (0.6, 0.8] | 1391 | 0.733 | 66.5% |
| hgb_fair_state | (0.8, 1.0] | 2756 | 0.917 | 87.4% |
| logistic_fair_state | (-0.001, 0.2] | 4303 | 0.074 | 11.9% |
| logistic_fair_state | (0.2, 0.4] | 1737 | 0.274 | 31.2% |
| logistic_fair_state | (0.4, 0.6] | 2246 | 0.475 | 50.5% |
| logistic_fair_state | (0.6, 0.8] | 1251 | 0.721 | 66.3% |
| logistic_fair_state | (0.8, 1.0] | 3166 | 0.901 | 82.4% |
| logistic_residual_trade | (-0.001, 0.2] | 4303 | 0.074 | 11.9% |
| logistic_residual_trade | (0.2, 0.4] | 1737 | 0.274 | 31.2% |
| logistic_residual_trade | (0.4, 0.6] | 2246 | 0.475 | 50.5% |
| logistic_residual_trade | (0.6, 0.8] | 1251 | 0.721 | 66.3% |
| logistic_residual_trade | (0.8, 1.0] | 3166 | 0.901 | 82.4% |
| rf_fair_state | (-0.001, 0.2] | 3851 | 0.049 | 7.7% |
| rf_fair_state | (0.2, 0.4] | 1785 | 0.292 | 33.2% |
| rf_fair_state | (0.4, 0.6] | 3027 | 0.496 | 51.2% |
| rf_fair_state | (0.6, 0.8] | 1169 | 0.663 | 61.3% |
| rf_fair_state | (0.8, 1.0] | 2871 | 0.922 | 85.9% |

## Threshold Search

| fold | model_name | threshold_type | threshold | trades | avg_pnl | total_pnl | avg_pnl_slip_1c | total_pnl_slip_1c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | hgb_fair_state | edge | 0.020 | 8 | -0.1500 | -1.2000 | -0.1600 | -1.2800 |
| 1 | hgb_fair_state | edge | 0.050 | 7 | -0.3443 | -2.4100 | -0.3543 | -2.4800 |
| 1 | hgb_fair_state | edge | 0.080 | 7 | -0.3443 | -2.4100 | -0.3543 | -2.4800 |
| 1 | hgb_fair_state | edge | 0.100 | 7 | -0.3443 | -2.4100 | -0.3543 | -2.4800 |
| 1 | hgb_fair_state | edge | 0.120 | 7 | -0.3443 | -2.4100 | -0.3543 | -2.4800 |
| 1 | hgb_fair_state | edge | 0.150 | 7 | -0.3371 | -2.3600 | -0.3471 | -2.4300 |
| 1 | hgb_fair_state | edge | 0.200 | 7 | -0.1814 | -1.2700 | -0.1914 | -1.3400 |
| 1 | logistic_fair_state | edge | 0.020 | 8 | -0.1000 | -0.8000 | -0.1100 | -0.8800 |
| 1 | logistic_fair_state | edge | 0.050 | 8 | -0.2250 | -1.8000 | -0.2350 | -1.8800 |
| 1 | logistic_fair_state | edge | 0.080 | 8 | -0.2263 | -1.8100 | -0.2363 | -1.8900 |
| 1 | logistic_fair_state | edge | 0.100 | 7 | -0.2786 | -1.9500 | -0.2886 | -2.0200 |
| 1 | logistic_fair_state | edge | 0.120 | 7 | -0.2743 | -1.9200 | -0.2843 | -1.9900 |
| 1 | logistic_fair_state | edge | 0.150 | 7 | -0.2500 | -1.7500 | -0.2600 | -1.8200 |
| 1 | logistic_fair_state | edge | 0.200 | 5 | -0.2220 | -1.1100 | -0.2320 | -1.1600 |
| 1 | logistic_residual_trade | trade_probability | 0.500 | 8 | +0.1750 | +1.4000 | +0.1650 | +1.3200 |
| 1 | logistic_residual_trade | trade_probability | 0.550 | 8 | +0.1750 | +1.4000 | +0.1650 | +1.3200 |
| 1 | logistic_residual_trade | trade_probability | 0.600 | 8 | +0.1812 | +1.4500 | +0.1712 | +1.3700 |
| 1 | logistic_residual_trade | trade_probability | 0.650 | 8 | +0.1812 | +1.4500 | +0.1712 | +1.3700 |
| 1 | logistic_residual_trade | trade_probability | 0.700 | 8 | +0.2888 | +2.3100 | +0.2787 | +2.2300 |
| 1 | rf_fair_state | edge | 0.020 | 8 | -0.1000 | -0.8000 | -0.1100 | -0.8800 |
| 1 | rf_fair_state | edge | 0.050 | 8 | -0.2250 | -1.8000 | -0.2350 | -1.8800 |
| 1 | rf_fair_state | edge | 0.080 | 8 | -0.3350 | -2.6800 | -0.3450 | -2.7600 |
| 1 | rf_fair_state | edge | 0.100 | 8 | -0.2062 | -1.6500 | -0.2162 | -1.7300 |
| 1 | rf_fair_state | edge | 0.120 | 8 | -0.2062 | -1.6500 | -0.2162 | -1.7300 |
| 1 | rf_fair_state | edge | 0.150 | 7 | -0.1071 | -0.7500 | -0.1171 | -0.8200 |
| 1 | rf_fair_state | edge | 0.200 | 7 | -0.1857 | -1.3000 | -0.1957 | -1.3700 |
| 2 | hgb_fair_state | edge | 0.020 | 8 | -0.2737 | -2.1900 | -0.2838 | -2.2700 |
| 2 | hgb_fair_state | edge | 0.050 | 8 | -0.1300 | -1.0400 | -0.1400 | -1.1200 |
| 2 | hgb_fair_state | edge | 0.080 | 7 | -0.1300 | -0.9100 | -0.1400 | -0.9800 |
| 2 | hgb_fair_state | edge | 0.100 | 7 | -0.1329 | -0.9300 | -0.1429 | -1.0000 |
| 2 | hgb_fair_state | edge | 0.120 | 7 | -0.1286 | -0.9000 | -0.1386 | -0.9700 |
| 2 | hgb_fair_state | edge | 0.150 | 7 | -0.1357 | -0.9500 | -0.1457 | -1.0200 |
| 2 | hgb_fair_state | edge | 0.200 | 7 | -0.1200 | -0.8400 | -0.1300 | -0.9100 |
| 2 | logistic_fair_state | edge | 0.020 | 9 | -0.2500 | -2.2500 | -0.2600 | -2.3400 |
| 2 | logistic_fair_state | edge | 0.050 | 8 | -0.2600 | -2.0800 | -0.2700 | -2.1600 |
| 2 | logistic_fair_state | edge | 0.080 | 8 | -0.2562 | -2.0500 | -0.2662 | -2.1300 |
| 2 | logistic_fair_state | edge | 0.100 | 8 | -0.2525 | -2.0200 | -0.2625 | -2.1000 |
| 2 | logistic_fair_state | edge | 0.120 | 8 | -0.2487 | -1.9900 | -0.2587 | -2.0700 |
| 2 | logistic_fair_state | edge | 0.150 | 8 | -0.1175 | -0.9400 | -0.1275 | -1.0200 |
| 2 | logistic_fair_state | edge | 0.200 | 8 | -0.1037 | -0.8300 | -0.1138 | -0.9100 |
| 2 | logistic_residual_trade | trade_probability | 0.500 | 8 | +0.0312 | +0.2500 | +0.0212 | +0.1700 |
| 2 | logistic_residual_trade | trade_probability | 0.550 | 8 | +0.0312 | +0.2500 | +0.0212 | +0.1700 |
| 2 | logistic_residual_trade | trade_probability | 0.600 | 8 | -0.0063 | -0.0500 | -0.0163 | -0.1300 |
| 2 | logistic_residual_trade | trade_probability | 0.650 | 8 | -0.0063 | -0.0500 | -0.0163 | -0.1300 |
| 2 | logistic_residual_trade | trade_probability | 0.700 | 7 | -0.0243 | -0.1700 | -0.0343 | -0.2400 |
| 2 | rf_fair_state | edge | 0.020 | 8 | -0.1625 | -1.3000 | -0.1725 | -1.3800 |
| 2 | rf_fair_state | edge | 0.050 | 8 | -0.1625 | -1.3000 | -0.1725 | -1.3800 |
| 2 | rf_fair_state | edge | 0.080 | 8 | -0.1675 | -1.3400 | -0.1775 | -1.4200 |
| 2 | rf_fair_state | edge | 0.100 | 8 | -0.1687 | -1.3500 | -0.1787 | -1.4300 |
| 2 | rf_fair_state | edge | 0.120 | 8 | -0.1687 | -1.3500 | -0.1787 | -1.4300 |
| 2 | rf_fair_state | edge | 0.150 | 8 | -0.1263 | -1.0100 | -0.1363 | -1.0900 |
| 2 | rf_fair_state | edge | 0.200 | 8 | -0.0988 | -0.7900 | -0.1088 | -0.8700 |
| 3 | hgb_fair_state | edge | 0.020 | 13 | -0.0008 | -0.0100 | -0.0108 | -0.1400 |
| 3 | hgb_fair_state | edge | 0.050 | 13 | -0.0023 | -0.0300 | -0.0123 | -0.1600 |
| 3 | hgb_fair_state | edge | 0.080 | 13 | -0.0038 | -0.0500 | -0.0138 | -0.1800 |
| 3 | hgb_fair_state | edge | 0.100 | 13 | -0.0038 | -0.0500 | -0.0138 | -0.1800 |
| 3 | hgb_fair_state | edge | 0.120 | 13 | -0.0038 | -0.0500 | -0.0138 | -0.1800 |
| 3 | hgb_fair_state | edge | 0.150 | 13 | -0.0015 | -0.0200 | -0.0115 | -0.1500 |
| 3 | hgb_fair_state | edge | 0.200 | 12 | +0.0142 | +0.1700 | +0.0042 | +0.0500 |
| 3 | logistic_fair_state | edge | 0.020 | 16 | -0.0756 | -1.2100 | -0.0856 | -1.3700 |
| 3 | logistic_fair_state | edge | 0.050 | 16 | -0.0756 | -1.2100 | -0.0856 | -1.3700 |
| 3 | logistic_fair_state | edge | 0.080 | 16 | -0.0737 | -1.1800 | -0.0838 | -1.3400 |
| 3 | logistic_fair_state | edge | 0.100 | 15 | -0.0873 | -1.3100 | -0.0973 | -1.4600 |
| 3 | logistic_fair_state | edge | 0.120 | 13 | -0.0838 | -1.0900 | -0.0938 | -1.2200 |
| 3 | logistic_fair_state | edge | 0.150 | 13 | -0.0838 | -1.0900 | -0.0938 | -1.2200 |
| 3 | logistic_fair_state | edge | 0.200 | 11 | -0.0127 | -0.1400 | -0.0227 | -0.2500 |
| 3 | logistic_residual_trade | trade_probability | 0.500 | 12 | +0.0758 | +0.9100 | +0.0658 | +0.7900 |
| 3 | logistic_residual_trade | trade_probability | 0.550 | 12 | +0.1550 | +1.8600 | +0.1450 | +1.7400 |
| 3 | logistic_residual_trade | trade_probability | 0.600 | 12 | +0.0617 | +0.7400 | +0.0517 | +0.6200 |
| 3 | logistic_residual_trade | trade_probability | 0.650 | 12 | +0.0367 | +0.4400 | +0.0267 | +0.3200 |
| 3 | logistic_residual_trade | trade_probability | 0.700 | 12 | +0.0358 | +0.4300 | +0.0258 | +0.3100 |
| 3 | rf_fair_state | edge | 0.020 | 13 | -0.1362 | -1.7700 | -0.1462 | -1.9000 |
| 3 | rf_fair_state | edge | 0.050 | 13 | -0.1362 | -1.7700 | -0.1462 | -1.9000 |
| 3 | rf_fair_state | edge | 0.080 | 13 | -0.0562 | -0.7300 | -0.0662 | -0.8600 |
| 3 | rf_fair_state | edge | 0.100 | 12 | -0.0475 | -0.5700 | -0.0575 | -0.6900 |
| 3 | rf_fair_state | edge | 0.120 | 12 | -0.0458 | -0.5500 | -0.0558 | -0.6700 |
| 3 | rf_fair_state | edge | 0.150 | 12 | -0.0475 | -0.5700 | -0.0575 | -0.6900 |
| 3 | rf_fair_state | edge | 0.200 | 12 | -0.0633 | -0.7600 | -0.0733 | -0.8800 |
| 4 | hgb_fair_state | edge | 0.020 | 16 | +0.0631 | +1.0100 | +0.0531 | +0.8500 |
| 4 | hgb_fair_state | edge | 0.050 | 16 | +0.0700 | +1.1200 | +0.0600 | +0.9600 |
| 4 | hgb_fair_state | edge | 0.080 | 16 | +0.0975 | +1.5600 | +0.0875 | +1.4000 |
| 4 | hgb_fair_state | edge | 0.100 | 15 | +0.0760 | +1.1400 | +0.0660 | +0.9900 |
| 4 | hgb_fair_state | edge | 0.120 | 15 | +0.0807 | +1.2100 | +0.0707 | +1.0600 |
| 4 | hgb_fair_state | edge | 0.150 | 14 | +0.0964 | +1.3500 | +0.0864 | +1.2100 |
| 4 | hgb_fair_state | edge | 0.200 | 11 | +0.1400 | +1.5400 | +0.1300 | +1.4300 |
| 4 | logistic_fair_state | edge | 0.020 | 16 | +0.0956 | +1.5300 | +0.0856 | +1.3700 |
| 4 | logistic_fair_state | edge | 0.050 | 15 | +0.0733 | +1.1000 | +0.0633 | +0.9500 |
| 4 | logistic_fair_state | edge | 0.080 | 15 | +0.0860 | +1.2900 | +0.0760 | +1.1400 |
| 4 | logistic_fair_state | edge | 0.100 | 15 | +0.0893 | +1.3400 | +0.0793 | +1.1900 |
| 4 | logistic_fair_state | edge | 0.120 | 15 | +0.0527 | +0.7900 | +0.0427 | +0.6400 |
| 4 | logistic_fair_state | edge | 0.150 | 13 | -0.0115 | -0.1500 | -0.0215 | -0.2800 |
| 4 | logistic_fair_state | edge | 0.200 | 8 | +0.0638 | +0.5100 | +0.0538 | +0.4300 |
| 4 | logistic_residual_trade | trade_probability | 0.500 | 16 | -0.0480 | -0.7680 | -0.0580 | -0.9280 |
| 4 | logistic_residual_trade | trade_probability | 0.550 | 16 | -0.0480 | -0.7680 | -0.0580 | -0.9280 |
| 4 | logistic_residual_trade | trade_probability | 0.600 | 15 | -0.0139 | -0.2080 | -0.0239 | -0.3580 |
| 4 | logistic_residual_trade | trade_probability | 0.650 | 15 | -0.0112 | -0.1680 | -0.0212 | -0.3180 |
| 4 | logistic_residual_trade | trade_probability | 0.700 | 15 | -0.0199 | -0.2980 | -0.0299 | -0.4480 |
| 4 | rf_fair_state | edge | 0.020 | 17 | +0.0471 | +0.8000 | +0.0371 | +0.6300 |
| 4 | rf_fair_state | edge | 0.050 | 17 | +0.1047 | +1.7800 | +0.0947 | +1.6100 |
| 4 | rf_fair_state | edge | 0.080 | 16 | +0.0812 | +1.3000 | +0.0712 | +1.1400 |

## Readout

- These are walk-forward research results, not deployment approval.
- Fair-probability models use state features only; ask/spread/liquidity are used only for edge conversion and the residual trade benchmark.
- Thresholds are selected on past validation matches inside each fold, then applied once to future matches.
- If no model or hand rule stays positive after 1c and 2c slippage, do not trade it.

## Files Written

- `walk_forward_model_report.md`
- `walk_forward_model_predictions.csv`
- `walk_forward_model_trades.csv`
