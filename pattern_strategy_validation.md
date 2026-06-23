# Pattern Strategy Validation

Method: mine rule-level state signals on the pattern-discovery dataset, then validate the same rules on the executable dataset by buying the predicted side at `book_best_ask`. Validation is first qualifying trade per `match_id` and `label_market_bucket` to avoid row-repeat inflation.

## Discovery Scores

| Strategy | Snapshot rows | Snapshot win | Match signals | First-signal win |
| --- | ---: | ---: | ---: | ---: |
| nw_lead_20k | 7,810 | 98.8% | 234 | 98.3% |
| rax_lane_adv_2 | 1,813 | 89.5% | 216 | 94.9% |
| rax_lane_adv_1_and_nw_leader | 2,972 | 88.1% | 256 | 92.2% |
| rax_lane_adv_1 | 3,148 | 85.8% | 256 | 91.8% |
| nw_lead_10k | 14,731 | 94.3% | 280 | 90.7% |
| nw_momentum_100s_5k_same_leader | 7,647 | 96.8% | 248 | 90.3% |
| nw_lead_5k | 21,327 | 90.8% | 284 | 88.4% |
| nw_momentum_100s_5k | 8,026 | 94.2% | 252 | 86.5% |
| tower_adv_3 | 14,171 | 69.2% | 263 | 76.8% |
| nw_vs_kill_disagree | 6,007 | 65.7% | 197 | 54.8% |

## Executable Validation

