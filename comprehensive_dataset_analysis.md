# Comprehensive Dota Dataset Analysis

This report analyzes both datasets with separate purposes:

- `pattern_discovery_dataset`: state/outcome mining, no prices.
- `clean_executable_backtest_dataset`: executable validation using `book_best_ask`, settlement labels, book age, and first-trade dedupe.

## Dataset Audit

- Pattern raw: 42,887 rows / 292 matches.
- Pattern clean: 42,873 rows / 289 matches.
- Executable: 34,317 side-token rows / 135 matches / 150 match-market groups.
- Match overlap: 134 overlap, 155 pattern-only, 1 executable-only.
- Radiant match win rate: pattern 59.2%, executable 54.1%.

### Pattern Feature Missingness

| column | nonnull | null_rate |
| --- | --- | --- |
| building_state | 17081 | 60.2% |
| radiant_rax_lanes_down | 17081 | 60.2% |
| rax_lane_advantage | 17081 | 60.2% |
| dire_rax_lanes_down | 17081 | 60.2% |
| spectators | 17179 | 59.9% |
| source_update_age_sec | 26718 | 37.7% |
| tower_advantage | 28436 | 33.7% |
| tower_state | 28436 | 33.7% |
| towers_alive_radiant | 28436 | 33.7% |
| towers_alive_dire | 28436 | 33.7% |
| nw_change_300s | 34424 | 19.7% |
| nw_change_100s | 37042 | 13.6% |
| nw_lead_clean | 40653 | 5.2% |
| abs_nw_lead | 40653 | 5.2% |
| kills_change_100s | 40778 | 4.9% |
| game_time_sec | 42758 | 0.3% |
| abs_score_diff | 42873 | 0.0% |
| total_kills | 42873 | 0.0% |
| score_diff | 42873 | 0.0% |

### Executable Feature Missingness

| column | nonnull | null_rate |
| --- | --- | --- |
| dire_rax_lanes_down | 14169 | 58.7% |
| rax_lane_advantage | 14169 | 58.7% |
| radiant_rax_lanes_down | 14169 | 58.7% |
| spectators | 14330 | 58.2% |
| source_update_age_sec | 18380 | 46.4% |
| towers_alive_dire | 18471 | 46.2% |
| tower_advantage | 18471 | 46.2% |
| towers_alive_radiant | 18471 | 46.2% |
| nw_change_300s | 29919 | 12.8% |
| nw_change_100s | 32528 | 5.2% |
| kills_change_100s | 32603 | 5.0% |
| nw_lead_clean | 34247 | 0.2% |
| abs_nw_lead | 34247 | 0.2% |
| game_time_sec | 34254 | 0.2% |
| score_diff | 34317 | 0.0% |
| abs_score_diff | 34317 | 0.0% |
| total_kills | 34317 | 0.0% |
| book_best_ask | 34317 | 0.0% |
| book_age_ms | 34317 | 0.0% |
| book_ask_size | 34317 | 0.0% |

### Executable Market Buckets

| label_market_bucket | rows | share |
| --- | --- | --- |
| MAP_WINNER | 26517 | 0.773 |
| MATCH_WINNER_BO1 | 4026 | 0.117 |
| MATCH_WINNER_GAME3_PROXY | 3774 | 0.110 |

### Book Age And Price

| bucket | rows | share |
| --- | --- | --- |
| <=1s | 6577 | 0.192 |
| 1-5s | 9409 | 0.274 |
| 5-15s | 3718 | 0.108 |
| 15-60s | 3577 | 0.104 |
| 1-5m | 4485 | 0.131 |
| 5-15m | 4005 | 0.117 |
| 15-60m | 2140 | 0.062 |
| >60m | 406 | 0.012 |

| bucket | rows | win_rate | avg_pnl_if_buy_all |
| --- | --- | --- | --- |
| 0-5c | 4990 | 10.0% | +0.0877 |
| 5-10c | 1582 | 10.3% | +0.0200 |
| 10-25c | 3859 | 8.4% | -0.1024 |
| 25-50c | 6921 | 32.0% | -0.0654 |
| 50-75c | 5990 | 62.7% | -0.0051 |
| 75-90c | 4373 | 82.7% | -0.0069 |
| 90-95c | 2002 | 81.8% | -0.1159 |
| 95-100c | 4600 | 80.7% | -0.1740 |

## Pattern Discovery Findings

These are state/outcome relationships before prices. Rows are snapshots; matches dedupe repeated observations.

### Net-Worth Lead

