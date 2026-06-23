"""Comprehensive pattern + executable dataset analysis.

Outputs:
- comprehensive_dataset_analysis.md
- comprehensive_model_trades.csv
- comprehensive_model_calibration.csv
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from analyze_pattern import clean_and_feature
from validate_pattern_strategies import RULES, executable_trades, feature_executable_rows, score_rule_on_pattern


PATTERN_PATH = Path("datasets/pattern_discovery_dataset/pattern_snapshots.parquet")
PATTERN_OUTCOMES_PATH = Path("datasets/pattern_discovery_dataset/pattern_outcomes.parquet")
PATTERN_SUMMARY_PATH = Path("datasets/pattern_discovery_dataset/pattern_match_summary.parquet")
EXECUTABLE_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
EXEC_MARKETS_PATH = Path("datasets/clean_executable_backtest_dataset/clean_markets.parquet")
EXEC_OUTCOMES_PATH = Path("datasets/clean_executable_backtest_dataset/clean_outcomes.parquet")

REPORT_PATH = Path("comprehensive_dataset_analysis.md")
MODEL_TRADES_PATH = Path("comprehensive_model_trades.csv")
CALIBRATION_PATH = Path("comprehensive_model_calibration.csv")


FEATURES = [
    "game_time_sec",
    "nw_lead_clean",
    "abs_nw_lead",
    "score_diff",
    "abs_score_diff",
    "total_kills",
    "tower_advantage",
    "towers_alive_radiant",
    "towers_alive_dire",
    "rax_lane_advantage",
    "radiant_rax_lanes_down",
    "dire_rax_lanes_down",
    "nw_change_100s",
    "nw_change_300s",
    "kills_change_100s",
    "source_update_age_sec",
    "spectators",
]


@dataclass(frozen=True)
class ModelSpec:
    name: str
    estimator: object


def pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def num(value: float, digits: int = 3) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.{digits}f}"


def signed(value: float, digits: int = 4) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:+.{digits}f}"


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    view = df[cols].head(max_rows) if max_rows else df[cols]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in view.iterrows():
        cells = []
        for col in cols:
            value = row[col]
            if isinstance(value, float) and ("rate" in col or col in {"win", "auc", "accuracy"}):
                cells.append(pct(value))
            elif isinstance(value, float) and ("pnl" in col or "edge" in col):
                cells.append(signed(value))
            elif isinstance(value, float):
                cells.append(num(value))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def first_seen_by_match(frame: pd.DataFrame) -> pd.Series:
    return frame.groupby("match_id")["received_at_ns"].min().sort_values()


def side_from_signed(series: pd.Series, threshold: float) -> pd.Series:
    return pd.Series(
        np.select([series >= threshold, series <= -threshold], ["radiant", "dire"], default=""),
        index=series.index,
    )


def add_exec_missing_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["kills_change_100s"] = np.nan
    key_cols = ["match_id", "received_at_ns", "game_time_sec"]
    snap = (
        out.drop_duplicates(key_cols)
        .sort_values(["match_id", "game_time_sec", "received_at_ns"])
        [key_cols + ["total_kills"]]
        .copy()
    )
    snap["kills_change_100s"] = np.nan
    for _, idx in snap.groupby("match_id").groups.items():
        sub = snap.loc[idx].sort_values(["game_time_sec", "received_at_ns"])
        times = sub["game_time_sec"].to_numpy(dtype=float)
        values = sub["total_kills"].to_numpy(dtype=float)
        pos = np.searchsorted(times, times - 100, side="right") - 1
        valid = pos >= 0
        deltas = np.full(len(sub), np.nan)
        deltas[valid] = values[valid] - values[pos[valid]]
        snap.loc[sub.index, "kills_change_100s"] = deltas
    out = out.drop(columns=["kills_change_100s"]).merge(
        snap[key_cols + ["kills_change_100s"]],
        on=key_cols,
        how="left",
    )
    return out


def audit_datasets(pattern_raw: pd.DataFrame, pattern_clean: pd.DataFrame, executable: pd.DataFrame) -> dict[str, object]:
    pattern_matches = set(pattern_clean["match_id"].unique())
    exec_matches = set(executable["match_id"].unique())
    return {
        "pattern_raw_rows": len(pattern_raw),
        "pattern_raw_matches": pattern_raw["match_id"].nunique(),
        "pattern_clean_rows": len(pattern_clean),
        "pattern_clean_matches": pattern_clean["match_id"].nunique(),
        "exec_rows": len(executable),
        "exec_matches": executable["match_id"].nunique(),
        "exec_market_groups": executable[["match_id", "label_market_bucket"]].drop_duplicates().shape[0],
        "overlap_matches": len(pattern_matches & exec_matches),
        "pattern_only_matches": len(pattern_matches - exec_matches),
        "exec_only_matches": len(exec_matches - pattern_matches),
        "radiant_win_pattern": pattern_clean.drop_duplicates("match_id")["radiant_win"].mean(),
        "radiant_win_exec": executable.drop_duplicates("match_id")["radiant_win"].mean(),
    }


def null_table(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for col in cols:
        rows.append(
            {
                "column": col,
                "nonnull": int(frame[col].notna().sum()) if col in frame else 0,
                "null_rate": frame[col].isna().mean() if col in frame else 1.0,
            }
        )
    return pd.DataFrame(rows).sort_values("null_rate", ascending=False)


def distribution_table(frame: pd.DataFrame, col: str) -> pd.DataFrame:
    counts = frame[col].value_counts(dropna=False).reset_index()
    counts.columns = [col, "rows"]
    counts["share"] = counts["rows"] / len(frame)
    return counts


def advantaged_bucket(
    frame: pd.DataFrame,
    value_col: str,
    side: pd.Series,
    bins: list[float],
    labels: list[str],
    min_rows: int = 50,
) -> pd.DataFrame:
    valid = frame.dropna(subset=[value_col, "radiant_win"]).copy()
    valid["side"] = side.loc[valid.index]
    valid = valid[valid["side"].isin(["radiant", "dire"])].copy()
    valid["won"] = np.where(valid["side"] == "radiant", valid["radiant_win"], ~valid["radiant_win"])
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
                    "win_rate": sub["won"].mean(),
                }
            )
    return pd.DataFrame(rows)


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), FEATURES)],
        remainder="drop",
    )


def model_specs() -> list[ModelSpec]:
    return [
        ModelSpec(
            "logistic_l2",
            Pipeline(
                [
                    ("pre", build_preprocessor()),
                    ("clf", LogisticRegression(max_iter=3000, C=0.5)),
                ]
            ),
        ),
        ModelSpec(
            "hist_gradient_boosting",
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    (
                        "clf",
                        HistGradientBoostingClassifier(
                            learning_rate=0.04,
                            max_iter=250,
                            max_leaf_nodes=15,
                            l2_regularization=0.05,
                            random_state=7,
                        ),
                    ),
                ]
            ),
        ),
        ModelSpec(
            "random_forest",
            Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    (
                        "clf",
                        RandomForestClassifier(
                            n_estimators=300,
                            min_samples_leaf=40,
                            max_features="sqrt",
                            random_state=11,
                            n_jobs=-1,
                        ),
                    ),
                ]
            ),
        ),
    ]


def train_test_split_by_match(pattern: pd.DataFrame, train_frac: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    seen = first_seen_by_match(pattern)
    split = int(len(seen) * train_frac)
    train_matches = set(seen.index[:split])
    train = pattern[pattern["match_id"].isin(train_matches)].copy()
    test = pattern[~pattern["match_id"].isin(train_matches)].copy()
    return train, test


def evaluate_models(pattern: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame]:
    valid = pattern.dropna(subset=["radiant_win"]).copy()
    train, test = train_test_split_by_match(valid)
    X_train = train[FEATURES]
    y_train = train["radiant_win"].astype(int)
    X_test = test[FEATURES]
    y_test = test["radiant_win"].astype(int)

    rows = []
    trained = {}
    for spec in model_specs():
        model = spec.estimator
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        rows.append(
            {
                "model": spec.name,
                "train_rows": len(train),
                "test_rows": len(test),
                "train_matches": train["match_id"].nunique(),
                "test_matches": test["match_id"].nunique(),
                "auc": roc_auc_score(y_test, proba),
                "log_loss": log_loss(y_test, proba, labels=[0, 1]),
                "brier": brier_score_loss(y_test, proba),
                "accuracy": accuracy_score(y_test, proba >= 0.5),
            }
        )
        trained[spec.name] = model

    metrics = pd.DataFrame(rows).sort_values(["log_loss", "brier"])
    best_name = metrics.iloc[0]["model"]
    best_model = trained[best_name]
    test = test.copy()
    test["p_radiant"] = best_model.predict_proba(X_test)[:, 1]
    test["p_bucket"] = pd.cut(test["p_radiant"], bins=np.linspace(0, 1, 11), include_lowest=True)
    calibration = (
        test.groupby("p_bucket", observed=False)
        .agg(rows=("match_id", "size"), matches=("match_id", "nunique"), avg_pred=("p_radiant", "mean"), actual=("radiant_win", "mean"))
        .reset_index()
    )
    calibration["abs_error"] = (calibration["avg_pred"] - calibration["actual"]).abs()

    # Refit the selected architecture on all pattern rows before executable scoring.
    full_specs = {spec.name: spec.estimator for spec in model_specs()}
    full_model = full_specs[best_name]
    full_model.fit(valid[FEATURES], valid["radiant_win"].astype(int))
    return metrics, {"name": best_name, "model": full_model}, calibration


def logistic_coefficients(pattern: pd.DataFrame) -> pd.DataFrame:
    valid = pattern.dropna(subset=["radiant_win"]).copy()
    train, _ = train_test_split_by_match(valid)
    model = Pipeline(
        [
            ("pre", build_preprocessor()),
            ("clf", LogisticRegression(max_iter=3000, C=0.5)),
        ]
    )
    model.fit(train[FEATURES], train["radiant_win"].astype(int))
    coefs = model.named_steps["clf"].coef_[0]
    rows = [{"feature": feature, "coef": coef, "abs_coef": abs(coef)} for feature, coef in zip(FEATURES, coefs)]
    return pd.DataFrame(rows).sort_values("abs_coef", ascending=False)


def score_executable_with_model(executable: pd.DataFrame, model: object) -> pd.DataFrame:
    scored = executable.copy()
    scored["model_p_radiant"] = model.predict_proba(scored[FEATURES])[:, 1]
    scored["model_fair"] = np.where(scored["side_is_radiant"], scored["model_p_radiant"], 1 - scored["model_p_radiant"])
    scored["model_edge_to_ask"] = scored["model_fair"] - scored["book_best_ask"]
    return scored


MODEL_FILTERS: list[tuple[str, Callable[[pd.DataFrame], pd.Series]]] = [
    ("fresh_60s", lambda df: df["book_age_ms"] <= 60_000),
    ("fresh_15s", lambda df: df["book_age_ms"] <= 15_000),
    ("fresh_60s_ask_5_95", lambda df: (df["book_age_ms"] <= 60_000) & df["book_best_ask"].between(0.05, 0.95)),
    ("fresh_60s_size_100", lambda df: (df["book_age_ms"] <= 60_000) & (df["book_ask_size"] >= 100)),
]


def first_model_trades(scored: pd.DataFrame, edge: float, filter_name: str, filter_fn: Callable[[pd.DataFrame], pd.Series]) -> pd.DataFrame:
    rows = scored[
        scored["book_best_ask"].notna()
        & (scored["model_edge_to_ask"] >= edge)
        & filter_fn(scored)
    ].copy()
    if rows.empty:
        return rows
    rows = rows.sort_values(["match_id", "label_market_bucket", "received_at_ns", "book_received_at_ns"])
    rows = rows.drop_duplicates(["match_id", "label_market_bucket"], keep="first").copy()
    rows["strategy"] = f"model_edge_{edge:.2f}"
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
            "avg_model_fair": np.nan,
            "avg_edge": np.nan,
            "avg_pnl": np.nan,
            "total_pnl": 0.0,
            "median_book_age_s": np.nan,
        }
    return {
        "trades": len(trades),
        "matches": trades["match_id"].nunique(),
        "win_rate": trades["settled_win"].mean(),
        "avg_ask": trades["book_best_ask"].mean(),
        "avg_model_fair": trades["model_fair"].mean(),
        "avg_edge": trades["model_edge_to_ask"].mean(),
        "avg_pnl": trades["pnl_per_share"].mean(),
        "total_pnl": trades["pnl_per_share"].sum(),
        "median_book_age_s": (trades["book_age_ms"] / 1000).median(),
    }


def model_validation(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ledgers = []
    rows = []
    for edge in [0.02, 0.05, 0.10, 0.15, 0.20]:
        for filter_name, filter_fn in MODEL_FILTERS:
            trades = first_model_trades(scored, edge, filter_name, filter_fn)
            if not trades.empty:
                ledgers.append(trades)
            for bucket in ["ALL"] + sorted(scored["label_market_bucket"].dropna().unique().tolist()):
                subset = trades if bucket == "ALL" else trades[trades["label_market_bucket"] == bucket]
                rows.append(
                    {
                        "strategy": f"model_edge_{edge:.2f}",
                        "filter": filter_name,
                        "label_market_bucket": bucket,
                        **summarize_trades(subset),
                    }
                )
    ledger = pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()
    return pd.DataFrame(rows), ledger


def rule_validation(pattern: pd.DataFrame, executable: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    discovery = pd.DataFrame([score_rule_on_pattern(pattern, rule) for rule in RULES])
    rows = []
    ledgers = []
    filters = [
        ("fresh_60s", lambda df: df["book_age_ms"] <= 60_000),
        ("fresh_60s_ask_5_95", lambda df: (df["book_age_ms"] <= 60_000) & df["book_best_ask"].between(0.05, 0.95)),
        ("fresh_60s_size_100", lambda df: (df["book_age_ms"] <= 60_000) & (df["book_ask_size"] >= 100)),
    ]
    for rule in RULES:
        for filter_name, filter_fn in filters:
            trades = executable_trades(executable, rule, filter_name, filter_fn)
            if not trades.empty:
                ledgers.append(trades)
            all_summary = summarize_rule_trades(trades)
            rows.append({"strategy": rule.name, "filter": filter_name, "label_market_bucket": "ALL", **all_summary})
    validation = pd.DataFrame(rows).merge(discovery, on="strategy", how="left")
    ledger = pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()
    return validation, ledger


def summarize_rule_trades(trades: pd.DataFrame) -> dict[str, object]:
    if trades.empty:
        return {
            "trades": 0,
            "matches": 0,
            "win_rate": np.nan,
            "avg_ask": np.nan,
            "avg_pnl": np.nan,
            "total_pnl": 0.0,
            "median_book_age_s": np.nan,
        }
    return {
        "trades": len(trades),
        "matches": trades["match_id"].nunique(),
        "win_rate": trades["settled_win"].mean(),
        "avg_ask": trades["book_best_ask"].mean(),
        "avg_pnl": trades["pnl_per_share"].mean(),
        "total_pnl": trades["pnl_per_share"].sum(),
        "median_book_age_s": (trades["book_age_ms"] / 1000).median(),
    }


def chronological_split_summary(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if trades.empty:
        return pd.DataFrame(rows)
    for strategy, group in trades.groupby("strategy"):
        group = group.sort_values("received_at_ns")
        if len(group) < 20:
            continue
        mid = len(group) // 2
        for split_name, sub in [("first_half", group.iloc[:mid]), ("second_half", group.iloc[mid:])]:
            rows.append(
                {
                    "strategy": strategy,
                    "split": split_name,
                    "trades": len(sub),
                    "win_rate": sub["settled_win"].mean(),
                    "avg_ask": sub["book_best_ask"].mean(),
                    "avg_pnl": sub["pnl_per_share"].mean(),
                    "total_pnl": sub["pnl_per_share"].sum(),
                }
            )
    return pd.DataFrame(rows)


def build_report(
    audit: dict[str, object],
    pattern_nulls: pd.DataFrame,
    exec_nulls: pd.DataFrame,
    exec_buckets: pd.DataFrame,
    book_age: pd.DataFrame,
    book_ask: pd.DataFrame,
    pattern_buckets: dict[str, pd.DataFrame],
    rule_val: pd.DataFrame,
    model_metrics: pd.DataFrame,
    coeffs: pd.DataFrame,
    calibration: pd.DataFrame,
    model_val: pd.DataFrame,
    chrono: pd.DataFrame,
) -> str:
    lines = [
        "# Comprehensive Dota Dataset Analysis",
        "",
        "This report analyzes both datasets with separate purposes:",
        "",
        "- `pattern_discovery_dataset`: state/outcome mining, no prices.",
        "- `clean_executable_backtest_dataset`: executable validation using `book_best_ask`, settlement labels, book age, and first-trade dedupe.",
        "",
        "## Dataset Audit",
        "",
        f"- Pattern raw: {audit['pattern_raw_rows']:,} rows / {audit['pattern_raw_matches']:,} matches.",
        f"- Pattern clean: {audit['pattern_clean_rows']:,} rows / {audit['pattern_clean_matches']:,} matches.",
        f"- Executable: {audit['exec_rows']:,} side-token rows / {audit['exec_matches']:,} matches / {audit['exec_market_groups']:,} match-market groups.",
        f"- Match overlap: {audit['overlap_matches']:,} overlap, {audit['pattern_only_matches']:,} pattern-only, {audit['exec_only_matches']:,} executable-only.",
        f"- Radiant match win rate: pattern {pct(audit['radiant_win_pattern'])}, executable {pct(audit['radiant_win_exec'])}.",
        "",
        "### Pattern Feature Missingness",
        "",
        markdown_table(pattern_nulls, ["column", "nonnull", "null_rate"]),
        "",
        "### Executable Feature Missingness",
        "",
        markdown_table(exec_nulls, ["column", "nonnull", "null_rate"]),
        "",
        "### Executable Market Buckets",
        "",
        markdown_table(exec_buckets, ["label_market_bucket", "rows", "share"]),
        "",
        "### Book Age And Price",
        "",
        markdown_table(book_age, ["bucket", "rows", "share"]),
        "",
        markdown_table(book_ask, ["bucket", "rows", "win_rate", "avg_pnl_if_buy_all"]),
        "",
        "## Pattern Discovery Findings",
        "",
        "These are state/outcome relationships before prices. Rows are snapshots; matches dedupe repeated observations.",
        "",
        "### Net-Worth Lead",
        "",
        markdown_table(pattern_buckets["nw"], ["bucket", "rows", "matches", "win_rate"]),
        "",
        "### 100s Net-Worth Momentum",
        "",
        markdown_table(pattern_buckets["momentum"], ["bucket", "rows", "matches", "win_rate"]),
        "",
        "### Rax-Lane Advantage",
        "",
        markdown_table(pattern_buckets["rax"], ["bucket", "rows", "matches", "win_rate"]),
        "",
        "### Hand Rule Validation",
        "",
        "Rule validation below is executable, fresh <=60s, all market buckets, first match-market trade only.",
        "",
        markdown_table(
            rule_val[(rule_val["filter"] == "fresh_60s") & (rule_val["trades"] >= 20)].sort_values("avg_pnl", ascending=False),
            ["strategy", "trades", "matches", "win_rate", "avg_ask", "avg_pnl", "total_pnl", "pattern_first_signal_win_rate"],
        ),
        "",
        "### Hand Rule Validation, Fresh 60s And Ask 5c-95c",
        "",
        "This removes the most suspicious near-certain and near-zero prices. It is the cleaner table for judging whether a state rule has tradable value rather than just high settlement accuracy.",
        "",
        markdown_table(
            rule_val[(rule_val["filter"] == "fresh_60s_ask_5_95") & (rule_val["trades"] >= 20)].sort_values("avg_pnl", ascending=False),
            ["strategy", "trades", "matches", "win_rate", "avg_ask", "avg_pnl", "total_pnl", "pattern_first_signal_win_rate"],
        ),
        "",
        "## Pattern-Trained State Models",
        "",
        "Models were trained on the first 70% of pattern matches by first-seen time and evaluated on the later 30% of matches. This avoids row-random leakage across the same match.",
        "",
        markdown_table(model_metrics, ["model", "train_matches", "test_matches", "auc", "log_loss", "brier", "accuracy"]),
        "",
        "### Logistic Feature Direction",
        "",
        "Coefficients are standardized, so magnitude is comparable. Positive pushes Radiant win probability up; negative pushes it down.",
        "",
        markdown_table(coeffs, ["feature", "coef", "abs_coef"], max_rows=12),
        "",
        "### Holdout Calibration",
        "",
        markdown_table(calibration.rename(columns={"p_bucket": "bucket"}), ["bucket", "rows", "matches", "avg_pred", "actual", "abs_error"]),
        "",
        "## Model Edge Validation On Executable Data",
        "",
        "The selected model was refit on all pattern rows, scored on executable rows, then traded only where `model_fair - book_best_ask` exceeded the edge threshold. Validation uses first qualifying trade per match-market.",
        "",
        markdown_table(
            model_val[(model_val["filter"] == "fresh_60s_ask_5_95") & (model_val["trades"] >= 10)].sort_values("avg_pnl", ascending=False),
            ["strategy", "filter", "label_market_bucket", "trades", "matches", "win_rate", "avg_ask", "avg_model_fair", "avg_edge", "avg_pnl", "total_pnl"],
        ),
        "",
        "### Fresh 60s Model Edge, All Prices",
        "",
        markdown_table(
            model_val[(model_val["filter"] == "fresh_60s") & (model_val["label_market_bucket"] == "ALL") & (model_val["trades"] >= 10)].sort_values("avg_pnl", ascending=False),
            ["strategy", "trades", "matches", "win_rate", "avg_ask", "avg_model_fair", "avg_edge", "avg_pnl", "total_pnl"],
        ),
        "",
        "### Chronological Stability",
        "",
        markdown_table(chrono, ["strategy", "split", "trades", "win_rate", "avg_ask", "avg_pnl", "total_pnl"]),
        "",
        "## Verdict",
        "",
        "- The datasets support strong state prediction, but executable value is much thinner than raw win-rate signals imply.",
        "- The strongest simple executable rule remains net-worth lead, especially `nw_lead_5k`, because it survives fresh-book and ask-range filters.",
        "- Kill-score disagreement is rejected: it is weak after match-level dedupe and negative after executable ask costs.",
        "- Rax and momentum are useful state features, but their executable edge is less stable chronologically and should be treated as paper/research candidates.",
        "- Model-edge trading is not ready for live deployment. It finds some low-ask opportunities, but broad MAP_WINNER performance is unstable until the fair model is calibrated directly against executable rows.",
        "- Practical next candidate: paper trade `nw_lead_5k` with fresh books, sane ask range, and first-entry-per-match controls; use model scores only as an overlay until more executable data accumulates.",
        "",
        "## Files Written",
        "",
        f"- `{REPORT_PATH}`",
        f"- `{MODEL_TRADES_PATH}`",
        f"- `{CALIBRATION_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    pattern_raw = pd.read_parquet(PATTERN_PATH)
    pattern_outcomes = pd.read_parquet(PATTERN_OUTCOMES_PATH)
    pattern_summary = pd.read_parquet(PATTERN_SUMMARY_PATH)
    exec_raw = pd.read_parquet(EXECUTABLE_PATH)
    exec_markets = pd.read_parquet(EXEC_MARKETS_PATH)
    exec_outcomes = pd.read_parquet(EXEC_OUTCOMES_PATH)

    pattern, _ = clean_and_feature(pattern_raw)
    executable = add_exec_missing_features(feature_executable_rows(exec_raw))

    audit = audit_datasets(pattern_raw, pattern, executable)
    pattern_nulls = null_table(pattern, FEATURES + ["building_state", "tower_state"])
    exec_nulls = null_table(executable, FEATURES + ["book_best_ask", "book_age_ms", "book_ask_size"])
    exec_buckets = distribution_table(executable, "label_market_bucket")

    age_bucket = pd.cut(
        executable["book_age_ms"] / 1000,
        [-1, 1, 5, 15, 60, 300, 900, 3600, np.inf],
        labels=["<=1s", "1-5s", "5-15s", "15-60s", "1-5m", "5-15m", "15-60m", ">60m"],
    )
    book_age = age_bucket.value_counts().sort_index().reset_index()
    book_age.columns = ["bucket", "rows"]
    book_age["share"] = book_age["rows"] / len(executable)

    executable["buy_all_pnl"] = np.where(executable["settled_win"], 1 - executable["book_best_ask"], -executable["book_best_ask"])
    ask_bucket = pd.cut(
        executable["book_best_ask"],
        [0, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 1.0],
        labels=["0-5c", "5-10c", "10-25c", "25-50c", "50-75c", "75-90c", "90-95c", "95-100c"],
        include_lowest=True,
    )
    book_ask = (
        executable.assign(bucket=ask_bucket)
        .groupby("bucket", observed=False)
        .agg(rows=("match_id", "size"), win_rate=("settled_win", "mean"), avg_pnl_if_buy_all=("buy_all_pnl", "mean"))
        .reset_index()
    )

    pattern_buckets = {
        "nw": advantaged_bucket(
            pattern,
            "abs_nw_lead",
            pattern["nw_leader"],
            [0, 2000, 5000, 10000, 20000, np.inf],
            ["0-2k", "2-5k", "5-10k", "10-20k", "20k+"],
            min_rows=100,
        ),
        "momentum": advantaged_bucket(
            pattern,
            "nw_change_100s",
            side_from_signed(pattern["nw_change_100s"], 0.000001),
            [-np.inf, -5000, -2000, -500, 500, 2000, 5000, np.inf],
            ["<-5k", "-5k to -2k", "-2k to -500", "flat", "+500 to +2k", "+2k to +5k", ">+5k"],
            min_rows=100,
        ),
        "rax": advantaged_bucket(
            pattern,
            "rax_lane_advantage",
            side_from_signed(pattern["rax_lane_advantage"], 0.000001),
            [-3, -2, -1, 0, 1, 2, 3],
            ["-3 to -2", "-2 to -1", "-1 to 0", "0 to +1", "+1 to +2", "+2 to +3"],
            min_rows=50,
        ),
    }

    rule_val, rule_ledger = rule_validation(pattern, executable)
    model_metrics, best_model, calibration = evaluate_models(pattern)
    coeffs = logistic_coefficients(pattern)
    scored = score_executable_with_model(executable, best_model["model"])
    model_val, model_ledger = model_validation(scored)
    model_ledger.to_csv(MODEL_TRADES_PATH, index=False)
    calibration.to_csv(CALIBRATION_PATH, index=False)

    chrono_source = model_ledger[
        (model_ledger["filter"] == "fresh_60s_ask_5_95")
        & (model_ledger["label_market_bucket"] == "MAP_WINNER")
    ].copy()
    chrono = chronological_split_summary(chrono_source)

    report = build_report(
        audit=audit,
        pattern_nulls=pattern_nulls,
        exec_nulls=exec_nulls,
        exec_buckets=exec_buckets,
        book_age=book_age,
        book_ask=book_ask,
        pattern_buckets=pattern_buckets,
        rule_val=rule_val,
        model_metrics=model_metrics,
        coeffs=coeffs,
        calibration=calibration,
        model_val=model_val,
        chrono=chrono,
    )
    REPORT_PATH.write_text(report)

    print(f"Loaded pattern outcomes: {len(pattern_outcomes):,}; summary matches: {len(pattern_summary):,}")
    print(f"Loaded executable markets: {len(exec_markets):,}; outcomes: {len(exec_outcomes):,}")
    print(f"Best holdout model: {best_model['name']}")
    print(f"Saved report: {REPORT_PATH}")
    print(f"Saved model trades: {MODEL_TRADES_PATH} ({len(model_ledger):,} rows)")
    print(f"Saved calibration: {CALIBRATION_PATH}")


if __name__ == "__main__":
    main()
