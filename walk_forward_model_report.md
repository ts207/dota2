# Walk-Forward Model Research

Method: train only on past matches, choose entry thresholds on past validation matches, then score the next future match block once. Trade ledgers dedupe to first qualifying row per `match_id` and `label_market_bucket`.

## Data Audit

- Source rows: 34,254
- Matches: 135
- Development matches: 108
- Lockbox matches: 27
- Markets: 132
- Tradable rows: 9,981
- Minimum game time for tradable rows: 600s
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
| market_baseline_ask | benchmark_probability | 9981 | 0.833 | 0.507 | 0.167 | 0.513 | 48.3% |
| hand_composite_proxy | benchmark_probability | 9975 | 0.784 | 0.577 | 0.193 | 0.485 | 48.3% |

Note: hand-rule benchmark AUC/log-loss/Brier use the shared composite `state_prob_proxy`; they are heuristic diagnostics, not calibrated rule probabilities. Trade metrics are the relevant hand-rule measure.

## Game-Time Sensitivity

| min_game_time_sec | tradable_rows | tradable_matches | structure_nw8000_struct1_ask75_trades | structure_nw8000_struct1_ask75_total_pnl_slip_1c | nw_mom_discount_nw8000_mom5000_ask90_trades | nw_mom_discount_nw8000_mom5000_ask90_total_pnl_slip_1c | scoreboard_lag_nw3000_score6_edge10_trades | scoreboard_lag_nw3000_score6_edge10_total_pnl_slip_1c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.000 | 13764.000 | 113.000 | 26.000 | +3.8800 | 38.000 | +4.4100 | +46.0000 | +2.8900 |
| 300.000 | 11955.000 | 110.000 | 26.000 | +3.8800 | 38.000 | +4.4100 | +46.0000 | +2.8900 |
| 600.000 | 9981.000 | 104.000 | 26.000 | +3.8800 | 38.000 | +4.4100 | +46.0000 | +2.8100 |
| 900.000 | 8289.000 | 102.000 | 26.000 | +3.8800 | 38.000 | +4.4100 | +45.0000 | +3.5700 |

## Walk-Forward Comparison

| model_name | model_type | folds | median_threshold | auc | log_loss | brier | trades | win_rate | avg_ask | avg_edge | avg_pnl | total_pnl | max_drawdown | avg_pnl_slip_1c | total_pnl_slip_1c | avg_pnl_slip_2c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | 5 | n/a | 78.2% | 0.552 | 0.186 | 14 | 85.4% | 0.695 | +0.2060 | +0.1592 | +2.1300 | -0.6600 | +0.1492 | +1.9900 | +0.1392 | +1.8500 |
| all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | 5 | n/a | 78.2% | 0.552 | 0.186 | 15 | 61.6% | 0.496 | +0.2325 | +0.1204 | +1.8600 | -0.6500 | +0.1104 | +1.7100 | +0.1004 | +1.5600 |
| logistic_residual_trade | market_aware_residual | 5 | 0.550 | 78.7% | 0.567 | 0.186 | 39 | 80.0% | 0.758 | +0.2321 | +0.0420 | +1.7120 | -1.7100 | +0.0320 | +1.3220 | +0.0220 | +0.9320 |
| rf_fair_state | fair_probability | 5 | 0.120 | 80.8% | 0.593 | 0.181 | 33 | 47.3% | 0.415 | +0.1825 | +0.0578 | +1.2300 | -1.3400 | +0.0478 | +0.9000 | +0.0378 | +0.5700 |
| all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | 5 | n/a | 78.2% | 0.552 | 0.186 | 9 | 68.8% | 0.547 | +0.3895 | +0.1406 | +0.7600 | -0.6800 | +0.1306 | +0.6700 | +0.1206 | +0.5800 |
| logistic_fair_state | fair_probability | 5 | 0.200 | 78.7% | 0.567 | 0.186 | 30 | 46.2% | 0.477 | +0.2307 | -0.0152 | -0.1000 | -1.3600 | -0.0252 | -0.4000 | -0.0352 | -0.7000 |
| hgb_fair_state | fair_probability | 5 | 0.100 | 80.5% | 0.672 | 0.181 | 29 | 41.9% | 0.429 | +0.2071 | -0.0099 | -1.7200 | -1.7800 | -0.0199 | -2.0100 | -0.0299 | -2.3000 |

## Fold Metrics

