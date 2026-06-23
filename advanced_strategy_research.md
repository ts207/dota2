# Advanced Price-Aware Strategy Research

This pass searches conditional strategy shapes instead of testing only obvious leader rules. Every row below uses executable ask prices, fresh-book gates, ask-size gates, and first qualifying trade per match-market. Rule selection is based on earlier matches; validation is on later matches.

## Inputs

- Pattern side-expanded rows: 85,746.
- Executable side rows after basic non-null filter: 34,254.
- Base tradability gate: `book_age <= 60s`, `0.05 <= ask <= 0.95`, `ask_size >= 25`.
- Candidate rules generated: 784.
- Rules passing train selection and test sample gates: 44.

## Candidate Family Diagnostics

| family | candidates | train_avg_pnl | test_avg_pnl | test_positive_rate | best_test_pnl |
| --- | --- | --- | --- | --- | --- |
| cheap_leader | 28 | +0.0321 | +0.0750 | 100.0% | +0.2609 |
| compound_state | 34 | +0.0209 | +0.0658 | 100.0% | +0.2550 |
| comeback_momentum | 32 | +0.0172 | +0.0644 | 81.2% | +0.2378 |
| rax_discount | 16 | -0.0382 | +0.1125 | 100.0% | +0.1771 |
| scoreboard_lag | 27 | -0.0050 | +0.0578 | 96.3% | +0.1026 |

## Canonical Strategy Shapes

Many selected rows are threshold variants of the same idea. These are the canonical shapes worth carrying forward.

| strategy | family | description | train_trades | train_avg_pnl | test_trades | test_win_rate | test_avg_ask | test_avg_pnl | all_trades | all_avg_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_cheap_leader_nw20000_ask95 | cheap_leader | ALL: side has >= 20000 NW lead and ask <= 0.95. | 19 | +0.0400 | 11 | 100.0% | 0.739 | +0.2609 | 30 | +0.1210 |
| all_cheap_leader_nw3000_ask80 | cheap_leader | ALL: side has >= 3000 NW lead and ask <= 0.80. | 39 | +0.0636 | 37 | 75.7% | 0.634 | +0.1232 | 76 | +0.0926 |
| map_winner_comeback_mom2000_nwmax5000_ask45 | comeback_momentum | MAP_WINNER: side has positive 100s momentum while not yet heavily ahead. | 13 | +0.0662 | 16 | 43.8% | 0.296 | +0.1419 | 29 | +0.1079 |
| map_winner_comeback_mom2000_nwmax0_ask45 | comeback_momentum | MAP_WINNER: side has positive 100s momentum while not yet heavily ahead. | 13 | +0.0662 | 13 | 38.5% | 0.274 | +0.1108 | 26 | +0.0885 |
| all_compound_nw15000_mom2000_t1500 | compound_state | ALL: NW lead plus nonnegative/positive momentum after time gate. | 18 | +0.1500 | 12 | 100.0% | 0.745 | +0.2550 | 30 | +0.1920 |
| all_compound_nw15000_mom2000_t900 | compound_state | ALL: NW lead plus nonnegative/positive momentum after time gate. | 18 | +0.1500 | 12 | 100.0% | 0.748 | +0.2517 | 30 | +0.1907 |
| all_scoreboard_lag_nw5000_score3_ask80 | scoreboard_lag | ALL: gold leader is not leading kills enough, ask <= 0.80. | 25 | +0.0868 | 27 | 74.1% | 0.659 | +0.0815 | 52 | +0.0840 |
| all_scoreboard_lag_nw3000_score3_ask80 | scoreboard_lag | ALL: gold leader is not leading kills enough, ask <= 0.80. | 35 | +0.0697 | 35 | 71.4% | 0.651 | +0.0637 | 70 | +0.0667 |

## Best Validated Conditional Rules

