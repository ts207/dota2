"""Clean the pattern discovery dataset and mine state/outcome patterns."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("datasets/pattern_discovery_dataset")
SNAPSHOTS_PATH = DATA_DIR / "pattern_snapshots.parquet"
OUTCOMES_PATH = DATA_DIR / "pattern_outcomes.parquet"
SUMMARY_PATH = DATA_DIR / "pattern_match_summary.parquet"
CLEAN_PATH = DATA_DIR / "pattern_snapshots_clean.parquet"
REPORT_PATH = Path("pattern_analysis_report.md")


@dataclass(frozen=True)
class SignalResult:
    name: str
    snapshot_rows: int
    snapshot_win_rate: float
    match_rows: int
    match_win_rate: float
    note: str


def pct(x: float) -> str:
    if pd.isna(x):
        return "n/a"
    return f"{x * 100:.1f}%"


def bit_count(value: float, bits: range | list[int]) -> float:
    if pd.isna(value):
        return np.nan
    ivalue = int(value)
    return float(sum(1 for bit in bits if ivalue & (1 << bit)))


def add_time_delta_feature(
    frame: pd.DataFrame,
    value_col: str,
    seconds: int,
    out_col: str,
) -> None:
    """Compare each row to the latest prior row at least `seconds` earlier."""
    frame[out_col] = np.nan
    for _, idx in frame.groupby("match_id").groups.items():
        sub = frame.loc[idx].sort_values(["game_time_sec", "received_at_ns"])
        times = sub["game_time_sec"].to_numpy(dtype=float)
        values = sub[value_col].to_numpy(dtype=float)
        pos = np.searchsorted(times, times - seconds, side="right") - 1
        valid = pos >= 0
        deltas = np.full(len(sub), np.nan)
        deltas[valid] = values[valid] - values[pos[valid]]
        frame.loc[sub.index, out_col] = deltas


def first_signal_result(
    frame: pd.DataFrame,
    mask: pd.Series,
    predicted_side: pd.Series | np.ndarray,
    name: str,
    note: str,
) -> SignalResult:
    if not isinstance(predicted_side, pd.Series):
        predicted_side = pd.Series(predicted_side, index=frame.index)
    candidates = frame.loc[mask].copy()
    candidates = candidates[predicted_side.loc[candidates.index].isin(["radiant", "dire"])]
    if candidates.empty:
        return SignalResult(name, 0, np.nan, 0, np.nan, note)

    candidates["predicted_side"] = predicted_side.loc[candidates.index]
    candidates["signal_won"] = np.where(
        candidates["predicted_side"] == "radiant",
        candidates["radiant_win"],
        ~candidates["radiant_win"],
    )
    candidates = candidates.sort_values(["match_id", "game_time_sec", "received_at_ns"])
    first_per_match = candidates.drop_duplicates("match_id", keep="first")
    return SignalResult(
        name=name,
        snapshot_rows=len(candidates),
        snapshot_win_rate=float(candidates["signal_won"].mean()),
        match_rows=len(first_per_match),
        match_win_rate=float(first_per_match["signal_won"].mean()),
        note=note,
    )


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    snapshots = pd.read_parquet(SNAPSHOTS_PATH)
    outcomes = pd.read_parquet(OUTCOMES_PATH)
    summary = pd.read_parquet(SUMMARY_PATH)
    return snapshots, outcomes, summary


def clean_and_feature(snapshots: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    snap = snapshots.copy()
    raw_rows = len(snap)
    raw_matches = snap["match_id"].nunique()

    snap["nw_lead_clean"] = snap["radiant_net_worth_lead"].fillna(
        snap["radiant_lead"].fillna(snap["net_worth_diff"])
    )
    before_nw_null = int(snap["radiant_lead"].isna().sum())
    after_nw_null = int(snap["nw_lead_clean"].isna().sum())

    dead_cols = ["roshan_respawn_timer", "series_id", "series_type"]
    snap = snap.drop(columns=[col for col in dead_cols if col in snap.columns])

    match_counts = snap.groupby("match_id").size()
    small_matches = match_counts[match_counts < 10].index
    snap = snap[~snap["match_id"].isin(small_matches)].copy()

    snap = snap.sort_values(["match_id", "game_time_sec", "received_at_ns"]).reset_index(drop=True)

    snap["abs_nw_lead"] = snap["nw_lead_clean"].abs()
    snap["score_diff"] = snap["radiant_score"] - snap["dire_score"]
    snap["abs_score_diff"] = snap["score_diff"].abs()
    snap["total_kills"] = snap["radiant_score"] + snap["dire_score"]

    snap["nw_leader"] = np.select(
        [snap["nw_lead_clean"] > 0, snap["nw_lead_clean"] < 0],
        ["radiant", "dire"],
        default="tied",
    )
    snap["kill_leader"] = np.select(
        [snap["score_diff"] > 0, snap["score_diff"] < 0],
        ["radiant", "dire"],
        default="tied",
    )
    snap["leaders_agree"] = snap["nw_leader"] == snap["kill_leader"]

    # Dota live tower_status uses low 11 bits for Radiant towers and high 11 bits
    # for Dire towers. These counts represent structures still alive.
    snap["towers_alive_radiant"] = snap["tower_state"].apply(lambda value: bit_count(value, range(0, 11)))
    snap["towers_alive_dire"] = snap["tower_state"].apply(lambda value: bit_count(value, range(11, 22)))
    snap["tower_advantage"] = snap["towers_alive_radiant"] - snap["towers_alive_dire"]

    # building_state is not a simple 6+6 barracks bitmask in this dataset.
    # It is packed as 3-bit lane chunks at offsets 0/3/6 for Radiant and
    # 16/19/22 for Dire. The 0x4 bit in each chunk behaves like a lane/racks
    # destruction flag: when Radiant wins, Dire chunks much more often have it.
    build_int = snap["building_state"].fillna(0).astype("int64").to_numpy()
    for side, offsets in {
        "radiant": [0, 3, 6],
        "dire": [16, 19, 22],
    }.items():
        lane_cols = []
        for lane_num, offset in enumerate(offsets):
            col = f"{side}_building_lane_{lane_num}_state"
            snap[col] = np.where(
                snap["building_state"].notna(),
                ((build_int >> offset) & 0b111).astype("float64"),
                np.nan,
            )
            lane_cols.append(col)
        snap[f"{side}_rax_lanes_down"] = (snap[lane_cols] >= 4).sum(axis=1).astype("float64")
        snap.loc[snap["building_state"].isna(), f"{side}_rax_lanes_down"] = np.nan
        snap[f"{side}_building_state_score"] = snap[lane_cols].sum(axis=1)
        snap.loc[snap["building_state"].isna(), f"{side}_building_state_score"] = np.nan

    snap["rax_lane_advantage"] = snap["dire_rax_lanes_down"] - snap["radiant_rax_lanes_down"]
    snap["building_score_advantage"] = (
        snap["dire_building_state_score"] - snap["radiant_building_state_score"]
    )

    add_time_delta_feature(snap, "nw_lead_clean", 100, "nw_change_100s")
    add_time_delta_feature(snap, "nw_lead_clean", 300, "nw_change_300s")
    add_time_delta_feature(snap, "total_kills", 100, "kills_change_100s")

    snap["is_comeback_state"] = False
    snap["max_deficit"] = 0.0
    for _, idx in snap.groupby("match_id").groups.items():
        sub = snap.loc[idx]
        radiant_win = bool(sub["radiant_win"].iloc[0])
        nw = sub["nw_lead_clean"]
        if radiant_win:
            snap.loc[idx, "is_comeback_state"] = nw < 0
            snap.loc[idx, "max_deficit"] = (-nw).clip(lower=0).expanding().max().to_numpy()
        else:
            snap.loc[idx, "is_comeback_state"] = nw > 0
            snap.loc[idx, "max_deficit"] = nw.clip(lower=0).expanding().max().to_numpy()

    meta = {
        "raw_rows": raw_rows,
        "raw_matches": raw_matches,
        "clean_rows": len(snap),
        "clean_matches": snap["match_id"].nunique(),
        "small_matches_dropped": len(small_matches),
        "small_match_ids": list(small_matches),
        "before_nw_null": before_nw_null,
        "after_nw_null": after_nw_null,
    }
    return snap, meta


def advantage_bucket_table(
    frame: pd.DataFrame,
    value_col: str,
    predicted_side: pd.Series | np.ndarray,
    bins: list[float],
    labels: list[str],
    min_rows: int = 50,
) -> pd.DataFrame:
    if not isinstance(predicted_side, pd.Series):
        predicted_side = pd.Series(predicted_side, index=frame.index)
    valid = frame.dropna(subset=[value_col, "radiant_win"]).copy()
    valid["predicted_side"] = predicted_side.loc[valid.index]
    valid = valid[valid["predicted_side"].isin(["radiant", "dire"])].copy()
    valid["advantaged_side_won"] = np.where(
        valid["predicted_side"] == "radiant",
        valid["radiant_win"],
        ~valid["radiant_win"],
    )
    valid["bucket"] = pd.cut(valid[value_col], bins=bins, labels=labels, include_lowest=True)
    rows = []
    for label in labels:
        sub = valid[valid["bucket"] == label]
        if len(sub) >= min_rows:
            rows.append(
                {
                    "bucket": label,
                    "rows": len(sub),
                    "matches": sub["match_id"].nunique(),
                    "advantaged_side_win_rate": sub["advantaged_side_won"].mean(),
                }
            )
    return pd.DataFrame(rows)


def mine_patterns(snap: pd.DataFrame) -> dict[str, object]:
    valid = snap.dropna(subset=["radiant_win"]).copy()

    signal_results = [
        first_signal_result(
            valid,
            (valid["nw_leader"] != "tied")
            & (valid["kill_leader"] != "tied")
            & (valid["nw_leader"] != valid["kill_leader"]),
            valid["nw_leader"],
            "NW leader when kill leader disagrees",
            "Tests whether gold beats scoreboard when the two point opposite ways.",
        ),
        first_signal_result(
            valid,
            valid["nw_change_100s"].abs() >= 5000,
            np.select(
                [valid["nw_change_100s"] >= 5000, valid["nw_change_100s"] <= -5000],
                ["radiant", "dire"],
                default="tied",
            ),
            "100s net-worth momentum >= 5k",
            "Fast gold swing over a time-based 100 second window.",
        ),
        first_signal_result(
            valid,
            valid["tower_advantage"].abs() >= 3,
            np.select(
                [valid["tower_advantage"] >= 3, valid["tower_advantage"] <= -3],
                ["radiant", "dire"],
                default="tied",
            ),
            "Tower advantage >= 3",
            "Structural advantage using verified tower_state side grouping.",
        ),
        first_signal_result(
            valid,
            valid["rax_lane_advantage"].abs() >= 1,
            np.select(
                [valid["rax_lane_advantage"] >= 1, valid["rax_lane_advantage"] <= -1],
                ["radiant", "dire"],
                default="tied",
            ),
            "Rax lane advantage >= 1",
            "Uses decoded building_state lane chunks; positive means Dire has more lanes down.",
        ),
    ]

    nw_abs = advantage_bucket_table(
        valid,
        "abs_nw_lead",
        valid["nw_leader"],
        [0, 2000, 5000, 10000, 20000, np.inf],
        ["0-2k", "2-5k", "5-10k", "10-20k", "20k+"],
        min_rows=100,
    )
    valid["abs_tower_advantage"] = valid["tower_advantage"].abs()
    tower = advantage_bucket_table(
        valid,
        "abs_tower_advantage",
        np.select(
            [valid["tower_advantage"] > 0, valid["tower_advantage"] < 0],
            ["radiant", "dire"],
            default="tied",
        ),
        [0, 1, 3, 5, np.inf],
        ["0-1", "1-3", "3-5", "5+"],
        min_rows=100,
    )
    valid["abs_rax_lane_advantage"] = valid["rax_lane_advantage"].abs()
    rax = advantage_bucket_table(
        valid,
        "abs_rax_lane_advantage",
        np.select(
            [valid["rax_lane_advantage"] > 0, valid["rax_lane_advantage"] < 0],
            ["radiant", "dire"],
            default="tied",
        ),
        [0, 1, 2, 3],
        ["1", "2", "3"],
        min_rows=50,
    )

    comeback_by_match = valid.groupby("match_id")["is_comeback_state"].any()
    max_deficit_by_match = valid.groupby("match_id")["max_deficit"].max()

    return {
        "signals": signal_results,
        "nw_abs": nw_abs,
        "tower": tower,
        "rax": rax,
        "comeback_matches": int(comeback_by_match.sum()),
        "comeback_match_total": int(len(comeback_by_match)),
        "median_deficit": float(max_deficit_by_match[max_deficit_by_match > 0].median()),
        "max_deficit": float(max_deficit_by_match.max()),
    }


def markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_No rows met the minimum sample threshold._"
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.iterrows():
        cells = []
        for col in columns:
            value = row[col]
            if isinstance(value, float) and "rate" in col:
                cells.append(pct(value))
            elif isinstance(value, float):
                cells.append(f"{value:.2f}")
            else:
                cells.append(str(value))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def build_report(meta: dict[str, object], patterns: dict[str, object]) -> str:
    lines = [
        "# Pattern Discovery Dataset Analysis",
        "",
        "This dataset is useful for state/outcome pattern discovery. It is not an executable ROI dataset; any rule here still needs validation on the clean executable backtest dataset with book prices.",
        "",
        "## Cleaning",
        "",
        f"- Raw rows/matches: {meta['raw_rows']:,} / {meta['raw_matches']:,}",
        f"- Clean rows/matches: {meta['clean_rows']:,} / {meta['clean_matches']:,}",
        f"- Dropped matches with fewer than 10 snapshots: {meta['small_matches_dropped']} ({', '.join(meta['small_match_ids'])})",
        f"- Net-worth nulls after coalescing: {meta['before_nw_null']:,} in `radiant_lead` -> {meta['after_nw_null']:,} in `nw_lead_clean`",
        "",
        "## Building-State Correction",
        "",
        "- `tower_state` validates as low 11 bits = Radiant towers alive, high 11 bits = Dire towers alive.",
        "- `building_state` is not a 6+6 barracks bitmask here. The common start value is `0x490049`, which decodes as three 3-bit lane chunks per side.",
        "- Exported lane chunks: `radiant_building_lane_0_state` through `dire_building_lane_2_state`.",
        "- Exported conservative rax proxy: `*_rax_lanes_down`, counting lane chunks whose `0x4` bit is set.",
        "",
        "## First Signal Per Match",
        "",
        "| Signal | Snapshot rows | Snapshot win | Match signals | First-signal win | Note |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in patterns["signals"]:
        lines.append(
            f"| {result.name} | {result.snapshot_rows:,} | {pct(result.snapshot_win_rate)} | "
            f"{result.match_rows:,} | {pct(result.match_win_rate)} | {result.note} |"
        )

    lines.extend(
        [
            "",
            "## Snapshot Diagnostics",
            "",
            "Net-worth magnitude buckets show how the advantaged side's final win rate changes as absolute gold lead grows. These are diagnostics, not trade triggers.",
            "",
            markdown_table(patterns["nw_abs"], ["bucket", "rows", "matches", "advantaged_side_win_rate"]),
            "",
            "Tower advantage buckets use absolute tower advantage and report the advantaged side's win rate. This table is non-monotonic at larger positive advantages, so tower counts should be treated as source-sensitive confirmation rather than a clean standalone rule.",
            "",
            markdown_table(patterns["tower"], ["bucket", "rows", "matches", "advantaged_side_win_rate"]),
            "",
            "Rax lane buckets use absolute lane advantage and report the advantaged side's win rate.",
            "",
            markdown_table(patterns["rax"], ["bucket", "rows", "matches", "advantaged_side_win_rate"]),
            "",
            "## Comebacks",
            "",
            f"- Matches where the eventual winner trailed in net worth at least once: {patterns['comeback_matches']:,} / {patterns['comeback_match_total']:,} ({patterns['comeback_matches'] / patterns['comeback_match_total'] * 100:.1f}%)",
            f"- Median max deficit overcome: {patterns['median_deficit']:,.0f} gold",
            f"- Biggest deficit overcome: {patterns['max_deficit']:,.0f} gold",
            "",
            "## Takeaways",
            "",
            "- After match-level dedupe, gold leader vs kill leader disagreement is only a modest diagnostic, not a strong standalone rule.",
            "- The strongest first-signal patterns are fast 100s net-worth momentum and decoded rax-lane advantage.",
            "- Structural signals are real, but tower counts are non-monotonic in this source and all tower/rax effects still need executable ask-price validation.",
            "- The old rax fields from a 6+6 bit split were invalid and should not be used.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    snapshots, outcomes, summary = load_inputs()
    clean, meta = clean_and_feature(snapshots)
    patterns = mine_patterns(clean)

    clean.to_parquet(CLEAN_PATH, index=False)
    report = build_report(meta, patterns)
    REPORT_PATH.write_text(report)

    print(f"Raw: {meta['raw_rows']:,} rows, {meta['raw_matches']:,} matches")
    print(f"Clean: {meta['clean_rows']:,} rows, {meta['clean_matches']:,} matches")
    print(f"Saved cleaned dataset: {CLEAN_PATH}")
    print(f"Saved report: {REPORT_PATH}")
    print()
    print("First-signal-per-match results:")
    for result in patterns["signals"]:
        print(
            f"- {result.name}: {result.match_rows} matches, "
            f"{pct(result.match_win_rate)} first-signal win "
            f"({result.snapshot_rows} snapshots, {pct(result.snapshot_win_rate)} snapshot win)"
        )


if __name__ == "__main__":
    main()