| fold | model_name | model_type | selected_threshold | pred_auc | pred_log_loss | pred_brier | trade_trades | trade_win_rate | trade_avg_ask | trade_avg_edge | trade_avg_pnl | trade_total_pnl | trade_total_pnl_slip_1c | trade_total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.869 | 0.501 | 0.156 | 0 | n/a | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| 1 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.869 | 0.501 | 0.156 | 0 | n/a | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| 1 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.869 | 0.501 | 0.156 | 0 | n/a | n/a | n/a | n/a | +0.0000 | +0.0000 | +0.0000 |
| 1 | hgb_fair_state | fair_probability | 0.020 | 0.960 | 0.313 | 0.090 | 5 | 20.0% | 0.344 | +0.1877 | -0.1440 | -0.7200 | -0.7700 | -0.8200 |
| 1 | logistic_fair_state | fair_probability | 0.080 | 0.915 | 0.445 | 0.109 | 6 | 50.0% | 0.575 | +0.1760 | -0.0750 | -0.4500 | -0.5100 | -0.5700 |
| 1 | logistic_residual_trade | market_aware_residual | 0.500 | 0.915 | 0.445 | 0.109 | 6 | 66.7% | 0.722 | +0.2651 | -0.0550 | -0.3300 | -0.3900 | -0.4500 |
| 1 | rf_fair_state | fair_probability | 0.050 | 0.943 | 0.364 | 0.111 | 5 | 20.0% | 0.344 | +0.1402 | -0.1440 | -0.7200 | -0.7700 | -0.8200 |
| 2 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.900 | 0.419 | 0.129 | 4 | 75.0% | 0.605 | +0.3064 | +0.1450 | +0.5800 | +0.5400 | +0.5000 |
| 2 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.900 | 0.419 | 0.129 | 2 | 50.0% | 0.335 | +0.3681 | +0.1650 | +0.3300 | +0.3100 | +0.2900 |
| 2 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.900 | 0.419 | 0.129 | 2 | 50.0% | 0.370 | +0.5699 | +0.1300 | +0.2600 | +0.2400 | +0.2200 |
| 2 | hgb_fair_state | fair_probability | 0.120 | 0.882 | 1.016 | 0.118 | 4 | 50.0% | 0.412 | +0.2091 | +0.0875 | +0.3500 | +0.3100 | +0.2700 |
| 2 | logistic_fair_state | fair_probability | 0.050 | 0.892 | 0.367 | 0.108 | 6 | 66.7% | 0.512 | +0.1556 | +0.1550 | +0.9300 | +0.8700 | +0.8100 |
| 2 | logistic_residual_trade | market_aware_residual | 0.700 | 0.892 | 0.367 | 0.108 | 5 | 100.0% | 0.824 | +0.1907 | +0.1760 | +0.8800 | +0.8300 | +0.7800 |
| 2 | rf_fair_state | fair_probability | 0.020 | 0.879 | 0.608 | 0.131 | 6 | 50.0% | 0.447 | +0.1450 | +0.0533 | +0.3200 | +0.2600 | +0.2000 |
| 3 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.634 | 0.691 | 0.247 | 2 | 100.0% | 0.635 | +0.2715 | +0.3650 | +0.7300 | +0.7100 | +0.6900 |
| 3 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.634 | 0.691 | 0.247 | 2 | 50.0% | 0.460 | +0.2103 | +0.0400 | +0.0800 | +0.0600 | +0.0400 |
| 3 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.634 | 0.691 | 0.247 | 1 | 100.0% | 0.470 | +0.4809 | +0.5300 | +0.5300 | +0.5200 | +0.5100 |
| 3 | hgb_fair_state | fair_probability | 0.050 | 0.610 | 0.931 | 0.319 | 7 | 42.9% | 0.631 | +0.2031 | -0.2029 | -1.4200 | -1.4900 | -1.5600 |
| 3 | logistic_fair_state | fair_probability | 0.200 | 0.606 | 0.868 | 0.310 | 4 | 50.0% | 0.570 | +0.2846 | -0.0700 | -0.2800 | -0.3200 | -0.3600 |
| 3 | logistic_residual_trade | market_aware_residual | 0.500 | 0.606 | 0.868 | 0.310 | 8 | 75.0% | 0.806 | +0.3792 | -0.0560 | -0.4480 | -0.5280 | -0.6080 |
| 3 | rf_fair_state | fair_probability | 0.120 | 0.637 | 0.874 | 0.287 | 6 | 50.0% | 0.387 | +0.2179 | +0.1133 | +0.6800 | +0.6200 | +0.5600 |
| 4 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.713 | 0.606 | 0.215 | 3 | 66.7% | 0.760 | +0.1213 | -0.0933 | -0.2800 | -0.3100 | -0.3400 |
| 4 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.713 | 0.606 | 0.215 | 4 | 75.0% | 0.587 | +0.1538 | +0.1625 | +0.6500 | +0.6100 | +0.5700 |
| 4 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.713 | 0.606 | 0.215 | 2 | 50.0% | 0.680 | +0.2473 | -0.1800 | -0.3600 | -0.3800 | -0.4000 |
| 4 | hgb_fair_state | fair_probability | 0.200 | 0.794 | 0.541 | 0.186 | 3 | 66.7% | 0.377 | +0.2682 | +0.2900 | +0.8700 | +0.8400 | +0.8100 |
| 4 | logistic_fair_state | fair_probability | 0.200 | 0.731 | 0.617 | 0.219 | 5 | 20.0% | 0.318 | +0.2735 | -0.1180 | -0.5900 | -0.6400 | -0.6900 |
| 4 | logistic_residual_trade | market_aware_residual | 0.600 | 0.731 | 0.617 | 0.219 | 8 | 75.0% | 0.718 | +0.1368 | +0.0325 | +0.2600 | +0.1800 | +0.1000 |
| 4 | rf_fair_state | fair_probability | 0.150 | 0.799 | 0.538 | 0.188 | 5 | 80.0% | 0.470 | +0.2058 | +0.3300 | +1.6500 | +1.6000 | +1.5500 |
| 5 | all_nw_mom_discount_nw8000_mom5000_ask90 | hand_rule_benchmark | n/a | 0.794 | 0.541 | 0.183 | 5 | 100.0% | 0.780 | +0.1248 | +0.2200 | +1.1000 | +1.0500 | +1.0000 |
| 5 | all_scoreboard_lag_nw3000_score6_edge10 | hand_rule_benchmark | n/a | 0.794 | 0.541 | 0.183 | 7 | 71.4% | 0.600 | +0.1979 | +0.1143 | +0.8000 | +0.7300 | +0.6600 |
| 5 | all_structure_nw8000_struct1_ask75 | hand_rule_benchmark | n/a | 0.794 | 0.541 | 0.183 | 4 | 75.0% | 0.667 | +0.2599 | +0.0825 | +0.3300 | +0.2900 | +0.2500 |
| 5 | hgb_fair_state | fair_probability | 0.100 | 0.776 | 0.560 | 0.191 | 10 | 30.0% | 0.380 | +0.1674 | -0.0800 | -0.8000 | -0.9000 | -1.0000 |
| 5 | logistic_fair_state | fair_probability | 0.200 | 0.789 | 0.539 | 0.184 | 9 | 44.4% | 0.412 | +0.2637 | +0.0322 | +0.2900 | +0.2000 | +0.1100 |
| 5 | logistic_residual_trade | market_aware_residual | 0.550 | 0.789 | 0.539 | 0.184 | 12 | 83.3% | 0.721 | +0.1886 | +0.1125 | +1.3500 | +1.2300 | +1.1100 |
| 5 | rf_fair_state | fair_probability | 0.120 | 0.783 | 0.580 | 0.189 | 11 | 36.4% | 0.427 | +0.2039 | -0.0636 | -0.7000 | -0.8100 | -0.9200 |

