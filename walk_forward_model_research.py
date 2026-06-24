"""Walk-forward model validation for executable Dota side snapshots.

This script treats hand rules as benchmarks only. The main fair-value models
use game-state features, choose entry thresholds on past validation matches,
and then score once on future match blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from dota2bot.side_features import RESEARCH_MIN_GAME_TIME_SEC, add_side_features


EXECUTABLE_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
REPORT_PATH = Path("walk_forward_model_report.md")
PREDICTIONS_PATH = Path("walk_forward_model_predictions.csv")
TRADES_PATH = Path("walk_forward_model_trades.csv")

INITIAL_TRAIN_MATCHES = 50
N_FOLDS = 5
LOCKBOX_FRACTION = 0.20
VALIDATION_FRACTION = 0.25
MIN_VALIDATION_MATCHES = 10
MIN_GAME_TIME_SEC = RESEARCH_MIN_GAME_TIME_SEC
EDGE_THRESHOLDS = [0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
RESIDUAL_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70]
MIN_THRESHOLD_TRADES = 3

NUMERIC_STATE_FEATURES = [
    "side_nw",
    "side_score",
    "side_tower",
    "side_rax",
    "side_mom_100",
    "side_mom_300",
    "side_kill_mom",
    "game_time_sec",
    "total_kills",
    "seconds_since_state_change",
]
CATEGORICAL_STATE_FEATURES = ["label_market_bucket"]
STATE_FEATURES = NUMERIC_STATE_FEATURES + CATEGORICAL_STATE_FEATURES

MARKET_FEATURES = [
    "fair_prob",
    "book_best_ask",
    "book_best_bid",
    "book_spread",
    "book_ask_size",
    "book_age_ms",
    "source_update_age_sec",
    "label_market_bucket",
]

TOP_RULES = [
    "all_structure_nw8000_struct1_ask75",
    "all_nw_mom_discount_nw8000_mom5000_ask90",
    "all_scoreboard_lag_nw3000_score6_edge10",
]


@dataclass(frozen=True)
class Fold:
    fold: int
    fit_matches: list[str]
    validation_matches: list[str]
    test_matches: list[str]
    training_cutoff_match_time: str


@dataclass(frozen=True)
class DatasetSplit:
    development_matches: list[str]
    lockbox_matches: list[str]


def pct(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value * 100:.1f}%"


def signed(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:+.4f}"


def load_model_frame(path: Path = EXECUTABLE_PATH) -> pd.DataFrame:
    frame = add_side_features(pd.read_parquet(path), min_game_time_sec=MIN_GAME_TIME_SEC)
    frame["tradable"] = frame["tradable_research"]
    frame["pnl_per_share"] = np.where(frame["settled_win"], 1.0 - frame["book_best_ask"], -frame["book_best_ask"])
    frame["pnl_slip_1c"] = np.where(frame["settled_win"], 1.0 - (frame["book_best_ask"] + 0.01), -(frame["book_best_ask"] + 0.01))
    frame["pnl_slip_2c"] = np.where(frame["settled_win"], 1.0 - (frame["book_best_ask"] + 0.02), -(frame["book_best_ask"] + 0.02))
    return frame[
        frame["settled_win"].notna()
        & frame["side_is_radiant"].notna()
        & frame["game_time_sec"].notna()
        & frame["book_best_ask"].notna()
    ].copy()


def add_time_delta(frame: pd.DataFrame, value_col: str, seconds: int, out_col: str) -> None:
    frame[out_col] = np.nan
    key_cols = ["match_id", "received_at_ns", "game_time_sec"]
    snap = (
        frame.drop_duplicates(key_cols)
        .sort_values(["match_id", "game_time_sec", "received_at_ns"])
        [key_cols + [value_col]]
        .copy()
    )
    snap[out_col] = np.nan
    for _, idx in snap.groupby("match_id").groups.items():
        sub = snap.loc[idx].sort_values(["game_time_sec", "received_at_ns"])
        times = sub["game_time_sec"].to_numpy(dtype=float)
        values = sub[value_col].to_numpy(dtype=float)
        pos = np.searchsorted(times, times - seconds, side="right") - 1
        valid = pos >= 0
        deltas = np.full(len(sub), np.nan)
        deltas[valid] = values[valid] - values[pos[valid]]
        snap.loc[sub.index, out_col] = deltas
    merged = frame.merge(snap[key_cols + [out_col]], on=key_cols, how="left", suffixes=("", "_new"))
    frame[out_col] = merged[f"{out_col}_new"].to_numpy()


def chronological_matches(frame: pd.DataFrame) -> pd.DataFrame:
    return (
        frame.groupby("match_id", as_index=False)
        .agg(first_received_at_ns=("received_at_ns", "min"), first_received_at_utc=("received_at_utc", "min"))
        .sort_values(["first_received_at_ns", "match_id"])
        .reset_index(drop=True)
    )


def make_folds(frame: pd.DataFrame, *, initial_train_matches: int = INITIAL_TRAIN_MATCHES, n_folds: int = N_FOLDS) -> list[Fold]:
    matches = chronological_matches(frame)
    if len(matches) <= initial_train_matches + 1:
        raise ValueError(f"Need more than {initial_train_matches + 1} matches for walk-forward validation")
    remaining = len(matches) - initial_train_matches
    block = max(1, remaining // n_folds)
    folds: list[Fold] = []
    for fold_idx, test_start in enumerate(range(initial_train_matches, len(matches), block), start=1):
        if len(folds) >= n_folds:
            break
        test_end = min(test_start + block, len(matches))
        train = matches.iloc[:test_start].copy()
        test = matches.iloc[test_start:test_end].copy()
        if test.empty:
            continue
        val_count = max(MIN_VALIDATION_MATCHES, int(round(len(train) * VALIDATION_FRACTION)))
        val_count = min(val_count, max(1, len(train) - 5))
        fit = train.iloc[:-val_count]
        validation = train.iloc[-val_count:]
        folds.append(
            Fold(
                fold=fold_idx,
                fit_matches=fit["match_id"].astype(str).tolist(),
                validation_matches=validation["match_id"].astype(str).tolist(),
                test_matches=test["match_id"].astype(str).tolist(),
                training_cutoff_match_time=str(train["first_received_at_utc"].iloc[-1]),
            )
        )
    return folds


def split_development_lockbox(frame: pd.DataFrame, *, lockbox_fraction: float = LOCKBOX_FRACTION) -> DatasetSplit:
    matches = chronological_matches(frame)
    lockbox_count = max(1, int(round(len(matches) * lockbox_fraction)))
    dev = matches.iloc[:-lockbox_count]
    lockbox = matches.iloc[-lockbox_count:]
    return DatasetSplit(
        development_matches=dev["match_id"].astype(str).tolist(),
        lockbox_matches=lockbox["match_id"].astype(str).tolist(),
    )


def state_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), NUMERIC_STATE_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_STATE_FEATURES),
        ],
        verbose_feature_names_out=False,
    )


def tree_state_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), NUMERIC_STATE_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_STATE_FEATURES),
        ],
        verbose_feature_names_out=False,
    )


def state_models() -> dict[str, Pipeline]:
    return {
        "logistic_fair_state": Pipeline(
            [
                ("pre", state_preprocessor()),
                ("clf", LogisticRegression(max_iter=3000, C=0.5)),
            ]
        ),
        "hgb_fair_state": Pipeline(
            [
                ("pre", tree_state_preprocessor()),
                ("clf", HistGradientBoostingClassifier(max_iter=160, max_leaf_nodes=9, learning_rate=0.04, random_state=17)),
            ]
        ),
        "rf_fair_state": Pipeline(
            [
                ("pre", tree_state_preprocessor()),
                ("clf", RandomForestClassifier(n_estimators=250, min_samples_leaf=25, random_state=23, n_jobs=-1)),
            ]
        ),
    }


def residual_model() -> Pipeline:
    return Pipeline(
        [
            (
                "pre",
                ColumnTransformer(
                    [
                        (
                            "num",
                            Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]),
                            [c for c in MARKET_FEATURES if c != "label_market_bucket"],
                        ),
                        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["label_market_bucket"]),
                    ],
                    verbose_feature_names_out=False,
                ),
            ),
            ("clf", LogisticRegression(max_iter=3000, C=0.8)),
        ]
    )


def fit_probability_calibrator(raw_prob: np.ndarray, y: pd.Series) -> IsotonicRegression | None:
    if len(np.unique(y.astype(int))) < 2 or len(y) < 20:
        return None
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_prob, y.astype(int).to_numpy())
    return calibrator


def apply_calibrator(raw_prob: np.ndarray, calibrator: IsotonicRegression | None) -> np.ndarray:
    if calibrator is None:
        return raw_prob
    return np.asarray(calibrator.predict(raw_prob), dtype=float)


def first_trade_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """Return the first qualifying row per canonical exposure.

    Canonical exposure is ``match_id + current_game_number + side`` when those
    columns exist, which collapses MAP_WINNER and MATCH_WINNER_GAME3_PROXY rows
    for the same live map/side into a single exposure (they are economically
    equivalent).  Falls back to ``match_id + label_market_bucket`` only when
    ``current_game_number`` or ``side`` is absent.
    """
    if rows.empty:
        return rows.copy()
    has_canonical = "current_game_number" in rows.columns and "side" in rows.columns
    if has_canonical:
        sort_cols = ["match_id", "current_game_number", "side", "received_at_ns", "book_best_ask"]
        dedup_cols = ["match_id", "current_game_number", "side"]
    else:
        sort_cols = ["match_id", "label_market_bucket", "received_at_ns", "book_best_ask"]
        dedup_cols = ["match_id", "label_market_bucket"]
    return (
        rows.sort_values(sort_cols)
        .drop_duplicates(dedup_cols, keep="first")
        .copy()
    )


def summarize_predictions(rows: pd.DataFrame, prob_col: str) -> dict[str, Any]:
    if rows.empty:
        return {"rows": 0, "auc": np.nan, "log_loss": np.nan, "brier": np.nan, "avg_prob": np.nan, "realized_win_rate": np.nan}
    rows = rows[rows[prob_col].notna()].copy()
    if rows.empty:
        return {"rows": 0, "auc": np.nan, "log_loss": np.nan, "brier": np.nan, "avg_prob": np.nan, "realized_win_rate": np.nan}
    y = rows["settled_win"].astype(int)
    p = rows[prob_col].clip(1e-6, 1 - 1e-6)
    auc = roc_auc_score(y, p) if y.nunique() == 2 else np.nan
    return {
        "rows": len(rows),
        "auc": auc,
        "log_loss": log_loss(y, p, labels=[0, 1]),
        "brier": brier_score_loss(y, p),
        "avg_prob": p.mean(),
        "realized_win_rate": y.mean(),
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
            "max_drawdown": 0.0,
            "avg_pnl_slip_1c": np.nan,
            "total_pnl_slip_1c": 0.0,
            "avg_pnl_slip_2c": np.nan,
            "total_pnl_slip_2c": 0.0,
        }
    ordered = trades.sort_values(["received_at_ns", "match_id", "label_market_bucket"]).copy()
    equity = ordered["pnl_per_share"].cumsum()
    peak = equity.cummax()
    drawdown = equity - peak
    return {
        "trades": len(ordered),
        "matches": ordered["match_id"].nunique(),
        "win_rate": ordered["settled_win"].mean(),
        "avg_ask": ordered["book_best_ask"].mean(),
        "avg_edge": ordered["edge"].mean() if "edge" in ordered.columns else np.nan,
        "avg_pnl": ordered["pnl_per_share"].mean(),
        "total_pnl": ordered["pnl_per_share"].sum(),
        "max_drawdown": drawdown.min(),
        "avg_pnl_slip_1c": ordered["pnl_slip_1c"].mean(),
        "total_pnl_slip_1c": ordered["pnl_slip_1c"].sum(),
        "avg_pnl_slip_2c": ordered["pnl_slip_2c"].mean(),
        "total_pnl_slip_2c": ordered["pnl_slip_2c"].sum(),
    }


def choose_edge_threshold(validation: pd.DataFrame, prob_col: str) -> tuple[float, pd.DataFrame]:
    candidates = []
    tradable = validation[validation["tradable"]].copy()
    for threshold in EDGE_THRESHOLDS:
        rows = tradable.assign(edge=tradable[prob_col] - tradable["book_best_ask"])
        trades = first_trade_rows(rows[rows["edge"] >= threshold])
        summary = summarize_trades(trades)
        candidates.append({"threshold": threshold, **summary})
    table = pd.DataFrame(candidates)
    eligible = table[table["trades"] >= MIN_THRESHOLD_TRADES].copy()
    if eligible.empty:
        return EDGE_THRESHOLDS[-1], table
    eligible = eligible.sort_values(["avg_pnl_slip_1c", "total_pnl_slip_1c", "trades"], ascending=[False, False, False])
    return float(eligible.iloc[0]["threshold"]), table


def choose_residual_threshold(validation: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    candidates = []
    tradable = validation[validation["tradable"]].copy()
    for threshold in RESIDUAL_THRESHOLDS:
        rows = tradable.assign(edge=tradable["residual_trade_prob"] - threshold)
        trades = first_trade_rows(rows[rows["residual_trade_prob"] >= threshold])
        summary = summarize_trades(trades)
        candidates.append({"threshold": threshold, **summary})
    table = pd.DataFrame(candidates)
    eligible = table[table["trades"] >= MIN_THRESHOLD_TRADES].copy()
    if eligible.empty:
        return RESIDUAL_THRESHOLDS[-1], table
    eligible = eligible.sort_values(["avg_pnl_slip_1c", "total_pnl_slip_1c", "trades"], ascending=[False, False, False])
    return float(eligible.iloc[0]["threshold"]), table


def score_rule(frame: pd.DataFrame, rule_name: str) -> pd.Series:
    if rule_name == "all_structure_nw8000_struct1_ask75":
        return (
            frame["tradable"]
            & (frame["side_nw"] >= 8000)
            & ((frame["side_tower"].fillna(0) + 2 * frame["side_rax"].fillna(0)) >= 1)
            & (frame["book_best_ask"] <= 0.75)
        )
    if rule_name == "all_nw_mom_discount_nw8000_mom5000_ask90":
        return frame["tradable"] & (frame["side_nw"] >= 8000) & (frame["side_mom_100"] >= 5000) & (frame["book_best_ask"] <= 0.90)
    if rule_name == "all_scoreboard_lag_nw3000_score6_edge10":
        return frame["tradable"] & (frame["side_nw"] >= 3000) & (frame["side_score"] <= 6) & (frame["state_edge_proxy"] >= 0.10)
    raise ValueError(f"Unknown rule benchmark: {rule_name}")


def run_walk_forward(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[Fold]]:
    folds = make_folds(frame)
    prediction_rows: list[pd.DataFrame] = []
    trade_rows: list[pd.DataFrame] = []
    threshold_rows: list[pd.DataFrame] = []
    fold_metric_rows: list[dict[str, Any]] = []

    models = state_models()
    for fold in folds:
        fit = frame[frame["match_id"].astype(str).isin(fold.fit_matches)].copy()
        validation = frame[frame["match_id"].astype(str).isin(fold.validation_matches)].copy()
        test = frame[frame["match_id"].astype(str).isin(fold.test_matches)].copy()

        for model_name, model in models.items():
            model.fit(fit[STATE_FEATURES], fit["settled_win"].astype(int))
            val_raw = model.predict_proba(validation[STATE_FEATURES])[:, 1]
            test_raw = model.predict_proba(test[STATE_FEATURES])[:, 1]
            calibrator = fit_probability_calibrator(val_raw, validation["settled_win"])
            validation_scored = validation.copy()
            test_scored = test.copy()
            validation_scored["raw_prob"] = val_raw
            validation_scored["calibrated_prob"] = apply_calibrator(val_raw, calibrator)
            test_scored["raw_prob"] = test_raw
            test_scored["calibrated_prob"] = apply_calibrator(test_raw, calibrator)

            threshold, threshold_table = choose_edge_threshold(validation_scored, "calibrated_prob")
            threshold_table["fold"] = fold.fold
            threshold_table["model_name"] = model_name
            threshold_table["threshold_type"] = "edge"
            threshold_rows.append(threshold_table)

            test_scored["fold"] = fold.fold
            test_scored["stage"] = "walk_forward"
            test_scored["model_name"] = model_name
            test_scored["model_version"] = "state_only_v1"
            test_scored["training_cutoff_match_time"] = fold.training_cutoff_match_time
            test_scored["fair_prob"] = test_scored["raw_prob"]
            test_scored["edge"] = test_scored["calibrated_prob"] - test_scored["book_best_ask"]
            test_scored["entry_threshold"] = threshold
            test_scored["signal"] = test_scored["tradable"] & (test_scored["edge"] >= threshold)
            test_scored["reason"] = np.where(test_scored["signal"], "model_edge", "below_threshold_or_not_tradable")
            prediction_rows.append(prediction_output(test_scored))

            trades = first_trade_rows(test_scored[test_scored["signal"]]).copy()
            trades["paper_entry_price"] = trades["book_best_ask"]
            trade_rows.append(trade_output(trades))
            fold_metric_rows.append(
                {
                    "fold": fold.fold,
                    "model_name": model_name,
                    "model_type": "fair_probability",
                    "selected_threshold": threshold,
                    **{f"pred_{k}": v for k, v in summarize_predictions(test_scored[test_scored["tradable"]], "calibrated_prob").items()},
                    **{f"trade_{k}": v for k, v in summarize_trades(trades).items()},
                }
            )

            if model_name == "logistic_fair_state":
                residual_fit = fit.copy()
                residual_validation = validation_scored.copy()
                residual_test = test_scored.copy()
                residual_fit_raw = model.predict_proba(residual_fit[STATE_FEATURES])[:, 1]
                residual_fit["fair_prob"] = residual_fit_raw
                residual_validation["fair_prob"] = residual_validation["calibrated_prob"]
                residual_test["fair_prob"] = residual_test["calibrated_prob"]
                residual_fit["positive_pnl"] = residual_fit["pnl_per_share"] > 0
                residual = residual_model()
                residual.fit(residual_fit[MARKET_FEATURES], residual_fit["positive_pnl"].astype(int))
                residual_validation["residual_trade_prob"] = residual.predict_proba(residual_validation[MARKET_FEATURES])[:, 1]
                residual_test["residual_trade_prob"] = residual.predict_proba(residual_test[MARKET_FEATURES])[:, 1]
                residual_threshold, residual_threshold_table = choose_residual_threshold(residual_validation)
                residual_threshold_table["fold"] = fold.fold
                residual_threshold_table["model_name"] = "logistic_residual_trade"
                residual_threshold_table["threshold_type"] = "trade_probability"
                threshold_rows.append(residual_threshold_table)

                residual_test["model_name"] = "logistic_residual_trade"
                residual_test["stage"] = "walk_forward"
                residual_test["model_version"] = "market_aware_residual_v1"
                residual_test["edge"] = residual_test["residual_trade_prob"] - residual_threshold
                residual_test["entry_threshold"] = residual_threshold
                residual_test["signal"] = residual_test["tradable"] & (residual_test["residual_trade_prob"] >= residual_threshold)
                residual_test["reason"] = np.where(residual_test["signal"], "residual_trade_prob", "below_threshold_or_not_tradable")
                prediction_rows.append(prediction_output(residual_test, residual=True))
                residual_trades = first_trade_rows(residual_test[residual_test["signal"]]).copy()
                residual_trades["paper_entry_price"] = residual_trades["book_best_ask"]
                trade_rows.append(trade_output(residual_trades))
                fold_metric_rows.append(
                    {
                        "fold": fold.fold,
                        "model_name": "logistic_residual_trade",
                        "model_type": "market_aware_residual",
                        "selected_threshold": residual_threshold,
                        **{f"pred_{k}": v for k, v in summarize_predictions(residual_test[residual_test["tradable"]], "calibrated_prob").items()},
                        **{f"trade_{k}": v for k, v in summarize_trades(residual_trades).items()},
                    }
                )

        for rule_name in TOP_RULES:
            rule_test = test.copy()
            rule_test["fold"] = fold.fold
            rule_test["stage"] = "walk_forward"
            rule_test["model_name"] = rule_name
            rule_test["model_version"] = "hand_rule_benchmark_v1"
            rule_test["training_cutoff_match_time"] = fold.training_cutoff_match_time
            rule_test["fair_prob"] = rule_test["state_prob_proxy"]
            rule_test["calibrated_prob"] = rule_test["state_prob_proxy"]
            rule_test["edge"] = rule_test["state_edge_proxy"]
            rule_test["entry_threshold"] = np.nan
            rule_test["signal"] = score_rule(rule_test, rule_name)
            rule_test["reason"] = np.where(rule_test["signal"], "hand_rule", "rule_false")
            trades = first_trade_rows(rule_test[rule_test["signal"]]).copy()
            trades["paper_entry_price"] = trades["book_best_ask"]
            trade_rows.append(trade_output(trades))
            fold_metric_rows.append(
                {
                    "fold": fold.fold,
                    "model_name": rule_name,
                    "model_type": "hand_rule_benchmark",
                    "selected_threshold": np.nan,
                    **{f"pred_{k}": v for k, v in summarize_predictions(rule_test[rule_test["tradable"]], "calibrated_prob").items()},
                    **{f"trade_{k}": v for k, v in summarize_trades(trades).items()},
                }
            )

    predictions = pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame()
    trades = pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame()
    thresholds = pd.concat(threshold_rows, ignore_index=True) if threshold_rows else pd.DataFrame()
    fold_metrics = pd.DataFrame(fold_metric_rows)
    return predictions, trades, thresholds, fold_metrics, folds


def select_lockbox_candidate(fold_metrics: pd.DataFrame) -> str:
    aggregate = aggregate_metrics(fold_metrics)
    eligible = aggregate[aggregate["trades"] >= MIN_THRESHOLD_TRADES].copy()
    if eligible.empty:
        raise ValueError("No walk-forward candidate produced enough trades for lockbox selection")
    eligible = eligible.sort_values(["total_pnl_slip_1c", "total_pnl", "trades"], ascending=[False, False, False])
    return str(eligible.iloc[0]["model_name"])


def run_lockbox_check(frame: pd.DataFrame, split: DatasetSplit, model_name: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dev = frame[frame["match_id"].astype(str).isin(split.development_matches)].copy()
    lockbox = frame[frame["match_id"].astype(str).isin(split.lockbox_matches)].copy()
    dev_matches = chronological_matches(dev)
    val_count = max(MIN_VALIDATION_MATCHES, int(round(len(dev_matches) * VALIDATION_FRACTION)))
    val_count = min(val_count, max(1, len(dev_matches) - 5))
    fit_matches = dev_matches.iloc[:-val_count]["match_id"].astype(str).tolist()
    validation_matches = dev_matches.iloc[-val_count:]["match_id"].astype(str).tolist()
    fit = dev[dev["match_id"].astype(str).isin(fit_matches)].copy()
    validation = dev[dev["match_id"].astype(str).isin(validation_matches)].copy()
    training_cutoff = str(dev_matches["first_received_at_utc"].iloc[-1])

    if model_name in TOP_RULES:
        scored = lockbox.copy()
        scored["stage"] = "lockbox"
        scored["fold"] = 0
        scored["model_name"] = model_name
        scored["model_version"] = "hand_rule_benchmark_v1"
        scored["training_cutoff_match_time"] = training_cutoff
        scored["fair_prob"] = scored["state_prob_proxy"]
        scored["calibrated_prob"] = scored["state_prob_proxy"]
        scored["edge"] = scored["state_edge_proxy"]
        scored["entry_threshold"] = np.nan
        scored["signal"] = score_rule(scored, model_name)
        scored["reason"] = np.where(scored["signal"], "hand_rule_lockbox", "rule_false")
        lockbox_trades = first_trade_rows(scored[scored["signal"]]).copy()
        lockbox_trades["paper_entry_price"] = lockbox_trades["book_best_ask"]
        metrics = pd.DataFrame(
            [
                {
                    "fold": 0,
                    "model_name": model_name,
                    "model_type": "lockbox_selected",
                    "selected_threshold": np.nan,
                    **{f"pred_{k}": v for k, v in summarize_predictions(scored[scored["tradable"]], "calibrated_prob").items()},
                    **{f"trade_{k}": v for k, v in summarize_trades(lockbox_trades).items()},
                }
            ]
        )
        return prediction_output(scored), trade_output(lockbox_trades), pd.DataFrame(), metrics

    if model_name == "logistic_residual_trade":
        fair_model = state_models()["logistic_fair_state"]
        fair_model.fit(fit[STATE_FEATURES], fit["settled_win"].astype(int))
        val_raw = fair_model.predict_proba(validation[STATE_FEATURES])[:, 1]
        calibrator = fit_probability_calibrator(val_raw, validation["settled_win"])
        validation_scored = validation.copy()
        lockbox_scored = lockbox.copy()
        validation_scored["fair_prob"] = apply_calibrator(val_raw, calibrator)
        lockbox_scored["fair_prob"] = apply_calibrator(fair_model.predict_proba(lockbox[STATE_FEATURES])[:, 1], calibrator)
        residual_fit = fit.copy()
        residual_fit["fair_prob"] = fair_model.predict_proba(fit[STATE_FEATURES])[:, 1]
        residual_fit["positive_pnl"] = residual_fit["pnl_per_share"] > 0
        residual = residual_model()
        residual.fit(residual_fit[MARKET_FEATURES], residual_fit["positive_pnl"].astype(int))
        validation_scored["residual_trade_prob"] = residual.predict_proba(validation_scored[MARKET_FEATURES])[:, 1]
        lockbox_scored["residual_trade_prob"] = residual.predict_proba(lockbox_scored[MARKET_FEATURES])[:, 1]
        threshold, threshold_table = choose_residual_threshold(validation_scored)
        threshold_table["fold"] = 0
        threshold_table["model_name"] = model_name
        threshold_table["threshold_type"] = "trade_probability_lockbox"
        lockbox_scored["stage"] = "lockbox"
        lockbox_scored["fold"] = 0
        lockbox_scored["model_name"] = model_name
        lockbox_scored["model_version"] = "market_aware_residual_v1"
        lockbox_scored["training_cutoff_match_time"] = training_cutoff
        lockbox_scored["calibrated_prob"] = lockbox_scored["fair_prob"]
        lockbox_scored["edge"] = lockbox_scored["residual_trade_prob"] - threshold
        lockbox_scored["entry_threshold"] = threshold
        lockbox_scored["signal"] = lockbox_scored["tradable"] & (lockbox_scored["residual_trade_prob"] >= threshold)
        lockbox_scored["reason"] = np.where(lockbox_scored["signal"], "residual_trade_prob_lockbox", "below_threshold_or_not_tradable")
        lockbox_trades = first_trade_rows(lockbox_scored[lockbox_scored["signal"]]).copy()
        lockbox_trades["paper_entry_price"] = lockbox_trades["book_best_ask"]
        metrics = pd.DataFrame(
            [
                {
                    "fold": 0,
                    "model_name": model_name,
                    "model_type": "lockbox_selected",
                    "selected_threshold": threshold,
                    **{f"pred_{k}": v for k, v in summarize_predictions(lockbox_scored[lockbox_scored["tradable"]], "calibrated_prob").items()},
                    **{f"trade_{k}": v for k, v in summarize_trades(lockbox_trades).items()},
                }
            ]
        )
        return prediction_output(lockbox_scored, residual=True), trade_output(lockbox_trades), threshold_table, metrics

    model = state_models()[model_name]
    model.fit(fit[STATE_FEATURES], fit["settled_win"].astype(int))
    val_raw = model.predict_proba(validation[STATE_FEATURES])[:, 1]
    calibrator = fit_probability_calibrator(val_raw, validation["settled_win"])
    validation_scored = validation.copy()
    lockbox_scored = lockbox.copy()
    validation_scored["calibrated_prob"] = apply_calibrator(val_raw, calibrator)
    validation_scored["raw_prob"] = val_raw
    lockbox_raw = model.predict_proba(lockbox[STATE_FEATURES])[:, 1]
    lockbox_scored["raw_prob"] = lockbox_raw
    lockbox_scored["calibrated_prob"] = apply_calibrator(lockbox_raw, calibrator)
    threshold, threshold_table = choose_edge_threshold(validation_scored, "calibrated_prob")
    threshold_table["fold"] = 0
    threshold_table["model_name"] = model_name
    threshold_table["threshold_type"] = "edge_lockbox"
    lockbox_scored["stage"] = "lockbox"
    lockbox_scored["fold"] = 0
    lockbox_scored["model_name"] = model_name
    lockbox_scored["model_version"] = "state_only_v1"
    lockbox_scored["training_cutoff_match_time"] = training_cutoff
    lockbox_scored["fair_prob"] = lockbox_scored["raw_prob"]
    lockbox_scored["edge"] = lockbox_scored["calibrated_prob"] - lockbox_scored["book_best_ask"]
    lockbox_scored["entry_threshold"] = threshold
    lockbox_scored["signal"] = lockbox_scored["tradable"] & (lockbox_scored["edge"] >= threshold)
    lockbox_scored["reason"] = np.where(lockbox_scored["signal"], "model_edge_lockbox", "below_threshold_or_not_tradable")
    lockbox_trades = first_trade_rows(lockbox_scored[lockbox_scored["signal"]]).copy()
    lockbox_trades["paper_entry_price"] = lockbox_trades["book_best_ask"]
    metrics = pd.DataFrame(
        [
            {
                "fold": 0,
                "model_name": model_name,
                "model_type": "lockbox_selected",
                "selected_threshold": threshold,
                **{f"pred_{k}": v for k, v in summarize_predictions(lockbox_scored[lockbox_scored["tradable"]], "calibrated_prob").items()},
                **{f"trade_{k}": v for k, v in summarize_trades(lockbox_trades).items()},
            }
        ]
    )
    return prediction_output(lockbox_scored), trade_output(lockbox_trades), threshold_table, metrics


def prediction_output(frame: pd.DataFrame, *, residual: bool = False) -> pd.DataFrame:
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
        "book_best_ask",
        "book_best_bid",
        "book_spread",
        "book_ask_size",
        "fair_prob",
        "calibrated_prob",
        "edge",
        "entry_threshold",
        "signal",
        "tradable",
        "reason",
        "side_nw",
        "side_score",
        "side_tower",
        "side_rax",
        "side_mom_100",
        "side_mom_300",
        "state_prob_proxy",
        "state_edge_proxy",
    ]
    out = frame.copy()
    if residual:
        out["calibrated_prob"] = out["fair_prob"]
        cols.insert(cols.index("edge"), "residual_trade_prob")
    return out[[c for c in cols if c in out.columns]]


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
        "fair_prob",
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
        "side_score",
        "side_tower",
        "side_rax",
        "side_mom_100",
        "reason",
    ]
    if frame.empty:
        return pd.DataFrame(columns=cols)
    return frame[[c for c in cols if c in frame.columns]].copy()


def aggregate_metrics(fold_metrics: pd.DataFrame) -> pd.DataFrame:
    if fold_metrics.empty:
        return fold_metrics
    return (
        fold_metrics.groupby(["model_name", "model_type"], as_index=False)
        .agg(
            folds=("fold", "nunique"),
            median_threshold=("selected_threshold", "median"),
            pred_rows=("pred_rows", "sum"),
            auc=("pred_auc", "mean"),
            log_loss=("pred_log_loss", "mean"),
            brier=("pred_brier", "mean"),
            avg_prob=("pred_avg_prob", "mean"),
            realized_win_rate=("pred_realized_win_rate", "mean"),
            trades=("trade_trades", "sum"),
            win_rate=("trade_win_rate", "mean"),
            avg_ask=("trade_avg_ask", "mean"),
            avg_edge=("trade_avg_edge", "mean"),
            avg_pnl=("trade_avg_pnl", "mean"),
            total_pnl=("trade_total_pnl", "sum"),
            max_drawdown=("trade_max_drawdown", "min"),
            avg_pnl_slip_1c=("trade_avg_pnl_slip_1c", "mean"),
            total_pnl_slip_1c=("trade_total_pnl_slip_1c", "sum"),
            avg_pnl_slip_2c=("trade_avg_pnl_slip_2c", "mean"),
            total_pnl_slip_2c=("trade_total_pnl_slip_2c", "sum"),
        )
        .sort_values(["total_pnl_slip_1c", "total_pnl"], ascending=[False, False])
    )


def calibration_table(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for model_name, sub in predictions.groupby("model_name"):
        if sub.empty or "calibrated_prob" not in sub:
            continue
        view = sub[sub["tradable"]].copy() if "tradable" in sub.columns else sub.copy()
        if view.empty:
            continue
        view["prob_bucket"] = pd.cut(view["calibrated_prob"], bins=np.linspace(0, 1, 6), include_lowest=True)
        for bucket, b in view.groupby("prob_bucket", observed=False):
            if b.empty:
                continue
            rows.append(
                {
                    "model_name": model_name,
                    "prob_bucket": str(bucket),
                    "rows": len(b),
                    "avg_prob": b["calibrated_prob"].mean(),
                    "realized_win_rate": b["settled_win"].mean(),
                }
            )
    return pd.DataFrame(rows)


def benchmark_market_and_proxy(frame: pd.DataFrame) -> pd.DataFrame:
    tradable = frame[frame["tradable"]].copy()
    rows = []
    for name, prob_col in [("market_baseline_ask", "book_best_ask"), ("hand_composite_proxy", "state_prob_proxy")]:
        pred = summarize_predictions(tradable, prob_col)
        rows.append({"model_name": name, "model_type": "benchmark_probability", **{f"pred_{k}": v for k, v in pred.items()}})
    return pd.DataFrame(rows)


def game_time_sensitivity(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for min_game_time_sec in [0, 300, 600, 900]:
        view = frame.copy()
        view["tradable"] = (
            view["book_best_ask"].between(0.05, 0.95)
            & view["book_best_bid"].notna()
            & (view["book_age_ms"] <= 60_000)
            & (view["book_ask_size"] >= 25)
            & (view["game_time_sec"] >= min_game_time_sec)
        )
        row: dict[str, Any] = {
            "min_game_time_sec": min_game_time_sec,
            "tradable_rows": int(view["tradable"].sum()),
            "tradable_matches": int(view.loc[view["tradable"], "match_id"].nunique()),
        }
        for rule_name in TOP_RULES:
            trades = first_trade_rows(view[score_rule(view, rule_name)]).copy()
            summary = summarize_trades(trades)
            prefix = rule_name.replace("all_", "")
            row[f"{prefix}_trades"] = summary["trades"]
            row[f"{prefix}_total_pnl_slip_1c"] = summary["total_pnl_slip_1c"]
        rows.append(row)
    return pd.DataFrame(rows)


def concentration_tables(trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if trades.empty:
        empty = pd.DataFrame()
        return empty, empty, empty
    by_bucket = (
        trades.groupby(["model_name", "label_market_bucket"], as_index=False)
        .agg(
            trades=("match_id", "size"),
            matches=("match_id", "nunique"),
            win_rate=("settled_win", "mean"),
            total_pnl=("pnl_per_share", "sum"),
            total_pnl_slip_1c=("pnl_slip_1c", "sum"),
            total_pnl_slip_2c=("pnl_slip_2c", "sum"),
        )
        .sort_values(["model_name", "total_pnl_slip_1c"], ascending=[True, False])
    )
    by_match = (
        trades.groupby(["model_name", "match_id"], as_index=False)
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
    by_match = by_match.sort_values(["model_name", "abs_total_pnl_slip_1c"], ascending=[True, False]).drop(
        columns=["abs_total_pnl_slip_1c"]
    )
    if "league_id" in trades.columns:
        by_league = (
            trades.groupby(["model_name", "league_id"], dropna=False, as_index=False)
            .agg(
                trades=("match_id", "size"),
                matches=("match_id", "nunique"),
                win_rate=("settled_win", "mean"),
                total_pnl=("pnl_per_share", "sum"),
                total_pnl_slip_1c=("pnl_slip_1c", "sum"),
                total_pnl_slip_2c=("pnl_slip_2c", "sum"),
            )
            .sort_values(["model_name", "total_pnl_slip_1c"], ascending=[True, False])
        )
    else:
        by_league = pd.DataFrame()
    return by_bucket, by_match, by_league


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
            elif isinstance(val, float) and ("pnl" in col or "edge" in col or "drawdown" in col):
                vals.append(signed(val))
            elif isinstance(val, float):
                vals.append(f"{val:.3f}" if not pd.isna(val) else "n/a")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def build_report(
    frame: pd.DataFrame,
    predictions: pd.DataFrame,
    trades: pd.DataFrame,
    thresholds: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    folds: list[Fold],
    split: DatasetSplit,
    selected_lockbox_candidate: str,
    lockbox_metrics: pd.DataFrame,
) -> str:
    aggregate = aggregate_metrics(fold_metrics)
    calibration = calibration_table(predictions)
    benchmarks = benchmark_market_and_proxy(frame)
    sensitivity = game_time_sensitivity(frame)
    by_bucket, by_match, by_league = concentration_tables(trades)
    fold_summary = pd.DataFrame(
        [
            {
                "fold": f.fold,
                "fit_matches": len(f.fit_matches),
                "validation_matches": len(f.validation_matches),
                "test_matches": len(f.test_matches),
                "training_cutoff_match_time": f.training_cutoff_match_time,
            }
            for f in folds
        ]
    )
    lines = [
        "# Walk-Forward Model Research",
        "",
        "Method: train only on past matches, choose entry thresholds on past validation matches, then score the next future match block once. Trade ledgers dedupe to first qualifying row per `match_id` and `label_market_bucket`.",
        "",
        "## Data Audit",
        "",
        f"- Source rows: {len(frame):,}",
        f"- Matches: {frame['match_id'].nunique():,}",
        f"- Development matches: {len(split.development_matches):,}",
        f"- Lockbox matches: {len(split.lockbox_matches):,}",
        f"- Markets: {frame['market_id'].nunique():,}",
        f"- Tradable rows: {int(frame['tradable'].sum()):,}",
        f"- Minimum game time for tradable rows: {MIN_GAME_TIME_SEC}s",
        f"- Rows with tower state: {int(frame['tower_state'].notna().sum()):,}",
        f"- Rows with building state: {int(frame['building_state'].notna().sum()):,}",
        f"- First timestamp: {frame['received_at_utc'].min()}",
        f"- Last timestamp: {frame['received_at_utc'].max()}",
        "",
        "## Folds",
        "",
        markdown_table(fold_summary, ["fold", "fit_matches", "validation_matches", "test_matches", "training_cutoff_match_time"]),
        "",
        "## Probability Benchmarks",
        "",
        markdown_table(
            benchmarks,
            ["model_name", "model_type", "pred_rows", "pred_auc", "pred_log_loss", "pred_brier", "pred_avg_prob", "pred_realized_win_rate"],
        ),
        "",
        "Note: hand-rule benchmark AUC/log-loss/Brier use the shared composite `state_prob_proxy`; they are heuristic diagnostics, not calibrated rule probabilities. Trade metrics are the relevant hand-rule measure.",
        "",
        "## Game-Time Sensitivity",
        "",
        markdown_table(sensitivity, list(sensitivity.columns)),
        "",
        "## Walk-Forward Comparison",
        "",
        markdown_table(
            aggregate,
            [
                "model_name",
                "model_type",
                "folds",
                "median_threshold",
                "auc",
                "log_loss",
                "brier",
                "trades",
                "win_rate",
                "avg_ask",
                "avg_edge",
                "avg_pnl",
                "total_pnl",
                "max_drawdown",
                "avg_pnl_slip_1c",
                "total_pnl_slip_1c",
                "avg_pnl_slip_2c",
                "total_pnl_slip_2c",
            ],
        ),
        "",
        "## Fold Metrics",
        "",
        markdown_table(
            fold_metrics.sort_values(["fold", "model_name"]),
            [
                "fold",
                "model_name",
                "model_type",
                "selected_threshold",
                "pred_auc",
                "pred_log_loss",
                "pred_brier",
                "trade_trades",
                "trade_win_rate",
                "trade_avg_ask",
                "trade_avg_edge",
                "trade_avg_pnl",
                "trade_total_pnl",
                "trade_total_pnl_slip_1c",
                "trade_total_pnl_slip_2c",
            ],
            max_rows=80,
        ),
        "",
        "## Final Lockbox Check",
        "",
        f"Selected from walk-forward by 1c-slippage PnL: `{selected_lockbox_candidate}`.",
        "",
        markdown_table(
            lockbox_metrics,
            [
                "model_name",
                "model_type",
                "selected_threshold",
                "pred_rows",
                "pred_auc",
                "pred_log_loss",
                "pred_brier",
                "trade_trades",
                "trade_win_rate",
                "trade_avg_ask",
                "trade_avg_edge",
                "trade_avg_pnl",
                "trade_total_pnl",
                "trade_total_pnl_slip_1c",
                "trade_total_pnl_slip_2c",
            ],
        ),
        "",
        "## Calibration By Probability Bucket",
        "",
        markdown_table(calibration, ["model_name", "prob_bucket", "rows", "avg_prob", "realized_win_rate"], max_rows=80),
        "",
        "## PnL Concentration",
        "",
        "By market bucket:",
        "",
        markdown_table(
            by_bucket,
            ["model_name", "label_market_bucket", "trades", "matches", "win_rate", "total_pnl", "total_pnl_slip_1c", "total_pnl_slip_2c"],
            max_rows=80,
        ),
        "",
        "Largest match contributions by absolute 1c-slippage PnL:",
        "",
        markdown_table(
            by_match,
            ["model_name", "match_id", "trades", "buckets", "win_rate", "total_pnl", "total_pnl_slip_1c", "total_pnl_slip_2c"],
            max_rows=80,
        ),
        "",
        "By league:",
        "",
        markdown_table(
            by_league,
            ["model_name", "league_id", "trades", "matches", "win_rate", "total_pnl", "total_pnl_slip_1c", "total_pnl_slip_2c"],
            max_rows=80,
        ),
        "",
        "## Threshold Search",
        "",
        markdown_table(
            thresholds.sort_values(["fold", "model_name", "threshold"]),
            ["fold", "model_name", "threshold_type", "threshold", "trades", "avg_pnl", "total_pnl", "avg_pnl_slip_1c", "total_pnl_slip_1c"],
            max_rows=100,
        ),
        "",
        "## Readout",
        "",
        "- These are walk-forward research results, not deployment approval.",
        "- Fair-probability models use state features only; ask/spread/liquidity are used only for edge conversion and the residual trade benchmark.",
        f"- Tradability now requires `game_time_sec >= {MIN_GAME_TIME_SEC}` so pregame and countdown rows cannot generate trades.",
        "- Thresholds are selected on past validation matches inside each fold, then applied once to future matches.",
        "- If no model or hand rule stays positive after 1c and 2c slippage, do not trade it.",
        "",
        "## Files Written",
        "",
        f"- `{REPORT_PATH}`",
        f"- `{PREDICTIONS_PATH}`",
        f"- `{TRADES_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = load_model_frame()
    split = split_development_lockbox(frame)
    development = frame[frame["match_id"].astype(str).isin(split.development_matches)].copy()
    predictions, trades, thresholds, fold_metrics, folds = run_walk_forward(development)
    selected_lockbox_candidate = select_lockbox_candidate(fold_metrics)
    lockbox_predictions, lockbox_trades, lockbox_thresholds, lockbox_metrics = run_lockbox_check(frame, split, selected_lockbox_candidate)
    if not lockbox_predictions.empty:
        predictions = pd.concat([predictions, lockbox_predictions], ignore_index=True)
    if not lockbox_trades.empty:
        trades = pd.concat([trades, lockbox_trades], ignore_index=True)
    if not lockbox_thresholds.empty:
        thresholds = pd.concat([thresholds, lockbox_thresholds], ignore_index=True)
    predictions.to_csv(PREDICTIONS_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    REPORT_PATH.write_text(
        build_report(
            frame,
            predictions,
            trades,
            thresholds,
            fold_metrics,
            folds,
            split,
            selected_lockbox_candidate,
            lockbox_metrics,
        )
    )
    print(f"Saved report: {REPORT_PATH}")
    print(f"Saved predictions: {PREDICTIONS_PATH} ({len(predictions)} rows)")
    print(f"Saved trades: {TRADES_PATH} ({len(trades)} rows)")
    print(f"Selected lockbox candidate: {selected_lockbox_candidate}")
    print("Lockbox:")
    print(lockbox_metrics.to_string(index=False))
    print(aggregate_metrics(fold_metrics).to_string(index=False))


if __name__ == "__main__":
    main()