| Strategy | Filter | Bucket | Trades | Matches | Win | Avg ask | Avg pnl/share | Total pnl | Avg ROI | Median book age |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| nw_lead_10k | all_books | MATCH_WINNER_BO1 | 15 | 15 | 100.0% | 0.836 | +0.1640 | +2.4600 | 138.4% | 3.0s |
| nw_lead_5k | all_books | MATCH_WINNER_BO1 | 15 | 15 | 93.3% | 0.780 | +0.1533 | +2.3000 | 18.0% | 2.4s |
| rax_lane_adv_1 | all_books | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.848 | +0.1515 | +1.9700 | 41.8% | 4.0s |
| rax_lane_adv_1_and_nw_leader | all_books | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.848 | +0.1515 | +1.9700 | 41.8% | 4.0s |
| nw_lead_20k | all_books | MATCH_WINNER_GAME3_PROXY | 13 | 13 | 100.0% | 0.864 | +0.1362 | +1.7710 | 25.4% | 44.3s |
| nw_lead_20k | all_books | MATCH_WINNER_BO1 | 12 | 12 | 100.0% | 0.874 | +0.1258 | +1.5100 | 829.6% | 4.4s |
| nw_lead_5k | all_books | MATCH_WINNER_GAME3_PROXY | 17 | 17 | 94.1% | 0.820 | +0.1208 | +2.0530 | 33.5% | 12.5s |
| nw_momentum_100s_5k | all_books | MATCH_WINNER_GAME3_PROXY | 16 | 16 | 87.5% | 0.764 | +0.1107 | +1.7710 | 33.6% | 18.8s |
| nw_momentum_100s_5k_same_leader | all_books | MATCH_WINNER_GAME3_PROXY | 16 | 16 | 87.5% | 0.764 | +0.1107 | +1.7710 | 33.6% | 18.8s |
| nw_lead_5k | all_books | ALL | 131 | 119 | 89.3% | 0.789 | +0.1045 | +13.6930 | 2303.8% | 4.1s |
| nw_momentum_100s_5k_same_leader | all_books | MATCH_WINNER_BO1 | 13 | 13 | 92.3% | 0.821 | +0.1023 | +1.3300 | 34.4% | 0.5s |
| nw_lead_20k | all_books | ALL | 96 | 88 | 97.9% | 0.877 | +0.1019 | +9.7870 | 3236.1% | 8.7s |
| rax_lane_adv_2 | all_books | MATCH_WINNER_BO1 | 10 | 10 | 100.0% | 0.902 | +0.0980 | +0.9800 | 20.7% | 0.8s |
| tower_adv_3 | all_books | MATCH_WINNER_GAME3_PROXY | 14 | 14 | 100.0% | 0.903 | +0.0972 | +1.3610 | 13.5% | 10.4s |
| nw_lead_5k | all_books | MAP_WINNER | 99 | 99 | 87.9% | 0.784 | +0.0943 | +9.3400 | 3039.9% | 4.1s |
| nw_lead_20k | all_books | MAP_WINNER | 71 | 71 | 97.2% | 0.880 | +0.0916 | +6.5060 | 4230.7% | 10.3s |
| nw_momentum_100s_5k | all_books | MATCH_WINNER_BO1 | 13 | 13 | 84.6% | 0.756 | +0.0900 | +1.1700 | 26.1% | 1.2s |
| tower_adv_3 | all_books | MAP_WINNER | 79 | 79 | 87.3% | 0.792 | +0.0812 | +6.4150 | 3799.8% | 12.1s |
| rax_lane_adv_2 | all_books | MAP_WINNER | 66 | 66 | 92.4% | 0.844 | +0.0800 | +5.2830 | 4546.9% | 18.6s |
| rax_lane_adv_2 | all_books | ALL | 90 | 81 | 92.2% | 0.844 | +0.0781 | +7.0330 | 3338.1% | 9.9s |
| nw_momentum_100s_5k_same_leader | all_books | ALL | 116 | 105 | 87.9% | 0.801 | +0.0780 | +9.0440 | 2599.0% | 4.8s |
| nw_momentum_100s_5k | all_books | ALL | 117 | 105 | 84.6% | 0.771 | +0.0751 | +8.7830 | 2574.5% | 4.9s |
| rax_lane_adv_1 | all_books | MATCH_WINNER_GAME3_PROXY | 15 | 15 | 86.7% | 0.797 | +0.0700 | +1.0500 | 12.9% | 41.7s |
| rax_lane_adv_1_and_nw_leader | all_books | MATCH_WINNER_GAME3_PROXY | 15 | 15 | 86.7% | 0.798 | +0.0687 | +1.0300 | 12.7% | 41.7s |
| nw_momentum_100s_5k_same_leader | all_books | MAP_WINNER | 87 | 87 | 87.4% | 0.805 | +0.0683 | +5.9430 | 3454.1% | 7.0s |
| nw_lead_10k | all_books | MATCH_WINNER_GAME3_PROXY | 17 | 17 | 82.4% | 0.757 | +0.0666 | +1.1320 | 8.4% | 7.2s |
| nw_momentum_100s_5k | all_books | MAP_WINNER | 88 | 88 | 84.1% | 0.775 | +0.0664 | +5.8420 | 3413.0% | 7.7s |
| tower_adv_3 | all_books | ALL | 108 | 99 | 84.3% | 0.778 | +0.0645 | +6.9660 | 2779.6% | 7.6s |
| nw_lead_10k | all_books | ALL | 128 | 116 | 89.1% | 0.828 | +0.0625 | +7.9940 | 2362.3% | 6.7s |
| rax_lane_adv_2 | all_books | MATCH_WINNER_GAME3_PROXY | 14 | 14 | 85.7% | 0.802 | +0.0550 | +0.7700 | 9.5% | 39.7s |
| rax_lane_adv_1 | all_books | ALL | 112 | 102 | 88.4% | 0.837 | +0.0465 | +5.2030 | 2684.4% | 8.2s |
| nw_lead_10k | all_books | MAP_WINNER | 96 | 96 | 88.5% | 0.840 | +0.0459 | +4.4020 | 3126.7% | 8.5s |
| rax_lane_adv_1_and_nw_leader | all_books | ALL | 112 | 102 | 88.4% | 0.840 | +0.0438 | +4.9030 | 2683.9% | 8.8s |
| rax_lane_adv_1 | all_books | MAP_WINNER | 84 | 84 | 86.9% | 0.843 | +0.0260 | +2.1830 | 3570.5% | 11.5s |
| rax_lane_adv_1_and_nw_leader | all_books | MAP_WINNER | 84 | 84 | 86.9% | 0.846 | +0.0227 | +1.9030 | 3569.8% | 13.3s |
| nw_vs_kill_disagree | all_books | MATCH_WINNER_BO1 | 9 | 9 | 55.6% | 0.570 | -0.0144 | -0.1300 | 0.8% | 1.8s |
| tower_adv_3 | all_books | MATCH_WINNER_BO1 | 15 | 15 | 53.3% | 0.587 | -0.0540 | -0.8100 | -11.6% | 3.4s |
| nw_vs_kill_disagree | all_books | MAP_WINNER | 77 | 77 | 53.2% | 0.598 | -0.0651 | -5.0110 | 5167.4% | 5.8s |
| nw_vs_kill_disagree | all_books | ALL | 95 | 87 | 52.6% | 0.600 | -0.0733 | -6.9600 | 4183.4% | 5.4s |
| nw_vs_kill_disagree | all_books | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 44.4% | 0.647 | -0.2021 | -1.8190 | -53.4% | 127.6s |
| rax_lane_adv_1_and_nw_leader | fresh_15s | MATCH_WINNER_GAME3_PROXY | 8 | 8 | 100.0% | 0.756 | +0.2439 | +1.9510 | 47.0% | 1.7s |
| rax_lane_adv_1 | fresh_15s | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 88.9% | 0.671 | +0.2179 | +1.9610 | 31.0% | 1.6s |
| rax_lane_adv_2 | fresh_15s | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 88.9% | 0.695 | +0.1934 | +1.7410 | 25.0% | 2.2s |
| nw_lead_10k | fresh_15s | MATCH_WINNER_BO1 | 15 | 15 | 100.0% | 0.836 | +0.1640 | +2.4600 | 138.4% | 3.0s |
| nw_momentum_100s_5k | fresh_15s | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 83.3% | 0.671 | +0.1623 | +1.9470 | 37.3% | 2.2s |
| nw_momentum_100s_5k_same_leader | fresh_15s | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 83.3% | 0.671 | +0.1623 | +1.9470 | 37.3% | 2.2s |
| nw_lead_5k | fresh_15s | MATCH_WINNER_BO1 | 15 | 15 | 93.3% | 0.780 | +0.1533 | +2.3000 | 18.0% | 2.4s |
| rax_lane_adv_1 | fresh_15s | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.848 | +0.1515 | +1.9700 | 41.8% | 4.0s |
| rax_lane_adv_1_and_nw_leader | fresh_15s | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.848 | +0.1515 | +1.9700 | 41.8% | 4.0s |
| nw_lead_20k | fresh_15s | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 100.0% | 0.854 | +0.1463 | +1.3170 | 29.1% | 2.2s |
| nw_lead_20k | fresh_15s | MATCH_WINNER_BO1 | 12 | 12 | 100.0% | 0.874 | +0.1258 | +1.5100 | 829.6% | 4.4s |
| tower_adv_3 | fresh_15s | MATCH_WINNER_GAME3_PROXY | 11 | 11 | 100.0% | 0.884 | +0.1165 | +1.2810 | 16.4% | 2.2s |
| nw_lead_10k | fresh_15s | MATCH_WINNER_GAME3_PROXY | 14 | 14 | 85.7% | 0.751 | +0.1063 | +1.4880 | 11.4% | 1.7s |
| nw_momentum_100s_5k_same_leader | fresh_15s | MATCH_WINNER_BO1 | 13 | 13 | 92.3% | 0.821 | +0.1023 | +1.3300 | 34.4% | 0.5s |
| rax_lane_adv_2 | fresh_15s | MATCH_WINNER_BO1 | 10 | 10 | 100.0% | 0.902 | +0.0980 | +0.9800 | 20.7% | 0.8s |
| nw_lead_20k | fresh_15s | ALL | 67 | 62 | 98.5% | 0.888 | +0.0975 | +6.5320 | 308.0% | 3.2s |
| nw_momentum_100s_5k | fresh_15s | MATCH_WINNER_BO1 | 13 | 13 | 84.6% | 0.756 | +0.0900 | +1.1700 | 26.1% | 1.2s |
| nw_lead_5k | fresh_15s | MATCH_WINNER_GAME3_PROXY | 15 | 15 | 86.7% | 0.777 | +0.0899 | +1.3490 | 24.7% | 4.7s |
| nw_lead_20k | fresh_15s | MAP_WINNER | 46 | 46 | 97.8% | 0.898 | +0.0805 | +3.7050 | 226.6% | 2.5s |
| nw_lead_5k | fresh_15s | ALL | 116 | 106 | 87.9% | 0.802 | +0.0769 | +8.9210 | 14.5% | 2.4s |
| rax_lane_adv_2 | fresh_15s | ALL | 59 | 54 | 91.5% | 0.844 | +0.0715 | +4.2170 | 177.2% | 2.2s |
| nw_lead_5k | fresh_15s | MAP_WINNER | 86 | 86 | 87.2% | 0.811 | +0.0613 | +5.2720 | 12.2% | 2.3s |
| nw_momentum_100s_5k_same_leader | fresh_15s | ALL | 89 | 82 | 85.4% | 0.799 | +0.0545 | +4.8500 | 124.6% | 1.8s |
| nw_momentum_100s_5k | fresh_15s | ALL | 90 | 83 | 82.2% | 0.776 | +0.0458 | +4.1200 | 121.4% | 2.0s |
| tower_adv_3 | fresh_15s | MAP_WINNER | 54 | 54 | 83.3% | 0.790 | +0.0430 | +2.3230 | 190.0% | 2.6s |
| rax_lane_adv_1 | fresh_15s | ALL | 77 | 72 | 88.3% | 0.843 | +0.0398 | +3.0660 | 139.5% | 1.8s |
| rax_lane_adv_2 | fresh_15s | MAP_WINNER | 40 | 40 | 90.0% | 0.863 | +0.0374 | +1.4960 | 250.5% | 2.8s |
| rax_lane_adv_1_and_nw_leader | fresh_15s | ALL | 76 | 72 | 89.5% | 0.858 | +0.0365 | +2.7760 | 141.9% | 2.1s |
| tower_adv_3 | fresh_15s | ALL | 80 | 75 | 80.0% | 0.765 | +0.0349 | +2.7940 | 128.3% | 2.8s |
| nw_lead_10k | fresh_15s | ALL | 105 | 96 | 89.5% | 0.864 | +0.0310 | +3.2510 | 22.2% | 2.9s |
| nw_momentum_100s_5k_same_leader | fresh_15s | MAP_WINNER | 64 | 64 | 84.4% | 0.819 | +0.0246 | +1.5730 | 159.3% | 2.0s |
| nw_momentum_100s_5k | fresh_15s | MAP_WINNER | 65 | 65 | 81.5% | 0.800 | +0.0154 | +1.0030 | 155.9% | 2.1s |
| nw_lead_10k | fresh_15s | MAP_WINNER | 76 | 76 | 88.2% | 0.891 | -0.0092 | -0.6970 | 1.2% | 2.9s |
| nw_vs_kill_disagree | fresh_15s | MATCH_WINNER_BO1 | 9 | 9 | 55.6% | 0.570 | -0.0144 | -0.1300 | 0.8% | 1.8s |
| rax_lane_adv_1 | fresh_15s | MAP_WINNER | 55 | 55 | 85.5% | 0.870 | -0.0157 | -0.8650 | 180.3% | 1.7s |
| rax_lane_adv_1_and_nw_leader | fresh_15s | MAP_WINNER | 55 | 55 | 85.5% | 0.875 | -0.0208 | -1.1450 | 179.3% | 1.8s |
| tower_adv_3 | fresh_15s | MATCH_WINNER_BO1 | 15 | 15 | 53.3% | 0.587 | -0.0540 | -0.8100 | -11.6% | 3.4s |
| nw_vs_kill_disagree | fresh_15s | MAP_WINNER | 63 | 63 | 55.6% | 0.636 | -0.0800 | -5.0400 | 1577.3% | 2.0s |
| nw_vs_kill_disagree | fresh_15s | ALL | 79 | 75 | 53.2% | 0.620 | -0.0885 | -6.9890 | 1251.8% | 2.1s |
| nw_vs_kill_disagree | fresh_15s | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 28.6% | 0.546 | -0.2599 | -1.8190 | -69.1% | 2.2s |
| nw_momentum_100s_5k | fresh_60s | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 83.3% | 0.655 | +0.1781 | +2.1370 | 39.0% | 2.8s |
| nw_momentum_100s_5k_same_leader | fresh_60s | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 83.3% | 0.655 | +0.1781 | +2.1370 | 39.0% | 2.8s |
| nw_lead_10k | fresh_60s | MATCH_WINNER_BO1 | 15 | 15 | 100.0% | 0.836 | +0.1640 | +2.4600 | 138.4% | 3.0s |
| nw_lead_5k | fresh_60s | MATCH_WINNER_BO1 | 15 | 15 | 93.3% | 0.780 | +0.1533 | +2.3000 | 18.0% | 2.4s |
| rax_lane_adv_1 | fresh_60s | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.848 | +0.1515 | +1.9700 | 41.8% | 4.0s |
| rax_lane_adv_1_and_nw_leader | fresh_60s | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.848 | +0.1515 | +1.9700 | 41.8% | 4.0s |
| nw_lead_20k | fresh_60s | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 100.0% | 0.853 | +0.1473 | +1.3260 | 29.2% | 2.7s |
| nw_lead_20k | fresh_60s | MATCH_WINNER_BO1 | 12 | 12 | 100.0% | 0.874 | +0.1258 | +1.5100 | 829.6% | 4.4s |
| nw_lead_10k | fresh_60s | MATCH_WINNER_GAME3_PROXY | 14 | 14 | 85.7% | 0.741 | +0.1166 | +1.6320 | 12.8% | 1.7s |
| nw_lead_5k | fresh_60s | MATCH_WINNER_GAME3_PROXY | 15 | 15 | 93.3% | 0.828 | +0.1049 | +1.5730 | 32.3% | 10.6s |
| nw_momentum_100s_5k_same_leader | fresh_60s | MATCH_WINNER_BO1 | 13 | 13 | 92.3% | 0.821 | +0.1023 | +1.3300 | 34.4% | 0.5s |
| tower_adv_3 | fresh_60s | MATCH_WINNER_GAME3_PROXY | 13 | 13 | 100.0% | 0.899 | +0.1013 | +1.3170 | 14.2% | 6.9s |
| nw_lead_20k | fresh_60s | ALL | 71 | 66 | 98.6% | 0.885 | +0.1004 | +7.1310 | 292.2% | 4.0s |
| rax_lane_adv_2 | fresh_60s | MATCH_WINNER_BO1 | 10 | 10 | 100.0% | 0.902 | +0.0980 | +0.9800 | 20.7% | 0.8s |
| nw_momentum_100s_5k | fresh_60s | MATCH_WINNER_BO1 | 13 | 13 | 84.6% | 0.756 | +0.0900 | +1.1700 | 26.1% | 1.2s |
| nw_lead_20k | fresh_60s | MAP_WINNER | 50 | 50 | 98.0% | 0.894 | +0.0859 | +4.2950 | 210.5% | 3.5s |
| rax_lane_adv_1 | fresh_60s | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 83.3% | 0.752 | +0.0814 | +0.9770 | 15.4% | 4.5s |
| nw_lead_5k | fresh_60s | ALL | 118 | 108 | 89.0% | 0.810 | +0.0802 | +9.4650 | 15.6% | 2.6s |
| rax_lane_adv_1_and_nw_leader | fresh_60s | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 83.3% | 0.754 | +0.0798 | +0.9570 | 15.2% | 4.5s |
| nw_lead_5k | fresh_60s | MAP_WINNER | 88 | 88 | 87.5% | 0.811 | +0.0635 | +5.5920 | 12.3% | 2.5s |
| rax_lane_adv_2 | fresh_60s | MATCH_WINNER_GAME3_PROXY | 12 | 12 | 83.3% | 0.772 | +0.0614 | +0.7370 | 10.7% | 2.2s |
| nw_momentum_100s_5k_same_leader | fresh_60s | ALL | 92 | 85 | 85.9% | 0.805 | +0.0538 | +4.9500 | 14.7% | 2.1s |
| nw_momentum_100s_5k | fresh_60s | ALL | 93 | 86 | 82.8% | 0.782 | +0.0455 | +4.2300 | 12.8% | 2.2s |
| rax_lane_adv_2 | fresh_60s | ALL | 67 | 62 | 91.0% | 0.867 | +0.0439 | +2.9430 | 156.2% | 2.8s |
| nw_lead_10k | fresh_60s | ALL | 108 | 99 | 89.8% | 0.859 | +0.0389 | +4.2050 | 22.8% | 3.1s |
| tower_adv_3 | fresh_60s | MAP_WINNER | 58 | 58 | 82.8% | 0.795 | +0.0328 | +1.9030 | 5.0% | 3.1s |
| tower_adv_3 | fresh_60s | ALL | 86 | 81 | 80.2% | 0.774 | +0.0280 | +2.4100 | 3.5% | 3.2s |
| rax_lane_adv_2 | fresh_60s | MAP_WINNER | 45 | 45 | 91.1% | 0.884 | +0.0272 | +1.2260 | 225.1% | 3.2s |
| rax_lane_adv_1 | fresh_60s | ALL | 85 | 80 | 88.2% | 0.860 | +0.0228 | +1.9420 | 10.3% | 2.3s |
| nw_momentum_100s_5k_same_leader | fresh_60s | MAP_WINNER | 67 | 67 | 85.1% | 0.829 | +0.0221 | +1.4830 | 6.6% | 2.2s |
| rax_lane_adv_1_and_nw_leader | fresh_60s | ALL | 85 | 80 | 88.2% | 0.863 | +0.0193 | +1.6420 | 9.6% | 2.3s |
| nw_momentum_100s_5k | fresh_60s | MAP_WINNER | 68 | 68 | 82.4% | 0.810 | +0.0136 | +0.9230 | 5.6% | 2.3s |
| nw_lead_10k | fresh_60s | MAP_WINNER | 79 | 79 | 88.6% | 0.885 | +0.0014 | +0.1130 | 2.7% | 3.3s |
| nw_vs_kill_disagree | fresh_60s | MATCH_WINNER_BO1 | 9 | 9 | 55.6% | 0.570 | -0.0144 | -0.1300 | 0.8% | 1.8s |
| rax_lane_adv_1 | fresh_60s | MAP_WINNER | 60 | 60 | 86.7% | 0.883 | -0.0167 | -1.0050 | 2.5% | 2.1s |
| rax_lane_adv_1_and_nw_leader | fresh_60s | MAP_WINNER | 60 | 60 | 86.7% | 0.888 | -0.0214 | -1.2850 | 1.6% | 2.3s |
| tower_adv_3 | fresh_60s | MATCH_WINNER_BO1 | 15 | 15 | 53.3% | 0.587 | -0.0540 | -0.8100 | -11.6% | 3.4s |
| nw_vs_kill_disagree | fresh_60s | MAP_WINNER | 64 | 64 | 54.7% | 0.650 | -0.1033 | -6.6100 | 1545.9% | 2.5s |
| nw_vs_kill_disagree | fresh_60s | ALL | 80 | 76 | 52.5% | 0.632 | -0.1070 | -8.5590 | 1230.8% | 2.3s |
| nw_vs_kill_disagree | fresh_60s | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 28.6% | 0.546 | -0.2599 | -1.8190 | -69.1% | 2.2s |
| nw_lead_20k | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 100.0% | 0.690 | +0.3100 | +1.2400 | 63.5% | 2.4s |
| nw_momentum_100s_5k | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 77.8% | 0.548 | +0.2301 | +2.0710 | 51.2% | 2.2s |
| nw_momentum_100s_5k_same_leader | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 77.8% | 0.548 | +0.2301 | +2.0710 | 51.2% | 2.2s |
| rax_lane_adv_1 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 9 | 9 | 100.0% | 0.792 | +0.2078 | +1.8700 | 59.3% | 2.1s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 9 | 9 | 100.0% | 0.792 | +0.2078 | +1.8700 | 59.3% | 2.1s |
| nw_lead_10k | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.815 | +0.1854 | +2.4100 | 159.3% | 3.0s |
| nw_lead_10k | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 8 | 8 | 75.0% | 0.565 | +0.1851 | +1.4810 | 20.5% | 1.7s |
| tower_adv_3 | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 100.0% | 0.830 | +0.1700 | +1.1900 | 24.4% | 1.4s |
| rax_lane_adv_2 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 6 | 6 | 100.0% | 0.833 | +0.1667 | +1.0000 | 35.2% | 1.4s |
| nw_lead_5k | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 14 | 14 | 92.9% | 0.767 | +0.1614 | +2.2600 | 19.0% | 2.1s |
| nw_momentum_100s_5k_same_leader | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 9 | 9 | 88.9% | 0.744 | +0.1444 | +1.3000 | 49.4% | 0.5s |
| nw_lead_20k | fresh_60s_ask_5_95 | ALL | 34 | 33 | 97.1% | 0.830 | +0.1406 | +4.7800 | 26.8% | 4.0s |
| nw_lead_20k | fresh_60s_ask_5_95 | MAP_WINNER | 22 | 22 | 95.5% | 0.819 | +0.1359 | +2.9900 | 27.1% | 4.3s |
| nw_lead_5k | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 11 | 11 | 90.9% | 0.773 | +0.1356 | +1.4920 | 43.3% | 3.3s |
| nw_momentum_100s_5k | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 9 | 9 | 77.8% | 0.651 | +0.1267 | +1.1400 | 37.4% | 1.2s |
| rax_lane_adv_1 | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 77.8% | 0.673 | +0.1044 | +0.9400 | 20.1% | 2.2s |
| nw_lead_5k | fresh_60s_ask_5_95 | ALL | 98 | 92 | 87.8% | 0.774 | +0.1039 | +10.1820 | 19.5% | 2.1s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 9 | 9 | 77.8% | 0.676 | +0.1022 | +0.9200 | 19.8% | 2.2s |
| rax_lane_adv_2 | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 71.4% | 0.623 | +0.0914 | +0.6400 | 16.9% | 2.2s |
| nw_lead_5k | fresh_60s_ask_5_95 | MAP_WINNER | 73 | 73 | 86.3% | 0.775 | +0.0881 | +6.4300 | 16.0% | 1.9s |
| rax_lane_adv_2 | fresh_60s_ask_5_95 | ALL | 36 | 34 | 86.1% | 0.787 | +0.0742 | +2.6700 | 17.7% | 2.4s |
| nw_momentum_100s_5k_same_leader | fresh_60s_ask_5_95 | ALL | 64 | 59 | 79.7% | 0.725 | +0.0720 | +4.6110 | 20.7% | 1.7s |
| nw_lead_20k | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 8 | 8 | 100.0% | 0.931 | +0.0688 | +0.5500 | 7.4% | 4.4s |
| tower_adv_3 | fresh_60s_ask_5_95 | MAP_WINNER | 44 | 44 | 79.5% | 0.733 | +0.0625 | +2.7500 | 8.5% | 2.8s |
| nw_momentum_100s_5k | fresh_60s_ask_5_95 | ALL | 67 | 62 | 73.1% | 0.681 | +0.0502 | +3.3610 | 14.3% | 1.9s |
| tower_adv_3 | fresh_60s_ask_5_95 | ALL | 64 | 62 | 75.0% | 0.702 | +0.0481 | +3.0800 | 5.7% | 2.5s |
| rax_lane_adv_1 | fresh_60s_ask_5_95 | ALL | 53 | 50 | 83.0% | 0.782 | +0.0479 | +2.5400 | 17.7% | 1.6s |
| nw_lead_10k | fresh_60s_ask_5_95 | ALL | 85 | 80 | 87.1% | 0.823 | +0.0479 | +4.0710 | 28.9% | 2.2s |
| rax_lane_adv_2 | fresh_60s_ask_5_95 | MAP_WINNER | 23 | 23 | 87.0% | 0.825 | +0.0448 | +1.0300 | 13.4% | 3.8s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_ask_5_95 | ALL | 53 | 50 | 83.0% | 0.788 | +0.0423 | +2.2400 | 16.6% | 2.1s |
| nw_momentum_100s_5k_same_leader | fresh_60s_ask_5_95 | MAP_WINNER | 46 | 46 | 78.3% | 0.756 | +0.0270 | +1.2400 | 9.1% | 1.7s |
| nw_momentum_100s_5k | fresh_60s_ask_5_95 | MAP_WINNER | 49 | 49 | 71.4% | 0.711 | +0.0031 | +0.1500 | 3.3% | 2.0s |
| nw_lead_10k | fresh_60s_ask_5_95 | MAP_WINNER | 64 | 64 | 85.9% | 0.857 | +0.0028 | +0.1800 | 3.4% | 2.0s |
| rax_lane_adv_1 | fresh_60s_ask_5_95 | MAP_WINNER | 35 | 35 | 80.0% | 0.808 | -0.0077 | -0.2700 | 6.4% | 1.6s |
| nw_vs_kill_disagree | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 9 | 9 | 55.6% | 0.570 | -0.0144 | -0.1300 | 0.8% | 1.8s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_ask_5_95 | MAP_WINNER | 35 | 35 | 80.0% | 0.816 | -0.0157 | -0.5500 | 4.8% | 1.8s |
| tower_adv_3 | fresh_60s_ask_5_95 | MATCH_WINNER_BO1 | 13 | 13 | 46.2% | 0.528 | -0.0662 | -0.8600 | -13.8% | 3.3s |
| nw_vs_kill_disagree | fresh_60s_ask_5_95 | MAP_WINNER | 60 | 60 | 51.7% | 0.630 | -0.1130 | -6.7800 | -15.7% | 2.1s |
| nw_vs_kill_disagree | fresh_60s_ask_5_95 | ALL | 76 | 72 | 50.0% | 0.615 | -0.1149 | -8.7290 | -18.7% | 2.2s |
| nw_vs_kill_disagree | fresh_60s_ask_5_95 | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 28.6% | 0.546 | -0.2599 | -1.8190 | -69.1% | 2.2s |
| nw_momentum_100s_5k | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 8 | 8 | 87.5% | 0.698 | +0.1765 | +1.4120 | 30.3% | 6.3s |
| nw_momentum_100s_5k_same_leader | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 8 | 8 | 87.5% | 0.698 | +0.1765 | +1.4120 | 30.3% | 6.3s |
| nw_lead_10k | fresh_60s_size_100 | MATCH_WINNER_BO1 | 15 | 15 | 100.0% | 0.837 | +0.1633 | +2.4500 | 138.6% | 3.0s |
| nw_lead_10k | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 10 | 10 | 90.0% | 0.747 | +0.1532 | +1.5320 | 21.2% | 3.1s |
| nw_lead_5k | fresh_60s_size_100 | MATCH_WINNER_BO1 | 15 | 15 | 93.3% | 0.781 | +0.1527 | +2.2900 | 18.0% | 2.4s |
| rax_lane_adv_1 | fresh_60s_size_100 | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.855 | +0.1446 | +1.8800 | 41.1% | 2.1s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_size_100 | MATCH_WINNER_BO1 | 13 | 13 | 100.0% | 0.855 | +0.1446 | +1.8800 | 41.1% | 2.1s |
| nw_lead_20k | fresh_60s_size_100 | MATCH_WINNER_BO1 | 12 | 12 | 100.0% | 0.872 | +0.1275 | +1.5300 | 829.8% | 4.4s |
| rax_lane_adv_2 | fresh_60s_size_100 | MATCH_WINNER_BO1 | 10 | 10 | 100.0% | 0.898 | +0.1020 | +1.0200 | 27.7% | 1.4s |
| nw_momentum_100s_5k_same_leader | fresh_60s_size_100 | MATCH_WINNER_BO1 | 13 | 13 | 92.3% | 0.825 | +0.0985 | +1.2800 | 35.3% | 0.5s |
| nw_lead_20k | fresh_60s_size_100 | ALL | 55 | 54 | 98.2% | 0.895 | +0.0872 | +4.7950 | 370.2% | 4.1s |
| nw_lead_20k | fresh_60s_size_100 | MAP_WINNER | 39 | 39 | 97.4% | 0.892 | +0.0819 | +3.1940 | 266.5% | 4.1s |
| nw_lead_5k | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 11 | 11 | 81.8% | 0.741 | +0.0776 | +0.8540 | 12.7% | 7.1s |
| nw_momentum_100s_5k | fresh_60s_size_100 | MATCH_WINNER_BO1 | 13 | 13 | 84.6% | 0.778 | +0.0685 | +0.8900 | 26.3% | 0.4s |
| nw_lead_5k | fresh_60s_size_100 | ALL | 103 | 99 | 88.3% | 0.824 | +0.0591 | +6.0850 | 8.6% | 2.4s |
| nw_momentum_100s_5k_same_leader | fresh_60s_size_100 | ALL | 72 | 69 | 88.9% | 0.834 | +0.0553 | +3.9840 | 150.1% | 1.9s |
| nw_momentum_100s_5k | fresh_60s_size_100 | ALL | 72 | 69 | 87.5% | 0.820 | +0.0552 | +3.9740 | 150.2% | 1.9s |
| rax_lane_adv_2 | fresh_60s_size_100 | ALL | 50 | 47 | 90.0% | 0.852 | +0.0483 | +2.4160 | 205.9% | 3.3s |
| rax_lane_adv_2 | fresh_60s_size_100 | MAP_WINNER | 33 | 33 | 90.9% | 0.864 | +0.0447 | +1.4750 | 304.4% | 3.8s |
| nw_lead_5k | fresh_60s_size_100 | MAP_WINNER | 77 | 77 | 88.3% | 0.845 | +0.0382 | +2.9410 | 6.2% | 2.2s |
| nw_momentum_100s_5k | fresh_60s_size_100 | MAP_WINNER | 51 | 51 | 88.2% | 0.850 | +0.0328 | +1.6720 | 200.6% | 2.3s |
| tower_adv_3 | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 100.0% | 0.970 | +0.0303 | +0.1210 | 3.2% | 1.9s |
| nw_lead_10k | fresh_60s_size_100 | ALL | 89 | 85 | 89.9% | 0.872 | +0.0269 | +2.3940 | 26.0% | 4.1s |
| nw_momentum_100s_5k_same_leader | fresh_60s_size_100 | MAP_WINNER | 51 | 51 | 88.2% | 0.857 | +0.0253 | +1.2920 | 198.2% | 2.3s |
| rax_lane_adv_1 | fresh_60s_size_100 | ALL | 66 | 63 | 86.4% | 0.843 | +0.0205 | +1.3550 | 157.3% | 2.1s |
| nw_lead_20k | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 100.0% | 0.982 | +0.0178 | +0.0710 | 1.8% | 24.0s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_size_100 | ALL | 65 | 63 | 87.7% | 0.861 | +0.0156 | +1.0150 | 160.4% | 2.1s |
| tower_adv_3 | fresh_60s_size_100 | MAP_WINNER | 47 | 47 | 80.9% | 0.809 | -0.0001 | -0.0060 | 1.6% | 1.9s |
| rax_lane_adv_1 | fresh_60s_size_100 | MAP_WINNER | 46 | 46 | 84.8% | 0.858 | -0.0097 | -0.4460 | 214.6% | 2.2s |
| rax_lane_adv_1 | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 71.4% | 0.726 | -0.0113 | -0.0790 | -3.5% | 2.2s |
| rax_lane_adv_2 | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 71.4% | 0.726 | -0.0113 | -0.0790 | -3.5% | 2.2s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 7 | 7 | 71.4% | 0.726 | -0.0113 | -0.0790 | -3.5% | 2.2s |
| tower_adv_3 | fresh_60s_size_100 | ALL | 66 | 64 | 75.8% | 0.769 | -0.0114 | -0.7550 | -1.6% | 1.9s |
| rax_lane_adv_1_and_nw_leader | fresh_60s_size_100 | MAP_WINNER | 45 | 45 | 86.7% | 0.884 | -0.0175 | -0.7860 | 220.4% | 2.0s |
| nw_lead_10k | fresh_60s_size_100 | MAP_WINNER | 64 | 64 | 87.5% | 0.900 | -0.0248 | -1.5880 | 0.4% | 4.2s |
| tower_adv_3 | fresh_60s_size_100 | MATCH_WINNER_BO1 | 15 | 15 | 53.3% | 0.591 | -0.0580 | -0.8700 | -12.8% | 3.3s |
| nw_vs_kill_disagree | fresh_60s_size_100 | MAP_WINNER | 54 | 54 | 53.7% | 0.641 | -0.1041 | -5.6210 | 1835.1% | 2.1s |
| nw_vs_kill_disagree | fresh_60s_size_100 | MATCH_WINNER_BO1 | 9 | 9 | 44.4% | 0.571 | -0.1267 | -1.1400 | -26.3% | 0.5s |
| nw_vs_kill_disagree | fresh_60s_size_100 | ALL | 67 | 66 | 50.7% | 0.636 | -0.1280 | -8.5790 | 1471.2% | 2.1s |
| nw_vs_kill_disagree | fresh_60s_size_100 | MATCH_WINNER_GAME3_PROXY | 4 | 4 | 25.0% | 0.705 | -0.4545 | -1.8180 | -72.5% | 3.1s |

## Readout

- Best fresh-60s candidate with at least 5 trades: `nw_momentum_100s_5k` on `MATCH_WINNER_GAME3_PROXY` with 12 trades, 83.3% win rate, and +0.1781 avg pnl/share.
- Best broad fresh-60s result: `nw_lead_20k` with 71 trades and +0.1004 avg pnl/share.
- Treat very small positive buckets as candidates only. This executable dataset has only 135 matches and stale books are common, so fresh-book validation matters more than all-row validation.
- Full first-trade ledger written to `pattern_strategy_validation_trades.csv`.