## Final Lockbox Check

Selected from walk-forward by 1c-slippage PnL: `all_nw_mom_discount_nw8000_mom5000_ask90`.

| model_name | model_type | selected_threshold | pred_rows | pred_auc | pred_log_loss | pred_brier | trade_trades | trade_win_rate | trade_avg_ask | trade_avg_edge | trade_avg_pnl | trade_total_pnl | trade_total_pnl_slip_1c | trade_total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | lockbox_selected | n/a | 1968 | 0.839 | 0.490 | 0.164 | 8 | 87.5% | 0.644 | +0.2721 | +0.2313 | +1.8500 | +1.7700 | +1.6900 |

## Calibration By Probability Bucket

| model_name | prob_bucket | rows | avg_prob | realized_win_rate |
| --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (-0.001, 0.2] | 398 | 0.096 | 8.0% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.2, 0.4] | 447 | 0.301 | 33.1% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.4, 0.6] | 311 | 0.499 | 45.3% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.6, 0.8] | 453 | 0.700 | 69.5% |
| all_nw_mom_discount_nw8000_mom5000_ask90 | (0.8, 1.0] | 359 | 0.899 | 88.9% |
| hgb_fair_state | (-0.001, 0.2] | 748 | 0.094 | 15.5% |
| hgb_fair_state | (0.2, 0.4] | 415 | 0.303 | 39.0% |
| hgb_fair_state | (0.4, 0.6] | 617 | 0.508 | 57.9% |
| hgb_fair_state | (0.6, 0.8] | 370 | 0.728 | 63.0% |
| hgb_fair_state | (0.8, 1.0] | 477 | 0.903 | 79.9% |
| logistic_fair_state | (-0.001, 0.2] | 745 | 0.124 | 15.6% |
| logistic_fair_state | (0.2, 0.4] | 468 | 0.278 | 42.9% |
| logistic_fair_state | (0.4, 0.6] | 562 | 0.471 | 55.2% |
| logistic_fair_state | (0.6, 0.8] | 255 | 0.727 | 68.2% |
| logistic_fair_state | (0.8, 1.0] | 597 | 0.880 | 75.0% |
| logistic_residual_trade | (-0.001, 0.2] | 745 | 0.124 | 15.6% |
| logistic_residual_trade | (0.2, 0.4] | 468 | 0.278 | 42.9% |
| logistic_residual_trade | (0.4, 0.6] | 562 | 0.471 | 55.2% |
| logistic_residual_trade | (0.6, 0.8] | 255 | 0.727 | 68.2% |
| logistic_residual_trade | (0.8, 1.0] | 597 | 0.880 | 75.0% |
| rf_fair_state | (-0.001, 0.2] | 595 | 0.062 | 12.3% |
| rf_fair_state | (0.2, 0.4] | 497 | 0.298 | 34.2% |
| rf_fair_state | (0.4, 0.6] | 735 | 0.494 | 56.6% |
| rf_fair_state | (0.6, 0.8] | 293 | 0.659 | 64.8% |
| rf_fair_state | (0.8, 1.0] | 507 | 0.909 | 78.9% |

## PnL Concentration

By market bucket:

