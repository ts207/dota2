# Pattern Discovery Dataset Analysis

This dataset is useful for state/outcome pattern discovery. It is not an executable ROI dataset; any rule here still needs validation on the clean executable backtest dataset with book prices.

## Cleaning

- Raw rows/matches: 42,887 / 292
- Clean rows/matches: 42,873 / 289
- Dropped matches with fewer than 10 snapshots: 3 (8811838021, 8829506471, 8834507847)
- Net-worth nulls after coalescing: 11,838 in `radiant_lead` -> 2,220 in `nw_lead_clean`

## Building-State Correction

- `tower_state` validates as low 11 bits = Radiant towers alive, high 11 bits = Dire towers alive.
- `building_state` is not a 6+6 barracks bitmask here. The common start value is `0x490049`, which decodes as three 3-bit lane chunks per side.
- Exported lane chunks: `radiant_building_lane_0_state` through `dire_building_lane_2_state`.
- Exported conservative rax proxy: `*_rax_lanes_down`, counting lane chunks whose `0x4` bit is set.

## First Signal Per Match

| Signal | Snapshot rows | Snapshot win | Match signals | First-signal win | Note |
| --- | ---: | ---: | ---: | ---: | --- |
| NW leader when kill leader disagrees | 6,007 | 65.7% | 197 | 54.8% | Tests whether gold beats scoreboard when the two point opposite ways. |
| 100s net-worth momentum >= 5k | 8,026 | 94.2% | 252 | 86.5% | Fast gold swing over a time-based 100 second window. |
| Tower advantage >= 3 | 14,171 | 69.2% | 263 | 76.8% | Structural advantage using verified tower_state side grouping. |
| Rax lane advantage >= 1 | 3,148 | 85.8% | 256 | 91.8% | Uses decoded building_state lane chunks; positive means Dire has more lanes down. |

## Snapshot Diagnostics

Net-worth magnitude buckets show how the advantaged side's final win rate changes as absolute gold lead grows. These are diagnostics, not trade triggers.

| bucket | rows | matches | advantaged_side_win_rate |
| --- | --- | --- | --- |
| 0-2k | 11028 | 277 | 58.4% |
| 2-5k | 6999 | 278 | 74.9% |
| 5-10k | 6590 | 277 | 82.9% |
| 10-20k | 6921 | 273 | 89.3% |
| 20k+ | 7810 | 234 | 98.8% |

Tower advantage buckets use absolute tower advantage and report the advantaged side's win rate. This table is non-monotonic at larger positive advantages, so tower counts should be treated as source-sensitive confirmation rather than a clean standalone rule.

| bucket | rows | matches | advantaged_side_win_rate |
| --- | --- | --- | --- |
| 0-1 | 4174 | 266 | 72.0% |
| 1-3 | 5504 | 274 | 87.5% |
| 3-5 | 1469 | 128 | 47.6% |
| 5+ | 10311 | 162 | 66.4% |

Rax lane buckets use absolute lane advantage and report the advantaged side's win rate.

| bucket | rows | matches | advantaged_side_win_rate |
| --- | --- | --- | --- |
| 1 | 1335 | 215 | 80.8% |
| 2 | 1168 | 188 | 83.7% |
| 3 | 645 | 130 | 100.0% |

## Comebacks

- Matches where the eventual winner trailed in net worth at least once: 207 / 289 (71.6%)
- Median max deficit overcome: 926 gold
- Biggest deficit overcome: 59,429 gold

## Takeaways

- After match-level dedupe, gold leader vs kill leader disagreement is only a modest diagnostic, not a strong standalone rule.
- The strongest first-signal patterns are fast 100s net-worth momentum and decoded rax-lane advantage.
- Structural signals are real, but tower counts are non-monotonic in this source and all tower/rax effects still need executable ask-price validation.
- The old rax fields from a 6+6 bit split were invalid and should not be used.
