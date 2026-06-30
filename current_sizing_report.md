# Sizing Report

Source: active (bankroll=$1000.0, max_shares=25.0, map_cap=$200.0)

## Main Summary

| sizing | positions | settled | win | avg ask | avg model edge (primary) | avg kill mom (gettoplive) | avg shares | total stake | pnl 2c | ROI | max DD | worst position |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| flat_1 | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 1.0 | 22.7 | 3.46 | 15.22% | 1.51 | -0.78 |
| flat_5 | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 5.0 | 113.7 | 17.30 | 15.22% | 7.55 | -3.90 |
| flat_25_liquidity_unchecked | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 25.0 | 568.5 | 86.52 | 15.22% | 37.75 | -19.50 |
| edge_scaled_0.5pct_bankroll_cap25 | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 16.2 | 361.7 | 85.47 | 23.63% | 21.47 | -10.47 |
| kill_mom_scaled_0.5pct_cap25 | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 6.0 | 133.8 | 32.63 | 24.38% | 7.77 | -7.09 |
| kelly_05_cap25 | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 4.7 | 81.8 | 20.21 | 24.72% | 18.22 | -13.00 |
| kelly_10_cap25 | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 6.1 | 105.4 | 14.72 | 13.96% | 23.44 | -13.00 |
| group_specific_default | 40 | 40 | 67.5% | 0.568 | 16.34% | 2.60 | 8.1 | 167.9 | 57.13 | 34.03% | 15.19 | -10.47 |

## Candidate Group Breakdown

| sizing | group | positions | stake | pnl 2c | ROI |
| --- | --- | --- | --- | --- | --- |
| flat_1 | gettoplive_candidate | 30 | 18.4 | 3.02 | 16.44% |
| flat_1 | primary | 10 | 4.4 | 0.44 | 10.09% |
| flat_1 | active_combined | 40 | 22.7 | 3.46 | 15.22% |
| flat_5 | gettoplive_candidate | 30 | 91.9 | 15.10 | 16.44% |
| flat_5 | primary | 10 | 21.8 | 2.20 | 10.09% |
| flat_5 | active_combined | 40 | 113.7 | 17.30 | 15.22% |
| flat_25_liquidity_unchecked | gettoplive_candidate | 30 | 459.5 | 75.52 | 16.44% |
| flat_25_liquidity_unchecked | primary | 10 | 109.0 | 11.00 | 10.09% |
| flat_25_liquidity_unchecked | active_combined | 40 | 568.5 | 86.52 | 15.22% |
| edge_scaled_0.5pct_bankroll_cap25 | gettoplive_candidate | 30 | 300.0 | 60.74 | 20.25% |
| edge_scaled_0.5pct_bankroll_cap25 | primary | 10 | 61.7 | 24.73 | 40.07% |
| edge_scaled_0.5pct_bankroll_cap25 | active_combined | 40 | 361.7 | 85.47 | 23.63% |
| kill_mom_scaled_0.5pct_cap25 | gettoplive_candidate | 30 | 106.2 | 32.40 | 30.52% |
| kill_mom_scaled_0.5pct_cap25 | primary | 10 | 27.7 | 0.22 | 0.81% |
| kill_mom_scaled_0.5pct_cap25 | active_combined | 40 | 133.8 | 32.63 | 24.38% |
| kelly_05_cap25 | gettoplive_candidate | 30 | 0.0 | 0.00 | 0.0% |
| kelly_05_cap25 | primary | 10 | 81.8 | 20.21 | 24.72% |
| kelly_05_cap25 | active_combined | 40 | 81.8 | 20.21 | 24.72% |
| kelly_10_cap25 | gettoplive_candidate | 30 | 0.0 | 0.00 | 0.0% |
| kelly_10_cap25 | primary | 10 | 105.4 | 14.72 | 13.96% |
| kelly_10_cap25 | active_combined | 40 | 105.4 | 14.72 | 13.96% |
| group_specific_default | gettoplive_candidate | 30 | 106.2 | 32.40 | 30.52% |
| group_specific_default | primary | 10 | 61.7 | 24.73 | 40.07% |
| group_specific_default | active_combined | 40 | 167.9 | 57.13 | 34.03% |

## By Strategy