| model_name | label_market_bucket | trades | matches | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | MAP_WINNER | 16 | 16 | 87.5% | +2.2800 | +2.1200 | +1.9600 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | MATCH_WINNER_GAME3_PROXY | 6 | 6 | 83.3% | +1.7000 | +1.6400 | +1.5800 |
| all_scoreboard_lag_nw3000_score6_edge10 | MAP_WINNER | 12 | 12 | 66.7% | +1.0400 | +0.9200 | +0.8000 |
| all_scoreboard_lag_nw3000_score6_edge10 | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.8200 | +0.7900 | +0.7600 |
| all_structure_nw8000_struct1_ask75 | MATCH_WINNER_GAME3_PROXY | 3 | 3 | 66.7% | +0.7700 | +0.7400 | +0.7100 |
| all_structure_nw8000_struct1_ask75 | MAP_WINNER | 6 | 6 | 66.7% | -0.0100 | -0.0700 | -0.1300 |
| hgb_fair_state | MATCH_WINNER_GAME3_PROXY | 6 | 6 | 33.3% | -0.2700 | -0.3300 | -0.3900 |
| hgb_fair_state | MAP_WINNER | 23 | 23 | 39.1% | -1.4500 | -1.6800 | -1.9100 |
| logistic_fair_state | MATCH_WINNER_GAME3_PROXY | 6 | 6 | 50.0% | +0.0700 | +0.0100 | -0.0500 |
| logistic_fair_state | MAP_WINNER | 24 | 24 | 45.8% | -0.1700 | -0.4100 | -0.6500 |
| logistic_residual_trade | MAP_WINNER | 32 | 32 | 78.1% | +1.3500 | +1.0300 | +0.7100 |
| logistic_residual_trade | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 85.7% | +0.3620 | +0.2920 | +0.2220 |
| rf_fair_state | MAP_WINNER | 26 | 26 | 46.2% | +1.3600 | +1.1000 | +0.8400 |
| rf_fair_state | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 42.9% | -0.1300 | -0.2000 | -0.2700 |

Largest match contributions by absolute 1c-slippage PnL:

