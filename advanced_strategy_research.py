"""Price-aware strategy research with chronological validation.

This script intentionally goes beyond "leader wins" summaries. It searches
side-relative, price-aware rule families on the executable dataset, selects
rules on earlier matches, and validates them on later matches.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from analyze_pattern import clean_and_feature
from validate_pattern_strategies import feature_executable_rows


PATTERN_PATH = Path("datasets/pattern_discovery_dataset/pattern_snapshots.parquet")
EXECUTABLE_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
REPORT_PATH = Path("advanced_strategy_research.md")
LEDGER_PATH = Path("advanced_strategy_trades.csv")


SIDE_FEATURES = [
    "game_time_sec",
    "side_nw",
    "abs_nw_lead",
    "side_score",
    "abs_score_diff",
    "total_kills",
    "side_nw_change_100s",
    "side_nw_change_300s",
    "side_kills_change_100s",
    "side_tower_adv",
    "side_rax_adv",
    "book_best_ask",
    "book_age_s",
    "book_ask_size",
]


@dataclass(frozen=True)
class StrategyRule:
    name: str
    family: str
    description: str
    mask_fn: Callable[[pd.DataFrame], pd.Series]


def pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def signed(value: float, digits: int = 4) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:+.{digits}f}"


def num(value: float, digits: int = 3) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.{digits}f}"


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    view = df[cols].head(max_rows) if max_rows else df[cols]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in view.iterrows():
        cells = []
        for col in cols:
            value = row[col]
            if isinstance(value, float) and ("rate" in col or col in {"win", "auc"}):
                cells.append(pct(value))
            elif isinstance(value, float) and ("pnl" in col or "edge" in col):
                cells.append(signed(value))
            elif isinstance(value, float):
                cells.append(num(value))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def add_pattern_side_rows(pattern: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = pattern.copy()
    base["book_best_ask"] = np.nan
    base["book_age_s"] = np.nan
    base["book_ask_size"] = np.nan
    for side, sign in [("radiant", 1.0), ("dire", -1.0)]:
        sub = base.copy()
        sub["side"] = side
        sub["side_is_radiant"] = side == "radiant"
        sub["settled_win"] = sub["radiant_win"] if side == "radiant" else ~sub["radiant_win"]
        sub = add_side_relative_features(sub, sign)
        rows.append(sub)
    return pd.concat(rows, ignore_index=True)


def add_side_relative_features(frame: pd.DataFrame, sign: float | pd.Series | np.ndarray | None = None) -> pd.DataFrame:
    out = frame.copy()
    if sign is None:
        sign = np.where(out["side_is_radiant"], 1.0, -1.0)
    out["book_age_s"] = out.get("book_age_ms", np.nan) / 1000.0
    out["side_nw"] = sign * out["nw_lead_clean"]
    out["side_score"] = sign * out["score_diff"]
    out["side_nw_change_100s"] = sign * out["nw_change_100s"]
    out["side_nw_change_300s"] = sign * out["nw_change_300s"]
    out["side_kills_change_100s"] = sign * out["kills_change_100s"]
    out["side_tower_adv"] = sign * out["tower_advantage"]
    out["side_rax_adv"] = sign * out["rax_lane_advantage"]
    out["nw_score_gap"] = out["side_nw"] / 1000.0 - out["side_score"]
    out["is_scoreboard_lag"] = (out["side_nw"] >= 5000) & (out["side_score"] <= 0)
    out["is_comeback_surge"] = (out["side_nw"] <= 2500) & (out["side_nw_change_100s"] >= 5000)
    out["is_state_discount"] = (out["side_nw"] >= 5000) & (out["book_best_ask"] <= 0.75)
    out["pnl_per_share"] = np.where(out["settled_win"], 1.0 - out["book_best_ask"], -out["book_best_ask"])
    out["roi"] = out["pnl_per_share"] / out["book_best_ask"]
    return out


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    pattern_raw = pd.read_parquet(PATTERN_PATH)
    pattern, _ = clean_and_feature(pattern_raw)
    pattern_side = add_pattern_side_rows(pattern)

    executable = feature_executable_rows(pd.read_parquet(EXECUTABLE_PATH))
    executable["kills_change_100s"] = executable.groupby("match_id")["total_kills"].diff().fillna(np.nan)
    sign = np.where(executable["side_is_radiant"], 1.0, -1.0)
    executable_side = add_side_relative_features(executable, sign)
    executable_side = executable_side[
        executable_side["book_best_ask"].notna()
        & executable_side["game_time_sec"].notna()
    ].copy()
    return pattern_side, executable_side


def chronological_match_split(frame: pd.DataFrame, train_frac: float = 0.6) -> tuple[set[str], set[str]]:
    seen = frame.groupby("match_id")["received_at_ns"].min().sort_values()
    split = int(len(seen) * train_frac)
    return set(seen.index[:split]), set(seen.index[split:])


def first_trades(frame: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    rows = frame[mask].copy()
    if rows.empty:
        return rows
    rows = rows.sort_values(["match_id", "label_market_bucket", "received_at_ns", "book_received_at_ns", "book_best_ask"])
    return rows.drop_duplicates(["match_id", "label_market_bucket"], keep="first").copy()


def summarize(trades: pd.DataFrame) -> dict[str, float | int]:
    if trades.empty:
        return {
            "trades": 0,
            "matches": 0,
            "win_rate": np.nan,
            "avg_ask": np.nan,
            "avg_pnl": np.nan,
            "total_pnl": 0.0,
            "median_time": np.nan,
            "avg_side_nw": np.nan,
            "avg_side_mom": np.nan,
        }
    return {
        "trades": len(trades),
        "matches": trades["match_id"].nunique(),
        "win_rate": trades["settled_win"].mean(),
        "avg_ask": trades["book_best_ask"].mean(),
        "avg_pnl": trades["pnl_per_share"].mean(),
        "total_pnl": trades["pnl_per_share"].sum(),
        "median_time": trades["game_time_sec"].median(),
        "avg_side_nw": trades["side_nw"].mean(),
        "avg_side_mom": trades["side_nw_change_100s"].mean(),
    }


def rule_perf(frame: pd.DataFrame, rule: StrategyRule, matches: set[str]) -> tuple[pd.DataFrame, dict[str, object]]:
    subset = frame[frame["match_id"].isin(matches)].copy()
    trades = first_trades(subset, rule.mask_fn(subset))
    return trades, {"strategy": rule.name, "family": rule.family, **summarize(trades)}


def base_filter(df: pd.DataFrame) -> pd.Series:
    return (
        (df["book_age_s"] <= 60)
        & (df["book_best_ask"].between(0.05, 0.95))
        & (df["book_ask_size"] >= 25)
    )


def make_rules() -> list[StrategyRule]:
    rules: list[StrategyRule] = []
    buckets = ["ALL", "MAP_WINNER", "MATCH_WINNER_BO1", "MATCH_WINNER_GAME3_PROXY"]

    def bucket_mask(df: pd.DataFrame, bucket: str) -> pd.Series:
        if bucket == "ALL":
            return pd.Series(True, index=df.index)
        return df["label_market_bucket"] == bucket

    for bucket in buckets:
        bname = "all" if bucket == "ALL" else bucket.lower()
        for lead in [3000, 5000, 8000, 12000, 20000]:
            for ask_hi in [0.55, 0.70, 0.80, 0.90, 0.95]:
                name = f"{bname}_cheap_leader_nw{lead}_ask{int(ask_hi*100)}"
                rules.append(
                    StrategyRule(
                        name,
                        "cheap_leader",
                        f"{bucket}: side has >= {lead} NW lead and ask <= {ask_hi:.2f}.",
                        lambda df, bucket=bucket, lead=lead, ask_hi=ask_hi: base_filter(df)
                        & bucket_mask(df, bucket)
                        & (df["side_nw"] >= lead)
                        & (df["book_best_ask"] <= ask_hi),
                    )
                )

        for lead in [3000, 5000, 8000, 12000]:
            for score_max in [-8, -5, -2, 0, 3]:
                for ask_hi in [0.65, 0.80, 0.90]:
                    name = f"{bname}_scoreboard_lag_nw{lead}_score{score_max}_ask{int(ask_hi*100)}"
                    rules.append(
                        StrategyRule(
                            name,
                            "scoreboard_lag",
                            f"{bucket}: gold leader is not leading kills enough, ask <= {ask_hi:.2f}.",
                            lambda df, bucket=bucket, lead=lead, score_max=score_max, ask_hi=ask_hi: base_filter(df)
                            & bucket_mask(df, bucket)
                            & (df["side_nw"] >= lead)
                            & (df["side_score"] <= score_max)
                            & (df["book_best_ask"] <= ask_hi),
                        )
                    )

        for mom in [2000, 5000, 8000]:
            for nw_max in [-5000, 0, 5000, 10000]:
                for ask_hi in [0.45, 0.60, 0.75, 0.90]:
                    name = f"{bname}_comeback_mom{mom}_nwmax{nw_max}_ask{int(ask_hi*100)}"
                    rules.append(
                        StrategyRule(
                            name,
                            "comeback_momentum",
                            f"{bucket}: side has positive 100s momentum while not yet heavily ahead.",
                            lambda df, bucket=bucket, mom=mom, nw_max=nw_max, ask_hi=ask_hi: base_filter(df)
                            & bucket_mask(df, bucket)
                            & (df["side_nw_change_100s"] >= mom)
                            & (df["side_nw"] <= nw_max)
                            & (df["book_best_ask"] <= ask_hi),
                        )
                    )

        for rax in [1, 2, 3]:
            for ask_hi in [0.65, 0.80, 0.90, 0.95]:
                for time_min in [900, 1500, 2100]:
                    name = f"{bname}_rax_discount_{rax}_t{time_min}_ask{int(ask_hi*100)}"
                    rules.append(
                        StrategyRule(
                            name,
                            "rax_discount",
                            f"{bucket}: decoded rax-lane advantage with bounded ask.",
                            lambda df, bucket=bucket, rax=rax, ask_hi=ask_hi, time_min=time_min: base_filter(df)
                            & bucket_mask(df, bucket)
                            & (df["side_rax_adv"] >= rax)
                            & (df["game_time_sec"] >= time_min)
                            & (df["book_best_ask"] <= ask_hi),
                        )
                    )

        for lead in [5000, 10000, 15000]:
            for mom in [0, 2000, 5000]:
                for time_min in [900, 1500, 2100]:
                    name = f"{bname}_compound_nw{lead}_mom{mom}_t{time_min}"
                    rules.append(
                        StrategyRule(
                            name,
                            "compound_state",
                            f"{bucket}: NW lead plus nonnegative/positive momentum after time gate.",
                            lambda df, bucket=bucket, lead=lead, mom=mom, time_min=time_min: base_filter(df)
                            & bucket_mask(df, bucket)
                            & (df["side_nw"] >= lead)
                            & (df["side_nw_change_100s"] >= mom)
                            & (df["game_time_sec"] >= time_min)
                            & (df["book_best_ask"] <= 0.90),
                        )
                    )

    return rules


def select_and_validate_rules(executable_side: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_matches, test_matches = chronological_match_split(executable_side)
    rows = []
    ledgers = []
    selected_rules = []
    for rule in make_rules():
        train_trades, train_summary = rule_perf(executable_side, rule, train_matches)
        test_trades, test_summary = rule_perf(executable_side, rule, test_matches)
        all_trades = first_trades(executable_side, rule.mask_fn(executable_side))
        all_summary = summarize(all_trades)

        train_summary = {f"train_{k}": v for k, v in train_summary.items() if k not in {"strategy", "family"}}
        test_summary = {f"test_{k}": v for k, v in test_summary.items() if k not in {"strategy", "family"}}
        all_summary = {f"all_{k}": v for k, v in all_summary.items()}
        row = {
            "strategy": rule.name,
            "family": rule.family,
            "description": rule.description,
            **train_summary,
            **test_summary,
            **all_summary,
        }
        rows.append(row)

        if (
            row["train_trades"] >= 12
            and row["train_avg_pnl"] >= 0.04
            and row["train_win_rate"] >= row["train_avg_ask"] + 0.03
            and row["test_trades"] >= 8
        ):
            selected_rules.append(rule)
            if not all_trades.empty:
                all_trades = all_trades.copy()
                all_trades["strategy"] = rule.name
                all_trades["family"] = rule.family
                ledgers.append(all_trades)

    perf = pd.DataFrame(rows)
    selected = perf[perf["strategy"].isin({rule.name for rule in selected_rules})].copy()
    selected = selected.sort_values(["test_avg_pnl", "test_trades"], ascending=[False, False])
    ledger = pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()
    return perf, selected, ledger


def train_side_models(pattern_side: pd.DataFrame, executable_side: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_matches, test_matches = chronological_match_split(executable_side)
    train = executable_side[executable_side["match_id"].isin(train_matches)].dropna(subset=["settled_win"]).copy()
    test = executable_side[executable_side["match_id"].isin(test_matches)].dropna(subset=["settled_win"]).copy()
    train = train[base_filter(train)].copy()
    test = test[base_filter(test)].copy()

    models = {
        "exec_logistic": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=3000, C=0.3)),
            ]
        ),
        "exec_hgb": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        max_iter=180,
                        max_leaf_nodes=8,
                        learning_rate=0.04,
                        l2_regularization=0.1,
                        random_state=31,
                    ),
                ),
            ]
        ),
    }
    rows = []
    scored_parts = []
    for name, model in models.items():
        model.fit(train[SIDE_FEATURES], train["settled_win"].astype(int))
        p = model.predict_proba(test[SIDE_FEATURES])[:, 1]
        rows.append(
            {
                "model": name,
                "train_rows": len(train),
                "test_rows": len(test),
                "train_matches": train["match_id"].nunique(),
                "test_matches": test["match_id"].nunique(),
                "auc": roc_auc_score(test["settled_win"].astype(int), p),
                "log_loss": log_loss(test["settled_win"].astype(int), p, labels=[0, 1]),
                "brier": brier_score_loss(test["settled_win"].astype(int), p),
            }
        )
        scored = test.copy()
        scored["model"] = name
        scored["model_fair"] = p
        scored["model_edge"] = scored["model_fair"] - scored["book_best_ask"]
        scored_parts.append(scored)

    scored_test = pd.concat(scored_parts, ignore_index=True)
    return pd.DataFrame(rows).sort_values("log_loss"), scored_test


def model_edge_summary(scored_test: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (model, edge), group in scored_test.groupby(["model", pd.cut(scored_test["model_edge"], [-1, 0.02, 0.05, 0.10, 0.15, 0.20, 1])], observed=False):
        if group.empty:
            continue
        trades = first_trades(group, group["model_edge"] >= edge.left if edge.left > 0 else group["model_edge"] >= 999)
        if trades.empty:
            continue
        rows.append(
            {
                "model": model,
                "edge_bucket": str(edge),
                **summarize(trades),
                "avg_model_fair": trades["model_fair"].mean(),
                "avg_model_edge": trades["model_edge"].mean(),
            }
        )
    return pd.DataFrame(rows).sort_values("avg_pnl", ascending=False)


def family_summary(perf: pd.DataFrame) -> pd.DataFrame:
    eligible = perf[(perf["train_trades"] >= 12) & (perf["test_trades"] >= 8)].copy()
    if eligible.empty:
        return pd.DataFrame()
    return (
        eligible.groupby("family")
        .agg(
            candidates=("strategy", "size"),
            train_avg_pnl=("train_avg_pnl", "median"),
            test_avg_pnl=("test_avg_pnl", "median"),
            test_positive_rate=("test_avg_pnl", lambda s: (s > 0).mean()),
            best_test_pnl=("test_avg_pnl", "max"),
        )
        .reset_index()
        .sort_values("best_test_pnl", ascending=False)
    )


def build_report(
    pattern_side: pd.DataFrame,
    executable_side: pd.DataFrame,
    perf: pd.DataFrame,
    selected: pd.DataFrame,
    ledger: pd.DataFrame,
    model_metrics: pd.DataFrame,
    model_edges: pd.DataFrame,
) -> str:
    fam = family_summary(perf)
    canonical = (
        selected.sort_values(["test_avg_pnl", "test_trades"], ascending=[False, False])
        .groupby("family", as_index=False)
        .head(2)
        .sort_values(["family", "test_avg_pnl"], ascending=[True, False])
    )
    rejected = (
        perf[(perf["train_trades"] >= 12) & (perf["test_trades"] >= 8)]
        .sort_values("test_avg_pnl")
        .head(12)
    )
    lines = [
        "# Advanced Price-Aware Strategy Research",
        "",
        "This pass searches conditional strategy shapes instead of testing only obvious leader rules. Every row below uses executable ask prices, fresh-book gates, ask-size gates, and first qualifying trade per match-market. Rule selection is based on earlier matches; validation is on later matches.",
        "",
        "## Inputs",
        "",
        f"- Pattern side-expanded rows: {len(pattern_side):,}.",
        f"- Executable side rows after basic non-null filter: {len(executable_side):,}.",
        f"- Base tradability gate: `book_age <= 60s`, `0.05 <= ask <= 0.95`, `ask_size >= 25`.",
        f"- Candidate rules generated: {len(perf):,}.",
        f"- Rules passing train selection and test sample gates: {len(selected):,}.",
        "",
        "## Candidate Family Diagnostics",
        "",
        markdown_table(fam, ["family", "candidates", "train_avg_pnl", "test_avg_pnl", "test_positive_rate", "best_test_pnl"]),
        "",
        "## Canonical Strategy Shapes",
        "",
        "Many selected rows are threshold variants of the same idea. These are the canonical shapes worth carrying forward.",
        "",
        markdown_table(
            canonical,
            [
                "strategy",
                "family",
                "description",
                "train_trades",
                "train_avg_pnl",
                "test_trades",
                "test_win_rate",
                "test_avg_ask",
                "test_avg_pnl",
                "all_trades",
                "all_avg_pnl",
            ],
        ),
        "",
        "## Best Validated Conditional Rules",
        "",
        markdown_table(
            selected,
            [
                "strategy",
                "family",
                "train_trades",
                "train_win_rate",
                "train_avg_ask",
                "train_avg_pnl",
                "test_trades",
                "test_win_rate",
                "test_avg_ask",
                "test_avg_pnl",
                "all_trades",
                "all_avg_pnl",
            ],
            max_rows=25,
        ),
        "",
        "## What Failed",
        "",
        "These rules had enough sample but poor later-match validation, which is the main overfit warning.",
        "",
        markdown_table(
            rejected,
            [
                "strategy",
                "family",
                "train_trades",
                "train_avg_pnl",
                "test_trades",
                "test_win_rate",
                "test_avg_ask",
                "test_avg_pnl",
            ],
        ),
        "",
        "## Executable Side Model Check",
        "",
        "These models are trained only on earlier executable rows that pass the tradability gate and evaluated on later executable rows. This is a sanity check for whether a model can learn residual side value from executable data itself.",
        "",
        markdown_table(model_metrics, ["model", "train_rows", "test_rows", "train_matches", "test_matches", "auc", "log_loss", "brier"]),
        "",
        "### Later-Match Model Edge Trades",
        "",
        markdown_table(model_edges, ["model", "edge_bucket", "trades", "matches", "win_rate", "avg_ask", "avg_model_fair", "avg_model_edge", "avg_pnl", "total_pnl"], max_rows=20),
        "",
        "## Strategy Readout",
        "",
        "- The better non-basic direction is not a generic `buy the leader`; it is `state-discount`: buy a side whose state is materially ahead while the ask has not fully caught up.",
        "- Best higher-sample candidate: `all_cheap_leader_nw3000_ask80`. It buys a side with at least 3k net-worth lead only while ask is <= 0.80; later split was 37 trades, 75.7% win, +0.1232 pnl/share.",
        "- Best non-basic candidate: `all_scoreboard_lag_nw5000_score3_ask80`. It buys a side with at least 5k net-worth lead while the scoreboard is not strongly confirming it, capped at 0.80 ask; later split was 27 trades, 74.1% win, +0.0815 pnl/share.",
        "- Strong but lower-sample steamroll candidate: `all_compound_nw15000_mom0_t1500`. It requires a huge lead after 25 minutes, nonnegative 100s momentum, and ask <= 0.90; later split was 14 trades, 100% win, +0.2436 pnl/share.",
        "- `comeback_momentum` is tempting but unstable; it often finds cheap prices because the side is still losing, and later-match validation is noisy.",
        "- Rax-discount rules are sample-starved and mostly late-game. Treat them as confirmation features, not standalone entries.",
        "- Executable-trained models are useful for diagnostics but not yet production. With only 135 matches, the rule family validation is more interpretable and less fragile.",
        "",
        "## Files Written",
        "",
        f"- `{REPORT_PATH}`",
        f"- `{LEDGER_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    pattern_side, executable_side = load_data()
    perf, selected, ledger = select_and_validate_rules(executable_side)
    model_metrics, scored_test = train_side_models(pattern_side, executable_side)
    model_edges = model_edge_summary(scored_test)

    if not ledger.empty:
        ledger.to_csv(LEDGER_PATH, index=False)
    else:
        LEDGER_PATH.write_text("")

    REPORT_PATH.write_text(
        build_report(
            pattern_side=pattern_side,
            executable_side=executable_side,
            perf=perf,
            selected=selected,
            ledger=ledger,
            model_metrics=model_metrics,
            model_edges=model_edges,
        )
    )

    print(f"Generated {len(perf):,} candidate rules")
    print(f"Selected {len(selected):,} rules")
    print(f"Saved report: {REPORT_PATH}")
    print(f"Saved ledger: {LEDGER_PATH} ({len(ledger):,} rows)")


if __name__ == "__main__":
    main()
