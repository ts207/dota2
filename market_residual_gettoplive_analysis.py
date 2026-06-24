"""Market-price anchored residual analysis for executable GetTopLive snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from dota2bot.side_features import RESEARCH_MIN_GAME_TIME_SEC, add_side_features
from walk_forward_model_research import (
    EDGE_THRESHOLDS,
    MIN_THRESHOLD_TRADES,
    DatasetSplit,
    Fold,
    first_trade_rows,
    make_folds,
    split_development_lockbox,
)


EXECUTABLE_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
REPORT_PATH = Path("market_residual_gettoplive_report.md")
RESIDUALS_PATH = Path("price_bucket_state_residuals.csv")
PREDICTIONS_PATH = Path("market_anchor_model_predictions.csv")
TRADES_PATH = Path("market_anchor_model_trades.csv")
CLV_PATH = Path("gettoplive_clv_event_study.csv")
SUMMARY_PATH = Path("market_anchor_model_summary.csv")

MIN_GAME_TIME_SEC = RESEARCH_MIN_GAME_TIME_SEC
FUTURE_PRICE_MAX_LAG_SEC = 20
ROBUST_RESIDUAL_MIN_ROWS = 25
ROBUST_RESIDUAL_MIN_MATCHES = 10

MARKET_NUMERIC_FEATURES = [
    "logit_market_price",
    "book_spread",
    "book_ask_size_log",
    "book_age_s",
    "game_time_sec",
]
NW_FEATURES = ["side_nw"]
MOMENTUM_FEATURES = ["side_mom_100", "side_mom_300"]
SCORE_FEATURES = [
    "side_score",
    "total_kills",
]
STRUCTURE_FEATURES = [
    "side_tower",
    "side_rax",
    "structure_score",
]
STATE_NUMERIC_FEATURES = NW_FEATURES + MOMENTUM_FEATURES + SCORE_FEATURES + STRUCTURE_FEATURES
CATEGORICAL_FEATURES = ["label_market_bucket"]


def pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def signed(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:+.4f}"


def load_analysis_frame(path: Path = EXECUTABLE_PATH) -> pd.DataFrame:
    frame = add_side_features(pd.read_parquet(path), min_game_time_sec=MIN_GAME_TIME_SEC)
    frame["tradable"] = frame["tradable_research"]
    frame["market_prob"] = frame["book_best_ask"].clip(1e-6, 1 - 1e-6)
    frame["logit_market_price"] = np.log(frame["market_prob"] / (1 - frame["market_prob"]))
    frame["book_ask_size_log"] = np.log1p(frame["book_ask_size"])
    frame["pnl_per_share"] = np.where(frame["settled_win"], 1.0 - frame["book_best_ask"], -frame["book_best_ask"])
    frame["pnl_slip_1c"] = np.where(frame["settled_win"], 1.0 - (frame["book_best_ask"] + 0.01), -(frame["book_best_ask"] + 0.01))
    frame["pnl_slip_2c"] = np.where(frame["settled_win"], 1.0 - (frame["book_best_ask"] + 0.02), -(frame["book_best_ask"] + 0.02))
    return frame[
        frame["settled_win"].notna()
        & frame["side_is_radiant"].notna()
        & frame["game_time_sec"].notna()
        & frame["book_best_ask"].notna()
    ].copy()


def add_residual_buckets(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["ask_bucket"] = pd.cut(
        out["book_best_ask"],
        bins=[0.0, 0.2, 0.35, 0.5, 0.65, 0.8, 1.0],
        labels=["00_20", "20_35", "35_50", "50_65", "65_80", "80_100"],
        include_lowest=True,
    ).astype(str)
    out["side_nw_bucket"] = pd.cut(
        out["side_nw"],
        bins=[-np.inf, -8000, -3000, 3000, 8000, np.inf],
        labels=["nw_lt_-8k", "nw_-8k_-3k", "nw_-3k_3k", "nw_3k_8k", "nw_ge_8k"],
    ).astype(str)
    out["side_mom_100_bucket"] = pd.cut(
        out["side_mom_100"],
        bins=[-np.inf, -5000, -1000, 1000, 5000, np.inf],
        labels=["mom_lt_-5k", "mom_-5k_-1k", "mom_-1k_1k", "mom_1k_5k", "mom_ge_5k"],
    ).astype(str)
    out["side_score_bucket"] = pd.cut(
        out["side_score"],
        bins=[-np.inf, -6, -2, 2, 6, np.inf],
        labels=["score_lt_-6", "score_-6_-2", "score_-2_2", "score_2_6", "score_ge_6"],
    ).astype(str)
    out["structure_score_bucket"] = pd.cut(
        out["structure_score"],
        bins=[-np.inf, -2, -1, 1, 2, np.inf],
        labels=["struct_lt_-2", "struct_-2_-1", "struct_-1_1", "struct_1_2", "struct_ge_2"],
    ).astype(str)
    out["game_time_bucket"] = pd.cut(
        out["game_time_sec"],
        bins=[0, 600, 900, 1200, 1800, 2400, np.inf],
        labels=["0000_0600", "0600_0900", "0900_1200", "1200_1800", "1800_2400", "2400_plus"],
        include_lowest=True,
    ).astype(str)
    return out


def summarize_price_rows(rows: pd.DataFrame) -> dict[str, Any]:
    if rows.empty:
        return {
            "rows": 0,
            "matches": 0,
            "avg_ask": np.nan,
            "win_rate": np.nan,
            "win_rate_minus_avg_ask": np.nan,
            "avg_pnl": np.nan,
            "total_pnl": 0.0,
        }
    avg_ask = rows["book_best_ask"].mean()
    win_rate = rows["settled_win"].mean()
    return {
        "rows": int(len(rows)),
        "matches": int(rows["match_id"].nunique()),
        "avg_ask": float(avg_ask),
        "win_rate": float(win_rate),
        "win_rate_minus_avg_ask": float(win_rate - avg_ask),
        "avg_pnl": float(rows["pnl_per_share"].mean()),
        "total_pnl": float(rows["pnl_per_share"].sum()),
    }


def market_calibration_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tradable = add_residual_buckets(frame[frame["tradable"]].copy())
    for bucket, sub in tradable.groupby("ask_bucket", observed=False):
        rows.append({"table": "market_calibration", "ask_bucket": bucket, "state_bucket_type": None, "state_bucket": None, **summarize_price_rows(sub)})
    return pd.DataFrame(rows)


def residual_bucket_tables(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tradable = add_residual_buckets(frame[frame["tradable"]].copy())
    for bucket_col in ["side_nw_bucket", "side_mom_100_bucket", "side_score_bucket", "structure_score_bucket", "game_time_bucket"]:
        for (ask_bucket, state_bucket), sub in tradable.groupby(["ask_bucket", bucket_col], observed=False):
            if sub.empty:
                continue
            rows.append(
                {
                    "table": "state_residual",
                    "ask_bucket": ask_bucket,
                    "state_bucket_type": bucket_col,
                    "state_bucket": state_bucket,
                    **summarize_price_rows(sub),
                }
            )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["robust_residual_bucket"] = (
        (out["rows"] >= ROBUST_RESIDUAL_MIN_ROWS)
        & (out["matches"] >= ROBUST_RESIDUAL_MIN_MATCHES)
        & (out["win_rate_minus_avg_ask"] > 0)
        & (out["avg_pnl"] > 0)
    )
    out["robust_gate_reason"] = np.select(
        [
            out["robust_residual_bucket"],
            out["rows"] < ROBUST_RESIDUAL_MIN_ROWS,
            out["matches"] < ROBUST_RESIDUAL_MIN_MATCHES,
            out["win_rate_minus_avg_ask"] <= 0,
            out["avg_pnl"] <= 0,
        ],
        [
            "pass",
            "too_few_rows",
            "too_few_matches",
            "nonpositive_residual",
            "nonpositive_pnl",
        ],
        default="other",
    )
    return out


def model_pipeline(numeric_features: list[str]) -> Pipeline:
    return Pipeline(
        [
            (
                "pre",
                ColumnTransformer(
                    [
                        ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_features),
                        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
                    ],
                    verbose_feature_names_out=False,
                ),
            ),
            ("clf", LogisticRegression(max_iter=3000, C=0.6)),
        ]
    )


def market_models() -> dict[str, tuple[Pipeline, list[str]]]:
    return {
        "market_only_logistic": (model_pipeline(MARKET_NUMERIC_FEATURES), MARKET_NUMERIC_FEATURES + CATEGORICAL_FEATURES),
        "market_nw_logistic": (
            model_pipeline(MARKET_NUMERIC_FEATURES + NW_FEATURES),
            MARKET_NUMERIC_FEATURES + NW_FEATURES + CATEGORICAL_FEATURES,
        ),
        "market_momentum_logistic": (
            model_pipeline(MARKET_NUMERIC_FEATURES + MOMENTUM_FEATURES),
            MARKET_NUMERIC_FEATURES + MOMENTUM_FEATURES + CATEGORICAL_FEATURES,
        ),
        "market_score_logistic": (
            model_pipeline(MARKET_NUMERIC_FEATURES + SCORE_FEATURES),
            MARKET_NUMERIC_FEATURES + SCORE_FEATURES + CATEGORICAL_FEATURES,
        ),
        "market_structure_logistic": (
            model_pipeline(MARKET_NUMERIC_FEATURES + STRUCTURE_FEATURES),
            MARKET_NUMERIC_FEATURES + STRUCTURE_FEATURES + CATEGORICAL_FEATURES,
        ),
        "market_gettoplive_logistic": (
            model_pipeline(MARKET_NUMERIC_FEATURES + STATE_NUMERIC_FEATURES),
            MARKET_NUMERIC_FEATURES + STATE_NUMERIC_FEATURES + CATEGORICAL_FEATURES,
        ),
    }


def summarize_predictions(rows: pd.DataFrame, prob_col: str) -> dict[str, Any]:
    rows = rows[rows[prob_col].notna()].copy()
    if rows.empty:
        return {"pred_rows": 0, "auc": np.nan, "log_loss": np.nan, "brier": np.nan}
    y = rows["settled_win"].astype(int)
    p = rows[prob_col].clip(1e-6, 1 - 1e-6)
    auc = roc_auc_score(y, p) if y.nunique() == 2 else np.nan
    return {
        "pred_rows": int(len(rows)),
        "auc": float(auc) if not pd.isna(auc) else np.nan,
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier": float(brier_score_loss(y, p)),
    }


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "matches": 0,
            "win_rate": np.nan,
            "avg_ask": np.nan,
            "avg_edge": np.nan,
            "avg_pnl": np.nan,
            "total_pnl": 0.0,
            "total_pnl_slip_1c": 0.0,
            "total_pnl_slip_2c": 0.0,
        }
    return {
        "trades": int(len(trades)),
        "matches": int(trades["match_id"].nunique()),
        "win_rate": float(trades["settled_win"].mean()),
        "avg_ask": float(trades["book_best_ask"].mean()),
        "avg_edge": float(trades["edge"].mean()),
        "avg_pnl": float(trades["pnl_per_share"].mean()),
        "total_pnl": float(trades["pnl_per_share"].sum()),
        "total_pnl_slip_1c": float(trades["pnl_slip_1c"].sum()),
        "total_pnl_slip_2c": float(trades["pnl_slip_2c"].sum()),
    }


def choose_threshold(validation: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    rows = []
    tradable = validation[validation["tradable"]].copy()
    for threshold in EDGE_THRESHOLDS:
        scored = tradable.assign(edge=tradable["calibrated_prob"] - tradable["book_best_ask"])
        trades = first_trade_rows(scored[scored["edge"] >= threshold])
        rows.append({"threshold": threshold, **summarize_trades(trades)})
    table = pd.DataFrame(rows)
    eligible = table[table["trades"] >= MIN_THRESHOLD_TRADES].copy()
    if eligible.empty:
        return EDGE_THRESHOLDS[-1], table
    eligible = eligible.sort_values(["total_pnl_slip_1c", "total_pnl", "trades"], ascending=[False, False, False])
    return float(eligible.iloc[0]["threshold"]), table


def run_market_anchor_walk_forward(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[Fold], DatasetSplit]:
    split = split_development_lockbox(frame)
    development = frame[frame["match_id"].astype(str).isin(split.development_matches)].copy()
    lockbox = frame[frame["match_id"].astype(str).isin(split.lockbox_matches)].copy()
    folds = make_folds(development)
    predictions: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    threshold_rows: list[pd.DataFrame] = []
    metrics: list[dict[str, Any]] = []

    for fold in folds:
        fit = development[development["match_id"].astype(str).isin(fold.fit_matches)].copy()
        validation = development[development["match_id"].astype(str).isin(fold.validation_matches)].copy()
        test = development[development["match_id"].astype(str).isin(fold.test_matches)].copy()
        for model_name, (model, features) in market_models().items():
            model.fit(fit[features], fit["settled_win"].astype(int))
            validation_scored = validation.copy()
            test_scored = test.copy()
            validation_scored["calibrated_prob"] = model.predict_proba(validation[features])[:, 1]
            test_scored["calibrated_prob"] = model.predict_proba(test[features])[:, 1]
            threshold, threshold_table = choose_threshold(validation_scored)
            threshold_table["stage"] = "walk_forward"
            threshold_table["fold"] = fold.fold
            threshold_table["model_name"] = model_name
            threshold_rows.append(threshold_table)

            test_scored["stage"] = "walk_forward"
            test_scored["fold"] = fold.fold
            test_scored["model_name"] = model_name
            test_scored["model_version"] = "market_anchor_v1"
            test_scored["training_cutoff_match_time"] = fold.training_cutoff_match_time
            test_scored["market_prob"] = test_scored["book_best_ask"]
            test_scored["edge"] = test_scored["calibrated_prob"] - test_scored["book_best_ask"]
            test_scored["entry_threshold"] = threshold
            test_scored["signal"] = test_scored["tradable"] & (test_scored["edge"] >= threshold)
            test_scored["reason"] = np.where(test_scored["signal"], "market_anchor_edge", "below_threshold_or_not_tradable")
            predictions.append(prediction_output(test_scored))
            model_trades = first_trade_rows(test_scored[test_scored["signal"]]).copy()
            model_trades["paper_entry_price"] = model_trades["book_best_ask"]
            trades.append(trade_output(model_trades))
            metrics.append(
                {
                    "stage": "walk_forward",
                    "fold": fold.fold,
                    "model_name": model_name,
                    "selected_threshold": threshold,
                    **summarize_predictions(test_scored[test_scored["tradable"]], "calibrated_prob"),
                    **{f"trade_{k}": v for k, v in summarize_trades(model_trades).items()},
                }
            )

    for model_name in market_models():
        lock_predictions, lock_trades, lock_thresholds, lock_metrics = run_lockbox(frame, split, model_name)
        predictions.append(lock_predictions)
        trades.append(lock_trades)
        threshold_rows.append(lock_thresholds)
        metrics.append(lock_metrics)
    return (
        pd.concat(predictions, ignore_index=True),
        pd.concat(trades, ignore_index=True),
        pd.concat(threshold_rows, ignore_index=True),
        pd.DataFrame(metrics),
        folds,
        split,
    )


def run_lockbox(frame: pd.DataFrame, split: DatasetSplit, model_name: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    dev = frame[frame["match_id"].astype(str).isin(split.development_matches)].copy()
    lockbox = frame[frame["match_id"].astype(str).isin(split.lockbox_matches)].copy()
    dev_matches = dev.groupby("match_id", as_index=False).agg(first_received_at_utc=("received_at_utc", "min"), first_received_at_ns=("received_at_ns", "min"))
    dev_matches = dev_matches.sort_values(["first_received_at_ns", "match_id"])
    val_count = min(max(10, int(round(len(dev_matches) * 0.25))), max(1, len(dev_matches) - 5))
    fit_matches = dev_matches.iloc[:-val_count]["match_id"].astype(str).tolist()
    validation_matches = dev_matches.iloc[-val_count:]["match_id"].astype(str).tolist()
    fit = dev[dev["match_id"].astype(str).isin(fit_matches)].copy()
    validation = dev[dev["match_id"].astype(str).isin(validation_matches)].copy()
    model, features = market_models()[model_name]
    model.fit(fit[features], fit["settled_win"].astype(int))
    validation_scored = validation.copy()
    lockbox_scored = lockbox.copy()
    validation_scored["calibrated_prob"] = model.predict_proba(validation[features])[:, 1]
    lockbox_scored["calibrated_prob"] = model.predict_proba(lockbox[features])[:, 1]
    threshold, threshold_table = choose_threshold(validation_scored)
    threshold_table["stage"] = "lockbox"
    threshold_table["fold"] = 0
    threshold_table["model_name"] = model_name
    lockbox_scored["stage"] = "lockbox"
    lockbox_scored["fold"] = 0
    lockbox_scored["model_name"] = model_name
    lockbox_scored["model_version"] = "market_anchor_v1"
    lockbox_scored["training_cutoff_match_time"] = str(dev_matches["first_received_at_utc"].iloc[-1])
    lockbox_scored["market_prob"] = lockbox_scored["book_best_ask"]
    lockbox_scored["edge"] = lockbox_scored["calibrated_prob"] - lockbox_scored["book_best_ask"]
    lockbox_scored["entry_threshold"] = threshold
    lockbox_scored["signal"] = lockbox_scored["tradable"] & (lockbox_scored["edge"] >= threshold)
    lockbox_scored["reason"] = np.where(lockbox_scored["signal"], "market_anchor_edge_lockbox", "below_threshold_or_not_tradable")
    trades = first_trade_rows(lockbox_scored[lockbox_scored["signal"]]).copy()
    trades["paper_entry_price"] = trades["book_best_ask"]
    metrics = {
        "stage": "lockbox",
        "fold": 0,
        "model_name": model_name,
        "selected_threshold": threshold,
        **summarize_predictions(lockbox_scored[lockbox_scored["tradable"]], "calibrated_prob"),
        **{f"trade_{k}": v for k, v in summarize_trades(trades).items()},
    }
    return prediction_output(lockbox_scored), trade_output(trades), threshold_table, metrics


def aggregate_model_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return metrics
    return (
        metrics.groupby(["stage", "model_name"], as_index=False)
        .agg(
            folds=("fold", "nunique"),
            median_threshold=("selected_threshold", "median"),
            pred_rows=("pred_rows", "sum"),
            auc=("auc", "mean"),
            log_loss=("log_loss", "mean"),
            brier=("brier", "mean"),
            trade_trades=("trade_trades", "sum"),
            trade_matches=("trade_matches", "sum"),
            trade_win_rate=("trade_win_rate", "mean"),
            trade_avg_ask=("trade_avg_ask", "mean"),
            trade_avg_edge=("trade_avg_edge", "mean"),
            trade_avg_pnl=("trade_avg_pnl", "mean"),
            trade_total_pnl=("trade_total_pnl", "sum"),
            trade_total_pnl_slip_1c=("trade_total_pnl_slip_1c", "sum"),
            trade_total_pnl_slip_2c=("trade_total_pnl_slip_2c", "sum"),
        )
        .sort_values(["stage", "trade_total_pnl_slip_1c"], ascending=[True, False])
    )


def concentration_tables(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        empty = pd.DataFrame()
        return empty, empty, empty
    by_bucket = (
        trades.groupby(["stage", "model_name", "label_market_bucket"], as_index=False)
        .agg(
            trades=("match_id", "size"),
            matches=("match_id", "nunique"),
            win_rate=("settled_win", "mean"),
            total_pnl=("pnl_per_share", "sum"),
            total_pnl_slip_1c=("pnl_slip_1c", "sum"),
            total_pnl_slip_2c=("pnl_slip_2c", "sum"),
        )
        .sort_values(["stage", "model_name", "total_pnl_slip_1c"], ascending=[True, True, False])
    )
    by_match = (
        trades.groupby(["stage", "model_name", "match_id"], as_index=False)
        .agg(
            trades=("label_market_bucket", "size"),
            buckets=("label_market_bucket", "nunique"),
            win_rate=("settled_win", "mean"),
            total_pnl=("pnl_per_share", "sum"),
            total_pnl_slip_1c=("pnl_slip_1c", "sum"),
            total_pnl_slip_2c=("pnl_slip_2c", "sum"),
        )
    )
    by_match["abs_total_pnl_slip_1c"] = by_match["total_pnl_slip_1c"].abs()
    by_match = by_match.sort_values(["stage", "model_name", "abs_total_pnl_slip_1c"], ascending=[True, True, False]).drop(
        columns=["abs_total_pnl_slip_1c"]
    )
    if "league_id" not in trades.columns:
        return by_bucket, by_match, pd.DataFrame()
    by_league = (
        trades.groupby(["stage", "model_name", "league_id"], dropna=False, as_index=False)
        .agg(
            trades=("match_id", "size"),
            matches=("match_id", "nunique"),
            win_rate=("settled_win", "mean"),
            total_pnl=("pnl_per_share", "sum"),
            total_pnl_slip_1c=("pnl_slip_1c", "sum"),
            total_pnl_slip_2c=("pnl_slip_2c", "sum"),
        )
        .sort_values(["stage", "model_name", "total_pnl_slip_1c"], ascending=[True, True, False])
    )
    return by_bucket, by_match, by_league


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return np.nan, np.nan
    p = wins / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2))) / denom
    return float(center - margin), float(center + margin)


def trade_uncertainty_table(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    for (stage, model_name), sub in trades.groupby(["stage", "model_name"]):
        wins = int(sub["settled_win"].sum())
        n = int(len(sub))
        low, high = wilson_interval(wins, n)
        rows.append(
            {
                "stage": stage,
                "model_name": model_name,
                "trades": n,
                "wins": wins,
                "win_rate": wins / n if n else np.nan,
                "win_rate_ci_low": low,
                "win_rate_ci_high": high,
                "avg_ask": sub["book_best_ask"].mean(),
                "total_pnl": sub["pnl_per_share"].sum(),
                "total_pnl_slip_1c": sub["pnl_slip_1c"].sum(),
                "total_pnl_slip_2c": sub["pnl_slip_2c"].sum(),
            }
        )
    return pd.DataFrame(rows).sort_values(["stage", "total_pnl_slip_1c"], ascending=[True, False])


def fold_robustness_table(model_metrics: pd.DataFrame) -> pd.DataFrame:
    walk = model_metrics[model_metrics["stage"] == "walk_forward"].copy()
    if walk.empty:
        return pd.DataFrame()
    return (
        walk.groupby("model_name", as_index=False)
        .agg(
            folds=("fold", "nunique"),
            folds_with_trades=("trade_trades", lambda s: int((s > 0).sum())),
            folds_positive_raw=("trade_total_pnl", lambda s: int((s > 0).sum())),
            folds_positive_1c=("trade_total_pnl_slip_1c", lambda s: int((s > 0).sum())),
            folds_positive_2c=("trade_total_pnl_slip_2c", lambda s: int((s > 0).sum())),
            total_trades=("trade_trades", "sum"),
            total_pnl=("trade_total_pnl", "sum"),
            total_pnl_slip_1c=("trade_total_pnl_slip_1c", "sum"),
            total_pnl_slip_2c=("trade_total_pnl_slip_2c", "sum"),
        )
        .sort_values(["total_pnl_slip_1c", "total_trades"], ascending=[False, False])
    )


def model_summary_table(model_metrics: pd.DataFrame, trades: pd.DataFrame | None = None) -> pd.DataFrame:
    aggregate = aggregate_model_metrics(model_metrics)
    if aggregate.empty:
        return pd.DataFrame(
            columns=[
                "stage",
                "model_name",
                "folds",
                "pred_rows",
                "auc",
                "log_loss",
                "brier",
                "trade_trades",
                "trade_win_rate",
                "trade_avg_ask",
                "trade_total_pnl",
                "trade_total_pnl_slip_1c",
                "trade_total_pnl_slip_2c",
                "folds_with_trades",
                "folds_positive_1c",
                "folds_positive_2c",
                "win_rate_ci_low",
                "win_rate_ci_high",
                "uncertainty_reason",
                "verdict",
            ]
        )
    robustness = (
        model_metrics.groupby(["stage", "model_name"], as_index=False)
        .agg(
            folds_with_trades=("trade_trades", lambda s: int((s > 0).sum())),
            folds_positive_1c=("trade_total_pnl_slip_1c", lambda s: int((s > 0).sum())),
            folds_positive_2c=("trade_total_pnl_slip_2c", lambda s: int((s > 0).sum())),
        )
    )
    summary = aggregate.merge(robustness, on=["stage", "model_name"], how="left")
    if trades is not None and not trades.empty:
        uncertainty = trade_uncertainty_table(trades)[["stage", "model_name", "win_rate_ci_low", "win_rate_ci_high"]]
        summary = summary.merge(uncertainty, on=["stage", "model_name"], how="left")
    else:
        summary["win_rate_ci_low"] = np.nan
        summary["win_rate_ci_high"] = np.nan

    positive_after_slip = (summary["trade_total_pnl_slip_1c"] > 0) & (summary["trade_total_pnl_slip_2c"] > 0) & (summary["trade_trades"] > 0)
    enough_fold_coverage = (
        (summary["stage"] == "walk_forward")
        & (summary["folds_with_trades"] >= 2)
        & (summary["folds_positive_1c"] >= 2)
        & (summary["folds_positive_2c"] >= 2)
    )
    wide_uncertainty = summary["win_rate_ci_low"].isna() | (summary["win_rate_ci_low"] <= summary["trade_avg_ask"])
    summary["uncertainty_reason"] = np.select(
        [
            summary["trade_trades"] == 0,
            summary["win_rate_ci_low"].isna(),
            wide_uncertainty,
        ],
        [
            "no_trades",
            "not_measured",
            "ci_low_not_above_breakeven",
        ],
        default="ci_low_above_breakeven",
    )
    summary["verdict"] = np.select(
        [positive_after_slip & enough_fold_coverage & ~wide_uncertainty, positive_after_slip],
        ["candidate", "research_only"],
        default="reject",
    )
    cols = [
        "stage",
        "model_name",
        "folds",
        "pred_rows",
        "auc",
        "log_loss",
        "brier",
        "trade_trades",
        "trade_win_rate",
        "trade_avg_ask",
        "trade_total_pnl",
        "trade_total_pnl_slip_1c",
        "trade_total_pnl_slip_2c",
        "folds_with_trades",
        "folds_positive_1c",
        "folds_positive_2c",
        "win_rate_ci_low",
        "win_rate_ci_high",
        "uncertainty_reason",
        "verdict",
    ]
    return summary[cols].sort_values(["stage", "trade_total_pnl_slip_1c"], ascending=[True, False])


def acceptance_summary(aggregate: pd.DataFrame, clv: pd.DataFrame) -> dict[str, Any]:
    def row(stage: str, model_name: str) -> pd.Series | None:
        rows = aggregate[(aggregate["stage"] == stage) & (aggregate["model_name"] == model_name)]
        return None if rows.empty else rows.iloc[0]

    walk_enhanced = row("walk_forward", "market_gettoplive_logistic")
    walk_market = row("walk_forward", "market_only_logistic")
    lock_enhanced = row("lockbox", "market_gettoplive_logistic")
    lock_market = row("lockbox", "market_only_logistic")

    settlement_pass = (
        walk_enhanced is not None
        and walk_market is not None
        and lock_enhanced is not None
        and lock_market is not None
        and walk_enhanced["trade_total_pnl_slip_1c"] > walk_market["trade_total_pnl_slip_1c"]
        and walk_enhanced["trade_total_pnl_slip_2c"] > walk_market["trade_total_pnl_slip_2c"]
        and lock_enhanced["trade_total_pnl_slip_1c"] > lock_market["trade_total_pnl_slip_1c"]
        and lock_enhanced["trade_total_pnl_slip_2c"] > lock_market["trade_total_pnl_slip_2c"]
        and walk_enhanced["trade_total_pnl_slip_1c"] > 0
        and walk_enhanced["trade_total_pnl_slip_2c"] > 0
        and lock_enhanced["trade_total_pnl_slip_1c"] > 0
        and lock_enhanced["trade_total_pnl_slip_2c"] > 0
    )

    clv_60 = clv[clv["horizon_s"] == 60].copy()
    positive_clv_60 = clv_60[(clv_60["avg_clv_bid"] > 0) & (clv_60["matches"] >= 3)]
    clv_pass = not positive_clv_60.empty
    walk_models = aggregate[aggregate["stage"] == "walk_forward"].copy()
    lock_models = aggregate[aggregate["stage"] == "lockbox"].copy()
    best_walk = walk_models.sort_values(["trade_total_pnl_slip_1c", "trade_total_pnl_slip_2c"], ascending=[False, False]).iloc[0] if not walk_models.empty else None
    best_lock = lock_models.sort_values(["trade_total_pnl_slip_1c", "trade_total_pnl_slip_2c"], ascending=[False, False]).iloc[0] if not lock_models.empty else None
    return {
        "settlement_pass": bool(settlement_pass),
        "clv_pass": bool(clv_pass),
        "walk_enhanced_1c": float(walk_enhanced["trade_total_pnl_slip_1c"]) if walk_enhanced is not None else np.nan,
        "walk_market_1c": float(walk_market["trade_total_pnl_slip_1c"]) if walk_market is not None else np.nan,
        "walk_enhanced_2c": float(walk_enhanced["trade_total_pnl_slip_2c"]) if walk_enhanced is not None else np.nan,
        "walk_market_2c": float(walk_market["trade_total_pnl_slip_2c"]) if walk_market is not None else np.nan,
        "lock_enhanced_1c": float(lock_enhanced["trade_total_pnl_slip_1c"]) if lock_enhanced is not None else np.nan,
        "lock_market_1c": float(lock_market["trade_total_pnl_slip_1c"]) if lock_market is not None else np.nan,
        "lock_enhanced_2c": float(lock_enhanced["trade_total_pnl_slip_2c"]) if lock_enhanced is not None else np.nan,
        "lock_market_2c": float(lock_market["trade_total_pnl_slip_2c"]) if lock_market is not None else np.nan,
        "positive_clv_60_events": int(len(positive_clv_60)),
        "best_avg_clv_bid_60": float(clv_60["avg_clv_bid"].max()) if not clv_60.empty else np.nan,
        "best_walk_model": str(best_walk["model_name"]) if best_walk is not None else "n/a",
        "best_walk_1c": float(best_walk["trade_total_pnl_slip_1c"]) if best_walk is not None else np.nan,
        "best_walk_2c": float(best_walk["trade_total_pnl_slip_2c"]) if best_walk is not None else np.nan,
        "best_lock_model": str(best_lock["model_name"]) if best_lock is not None else "n/a",
        "best_lock_1c": float(best_lock["trade_total_pnl_slip_1c"]) if best_lock is not None else np.nan,
        "best_lock_2c": float(best_lock["trade_total_pnl_slip_2c"]) if best_lock is not None else np.nan,
    }


def prediction_output(frame: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "stage",
        "fold",
        "model_name",
        "model_version",
        "training_cutoff_match_time",
        "match_id",
        "market_id",
        "label_market_bucket",
        "token_id",
        "side",
        "received_at_utc",
        "received_at_ns",
        "game_time_sec",
        "settled_win",
        "market_prob",
        "calibrated_prob",
        "book_best_ask",
        "book_best_bid",
        "book_spread",
        "book_ask_size",
        "edge",
        "entry_threshold",
        "signal",
        "tradable",
        "reason",
        "side_nw",
        "side_mom_100",
        "side_mom_300",
        "side_score",
        "side_tower",
        "side_rax",
        "structure_score",
    ]
    return frame[[c for c in cols if c in frame.columns]].copy()


def trade_output(frame: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "stage",
        "fold",
        "model_name",
        "model_version",
        "training_cutoff_match_time",
        "match_id",
        "market_id",
        "label_market_bucket",
        "token_id",
        "side",
        "received_at_utc",
        "received_at_ns",
        "game_time_sec",
        "league_id",
        "settled_win",
        "market_prob",
        "calibrated_prob",
        "book_best_ask",
        "book_best_bid",
        "book_spread",
        "book_ask_size",
        "edge",
        "entry_threshold",
        "paper_entry_price",
        "pnl_per_share",
        "pnl_slip_1c",
        "pnl_slip_2c",
        "side_nw",
        "side_mom_100",
        "side_score",
        "structure_score",
        "reason",
    ]
    if frame.empty:
        return pd.DataFrame(columns=cols)
    return frame[[c for c in cols if c in frame.columns]].copy()


def add_future_prices(frame: pd.DataFrame, horizons: list[int] | None = None) -> pd.DataFrame:
    horizons = horizons or [15, 30, 60, 120]
    out = frame.sort_values(["match_id", "market_id", "token_id", "game_time_sec", "received_at_ns"]).copy()
    for horizon in horizons:
        out[f"future_mid_{horizon}s"] = np.nan
        out[f"future_bid_{horizon}s"] = np.nan
        out[f"future_delay_{horizon}s"] = np.nan
    group_cols = ["match_id", "market_id", "token_id"]
    for _, idx in out.groupby(group_cols).groups.items():
        sub = out.loc[idx].sort_values(["game_time_sec", "received_at_ns"])
        times = sub["game_time_sec"].to_numpy(dtype=float)
        mids = sub["book_mid"].to_numpy(dtype=float)
        bids = sub["book_best_bid"].to_numpy(dtype=float)
        for horizon in horizons:
            pos = np.searchsorted(times, times + horizon, side="left")
            valid = pos < len(sub)
            future_mid = np.full(len(sub), np.nan)
            future_bid = np.full(len(sub), np.nan)
            future_delay = np.full(len(sub), np.nan)
            valid_pos = pos[valid]
            delays = times[valid_pos] - times[valid]
            close_enough = delays <= horizon + FUTURE_PRICE_MAX_LAG_SEC
            valid_indices = np.flatnonzero(valid)[close_enough]
            valid_pos = valid_pos[close_enough]
            future_mid[valid_indices] = mids[valid_pos]
            future_bid[valid_indices] = bids[valid_pos]
            future_delay[valid_indices] = times[valid_pos] - times[valid_indices]
            out.loc[sub.index, f"future_mid_{horizon}s"] = future_mid
            out.loc[sub.index, f"future_bid_{horizon}s"] = future_bid
            out.loc[sub.index, f"future_delay_{horizon}s"] = future_delay
    return out


def clv_event_study(frame: pd.DataFrame) -> pd.DataFrame:
    priced = add_future_prices(frame[frame["tradable"]].copy())
    group_cols = ["match_id", "market_id", "token_id"]
    priced["prev_side_nw"] = priced.groupby(group_cols)["side_nw"].shift(1)
    priced["prev_total_kills"] = priced.groupby(group_cols)["total_kills"].shift(1)
    priced["prev_building_state"] = priced.groupby(group_cols)["building_state"].shift(1)
    events = {
        "side_mom_100_ge_3000": priced["side_mom_100"] >= 3000,
        "side_mom_100_ge_5000": priced["side_mom_100"] >= 5000,
        "side_nw_crosses_5000": (priced["prev_side_nw"] < 5000) & (priced["side_nw"] >= 5000),
        "side_nw_crosses_8000": (priced["prev_side_nw"] < 8000) & (priced["side_nw"] >= 8000),
        "score_changes": priced["prev_total_kills"].notna() & (priced["total_kills"] != priced["prev_total_kills"]),
        "building_state_changes": priced["prev_building_state"].notna() & (priced["building_state"] != priced["prev_building_state"]),
    }
    if "state_changed" in priced.columns:
        events["state_changed_true"] = priced["state_changed"].fillna(False).astype(bool)

    rows = []
    for event_name, mask in events.items():
        event_rows = priced[mask].copy()
        event_rows = first_trade_rows(event_rows)
        for horizon in [15, 30, 60, 120]:
            view = event_rows[event_rows[f"future_bid_{horizon}s"].notna() & event_rows[f"future_mid_{horizon}s"].notna()].copy()
            if view.empty:
                rows.append(
                    {
                        "event": event_name,
                        "horizon_s": horizon,
                        "rows": 0,
                        "matches": 0,
                        "avg_ask": np.nan,
                        "avg_clv_mid": np.nan,
                        "avg_clv_bid": np.nan,
                        "avg_future_delay_s": np.nan,
                        "positive_bid_clv_rate": np.nan,
                    }
                )
                continue
            clv_mid = view[f"future_mid_{horizon}s"] - view["book_best_ask"]
            clv_bid = view[f"future_bid_{horizon}s"] - view["book_best_ask"]
            rows.append(
                {
                    "event": event_name,
                    "horizon_s": horizon,
                    "rows": int(len(view)),
                    "matches": int(view["match_id"].nunique()),
                    "avg_ask": float(view["book_best_ask"].mean()),
                    "avg_clv_mid": float(clv_mid.mean()),
                    "avg_clv_bid": float(clv_bid.mean()),
                    "avg_future_delay_s": float(view[f"future_delay_{horizon}s"].mean()),
                    "positive_bid_clv_rate": float((clv_bid > 0).mean()),
                }
            )
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    view = df[cols].head(max_rows) if max_rows else df[cols]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float) and ("rate" in col or col == "auc"):
                vals.append(pct(val))
            elif isinstance(val, float) and ("pnl" in col or "edge" in col or "clv" in col or "minus" in col):
                vals.append(signed(val))
            elif isinstance(val, float):
                vals.append("n/a" if pd.isna(val) else f"{val:.3f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def build_report(
    frame: pd.DataFrame,
    residuals: pd.DataFrame,
    predictions: pd.DataFrame,
    trades: pd.DataFrame,
    thresholds: pd.DataFrame,
    model_metrics: pd.DataFrame,
    clv: pd.DataFrame,
    folds: list[Fold],
    split: DatasetSplit,
) -> str:
    aggregate = aggregate_model_metrics(model_metrics)
    model_summary = model_summary_table(model_metrics, trades)
    acceptance = acceptance_summary(aggregate, clv)
    by_bucket, by_match, by_league = concentration_tables(trades)
    uncertainty = trade_uncertainty_table(trades)
    fold_robustness = fold_robustness_table(model_metrics)
    calibration = residuals[residuals["table"] == "market_calibration"].copy()
    residual_top = residuals[residuals["table"] == "state_residual"].sort_values(
        ["win_rate_minus_avg_ask", "matches", "rows"], ascending=[False, False, False]
    )
    robust_residuals = residual_top[residual_top["robust_residual_bucket"]].copy() if "robust_residual_bucket" in residual_top.columns else pd.DataFrame()
    clv_60 = clv[clv["horizon_s"] == 60].sort_values(["avg_clv_bid", "matches"], ascending=[False, False])
    fold_summary = pd.DataFrame(
        [
            {
                "fold": fold.fold,
                "fit_matches": len(fold.fit_matches),
                "validation_matches": len(fold.validation_matches),
                "test_matches": len(fold.test_matches),
                "training_cutoff_match_time": fold.training_cutoff_match_time,
            }
            for fold in folds
        ]
    )
    lines = [
        "# Market Residual GetTopLive Analysis",
        "",
        "Scope: executable backtest side snapshots only. This report tests whether GetTopLive state adds residual edge after anchoring on Polymarket ask price.",
        "",
        "## Data",
        "",
        f"- Source rows: {len(frame):,}",
        f"- Tradable rows: {int(frame['tradable'].sum()):,}",
        f"- Matches: {frame['match_id'].nunique():,}",
        f"- Development matches: {len(split.development_matches):,}",
        f"- Lockbox matches: {len(split.lockbox_matches):,}",
        f"- Minimum game time: {MIN_GAME_TIME_SEC}s",
        f"- Future-price max lag for CLV: {FUTURE_PRICE_MAX_LAG_SEC}s",
        f"- Robust residual bucket gate: rows >= {ROBUST_RESIDUAL_MIN_ROWS}, matches >= {ROBUST_RESIDUAL_MIN_MATCHES}, positive residual, positive PnL",
        "",
        "## Verdict",
        "",
        f"- Settlement residual test: {'PASS' if acceptance['settlement_pass'] else 'FAIL'}",
        f"- CLV / short-horizon future-bid test: {'PASS' if acceptance['clv_pass'] else 'FAIL'}",
        f"- Walk-forward 1c slippage PnL, enhanced vs market-only: {signed(acceptance['walk_enhanced_1c'])} vs {signed(acceptance['walk_market_1c'])}",
        f"- Walk-forward 2c slippage PnL, enhanced vs market-only: {signed(acceptance['walk_enhanced_2c'])} vs {signed(acceptance['walk_market_2c'])}",
        f"- Lockbox 1c slippage PnL, enhanced vs market-only: {signed(acceptance['lock_enhanced_1c'])} vs {signed(acceptance['lock_market_1c'])}",
        f"- Lockbox 2c slippage PnL, enhanced vs market-only: {signed(acceptance['lock_enhanced_2c'])} vs {signed(acceptance['lock_market_2c'])}",
        f"- Best walk-forward ablation by 1c slippage PnL: `{acceptance['best_walk_model']}` ({signed(acceptance['best_walk_1c'])} / {signed(acceptance['best_walk_2c'])} after 1c/2c)",
        f"- Best lockbox ablation by 1c slippage PnL: `{acceptance['best_lock_model']}` ({signed(acceptance['best_lock_1c'])} / {signed(acceptance['best_lock_2c'])} after 1c/2c)",
        f"- Positive 60s future-bid CLV events with at least 3 matches: {acceptance['positive_clv_60_events']}",
        f"- Best 60s average future-bid CLV: {signed(acceptance['best_avg_clv_bid_60'])}",
        "",
        "## Market Calibration",
        "",
        markdown_table(calibration, ["ask_bucket", "rows", "matches", "avg_ask", "win_rate", "win_rate_minus_avg_ask", "avg_pnl", "total_pnl"]),
        "",
        "## Strongest Price-Bucket State Residuals",
        "",
        markdown_table(
            residual_top,
            [
                "ask_bucket",
                "state_bucket_type",
                "state_bucket",
                "rows",
                "matches",
                "avg_ask",
                "win_rate",
                "win_rate_minus_avg_ask",
                "avg_pnl",
                "robust_residual_bucket",
                "robust_gate_reason",
            ],
            max_rows=40,
        ),
        "",
        "## Robust Price-Bucket State Residuals",
        "",
        markdown_table(
            robust_residuals,
            ["ask_bucket", "state_bucket_type", "state_bucket", "rows", "matches", "avg_ask", "win_rate", "win_rate_minus_avg_ask", "avg_pnl"],
            max_rows=40,
        ),
        "",
        "## Folds",
        "",
        markdown_table(fold_summary, ["fold", "fit_matches", "validation_matches", "test_matches", "training_cutoff_match_time"]),
        "",
        "## Market-Anchored Walk-Forward Models",
        "",
        "All rows below use the same chronological folds, threshold search, first-trade dedupe, and slippage accounting. The component models are ablations of GetTopLive feature families on top of the same market-price anchor.",
        "",
        markdown_table(
            aggregate,
            [
                "stage",
                "model_name",
                "folds",
                "median_threshold",
                "pred_rows",
                "auc",
                "log_loss",
                "brier",
                "trade_trades",
                "trade_win_rate",
                "trade_avg_ask",
                "trade_avg_edge",
                "trade_total_pnl",
                "trade_total_pnl_slip_1c",
                "trade_total_pnl_slip_2c",
            ],
        ),
        "",
        "## Model Summary Verdicts",
        "",
        markdown_table(
            model_summary,
            [
                "stage",
                "model_name",
                "folds",
                "pred_rows",
                "auc",
                "trade_trades",
                "trade_win_rate",
                "trade_total_pnl_slip_1c",
                "trade_total_pnl_slip_2c",
                "folds_with_trades",
                "folds_positive_1c",
                "folds_positive_2c",
                "win_rate_ci_low",
                "win_rate_ci_high",
                "uncertainty_reason",
                "verdict",
            ],
        ),
        "",
        "## Fold Robustness",
        "",
        markdown_table(
            fold_robustness,
            [
                "model_name",
                "folds",
                "folds_with_trades",
                "folds_positive_raw",
                "folds_positive_1c",
                "folds_positive_2c",
                "total_trades",
                "total_pnl",
                "total_pnl_slip_1c",
                "total_pnl_slip_2c",
            ],
        ),
        "",
        "## Trade Win-Rate Uncertainty",
        "",
        markdown_table(
            uncertainty,
            [
                "stage",
                "model_name",
                "trades",
                "wins",
                "win_rate",
                "win_rate_ci_low",
                "win_rate_ci_high",
                "avg_ask",
                "total_pnl",
                "total_pnl_slip_1c",
                "total_pnl_slip_2c",
            ],
        ),
        "",
        "## CLV Event Study At 60s",
        "",
        markdown_table(clv_60, ["event", "rows", "matches", "avg_ask", "avg_clv_mid", "avg_clv_bid", "avg_future_delay_s", "positive_bid_clv_rate"]),
        "",
        "## Trade PnL Concentration",
        "",
        "By market bucket:",
        "",
        markdown_table(
            by_bucket,
            ["stage", "model_name", "label_market_bucket", "trades", "matches", "win_rate", "total_pnl", "total_pnl_slip_1c", "total_pnl_slip_2c"],
            max_rows=80,
        ),
        "",
        "Largest match contributions by absolute 1c-slippage PnL:",
        "",
        markdown_table(
            by_match,
            ["stage", "model_name", "match_id", "trades", "buckets", "win_rate", "total_pnl", "total_pnl_slip_1c", "total_pnl_slip_2c"],
            max_rows=80,
        ),
        "",
        "By league:",
        "",
        markdown_table(
            by_league,
            ["stage", "model_name", "league_id", "trades", "matches", "win_rate", "total_pnl", "total_pnl_slip_1c", "total_pnl_slip_2c"],
            max_rows=80,
        ),
        "",
        "## Threshold Search",
        "",
        markdown_table(
            thresholds.sort_values(["fold", "model_name", "threshold"]),
            ["stage", "fold", "model_name", "threshold", "trades", "total_pnl", "total_pnl_slip_1c", "total_pnl_slip_2c"],
            max_rows=120,
        ),
        "",
        "## Readout",
        "",
        "- Acceptance criterion: enhanced market+GetTopLive must beat market-only after 1c and 2c slippage, including lockbox.",
        "- Current readout: settlement residual passes, but CLV fails; this supports hold-to-settlement residual research, not a short-horizon scalp.",
        "- Trade ledgers dedupe to first qualifying row per `match_id` and `label_market_bucket`.",
        f"- CLV uses future executable book rows in the same match/market/token stream, within {FUTURE_PRICE_MAX_LAG_SEC}s after the target horizon; positive future bid minus current ask is the conservative short-horizon test.",
        "",
        "## Files Written",
        "",
        f"- `{REPORT_PATH}`",
        f"- `{RESIDUALS_PATH}`",
        f"- `{PREDICTIONS_PATH}`",
        f"- `{TRADES_PATH}`",
        f"- `{CLV_PATH}`",
        f"- `{SUMMARY_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = load_analysis_frame()
    residuals = pd.concat([market_calibration_table(frame), residual_bucket_tables(frame)], ignore_index=True)
    predictions, trades, thresholds, metrics, folds, split = run_market_anchor_walk_forward(frame)
    clv = clv_event_study(frame)
    summary = model_summary_table(metrics, trades)
    residuals.to_csv(RESIDUALS_PATH, index=False)
    predictions.to_csv(PREDICTIONS_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    clv.to_csv(CLV_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    REPORT_PATH.write_text(build_report(frame, residuals, predictions, trades, thresholds, metrics, clv, folds, split))
    print(f"Saved report: {REPORT_PATH}")
    print(f"Saved residuals: {RESIDUALS_PATH} ({len(residuals)} rows)")
    print(f"Saved predictions: {PREDICTIONS_PATH} ({len(predictions)} rows)")
    print(f"Saved trades: {TRADES_PATH} ({len(trades)} rows)")
    print(f"Saved CLV study: {CLV_PATH} ({len(clv)} rows)")
    print(f"Saved summary: {SUMMARY_PATH} ({len(summary)} rows)")
    print(aggregate_model_metrics(metrics).to_string(index=False))


if __name__ == "__main__":
    main()