| sizing | strategy | positions | stake | pnl 2c | ROI |
| --- | --- | --- | --- | --- | --- |
| flat_1 | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 18.4 | 3.02 | 16.44% |
| flat_1 | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 4.4 | 0.44 | 10.09% |
| flat_5 | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 91.9 | 15.10 | 16.44% |
| flat_5 | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 21.8 | 2.20 | 10.09% |
| flat_25_liquidity_unchecked | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 459.5 | 75.52 | 16.44% |
| flat_25_liquidity_unchecked | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 109.0 | 11.00 | 10.09% |
| edge_scaled_0.5pct_bankroll_cap25 | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 300.0 | 60.74 | 20.25% |
| edge_scaled_0.5pct_bankroll_cap25 | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 61.7 | 24.73 | 40.07% |
| kill_mom_scaled_0.5pct_cap25 | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 106.2 | 32.40 | 30.52% |
| kill_mom_scaled_0.5pct_cap25 | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 27.7 | 0.22 | 0.81% |
| kelly_05_cap25 | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 0.0 | 0.00 | 0.0% |
| kelly_05_cap25 | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 81.8 | 20.21 | 24.72% |
| kelly_10_cap25 | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 0.0 | 0.00 | 0.0% |
| kelly_10_cap25 | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 105.4 | 14.72 | 13.96% |
| group_specific_default | paper_gettoplive_kill_mom_favorite_hold_v1 | 30 | 106.2 | 32.40 | 30.52% |
| group_specific_default | paper_winprob_logistic_evfilter_mapequiv_ask20_50_e05_gt900_mom100nonneg | 10 | 61.7 | 24.73 | 40.07% |

## Map Concentration

| sizing | largest map stake | largest map PnL | largest map loss | top 3 maps as % of PnL | top 3 maps as % of stake |
| --- | --- | --- | --- | --- | --- |
| flat_1 | 1.2 | 1.04 | -1.21 | 88.7% | 15.7% |
| flat_5 | 6.2 | 5.20 | -6.05 | 88.7% | 15.7% |
| flat_25_liquidity_unchecked | 31.0 | 26.00 | -30.25 | 88.7% | 15.7% |
| edge_scaled_0.5pct_bankroll_cap25 | 20.0 | 23.00 | -18.03 | 69.6% | 16.6% |
| kill_mom_scaled_0.5pct_cap25 | 8.9 | 7.99 | -9.15 | 70.4% | 19.5% |
| kelly_05_cap25 | 12.5 | 15.50 | -13.00 | 216.4% | 41.6% |
| kelly_10_cap25 | 12.5 | 15.50 | -13.00 | 297.2% | 33.7% |
| group_specific_default | 14.2 | 16.99 | -9.79 | 74.4% | 23.2% |

## Input Completeness

- fair_prob present: 25.0%
- edge present: 100.0%
- book_ask_size present: 100.0%
- source_update_age_sec present: 100.0%
- side_kill_mom present: 100.0%

## Per-Strategy Suggested Default

- primary recommended sizing: edge_scaled
- gettoplive recommended sizing: flat_1 or kill_mom_scaled
- combined active recommended sizing: group_specific_default

## Liquidity Summary

| sizing | liquidity capped | liquidity unknown |
| --- | --- | --- |
| flat_1 | 0.0% | 0.0% |
| flat_5 | 0.0% | 0.0% |
| flat_25_liquidity_unchecked | 0.0% | 0.0% |
| edge_scaled_0.5pct_bankroll_cap25 | 0.0% | 0.0% |
| kill_mom_scaled_0.5pct_cap25 | 0.0% | 0.0% |
| kelly_05_cap25 | 2.5% | 0.0% |
| kelly_10_cap25 | 2.5% | 0.0% |
| group_specific_default | 0.0% | 0.0% |

## Warnings

- [flat_1] less than 50 settled positions (40)
- [flat_5] less than 50 settled positions (40)
- [flat_25_liquidity_unchecked] less than 50 settled positions (40)
- [edge_scaled_0.5pct_bankroll_cap25] less than 50 settled positions (40)
- [kill_mom_scaled_0.5pct_cap25] less than 50 settled positions (40)
- [kelly_05_cap25] less than 50 settled positions (40)
- [kelly_10_cap25] less than 50 settled positions (40)
- [group_specific_default] less than 50 settled positions (40)