| bucket | rows | matches | win_rate |
| --- | --- | --- | --- |
| 0-2k | 11028 | 277 | 58.4% |
| 2-5k | 6999 | 278 | 74.9% |
| 5-10k | 6590 | 277 | 82.9% |
| 10-20k | 6921 | 273 | 89.3% |
| 20k+ | 7810 | 234 | 98.8% |

### 100s Net-Worth Momentum

| bucket | rows | matches | win_rate |
| --- | --- | --- | --- |
| <-5k | 3350 | 127 | 91.7% |
| -5k to -2k | 3231 | 186 | 71.6% |
| -2k to -500 | 5300 | 244 | 58.0% |
| flat | 6995 | 267 | 53.0% |
| +500 to +2k | 6579 | 257 | 75.7% |
| +2k to +5k | 4922 | 221 | 85.9% |
| >+5k | 4676 | 179 | 95.9% |

### Rax-Lane Advantage

| bucket | rows | matches | win_rate |
| --- | --- | --- | --- |
| -3 to -2 | 757 | 82 | 91.5% |
| -2 to -1 | 625 | 91 | 73.0% |
| 0 to +1 | 710 | 132 | 87.7% |
| +1 to +2 | 734 | 116 | 82.8% |
| +2 to +3 | 322 | 76 | 100.0% |

### Hand Rule Validation

Rule validation below is executable, fresh <=60s, all market buckets, first match-market trade only.

| strategy | trades | matches | win_rate | avg_ask | avg_pnl | total_pnl | pattern_first_signal_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| nw_lead_20k | 71 | 66 | 98.6% | 0.885 | +0.1004 | +7.1310 | 98.3% |
| nw_lead_5k | 118 | 108 | 89.0% | 0.810 | +0.0802 | +9.4650 | 88.4% |
| nw_momentum_100s_5k_same_leader | 92 | 85 | 85.9% | 0.805 | +0.0538 | +4.9500 | 90.3% |
| nw_momentum_100s_5k | 93 | 86 | 82.8% | 0.782 | +0.0455 | +4.2300 | 86.5% |
| rax_lane_adv_2 | 67 | 62 | 91.0% | 0.867 | +0.0439 | +2.9430 | 94.9% |
| nw_lead_10k | 108 | 99 | 89.8% | 0.859 | +0.0389 | +4.2050 | 90.7% |
| tower_adv_3 | 86 | 81 | 80.2% | 0.774 | +0.0280 | +2.4100 | 76.8% |
| rax_lane_adv_1 | 85 | 80 | 88.2% | 0.860 | +0.0228 | +1.9420 | 91.8% |
| rax_lane_adv_1_and_nw_leader | 85 | 80 | 88.2% | 0.863 | +0.0193 | +1.6420 | 92.2% |
| nw_vs_kill_disagree | 80 | 76 | 52.5% | 0.632 | -0.1070 | -8.5590 | 54.8% |

### Hand Rule Validation, Fresh 60s And Ask 5c-95c

This removes the most suspicious near-certain and near-zero prices. It is the cleaner table for judging whether a state rule has tradable value rather than just high settlement accuracy.

| strategy | trades | matches | win_rate | avg_ask | avg_pnl | total_pnl | pattern_first_signal_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| nw_lead_20k | 34 | 33 | 97.1% | 0.830 | +0.1406 | +4.7800 | 98.3% |
| nw_lead_5k | 98 | 92 | 87.8% | 0.774 | +0.1039 | +10.1820 | 88.4% |
| rax_lane_adv_2 | 36 | 34 | 86.1% | 0.787 | +0.0742 | +2.6700 | 94.9% |
| nw_momentum_100s_5k_same_leader | 64 | 59 | 79.7% | 0.725 | +0.0720 | +4.6110 | 90.3% |
| nw_momentum_100s_5k | 67 | 62 | 73.1% | 0.681 | +0.0502 | +3.3610 | 86.5% |
| tower_adv_3 | 64 | 62 | 75.0% | 0.702 | +0.0481 | +3.0800 | 76.8% |
| rax_lane_adv_1 | 53 | 50 | 83.0% | 0.782 | +0.0479 | +2.5400 | 91.8% |
| nw_lead_10k | 85 | 80 | 87.1% | 0.823 | +0.0479 | +4.0710 | 90.7% |
| rax_lane_adv_1_and_nw_leader | 53 | 50 | 83.0% | 0.788 | +0.0423 | +2.2400 | 92.2% |
| nw_vs_kill_disagree | 76 | 72 | 50.0% | 0.615 | -0.1149 | -8.7290 | 54.8% |

## Pattern-Trained State Models

Models were trained on the first 70% of pattern matches by first-seen time and evaluated on the later 30% of matches. This avoids row-random leakage across the same match.