| model_name | match_id | trades | buckets | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8839284303 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836220468 | 1 | 1 | 0.0% | -0.6600 | -0.6700 | -0.6800 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8837052943 | 2 | 2 | 100.0% | +0.6500 | +0.6300 | +0.6100 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8834230023 | 2 | 2 | 100.0% | +0.6300 | +0.6100 | +0.5900 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8834932746 | 1 | 1 | 100.0% | +0.5300 | +0.5200 | +0.5100 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8837288943 | 1 | 1 | 0.0% | -0.3900 | -0.4000 | -0.4100 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836692392 | 1 | 1 | 100.0% | +0.3900 | +0.3800 | +0.3700 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836485118 | 1 | 1 | 100.0% | +0.3300 | +0.3200 | +0.3100 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836897842 | 1 | 1 | 100.0% | +0.3000 | +0.2900 | +0.2800 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8835818773 | 1 | 1 | 100.0% | +0.2400 | +0.2300 | +0.2200 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8837725916 | 1 | 1 | 100.0% | +0.2200 | +0.2100 | +0.2000 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8835609186 | 1 | 1 | 100.0% | +0.2000 | +0.1900 | +0.1800 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8833592202 | 1 | 1 | 0.0% | -0.1600 | -0.1700 | -0.1800 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836916511 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8837692542 | 1 | 1 | 100.0% | +0.1700 | +0.1600 | +0.1500 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836485094 | 1 | 1 | 100.0% | +0.1600 | +0.1500 | +0.1400 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836292316 | 1 | 1 | 100.0% | +0.1400 | +0.1300 | +0.1200 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836445371 | 1 | 1 | 100.0% | +0.1200 | +0.1100 | +0.1000 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8833570075 | 1 | 1 | 100.0% | +0.1100 | +0.1000 | +0.0900 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 8836624153 | 1 | 1 | 100.0% | +0.1000 | +0.0900 | +0.0800 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836583316 | 1 | 1 | 0.0% | -0.6500 | -0.6600 | -0.6700 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8834932746 | 1 | 1 | 100.0% | +0.5400 | +0.5300 | +0.5200 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836292316 | 1 | 1 | 0.0% | -0.5100 | -0.5200 | -0.5300 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8835609186 | 1 | 1 | 0.0% | -0.4600 | -0.4700 | -0.4800 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836485118 | 1 | 1 | 100.0% | +0.4700 | +0.4600 | +0.4500 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836442480 | 1 | 1 | 100.0% | +0.4500 | +0.4400 | +0.4300 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8835818773 | 1 | 1 | 100.0% | +0.4100 | +0.4000 | +0.3900 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836220468 | 1 | 1 | 100.0% | +0.4100 | +0.4000 | +0.3900 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8834230023 | 1 | 1 | 100.0% | +0.4000 | +0.3900 | +0.3800 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836624153 | 1 | 1 | 100.0% | +0.3900 | +0.3800 | +0.3700 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836485094 | 1 | 1 | 0.0% | -0.3300 | -0.3400 | -0.3500 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836692392 | 1 | 1 | 100.0% | +0.3500 | +0.3400 | +0.3300 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8835703860 | 1 | 1 | 100.0% | +0.3400 | +0.3300 | +0.3200 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8836445371 | 1 | 1 | 100.0% | +0.1200 | +0.1100 | +0.1000 |
| all_scoreboard_lag_nw3000_score6_edge10 | 8833592202 | 1 | 1 | 0.0% | -0.0700 | -0.0800 | -0.0900 |
| all_structure_nw8000_struct1_ask75 | 8836583316 | 1 | 1 | 0.0% | -0.6800 | -0.6900 | -0.7000 |
| all_structure_nw8000_struct1_ask75 | 8836220468 | 1 | 1 | 0.0% | -0.6600 | -0.6700 | -0.6800 |
| all_structure_nw8000_struct1_ask75 | 8834932746 | 1 | 1 | 100.0% | +0.5300 | +0.5200 | +0.5100 |
| all_structure_nw8000_struct1_ask75 | 8834230023 | 1 | 1 | 100.0% | +0.4100 | +0.4000 | +0.3900 |
| all_structure_nw8000_struct1_ask75 | 8836692392 | 1 | 1 | 100.0% | +0.3900 | +0.3800 | +0.3700 |
| all_structure_nw8000_struct1_ask75 | 8836485118 | 1 | 1 | 100.0% | +0.3300 | +0.3200 | +0.3100 |
| all_structure_nw8000_struct1_ask75 | 8835728100 | 1 | 1 | 100.0% | +0.3000 | +0.2900 | +0.2800 |
| all_structure_nw8000_struct1_ask75 | 8836624153 | 1 | 1 | 100.0% | +0.2900 | +0.2800 | +0.2700 |
| all_structure_nw8000_struct1_ask75 | 8833592202 | 1 | 1 | 0.0% | -0.1500 | -0.1600 | -0.1700 |
| hgb_fair_state | 8835609186 | 1 | 1 | 0.0% | -0.7800 | -0.7900 | -0.8000 |
| hgb_fair_state | 8835703860 | 1 | 1 | 100.0% | +0.7700 | +0.7600 | +0.7500 |
| hgb_fair_state | 8835490699 | 1 | 1 | 0.0% | -0.6700 | -0.6800 | -0.6900 |
| hgb_fair_state | 8836220468 | 1 | 1 | 100.0% | +0.6100 | +0.6000 | +0.5900 |
| hgb_fair_state | 8836485118 | 1 | 1 | 0.0% | -0.5700 | -0.5800 | -0.5900 |
| hgb_fair_state | 8834230023 | 2 | 2 | 100.0% | +0.5800 | +0.5600 | +0.5400 |
| hgb_fair_state | 8836292316 | 1 | 1 | 0.0% | -0.5100 | -0.5200 | -0.5300 |
| hgb_fair_state | 8831927547 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| hgb_fair_state | 8834932746 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| hgb_fair_state | 8836624153 | 1 | 1 | 100.0% | +0.5100 | +0.5000 | +0.4900 |
| hgb_fair_state | 8832812084 | 1 | 1 | 100.0% | +0.4800 | +0.4700 | +0.4600 |
| hgb_fair_state | 8836583316 | 1 | 1 | 0.0% | -0.4300 | -0.4400 | -0.4500 |
| hgb_fair_state | 8836442480 | 1 | 1 | 100.0% | +0.4500 | +0.4400 | +0.4300 |
| hgb_fair_state | 8833492242 | 1 | 1 | 0.0% | -0.4100 | -0.4200 | -0.4300 |
| hgb_fair_state | 8834583981 | 1 | 1 | 100.0% | +0.3600 | +0.3500 | +0.3400 |
| hgb_fair_state | 8836641131 | 1 | 1 | 0.0% | -0.3100 | -0.3200 | -0.3300 |
| hgb_fair_state | 8836445371 | 1 | 1 | 0.0% | -0.3000 | -0.3100 | -0.3200 |
| hgb_fair_state | 8835428935 | 1 | 1 | 100.0% | +0.2500 | +0.2400 | +0.2300 |
| hgb_fair_state | 8834867207 | 1 | 1 | 0.0% | -0.2200 | -0.2300 | -0.2400 |
| hgb_fair_state | 8832889451 | 1 | 1 | 0.0% | -0.1900 | -0.2000 | -0.2100 |
| hgb_fair_state | 8833570075 | 1 | 1 | 0.0% | -0.1600 | -0.1700 | -0.1800 |
| hgb_fair_state | 8835373075 | 1 | 1 | 100.0% | +0.1400 | +0.1300 | +0.1200 |
| hgb_fair_state | 8836485094 | 1 | 1 | 0.0% | -0.1100 | -0.1200 | -0.1300 |
| hgb_fair_state | 8833327581 | 1 | 1 | 0.0% | -0.1000 | -0.1100 | -0.1200 |
| hgb_fair_state | 8836393663 | 1 | 1 | 0.0% | -0.0800 | -0.0900 | -0.1000 |
| hgb_fair_state | 8833592202 | 1 | 1 | 0.0% | -0.0700 | -0.0800 | -0.0900 |
| hgb_fair_state | 8836692392 | 2 | 2 | 50.0% | +0.0400 | +0.0200 | -0.0000 |
| logistic_fair_state | 8831978733 | 1 | 1 | 0.0% | -0.9000 | -0.9100 | -0.9200 |
| logistic_fair_state | 8835703860 | 1 | 1 | 100.0% | +0.7700 | +0.7600 | +0.7500 |
| logistic_fair_state | 8835490699 | 1 | 1 | 0.0% | -0.6900 | -0.7000 | -0.7100 |
| logistic_fair_state | 8834230023 | 2 | 2 | 100.0% | +0.5800 | +0.5600 | +0.5400 |
| logistic_fair_state | 8836583316 | 1 | 1 | 0.0% | -0.5500 | -0.5600 | -0.5700 |
| logistic_fair_state | 8834932746 | 1 | 1 | 100.0% | +0.5600 | +0.5500 | +0.5400 |
| logistic_fair_state | 8834573464 | 1 | 1 | 100.0% | +0.5300 | +0.5200 | +0.5100 |
| logistic_fair_state | 8831927547 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| logistic_fair_state | 8836292316 | 1 | 1 | 0.0% | -0.4900 | -0.5000 | -0.5100 |

By league:

