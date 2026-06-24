# Multifactor Strategy Research

This pass uses net worth together with other features. No selected rule is just a net-worth lead rule; each requires at least one of momentum, scoreboard lag, structure, composite state/price edge, time, or book microstructure.

## Selected Family Summary

| family | selected | test_trades | test_win_rate | test_avg_pnl | best_test_pnl |
| --- | --- | --- | --- | --- | --- |
| structure_state | 22 | 28.500 | 85.3% | +0.1176 | +0.2173 |
| nw_momentum_discount | 7 | 32.000 | 78.4% | +0.0966 | +0.1884 |
| scoreboard_lag_plus_price | 19 | 21.000 | 70.0% | +0.0735 | +0.1223 |

## Canonical Multifactor Strategies

| strategy | family | description | train_trades | train_avg_pnl | test_trades | test_win_rate | test_avg_ask | test_avg_state_edge | test_avg_side_nw | test_avg_mom | test_avg_pnl | all_trades | all_avg_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_structure_nw8000_struct1_ask75 | structure_state | NW plus tower/rax structural confirmation plus ask cap. | 15 | +0.1167 | 11 | 81.8% | 0.601 | +0.3239 | 12094.182 | 3689.727 | +0.2173 | 26 | +0.1592 |
| all_nw_mom_discount_nw8000_mom5000_ask90 | nw_momentum_discount | NW lead plus recent NW momentum plus ask cap. | 20 | +0.0685 | 19 | 89.5% | 0.706 | +0.1999 | 13351.526 | 6807.789 | +0.1884 | 39 | +0.1269 |
| all_structure_nw5000_struct1_ask75 | structure_state | NW plus tower/rax structural confirmation plus ask cap. | 19 | +0.0932 | 15 | 80.0% | 0.623 | +0.2638 | 9719.733 | 2754.267 | +0.1773 | 34 | +0.1303 |
| all_structure_nw2000_struct1_ask75 | structure_state | NW plus tower/rax structural confirmation plus ask cap. | 29 | +0.1031 | 22 | 77.3% | 0.596 | +0.1668 | 4837.864 | 1667.818 | +0.1768 | 51 | +0.1349 |
| all_nw_mom_discount_nw8000_mom3000_ask90 | nw_momentum_discount | NW lead plus recent NW momentum plus ask cap. | 29 | +0.0421 | 27 | 85.2% | 0.708 | +0.1850 | 11299.593 | 5171.037 | +0.1441 | 56 | +0.0912 |
| all_scoreboard_lag_nw3000_score6_edge10 | scoreboard_lag_plus_price | NW lead, kill score lag, and composite state edge. | 25 | +0.0328 | 22 | 68.2% | 0.560 | +0.2115 | 7906.364 | 3673.682 | +0.1223 | 47 | +0.0747 |
| all_scoreboard_lag_nw3000_score6_edge2 | scoreboard_lag_plus_price | NW lead, kill score lag, and composite state edge. | 34 | +0.0659 | 30 | 73.3% | 0.614 | +0.1489 | 6656.967 | 3252.233 | +0.1190 | 64 | +0.0908 |
| all_scoreboard_lag_nw5000_score6_edge10 | scoreboard_lag_plus_price | NW lead, kill score lag, and composite state edge. | 22 | +0.0755 | 20 | 70.0% | 0.589 | +0.2464 | 9861.850 | 4087.750 | +0.1115 | 42 | +0.0926 |
| all_nw_mom_discount_nw3000_mom1000_ask80 | nw_momentum_discount | NW lead plus recent NW momentum plus ask cap. | 33 | +0.0530 | 34 | 73.5% | 0.629 | +0.0867 | 5194.941 | 2936.059 | +0.1068 | 67 | +0.0803 |

## Executable-Trained Multifactor Model Edge

| model | edge | auc | log_loss | brier | trades | win_rate | avg_ask | avg_model_fair | avg_model_edge | avg_pnl | total_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rf_multifactor | +0.1500 | 75.8% | 0.622 | 0.208 | 42 | 76.2% | 0.648 | 0.851 | +0.2028 | +0.1138 | +4.7800 |
| rf_multifactor | +0.2000 | 75.8% | 0.622 | 0.208 | 32 | 65.6% | 0.582 | 0.825 | +0.2431 | +0.0741 | +2.3700 |
| rf_multifactor | +0.0500 | 75.8% | 0.622 | 0.208 | 49 | 71.4% | 0.651 | 0.797 | +0.1460 | +0.0637 | +3.1200 |
| rf_multifactor | +0.1000 | 75.8% | 0.622 | 0.208 | 44 | 72.7% | 0.665 | 0.847 | +0.1818 | +0.0618 | +2.7200 |
| rf_multifactor | +0.0200 | 75.8% | 0.622 | 0.208 | 50 | 72.0% | 0.665 | 0.782 | +0.1170 | +0.0552 | +2.7600 |
| hgb_multifactor | +0.0200 | 73.5% | 0.693 | 0.229 | 49 | 71.4% | 0.701 | 0.828 | +0.1271 | +0.0137 | +0.6700 |
| hgb_multifactor | +0.0500 | 73.5% | 0.693 | 0.229 | 48 | 70.8% | 0.696 | 0.833 | +0.1366 | +0.0119 | +0.5700 |
| hgb_multifactor | +0.1500 | 73.5% | 0.693 | 0.229 | 43 | 62.8% | 0.624 | 0.822 | +0.1972 | +0.0035 | +0.1500 |
| hgb_multifactor | +0.1000 | 73.5% | 0.693 | 0.229 | 46 | 65.2% | 0.689 | 0.849 | +0.1600 | -0.0367 | -1.6900 |
| hgb_multifactor | +0.2000 | 73.5% | 0.693 | 0.229 | 33 | 54.5% | 0.586 | 0.819 | +0.2331 | -0.0403 | -1.3300 |
| logistic_multifactor | +0.0200 | 76.3% | 0.611 | 0.204 | 51 | 60.8% | 0.679 | 0.735 | +0.0558 | -0.0712 | -3.6300 |
| logistic_multifactor | +0.0500 | 76.3% | 0.611 | 0.204 | 48 | 62.5% | 0.702 | 0.781 | +0.0788 | -0.0773 | -3.7100 |
| logistic_multifactor | +0.2000 | 76.3% | 0.611 | 0.204 | 12 | 41.7% | 0.576 | 0.816 | +0.2401 | -0.1592 | -1.9100 |
| logistic_multifactor | +0.1500 | 76.3% | 0.611 | 0.204 | 23 | 43.5% | 0.599 | 0.773 | +0.1738 | -0.1639 | -3.7700 |
| logistic_multifactor | +0.1000 | 76.3% | 0.611 | 0.204 | 37 | 48.6% | 0.651 | 0.774 | +0.1224 | -0.1646 | -6.0900 |

## Readout

- The most useful shape is multifactor state/price disagreement: composite state edge plus capped ask.
- The scoreboard-lag variants are the cleanest thesis: net worth says one thing, kill score is less obvious, and price is still below the composite state fair.
- Momentum only works as a confirmation or reversal guardrail; by itself it overtrades.
- Structure is useful when combined with net worth and price, but standalone rax/tower rules remain too sparse.
- Treat these as paper strategies until the live logger accumulates more fresh executable rows.

## Files Written

- `multifactor_strategy_research.md`
- `multifactor_strategy_trades.csv`