| model | train_matches | test_matches | auc | log_loss | brier | accuracy |
| --- | --- | --- | --- | --- | --- | --- |
| random_forest | 202 | 87 | 88.7% | 0.405 | 0.136 | 78.8% |
| hist_gradient_boosting | 202 | 87 | 89.1% | 0.405 | 0.136 | 78.7% |
| logistic_l2 | 202 | 87 | 88.3% | 0.414 | 0.138 | 78.9% |

### Logistic Feature Direction

Coefficients are standardized, so magnitude is comparable. Positive pushes Radiant win probability up; negative pushes it down.

| feature | coef | abs_coef |
| --- | --- | --- |
| nw_lead_clean | 1.495 | 1.495 |
| score_diff | 0.728 | 0.728 |
| total_kills | -0.594 | 0.594 |
| game_time_sec | 0.577 | 0.577 |
| nw_change_300s | 0.491 | 0.491 |
| abs_score_diff | -0.339 | 0.339 |
| nw_change_100s | 0.309 | 0.309 |
| kills_change_100s | 0.232 | 0.232 |
| towers_alive_radiant | 0.208 | 0.208 |
| spectators | -0.102 | 0.102 |
| dire_rax_lanes_down | 0.083 | 0.083 |
| abs_nw_lead | -0.065 | 0.065 |

### Holdout Calibration

| bucket | rows | matches | avg_pred | actual | abs_error |
| --- | --- | --- | --- | --- | --- |
| (-0.001, 0.1] | 2311 | 36 | 0.035 | 0.051 | 0.016 |
| (0.1, 0.2] | 980 | 45 | 0.146 | 0.202 | 0.056 |
| (0.2, 0.3] | 665 | 44 | 0.249 | 0.322 | 0.073 |
| (0.3, 0.4] | 679 | 53 | 0.353 | 0.465 | 0.112 |
| (0.4, 0.5] | 690 | 59 | 0.451 | 0.509 | 0.057 |
| (0.5, 0.6] | 1041 | 77 | 0.557 | 0.545 | 0.012 |
| (0.6, 0.7] | 1572 | 78 | 0.651 | 0.583 | 0.068 |
| (0.7, 0.8] | 1184 | 77 | 0.745 | 0.611 | 0.134 |
| (0.8, 0.9] | 1385 | 51 | 0.854 | 0.846 | 0.008 |
| (0.9, 1.0] | 3932 | 55 | 0.971 | 0.983 | 0.012 |

## Model Edge Validation On Executable Data

The selected model was refit on all pattern rows, scored on executable rows, then traded only where `model_fair - book_best_ask` exceeded the edge threshold. Validation uses first qualifying trade per match-market.

| strategy | filter | label_market_bucket | trades | matches | win_rate | avg_ask | avg_model_fair | avg_edge | avg_pnl | total_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model_edge_0.02 | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 14 | 14 | 50.0% | 0.356 | 0.607 | +0.2511 | +0.1443 | +2.0200 |
| model_edge_0.05 | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 14 | 14 | 50.0% | 0.369 | 0.639 | +0.2699 | +0.1307 | +1.8300 |
| model_edge_0.10 | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 13 | 13 | 46.2% | 0.352 | 0.642 | +0.2905 | +0.1100 | +1.4300 |
| model_edge_0.15 | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 41.7% | 0.310 | 0.621 | +0.3113 | +0.1067 | +1.2800 |
| model_edge_0.20 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 13 | 13 | 53.8% | 0.465 | 0.685 | +0.2195 | +0.0731 | +0.9500 |
| model_edge_0.20 | fresh_60s_ask_5_95 | ALL | 97 | 92 | 45.4% | 0.394 | 0.665 | +0.2711 | +0.0595 | +5.7720 |
| model_edge_0.15 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 14 | 14 | 50.0% | 0.441 | 0.624 | +0.1836 | +0.0593 | +0.8300 |
| model_edge_0.05 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 14 | 14 | 57.1% | 0.517 | 0.634 | +0.1172 | +0.0543 | +0.7600 |
| model_edge_0.20 | fresh_60s_ask_5_95 | MAP_WINNER | 75 | 75 | 45.3% | 0.402 | 0.670 | +0.2689 | +0.0518 | +3.8820 |
| model_edge_0.10 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 14 | 14 | 50.0% | 0.459 | 0.617 | +0.1576 | +0.0407 | +0.5700 |
| model_edge_0.15 | fresh_60s_ask_5_95 | ALL | 110 | 104 | 42.7% | 0.403 | 0.626 | +0.2229 | +0.0247 | +2.7120 |
| model_edge_0.15 | fresh_60s_ask_5_95 | MAP_WINNER | 84 | 84 | 41.7% | 0.409 | 0.626 | +0.2168 | +0.0072 | +0.6020 |
| model_edge_0.10 | fresh_60s_ask_5_95 | ALL | 116 | 108 | 39.7% | 0.409 | 0.603 | +0.1941 | -0.0121 | -1.4080 |
| model_edge_0.02 | fresh_60s_ask_5_95 | ALL | 121 | 113 | 38.0% | 0.417 | 0.564 | +0.1470 | -0.0370 | -4.4780 |
| model_edge_0.10 | fresh_60s_ask_5_95 | MAP_WINNER | 89 | 89 | 37.1% | 0.409 | 0.595 | +0.1857 | -0.0383 | -3.4080 |
| model_edge_0.05 | fresh_60s_ask_5_95 | ALL | 119 | 111 | 37.8% | 0.416 | 0.580 | +0.1640 | -0.0383 | -4.5580 |
| model_edge_0.02 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 15 | 15 | 40.0% | 0.451 | 0.552 | +0.1017 | -0.0507 | -0.7600 |
| model_edge_0.02 | fresh_60s_ask_5_95 | MAP_WINNER | 92 | 92 | 35.9% | 0.421 | 0.560 | +0.1386 | -0.0624 | -5.7380 |
| model_edge_0.05 | fresh_60s_ask_5_95 | MAP_WINNER | 91 | 91 | 33.0% | 0.408 | 0.563 | +0.1549 | -0.0785 | -7.1480 |

