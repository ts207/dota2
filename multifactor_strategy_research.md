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
| rf_multifactor | +0.0500 | 75.8% | 0.618 | 0.208 | 49 | 75.5% | 0.643 | 0.765 | +0.1219 | +0.1122 | +5.5000 |
| rf_multifactor | +0.1500 | 75.8% | 0.618 | 0.208 | 43 | 72.1% | 0.620 | 0.816 | +0.1961 | +0.1014 | +4.3600 |
| rf_multifactor | +0.1000 | 75.8% | 0.618 | 0.208 | 46 | 71.7% | 0.622 | 0.786 | +0.1635 | +0.0952 | +4.3800 |
| rf_multifactor | +0.0200 | 75.8% | 0.618 | 0.208 | 50 | 74.0% | 0.646 | 0.747 | +0.1012 | +0.0944 | +4.7200 |
| hgb_multifactor | +0.1500 | 73.5% | 0.688 | 0.228 | 42 | 69.0% | 0.641 | 0.830 | +0.1888 | +0.0495 | +2.0800 |
| hgb_multifactor | +0.0500 | 73.5% | 0.688 | 0.228 | 48 | 72.9% | 0.681 | 0.804 | +0.1228 | +0.0481 | +2.3100 |
| rf_multifactor | +0.2000 | 75.8% | 0.618 | 0.208 | 30 | 60.0% | 0.556 | 0.788 | +0.2323 | +0.0443 | +1.3300 |
| hgb_multifactor | +0.0200 | 73.5% | 0.688 | 0.228 | 50 | 72.0% | 0.685 | 0.788 | +0.1033 | +0.0354 | +1.7700 |
| logistic_multifactor | +0.0500 | 76.6% | 0.611 | 0.203 | 49 | 71.4% | 0.684 | 0.799 | +0.1155 | +0.0306 | +1.5000 |
| logistic_multifactor | +0.1500 | 76.6% | 0.611 | 0.203 | 33 | 66.7% | 0.661 | 0.839 | +0.1785 | +0.0061 | +0.2000 |
| logistic_multifactor | +0.1000 | 76.6% | 0.611 | 0.203 | 46 | 65.2% | 0.672 | 0.812 | +0.1399 | -0.0198 | -0.9100 |
| hgb_multifactor | +0.2000 | 73.5% | 0.688 | 0.228 | 33 | 54.5% | 0.567 | 0.800 | +0.2331 | -0.0215 | -0.7100 |
| logistic_multifactor | +0.0200 | 76.6% | 0.611 | 0.203 | 51 | 64.7% | 0.677 | 0.779 | +0.1017 | -0.0300 | -1.5300 |
| hgb_multifactor | +0.1000 | 73.5% | 0.688 | 0.228 | 45 | 64.4% | 0.686 | 0.836 | +0.1502 | -0.0413 | -1.8600 |
| logistic_multifactor | +0.2000 | 76.6% | 0.611 | 0.203 | 12 | 41.7% | 0.592 | 0.835 | +0.2431 | -0.1750 | -2.1000 |

## Readout

- The most useful shape is multifactor state/price disagreement: composite state edge plus capped ask.
- The scoreboard-lag variants are the cleanest thesis: net worth says one thing, kill score is less obvious, and price is still below the composite state fair.
- Momentum only works as a confirmation or reversal guardrail; by itself it overtrades.
- Structure is useful when combined with net worth and price, but standalone rax/tower rules remain too sparse.
- Treat these as paper strategies until the live logger accumulates more fresh executable rows.

## Files Written

- `multifactor_strategy_research.md`
- `multifactor_strategy_trades.csv`