| model_name | league_id | trades | matches | win_rate | total_pnl | total_pnl_slip_1c | total_pnl_slip_2c |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 19699 | 21 | 19 | 85.7% | +3.2500 | +3.0400 | +2.8300 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | 19101 | 1 | 1 | 100.0% | +0.7300 | +0.7200 | +0.7100 |
| all_scoreboard_lag_nw3000_score6_edge10 | 19699 | 15 | 15 | 66.7% | +1.8600 | +1.7100 | +1.5600 |
| all_structure_nw8000_struct1_ask75 | 19699 | 9 | 9 | 66.7% | +0.7600 | +0.6700 | +0.5800 |
| hgb_fair_state | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| hgb_fair_state | 19699 | 28 | 26 | 39.3% | -1.2200 | -1.5000 | -1.7800 |
| logistic_fair_state | 19699 | 29 | 27 | 48.3% | +0.4000 | +0.1100 | -0.1800 |
| logistic_fair_state | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| logistic_residual_trade | 19699 | 38 | 36 | 81.6% | +2.2120 | +1.8320 | +1.4520 |
| logistic_residual_trade | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |
| rf_fair_state | 19699 | 32 | 29 | 46.9% | +1.7300 | +1.4100 | +1.0900 |
| rf_fair_state | 19101 | 1 | 1 | 0.0% | -0.5000 | -0.5100 | -0.5200 |

## Threshold Search