### Fresh 60s Model Edge, All Prices

| strategy | trades | matches | win_rate | avg_ask | avg_model_fair | avg_edge | avg_pnl | total_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| model_edge_0.20 | 111 | 101 | 43.2% | 0.345 | 0.639 | +0.2944 | +0.0874 | +9.6970 |
| model_edge_0.15 | 123 | 112 | 40.7% | 0.361 | 0.603 | +0.2425 | +0.0459 | +5.6470 |
| model_edge_0.10 | 130 | 117 | 37.7% | 0.365 | 0.579 | +0.2138 | +0.0119 | +1.5480 |
| model_edge_0.02 | 137 | 124 | 36.5% | 0.376 | 0.544 | +0.1680 | -0.0110 | -1.5090 |
| model_edge_0.05 | 135 | 122 | 35.6% | 0.368 | 0.552 | +0.1843 | -0.0122 | -1.6510 |

### Chronological Stability

| strategy | split | trades | win_rate | avg_ask | avg_pnl | total_pnl |
| --- | --- | --- | --- | --- | --- | --- |
| model_edge_0.02 | first_half | 46 | 34.8% | 0.425 | -0.0769 | -3.5380 |
| model_edge_0.02 | second_half | 46 | 37.0% | 0.417 | -0.0478 | -2.2000 |
| model_edge_0.05 | first_half | 45 | 28.9% | 0.396 | -0.1075 | -4.8380 |
| model_edge_0.05 | second_half | 46 | 37.0% | 0.420 | -0.0502 | -2.3100 |
| model_edge_0.10 | first_half | 44 | 38.6% | 0.409 | -0.0222 | -0.9780 |
| model_edge_0.10 | second_half | 45 | 35.6% | 0.410 | -0.0540 | -2.4300 |
| model_edge_0.15 | first_half | 42 | 40.5% | 0.409 | -0.0040 | -0.1680 |
| model_edge_0.15 | second_half | 42 | 42.9% | 0.410 | +0.0183 | +0.7700 |
| model_edge_0.20 | first_half | 37 | 45.9% | 0.413 | +0.0463 | +1.7120 |
| model_edge_0.20 | second_half | 38 | 44.7% | 0.390 | +0.0571 | +2.1700 |

## Verdict

- The datasets support strong state prediction, but executable value is much thinner than raw win-rate signals imply.
- The strongest simple executable rule remains net-worth lead, especially `nw_lead_5k`, because it survives fresh-book and ask-range filters.
- Kill-score disagreement is rejected: it is weak after match-level dedupe and negative after executable ask costs.
- Rax and momentum are useful state features, but their executable edge is less stable chronologically and should be treated as paper/research candidates.
- Model-edge trading is not ready for live deployment. It finds some low-ask opportunities, but broad MAP_WINNER performance is unstable until the fair model is calibrated directly against executable rows.
- Practical next candidate: paper trade `nw_lead_5k` with fresh books, sane ask range, and first-entry-per-match controls; use model scores only as an overlay until more executable data accumulates.

## Files Written

- `comprehensive_dataset_analysis.md`
- `comprehensive_model_trades.csv`
- `comprehensive_model_calibration.csv`