| strategy | family | train_trades | train_win_rate | train_avg_ask | train_avg_pnl | test_trades | test_win_rate | test_avg_ask | test_avg_pnl | all_trades | all_avg_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_cheap_leader_nw20000_ask95 | cheap_leader | 19 | 94.7% | 0.907 | +0.0400 | 11 | 100.0% | 0.739 | +0.2609 | 30 | +0.1210 |
| all_compound_nw15000_mom2000_t1500 | compound_state | 18 | 94.4% | 0.794 | +0.1500 | 12 | 100.0% | 0.745 | +0.2550 | 30 | +0.1920 |
| all_compound_nw15000_mom2000_t900 | compound_state | 18 | 94.4% | 0.794 | +0.1500 | 12 | 100.0% | 0.748 | +0.2517 | 30 | +0.1907 |
| all_compound_nw15000_mom0_t1500 | compound_state | 19 | 94.7% | 0.798 | +0.1495 | 14 | 100.0% | 0.756 | +0.2436 | 33 | +0.1894 |
| all_compound_nw15000_mom0_t900 | compound_state | 19 | 94.7% | 0.798 | +0.1495 | 14 | 100.0% | 0.759 | +0.2407 | 33 | +0.1882 |
| all_compound_nw10000_mom5000_t900 | compound_state | 19 | 84.2% | 0.734 | +0.1079 | 15 | 86.7% | 0.690 | +0.1767 | 34 | +0.1382 |
| map_winner_comeback_mom2000_nwmax5000_ask45 | comeback_momentum | 13 | 30.8% | 0.242 | +0.0662 | 16 | 43.8% | 0.296 | +0.1419 | 29 | +0.1079 |
| all_compound_nw10000_mom5000_t1500 | compound_state | 19 | 84.2% | 0.734 | +0.1079 | 14 | 85.7% | 0.720 | +0.1371 | 33 | +0.1203 |
| all_compound_nw10000_mom5000_t2100 | compound_state | 12 | 91.7% | 0.693 | +0.2233 | 10 | 80.0% | 0.674 | +0.1260 | 22 | +0.1791 |
| all_cheap_leader_nw3000_ask80 | cheap_leader | 39 | 74.4% | 0.680 | +0.0636 | 37 | 75.7% | 0.634 | +0.1232 | 76 | +0.0926 |
| map_winner_comeback_mom2000_nwmax0_ask45 | comeback_momentum | 13 | 30.8% | 0.242 | +0.0662 | 13 | 38.5% | 0.274 | +0.1108 | 26 | +0.0885 |
| map_winner_comeback_mom2000_nwmax10000_ask45 | comeback_momentum | 13 | 30.8% | 0.242 | +0.0662 | 17 | 41.2% | 0.302 | +0.1094 | 30 | +0.0907 |
| map_winner_comeback_mom2000_nwmax0_ask75 | comeback_momentum | 15 | 40.0% | 0.351 | +0.0493 | 20 | 50.0% | 0.406 | +0.0945 | 35 | +0.0751 |
| all_cheap_leader_nw3000_ask55 | cheap_leader | 14 | 57.1% | 0.466 | +0.1050 | 15 | 53.3% | 0.441 | +0.0927 | 29 | +0.0986 |
| all_cheap_leader_nw3000_ask95 | cheap_leader | 54 | 83.3% | 0.769 | +0.0647 | 45 | 84.4% | 0.761 | +0.0838 | 99 | +0.0734 |
| all_cheap_leader_nw3000_ask90 | cheap_leader | 49 | 81.6% | 0.751 | +0.0655 | 42 | 81.0% | 0.727 | +0.0821 | 91 | +0.0732 |
| all_scoreboard_lag_nw5000_score3_ask80 | scoreboard_lag | 25 | 76.0% | 0.673 | +0.0868 | 27 | 74.1% | 0.659 | +0.0815 | 52 | +0.0840 |
| all_cheap_leader_nw8000_ask90 | cheap_leader | 37 | 86.5% | 0.795 | +0.0695 | 36 | 80.6% | 0.727 | +0.0781 | 73 | +0.0737 |
| all_compound_nw10000_mom0_t900 | compound_state | 32 | 84.4% | 0.787 | +0.0569 | 27 | 81.5% | 0.741 | +0.0737 | 59 | +0.0646 |
| all_compound_nw10000_mom2000_t900 | compound_state | 30 | 86.7% | 0.775 | +0.0917 | 23 | 78.3% | 0.711 | +0.0713 | 53 | +0.0828 |
| all_compound_nw10000_mom0_t1500 | compound_state | 30 | 83.3% | 0.770 | +0.0637 | 27 | 81.5% | 0.744 | +0.0711 | 57 | +0.0672 |
| all_cheap_leader_nw5000_ask70 | cheap_leader | 20 | 70.0% | 0.617 | +0.0830 | 22 | 63.6% | 0.566 | +0.0705 | 42 | +0.0764 |
| all_cheap_leader_nw5000_ask90 | cheap_leader | 46 | 84.8% | 0.777 | +0.0713 | 38 | 78.9% | 0.722 | +0.0679 | 84 | +0.0698 |
| all_cheap_leader_nw5000_ask95 | cheap_leader | 52 | 88.5% | 0.811 | +0.0737 | 43 | 83.7% | 0.770 | +0.0674 | 95 | +0.0709 |
| all_compound_nw5000_mom0_t900 | compound_state | 44 | 81.8% | 0.772 | +0.0466 | 36 | 77.8% | 0.711 | +0.0667 | 80 | +0.0556 |

## What Failed

These rules had enough sample but poor later-match validation, which is the main overfit warning.