| fold | model_name | threshold_type | threshold | trades | avg_pnl | total_pnl | avg_pnl_slip_1c | total_pnl_slip_1c |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | hgb_fair_state | edge | 0.020 | 8 | -0.0988 | -0.7900 | -0.1088 | -0.8700 |
| 1 | hgb_fair_state | edge | 0.050 | 7 | -0.1386 | -0.9700 | -0.1486 | -1.0400 |
| 1 | hgb_fair_state | edge | 0.080 | 7 | -0.1614 | -1.1300 | -0.1714 | -1.2000 |
| 1 | hgb_fair_state | edge | 0.100 | 7 | -0.1657 | -1.1600 | -0.1757 | -1.2300 |
| 1 | hgb_fair_state | edge | 0.120 | 7 | -0.1629 | -1.1400 | -0.1729 | -1.2100 |
| 1 | hgb_fair_state | edge | 0.150 | 7 | -0.1900 | -1.3300 | -0.2000 | -1.4000 |
| 1 | hgb_fair_state | edge | 0.200 | 6 | -0.3117 | -1.8700 | -0.3217 | -1.9300 |
| 1 | logistic_fair_state | edge | 0.020 | 8 | +0.0075 | +0.0600 | -0.0025 | -0.0200 |
| 1 | logistic_fair_state | edge | 0.050 | 8 | +0.0487 | +0.3900 | +0.0387 | +0.3100 |
| 1 | logistic_fair_state | edge | 0.080 | 8 | +0.0612 | +0.4900 | +0.0512 | +0.4100 |
| 1 | logistic_fair_state | edge | 0.100 | 6 | +0.0133 | +0.0800 | +0.0033 | +0.0200 |
| 1 | logistic_fair_state | edge | 0.120 | 5 | -0.0080 | -0.0400 | -0.0180 | -0.0900 |
| 1 | logistic_fair_state | edge | 0.150 | 5 | +0.0460 | +0.2300 | +0.0360 | +0.1800 |
| 1 | logistic_fair_state | edge | 0.200 | 4 | -0.0100 | -0.0400 | -0.0200 | -0.0800 |
| 1 | logistic_residual_trade | trade_probability | 0.500 | 8 | +0.0775 | +0.6200 | +0.0675 | +0.5400 |
| 1 | logistic_residual_trade | trade_probability | 0.550 | 8 | +0.0775 | +0.6200 | +0.0675 | +0.5400 |
| 1 | logistic_residual_trade | trade_probability | 0.600 | 8 | +0.0775 | +0.6200 | +0.0675 | +0.5400 |
| 1 | logistic_residual_trade | trade_probability | 0.650 | 8 | +0.0775 | +0.6200 | +0.0675 | +0.5400 |
| 1 | logistic_residual_trade | trade_probability | 0.700 | 8 | +0.0775 | +0.6200 | +0.0675 | +0.5400 |
| 1 | rf_fair_state | edge | 0.020 | 8 | -0.0550 | -0.4400 | -0.0650 | -0.5200 |
| 1 | rf_fair_state | edge | 0.050 | 8 | -0.0513 | -0.4100 | -0.0613 | -0.4900 |
| 1 | rf_fair_state | edge | 0.080 | 8 | -0.2125 | -1.7000 | -0.2225 | -1.7800 |
| 1 | rf_fair_state | edge | 0.100 | 8 | -0.2675 | -2.1400 | -0.2775 | -2.2200 |
| 1 | rf_fair_state | edge | 0.120 | 8 | -0.2675 | -2.1400 | -0.2775 | -2.2200 |
| 1 | rf_fair_state | edge | 0.150 | 7 | -0.2671 | -1.8700 | -0.2771 | -1.9400 |
| 1 | rf_fair_state | edge | 0.200 | 7 | -0.2457 | -1.7200 | -0.2557 | -1.7900 |
| 2 | hgb_fair_state | edge | 0.020 | 7 | +0.0814 | +0.5700 | +0.0714 | +0.5000 |
| 2 | hgb_fair_state | edge | 0.050 | 7 | +0.1329 | +0.9300 | +0.1229 | +0.8600 |
| 2 | hgb_fair_state | edge | 0.080 | 6 | +0.1450 | +0.8700 | +0.1350 | +0.8100 |
| 2 | hgb_fair_state | edge | 0.100 | 6 | +0.1450 | +0.8700 | +0.1350 | +0.8100 |
| 2 | hgb_fair_state | edge | 0.120 | 6 | +0.1567 | +0.9400 | +0.1467 | +0.8800 |
| 2 | hgb_fair_state | edge | 0.150 | 6 | +0.1550 | +0.9300 | +0.1450 | +0.8700 |
| 2 | hgb_fair_state | edge | 0.200 | 4 | -0.0300 | -0.1200 | -0.0400 | -0.1600 |
| 2 | logistic_fair_state | edge | 0.020 | 8 | +0.0437 | +0.3500 | +0.0338 | +0.2700 |
| 2 | logistic_fair_state | edge | 0.050 | 7 | +0.1114 | +0.7800 | +0.1014 | +0.7100 |
| 2 | logistic_fair_state | edge | 0.080 | 6 | +0.0833 | +0.5000 | +0.0733 | +0.4400 |
| 2 | logistic_fair_state | edge | 0.100 | 4 | +0.0275 | +0.1100 | +0.0175 | +0.0700 |
| 2 | logistic_fair_state | edge | 0.120 | 4 | +0.0350 | +0.1400 | +0.0250 | +0.1000 |
| 2 | logistic_fair_state | edge | 0.150 | 4 | +0.0375 | +0.1500 | +0.0275 | +0.1100 |
| 2 | logistic_fair_state | edge | 0.200 | 3 | +0.1000 | +0.3000 | +0.0900 | +0.2700 |
| 2 | logistic_residual_trade | trade_probability | 0.500 | 8 | +0.0038 | +0.0300 | -0.0063 | -0.0500 |
| 2 | logistic_residual_trade | trade_probability | 0.550 | 8 | +0.0038 | +0.0300 | -0.0063 | -0.0500 |
| 2 | logistic_residual_trade | trade_probability | 0.600 | 8 | +0.0038 | +0.0300 | -0.0063 | -0.0500 |
| 2 | logistic_residual_trade | trade_probability | 0.650 | 8 | -0.0037 | -0.0300 | -0.0137 | -0.1100 |
| 2 | logistic_residual_trade | trade_probability | 0.700 | 7 | +0.1186 | +0.8300 | +0.1086 | +0.7600 |
| 2 | rf_fair_state | edge | 0.020 | 7 | +0.0200 | +0.1400 | +0.0100 | +0.0700 |
| 2 | rf_fair_state | edge | 0.050 | 7 | +0.0114 | +0.0800 | +0.0014 | +0.0100 |
| 2 | rf_fair_state | edge | 0.080 | 7 | -0.0814 | -0.5700 | -0.0914 | -0.6400 |
| 2 | rf_fair_state | edge | 0.100 | 7 | -0.0786 | -0.5500 | -0.0886 | -0.6200 |
| 2 | rf_fair_state | edge | 0.120 | 6 | -0.0567 | -0.3400 | -0.0667 | -0.4000 |
| 2 | rf_fair_state | edge | 0.150 | 3 | -0.1667 | -0.5000 | -0.1767 | -0.5300 |
| 2 | rf_fair_state | edge | 0.200 | 3 | -0.1433 | -0.4300 | -0.1533 | -0.4600 |
| 3 | hgb_fair_state | edge | 0.020 | 9 | +0.1467 | +1.3200 | +0.1367 | +1.2300 |
| 3 | hgb_fair_state | edge | 0.050 | 8 | +0.1775 | +1.4200 | +0.1675 | +1.3400 |
| 3 | hgb_fair_state | edge | 0.080 | 8 | +0.1775 | +1.4200 | +0.1675 | +1.3400 |
| 3 | hgb_fair_state | edge | 0.100 | 8 | +0.0875 | +0.7000 | +0.0775 | +0.6200 |
| 3 | hgb_fair_state | edge | 0.120 | 8 | +0.0875 | +0.7000 | +0.0775 | +0.6200 |
| 3 | hgb_fair_state | edge | 0.150 | 8 | +0.0963 | +0.7700 | +0.0862 | +0.6900 |
| 3 | hgb_fair_state | edge | 0.200 | 7 | +0.1371 | +0.9600 | +0.1271 | +0.8900 |
| 3 | logistic_fair_state | edge | 0.020 | 13 | +0.0923 | +1.2000 | +0.0823 | +1.0700 |
| 3 | logistic_fair_state | edge | 0.050 | 13 | +0.1208 | +1.5700 | +0.1108 | +1.4400 |
| 3 | logistic_fair_state | edge | 0.080 | 12 | +0.1083 | +1.3000 | +0.0983 | +1.1800 |
| 3 | logistic_fair_state | edge | 0.100 | 11 | +0.1127 | +1.2400 | +0.1027 | +1.1300 |
| 3 | logistic_fair_state | edge | 0.120 | 7 | +0.1957 | +1.3700 | +0.1857 | +1.3000 |
| 3 | logistic_fair_state | edge | 0.150 | 6 | +0.2083 | +1.2500 | +0.1983 | +1.1900 |
| 3 | logistic_fair_state | edge | 0.200 | 4 | +0.3025 | +1.2100 | +0.2925 | +1.1700 |
| 3 | logistic_residual_trade | trade_probability | 0.500 | 10 | +0.2480 | +2.4800 | +0.2380 | +2.3800 |
| 3 | logistic_residual_trade | trade_probability | 0.550 | 10 | +0.2480 | +2.4800 | +0.2380 | +2.3800 |
| 3 | logistic_residual_trade | trade_probability | 0.600 | 10 | +0.1360 | +1.3600 | +0.1260 | +1.2600 |
| 3 | logistic_residual_trade | trade_probability | 0.650 | 10 | +0.1360 | +1.3600 | +0.1260 | +1.2600 |
| 3 | logistic_residual_trade | trade_probability | 0.700 | 10 | +0.1360 | +1.3600 | +0.1260 | +1.2600 |
| 3 | rf_fair_state | edge | 0.020 | 9 | -0.0033 | -0.0300 | -0.0133 | -0.1200 |
| 3 | rf_fair_state | edge | 0.050 | 9 | +0.0144 | +0.1300 | +0.0044 | +0.0400 |
| 3 | rf_fair_state | edge | 0.080 | 8 | +0.0088 | +0.0700 | -0.0013 | -0.0100 |
| 3 | rf_fair_state | edge | 0.100 | 7 | +0.0171 | +0.1200 | +0.0071 | +0.0500 |
| 3 | rf_fair_state | edge | 0.120 | 7 | +0.0414 | +0.2900 | +0.0314 | +0.2200 |
| 3 | rf_fair_state | edge | 0.150 | 7 | +0.0071 | +0.0500 | -0.0029 | -0.0200 |
| 3 | rf_fair_state | edge | 0.200 | 6 | -0.0183 | -0.1100 | -0.0283 | -0.1700 |
| 4 | hgb_fair_state | edge | 0.020 | 13 | +0.0692 | +0.9000 | +0.0592 | +0.7700 |
| 4 | hgb_fair_state | edge | 0.050 | 13 | +0.0808 | +1.0500 | +0.0708 | +0.9200 |
| 4 | hgb_fair_state | edge | 0.080 | 13 | +0.1708 | +2.2200 | +0.1608 | +2.0900 |
| 4 | hgb_fair_state | edge | 0.100 | 12 | +0.1458 | +1.7500 | +0.1358 | +1.6300 |
| 4 | hgb_fair_state | edge | 0.120 | 12 | +0.1692 | +2.0300 | +0.1592 | +1.9100 |
| 4 | hgb_fair_state | edge | 0.150 | 10 | +0.2250 | +2.2500 | +0.2150 | +2.1500 |
| 4 | hgb_fair_state | edge | 0.200 | 7 | +0.3243 | +2.2700 | +0.3143 | +2.2000 |
| 4 | logistic_fair_state | edge | 0.020 | 13 | +0.1269 | +1.6500 | +0.1169 | +1.5200 |
| 4 | logistic_fair_state | edge | 0.050 | 12 | +0.1017 | +1.2200 | +0.0917 | +1.1000 |
| 4 | logistic_fair_state | edge | 0.080 | 12 | +0.1158 | +1.3900 | +0.1058 | +1.2700 |
| 4 | logistic_fair_state | edge | 0.100 | 12 | +0.1275 | +1.5300 | +0.1175 | +1.4100 |
| 4 | logistic_fair_state | edge | 0.120 | 12 | +0.1275 | +1.5300 | +0.1175 | +1.4100 |
| 4 | logistic_fair_state | edge | 0.150 | 10 | +0.0820 | +0.8200 | +0.0720 | +0.7200 |
| 4 | logistic_fair_state | edge | 0.200 | 5 | +0.1760 | +0.8800 | +0.1660 | +0.8300 |
| 4 | logistic_residual_trade | trade_probability | 0.500 | 13 | -0.1060 | -1.3780 | -0.1160 | -1.5080 |
| 4 | logistic_residual_trade | trade_probability | 0.550 | 13 | -0.1037 | -1.3480 | -0.1137 | -1.4780 |
| 4 | logistic_residual_trade | trade_probability | 0.600 | 12 | -0.0707 | -0.8480 | -0.0807 | -0.9680 |
| 4 | logistic_residual_trade | trade_probability | 0.650 | 12 | -0.0707 | -0.8480 | -0.0807 | -0.9680 |
| 4 | logistic_residual_trade | trade_probability | 0.700 | 12 | -0.0765 | -0.9180 | -0.0865 | -1.0380 |
| 4 | rf_fair_state | edge | 0.020 | 14 | +0.0643 | +0.9000 | +0.0543 | +0.7600 |
| 4 | rf_fair_state | edge | 0.050 | 14 | +0.1471 | +2.0600 | +0.1371 | +1.9200 |
| 4 | rf_fair_state | edge | 0.080 | 13 | +0.1169 | +1.5200 | +0.1069 | +1.3900 |

## Readout

- These are walk-forward research results, not deployment approval.
- Fair-probability models use state features only; ask/spread/liquidity are used only for edge conversion and the residual trade benchmark.
- Tradability now requires `game_time_sec >= 600` so pregame and countdown rows cannot generate trades.
- Thresholds are selected on past validation matches inside each fold, then applied once to future matches.
- If no model or hand rule stays positive after 1c and 2c slippage, do not trade it.

## Files Written

- `walk_forward_model_report.md`
- `walk_forward_model_predictions.csv`
- `walk_forward_model_trades.csv`
