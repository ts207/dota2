"""Mine pattern-discovery rules and validate them on executable book data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from analyze_pattern import bit_count, clean_and_feature


PATTERN_PATH = Path("datasets/pattern_discovery_dataset/pattern_snapshots.parquet")
EXECUTABLE_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
REPORT_PATH = Path("pattern_strategy_validation.md")
TRADES_PATH = Path("pattern_strategy_validation_trades.csv")


@dataclass(frozen=True)
class Rule:
    name: str
    description: str
    side_fn: Callable[[pd.DataFrame], pd.Series]


def pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def money(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:+.4f}"


def side_from_signed(series: pd.Series, threshold: float) -> pd.Series:
    return pd.Series(
        np.select([series >= threshold, series <= -threshold], ["radiant", "dire"], default=""),
        index=series.index,
    )


def feature_executable_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """Add the same state features used for discovery to executable side rows."""
    frame = rows.copy()
    frame["nw_lead_clean"] = frame["radiant_lead"].fillna(frame["net_worth_diff"])
    frame["abs_nw_lead"] = frame["nw_lead_clean"].abs()
    frame["score_diff"] = frame["radiant_score"] - frame["dire_score"]
    frame["abs_score_diff"] = frame["score_diff"].abs()
    frame["total_kills"] = frame["radiant_score"] + frame["dire_score"]
    frame["nw_leader"] = side_from_signed(frame["nw_lead_clean"], 0.000001).replace("", "tied")
    frame["kill_leader"] = side_from_signed(frame["score_diff"], 0.000001).replace("", "tied")
    frame["leaders_agree"] = frame["nw_leader"] == frame["kill_leader"]

    frame["towers_alive_radiant"] = frame["tower_state"].apply(lambda value: bit_count(value, range(0, 11)))
    frame["towers_alive_dire"] = frame["tower_state"].apply(lambda value: bit_count(value, range(11, 22)))
    frame["tower_advantage"] = frame["towers_alive_radiant"] - frame["towers_alive_dire"]

    build_int = frame["building_state"].fillna(0).astype("int64").to_numpy()
    for side, offsets in {"radiant": [0, 3, 6], "dire": [16, 19, 22]}.items():
        lane_cols = []
        for lane_num, offset in enumerate(offsets):
            col = f"{side}_building_lane_{lane_num}_state"
            frame[col] = np.where(
                frame["building_state"].notna(),
                ((build_int >> offset) & 0b111).astype("float64"),
                np.nan,
            )
            lane_cols.append(col)
        frame[f"{side}_rax_lanes_down"] = (frame[lane_cols] >= 4).sum(axis=1).astype("float64")
        frame.loc[frame["building_state"].isna(), f"{side}_rax_lanes_down"] = np.nan

    frame["rax_lane_advantage"] = frame["dire_rax_lanes_down"] - frame["radiant_rax_lanes_down"]

    frame = frame.sort_values(["match_id", "label_market_bucket", "received_at_ns", "side"]).reset_index(drop=True)
    frame["nw_change_100s"] = np.nan
    frame["nw_change_300s"] = np.nan

    # Compute momentum on unique game snapshots, then merge back to side-token rows.
    key_cols = ["match_id", "received_at_ns", "game_time_sec"]
    snap = (
        frame.drop_duplicates(key_cols)
        .sort_values(["match_id", "game_time_sec", "received_at_ns"])
        [key_cols + ["nw_lead_clean"]]
        .copy()
    )
    for seconds, out_col in [(100, "nw_change_100s"), (300, "nw_change_300s")]:
        snap[out_col] = np.nan
        for _, idx in snap.groupby("match_id").groups.items():
            sub = snap.loc[idx].sort_values(["game_time_sec", "received_at_ns"])
            times = sub["game_time_sec"].to_numpy(dtype=float)
            values = sub["nw_lead_clean"].to_numpy(dtype=float)
            pos = np.searchsorted(times, times - seconds, side="right") - 1
            valid = pos >= 0
            deltas = np.full(len(sub), np.nan)
            deltas[valid] = values[valid] - values[pos[valid]]
            snap.loc[sub.index, out_col] = deltas
    frame = frame.drop(columns=["nw_change_100s", "nw_change_300s"]).merge(
        snap[key_cols + ["nw_change_100s", "nw_change_300s"]],
        on=key_cols,
        how="left",
    )
    return frame


RULES = [
    Rule(
        "nw_lead_5k",
        "Buy side with >= 5k current net-worth lead.",
        lambda df: side_from_signed(df["nw_lead_clean"], 5000),
    ),
    Rule(
        "nw_lead_10k",
        "Buy side with >= 10k current net-worth lead.",
        lambda df: side_from_signed(df["nw_lead_clean"], 10000),
    ),
    Rule(
        "nw_lead_20k",
        "Buy side with >= 20k current net-worth lead.",
        lambda df: side_from_signed(df["nw_lead_clean"], 20000),
    ),
    Rule(
        "nw_momentum_100s_5k",
        "Buy side gaining >= 5k net worth over the prior 100 seconds.",
        lambda df: side_from_signed(df["nw_change_100s"], 5000),
    ),
    Rule(
        "nw_momentum_100s_5k_same_leader",
        "Buy side gaining >= 5k over 100s only when it is also current NW leader.",
        lambda df: pd.Series(
            np.where(
                (df["nw_change_100s"] >= 5000) & (df["nw_leader"] == "radiant"),
                "radiant",
                np.where((df["nw_change_100s"] <= -5000) & (df["nw_leader"] == "dire"), "dire", ""),
            ),
            index=df.index,
        ),
    ),
    Rule(
        "rax_lane_adv_1",
        "Buy side with at least one decoded rax-lane advantage.",
        lambda df: side_from_signed(df["rax_lane_advantage"], 1),
    ),
    Rule(
        "rax_lane_adv_2",
        "Buy side with at least two decoded rax-lane advantage.",
        lambda df: side_from_signed(df["rax_lane_advantage"], 2),
    ),
    Rule(
        "rax_lane_adv_1_and_nw_leader",
        "Buy rax-lane advantaged side only when it is also current NW leader.",
        lambda df: pd.Series(
            np.where(
                (df["rax_lane_advantage"] >= 1) & (df["nw_leader"] == "radiant"),
                "radiant",
                np.where((df["rax_lane_advantage"] <= -1) & (df["nw_leader"] == "dire"), "dire", ""),
            ),
            index=df.index,
        ),
    ),
    Rule(
        "tower_adv_3",
        "Buy side with >= 3 tower advantage.",
        lambda df: side_from_signed(df["tower_advantage"], 3),
    ),
    Rule(
        "nw_vs_kill_disagree",
        "When NW leader and kill leader disagree, buy the NW leader.",
        lambda df: pd.Series(
            np.where(
                (df["nw_leader"].isin(["radiant", "dire"]))
                & (df["kill_leader"].isin(["radiant", "dire"]))
                & (df["nw_leader"] != df["kill_leader"]),
                df["nw_leader"],
                "",
            ),
            index=df.index,
        ),
    ),
]


FILTERS = [
    ("all_books", lambda df: pd.Series(True, index=df.index)),
    ("fresh_60s", lambda df: df["book_age_ms"] <= 60_000),
    ("fresh_15s", lambda df: df["book_age_ms"] <= 15_000),
    ("fresh_60s_size_100", lambda df: (df["book_age_ms"] <= 60_000) & (df["book_ask_size"] >= 100)),
    ("fresh_60s_ask_5_95", lambda df: (df["book_age_ms"] <= 60_000) & df["book_best_ask"].between(0.05, 0.95)),
]


def score_rule_on_pattern(pattern: pd.DataFrame, rule: Rule) -> dict[str, object]:
    side = rule.side_fn(pattern)
    candidates = pattern[side.isin(["radiant", "dire"])].copy()
    if candidates.empty:
        return {
            "strategy": rule.name,
            "pattern_snapshot_rows": 0,
            "pattern_snapshot_win_rate": np.nan,
            "pattern_match_signals": 0,
            "pattern_first_signal_win_rate": np.nan,
        }

    candidates["predicted_side"] = side.loc[candidates.index]
    candidates["signal_won"] = np.where(
        candidates["predicted_side"] == "radiant",
        candidates["radiant_win"],
        ~candidates["radiant_win"],
    )
    first = candidates.sort_values(["match_id", "game_time_sec", "received_at_ns"]).drop_duplicates("match_id")
    return {
        "strategy": rule.name,
        "pattern_snapshot_rows": len(candidates),
        "pattern_snapshot_win_rate": candidates["signal_won"].mean(),
        "pattern_match_signals": len(first),
        "pattern_first_signal_win_rate": first["signal_won"].mean(),
    }


def executable_trades(executable: pd.DataFrame, rule: Rule, filter_name: str, filter_fn: Callable[[pd.DataFrame], pd.Series]) -> pd.DataFrame:
    side = rule.side_fn(executable)
    rows = executable[side.isin(["radiant", "dire"])].copy()
    if rows.empty:
        return rows

    rows["predicted_side"] = side.loc[rows.index]
    wants_radiant = rows["predicted_side"] == "radiant"
    rows = rows[rows["side_is_radiant"] == wants_radiant]
    rows = rows[rows["book_best_ask"].notna() & filter_fn(rows)].copy()
    if rows.empty:
        return rows

    rows = rows.sort_values(["match_id", "label_market_bucket", "received_at_ns", "book_received_at_ns"])
    rows = rows.drop_duplicates(["match_id", "label_market_bucket"], keep="first").copy()
    rows["strategy"] = rule.name
    rows["filter"] = filter_name
    rows["pnl_per_share"] = np.where(rows["settled_win"], 1.0 - rows["book_best_ask"], -rows["book_best_ask"])
    rows["roi"] = rows["pnl_per_share"] / rows["book_best_ask"]
    return rows


def summarize_trades(trades: pd.DataFrame) -> dict[str, object]:
    if trades.empty:
        return {
            "trades": 0,
            "matches": 0,
            "win_rate": np.nan,
            "avg_ask": np.nan,
            "avg_pnl": np.nan,
            "total_pnl": 0.0,
            "avg_roi": np.nan,
            "median_book_age_s": np.nan,
        }
    return {
        "trades": len(trades),
        "matches": trades["match_id"].nunique(),
        "win_rate": trades["settled_win"].mean(),
        "avg_ask": trades["book_best_ask"].mean(),
        "avg_pnl": trades["pnl_per_share"].mean(),
        "total_pnl": trades["pnl_per_share"].sum(),
        "avg_roi": trades["roi"].mean(),
        "median_book_age_s": (trades["book_age_ms"] / 1000).median(),
    }


def build_report(pattern_scores: pd.DataFrame, validation: pd.DataFrame, trades: pd.DataFrame) -> str:
    lines = [
        "# Pattern Strategy Validation",
        "",
        "Method: mine rule-level state signals on the pattern-discovery dataset, then validate the same rules on the executable dataset by buying the predicted side at `book_best_ask`. Validation is first qualifying trade per `match_id` and `label_market_bucket` to avoid row-repeat inflation.",
        "",
        "## Discovery Scores",
        "",
        "| Strategy | Snapshot rows | Snapshot win | Match signals | First-signal win |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for _, row in pattern_scores.sort_values("pattern_first_signal_win_rate", ascending=False).iterrows():
        lines.append(
            f"| {row.strategy} | {int(row.pattern_snapshot_rows):,} | {pct(row.pattern_snapshot_win_rate)} | "
            f"{int(row.pattern_match_signals):,} | {pct(row.pattern_first_signal_win_rate)} |"
        )

    lines.extend(
        [
            "",
            "## Executable Validation",
            "",
            "| Strategy | Filter | Bucket | Trades | Matches | Win | Avg ask | Avg pnl/share | Total pnl | Avg ROI | Median book age |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    view = validation[validation["trades"] > 0].copy()
    view = view.sort_values(["filter", "avg_pnl", "trades"], ascending=[True, False, False])
    for _, row in view.iterrows():
        lines.append(
            f"| {row.strategy} | {row['filter']} | {row.label_market_bucket} | {int(row.trades)} | "
            f"{int(row.matches)} | {pct(row.win_rate)} | {row.avg_ask:.3f} | {money(row.avg_pnl)} | "
            f"{money(row.total_pnl)} | {pct(row.avg_roi)} | {row.median_book_age_s:.1f}s |"
        )

    best = view[(view["filter"] == "fresh_60s") & (view["trades"] >= 5)].sort_values("avg_pnl", ascending=False)
    lines.extend(["", "## Readout", ""])
    if best.empty:
        lines.append("- No strategy/filter combination with at least 5 fresh executable trades has positive evidence.")
    else:
        top = best.iloc[0]
        lines.append(
            f"- Best fresh-60s candidate with at least 5 trades: `{top.strategy}` on `{top.label_market_bucket}` "
            f"with {int(top.trades)} trades, {pct(top.win_rate)} win rate, and {money(top.avg_pnl)} avg pnl/share."
        )

    broad = view[(view["filter"] == "fresh_60s") & (view["label_market_bucket"] == "ALL") & (view["trades"] >= 10)]
    if not broad.empty:
        top_broad = broad.sort_values("avg_pnl", ascending=False).iloc[0]
        lines.append(
            f"- Best broad fresh-60s result: `{top_broad.strategy}` with {int(top_broad.trades)} trades and "
            f"{money(top_broad.avg_pnl)} avg pnl/share."
        )
    lines.extend(
        [
            "- Treat very small positive buckets as candidates only. This executable dataset has only 135 matches and stale books are common, so fresh-book validation matters more than all-row validation.",
            f"- Full first-trade ledger written to `{TRADES_PATH}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw_pattern = pd.read_parquet(PATTERN_PATH)
    pattern, _ = clean_and_feature(raw_pattern)
    executable = feature_executable_rows(pd.read_parquet(EXECUTABLE_PATH))

    pattern_scores = pd.DataFrame([score_rule_on_pattern(pattern, rule) for rule in RULES])

    all_trades = []
    validation_rows = []
    for rule in RULES:
        for filter_name, filter_fn in FILTERS:
            trades = executable_trades(executable, rule, filter_name, filter_fn)
            if not trades.empty:
                all_trades.append(trades)
            for bucket in ["ALL"] + sorted(executable["label_market_bucket"].dropna().unique().tolist()):
                subset = trades if bucket == "ALL" else trades[trades["label_market_bucket"] == bucket]
                row = {
                    "strategy": rule.name,
                    "filter": filter_name,
                    "label_market_bucket": bucket,
                    **summarize_trades(subset),
                }
                validation_rows.append(row)

    validation = pd.DataFrame(validation_rows)
    trade_ledger = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    if not trade_ledger.empty:
        trade_ledger.to_csv(TRADES_PATH, index=False)
    REPORT_PATH.write_text(build_report(pattern_scores, validation, trade_ledger))

    print(f"Saved report: {REPORT_PATH}")
    print(f"Saved trade ledger: {TRADES_PATH} ({len(trade_ledger)} rows)")
    print()
    fresh = validation[(validation["filter"] == "fresh_60s") & (validation["label_market_bucket"] == "ALL") & (validation["trades"] >= 5)]
    fresh = fresh.sort_values("avg_pnl", ascending=False)
    print("Fresh <=60s executable validation, all buckets:")
    print(fresh[["strategy", "trades", "matches", "win_rate", "avg_ask", "avg_pnl", "total_pnl", "avg_roi"]].to_string(index=False))


if __name__ == "__main__":
    main()