| strategy | family | train_trades | train_avg_pnl | test_trades | test_win_rate | test_avg_ask | test_avg_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- |
| all_comeback_mom2000_nwmax-5000_ask60 | comeback_momentum | 17 | +0.0494 | 12 | 16.7% | 0.364 | -0.1975 |
| all_comeback_mom2000_nwmax-5000_ask90 | comeback_momentum | 17 | +0.0494 | 15 | 26.7% | 0.449 | -0.1827 |
| all_comeback_mom2000_nwmax-5000_ask45 | comeback_momentum | 16 | +0.0231 | 9 | 11.1% | 0.283 | -0.1722 |
| all_comeback_mom2000_nwmax-5000_ask75 | comeback_momentum | 17 | +0.0494 | 13 | 23.1% | 0.389 | -0.1585 |
| all_comeback_mom2000_nwmax5000_ask90 | comeback_momentum | 36 | +0.0550 | 37 | 54.1% | 0.603 | -0.0622 |
| map_winner_comeback_mom2000_nwmax5000_ask90 | comeback_momentum | 23 | -0.0122 | 33 | 54.5% | 0.594 | -0.0485 |
| all_scoreboard_lag_nw3000_score0_ask65 | scoreboard_lag | 14 | -0.1143 | 14 | 50.0% | 0.519 | -0.0193 |
| map_winner_compound_nw5000_mom2000_t900 | compound_state | 25 | -0.0088 | 29 | 72.4% | 0.719 | +0.0048 |
| map_winner_compound_nw5000_mom2000_t2100 | compound_state | 13 | -0.1146 | 11 | 72.7% | 0.717 | +0.0100 |
| map_winner_compound_nw5000_mom2000_t1500 | compound_state | 22 | -0.0809 | 25 | 72.0% | 0.710 | +0.0100 |
| all_compound_nw10000_mom2000_t2100 | compound_state | 17 | +0.0918 | 13 | 69.2% | 0.682 | +0.0100 |
| all_comeback_mom2000_nwmax10000_ask90 | comeback_momentum | 41 | +0.0829 | 40 | 65.0% | 0.638 | +0.0117 |

## Executable Side Model Check

These models are trained only on earlier executable rows that pass the tradability gate and evaluated on later executable rows. This is a sanity check for whether a model can learn residual side value from executable data itself.

| model | train_rows | test_rows | train_matches | test_matches | auc | log_loss | brier |
| --- | --- | --- | --- | --- | --- | --- | --- |
| exec_logistic | 8382 | 5769 | 67 | 48 | 76.7% | 0.600 | 0.202 |
| exec_hgb | 8382 | 5769 | 67 | 48 | 74.8% | 0.652 | 0.219 |

### Later-Match Model Edge Trades

| model | edge_bucket | trades | matches | win_rate | avg_ask | avg_model_fair | avg_model_edge | avg_pnl | total_pnl |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| exec_hgb | (0.15, 0.2] | 42 | 37 | 66.7% | 0.640 | 0.810 | +0.1700 | +0.0262 | +1.1000 |
| exec_logistic | (0.02, 0.05] | 50 | 45 | 66.0% | 0.679 | 0.715 | +0.0353 | -0.0194 | -0.9700 |
| exec_hgb | (0.1, 0.15] | 45 | 40 | 64.4% | 0.685 | 0.807 | +0.1221 | -0.0407 | -1.8300 |
| exec_hgb | (0.05, 0.1] | 47 | 43 | 66.0% | 0.701 | 0.779 | +0.0772 | -0.0419 | -1.9700 |
| exec_logistic | (0.05, 0.1] | 47 | 42 | 66.0% | 0.706 | 0.775 | +0.0684 | -0.0466 | -2.1900 |
| exec_logistic | (0.2, 1.0] | 9 | 9 | 55.6% | 0.604 | 0.851 | +0.2466 | -0.0489 | -0.4400 |
| exec_hgb | (0.2, 1.0] | 31 | 30 | 51.6% | 0.576 | 0.806 | +0.2294 | -0.0603 | -1.8700 |
| exec_hgb | (0.02, 0.05] | 48 | 43 | 58.3% | 0.661 | 0.697 | +0.0351 | -0.0781 | -3.7500 |
| exec_logistic | (0.1, 0.15] | 27 | 25 | 48.1% | 0.649 | 0.760 | +0.1108 | -0.1678 | -4.5300 |
| exec_logistic | (0.15, 0.2] | 11 | 11 | 36.4% | 0.640 | 0.805 | +0.1648 | -0.2764 | -3.0400 |

## Strategy Readout

- The better non-basic direction is not a generic `buy the leader`; it is `state-discount`: buy a side whose state is materially ahead while the ask has not fully caught up.
- Best higher-sample candidate: `all_cheap_leader_nw3000_ask80`. It buys a side with at least 3k net-worth lead only while ask is <= 0.80; later split was 37 trades, 75.7% win, +0.1232 pnl/share.
- Best non-basic candidate: `all_scoreboard_lag_nw5000_score3_ask80`. It buys a side with at least 5k net-worth lead while the scoreboard is not strongly confirming it, capped at 0.80 ask; later split was 27 trades, 74.1% win, +0.0815 pnl/share.
- Strong but lower-sample steamroll candidate: `all_compound_nw15000_mom0_t1500`. It requires a huge lead after 25 minutes, nonnegative 100s momentum, and ask <= 0.90; later split was 14 trades, 100% win, +0.2436 pnl/share.
- `comeback_momentum` is tempting but unstable; it often finds cheap prices because the side is still losing, and later-match validation is noisy.
- Rax-discount rules are sample-starved and mostly late-game. Treat them as confirmation features, not standalone entries.
- Executable-trained models are useful for diagnostics but not yet production. With only 135 matches, the rule family validation is more interpretable and less fragile.

## Files Written

- `advanced_strategy_research.md`
- `advanced_strategy_trades.csv`
