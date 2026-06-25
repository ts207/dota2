"""Executable EV-filter model contract for paper validation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .strategy_contract import ACTIVE_MARKET_EQUIVALENT_SCOPES


SLIPPAGE_2C = 0.02

NUMERIC_FEATURES = [
    "logit_market_price",
    "book_spread",
    "book_ask_size_log",
    "book_age_s",
    "game_time_sec",
    "book_best_ask",
    "book_best_bid",
    "side_nw",
    "side_score",
    "side_mom_100",
    "side_mom_300",
    "side_kill_mom",
    "side_tower",
    "side_rax",
    "structure_score",
    "total_kills",
]
CATEGORICAL_FEATURES = ["market_scope", "current_game_number"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def value_logistic_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [
            (
                "num",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUMERIC_FEATURES,
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=3000, C=0.5))])


def executable_value_training_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Filter prepared feature rows to the historical executable universe."""
    out = frame.copy()
    for col in FEATURES:
        if col not in out.columns:
            out[col] = np.nan
    ask = pd.to_numeric(out["book_best_ask"], errors="coerce")
    win = out["settled_win"].fillna(False).astype(bool)
    out["pnl_2c"] = np.where(win, 1.0 - (ask + SLIPPAGE_2C), -(ask + SLIPPAGE_2C))
    eligible = (
        out["settled_win"].notna()
        & out["tradable_research"].fillna(False).astype(bool)
        & out["market_scope"].isin(ACTIVE_MARKET_EQUIVALENT_SCOPES)
    )
    return out[eligible].copy()


def train_winprob_logistic_evfilter_model(frame: pd.DataFrame) -> tuple[Pipeline, list[str]]:
    train = executable_value_training_frame(frame)
    if train.empty:
        raise ValueError("no rows available to train winprob_logistic_evfilter")
    model = value_logistic_pipeline()
    model.fit(train[FEATURES], train["settled_win"].astype(bool).astype(int))
    return model, list(FEATURES)
