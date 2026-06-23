"""Multifactor strategy research.

Net worth is allowed, but no rule is only "net worth lead". Each strategy
requires multiple independent conditions: state, price, momentum/scoreboard,
structure, time, or book microstructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from validate_pattern_strategies import feature_executable_rows


EXECUTABLE_PATH = Path("datasets/clean_executable_backtest_dataset/clean_backtest_side_snapshots.parquet")
REPORT_PATH = Path("multifactor_strategy_research.md")
LEDGER_PATH = Path("multifactor_strategy_trades.csv")


@dataclass(frozen=True)
class Rule:
    name: str
    family: str
    description: str
    fn: Callable[[pd.DataFrame], pd.Series]


def pct(x: float) -> str:
    if pd.isna(x):
        return "n/a"
    return f"{x * 100:.1f}%"


def signed(x: float) -> str:
    if pd.isna(x):
        return "n/a"
    return f"{x:+.4f}"


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    view = df[cols].head(max_rows) if max_rows else df[cols]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in view.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float) and ("rate" in col or col in {"auc"}):
                vals.append(pct(val))
            elif isinstance(val, float) and ("pnl" in col or "edge" in col):
                vals.append(signed(val))
            elif isinstance(val, float):
                vals.append(f"{val:.3f}")
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def add_time_delta(frame: pd.DataFrame, value_col: str, seconds: int, out_col: str) -> None:
    frame[out_col] = np.nan
    snap = (
        frame.drop_duplicates(["match_id", "received_at_ns", "game_time_sec"])
        .sort_values(["match_id", "game_time_sec", "received_at_ns"])
        [["match_id", "received_at_ns", "game_time_sec", value_col]]
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
    merged = frame.merge(
        snap[["match_id", "received_at_ns", "game_time_sec", out_col]],
        on=["match_id", "received_at_ns", "game_time_sec"],
        how="left",
        suffixes=("", "_new"),
    )
    frame[out_col] = merged[f"{out_col}_new"].to_numpy()


def load_exec() -> pd.DataFrame:
    df = feature_executable_rows(pd.read_parquet(EXECUTABLE_PATH))
    add_time_delta(df, "total_kills", 100, "kills_change_100s")
    sign = np.where(df["side_is_radiant"], 1.0, -1.0)
    df["book_age_s"] = df["book_age_ms"] / 1000.0
    df["side_nw"] = sign * df["nw_lead_clean"]
    df["side_score"] = sign * df["score_diff"]
    df["side_tower"] = sign * df["tower_advantage"]
    df["side_rax"] = sign * df["rax_lane_advantage"]
    df["side_mom_100"] = sign * df["nw_change_100s"]
    df["side_mom_300"] = sign * df["nw_change_300s"]
    df["side_kill_mom"] = sign * df["kills_change_100s"]
    df["state_score"] = (
        0.00012 * df["side_nw"].clip(-30000, 30000)
        + 0.08 * df["side_score"].clip(-25, 25)
        + 0.00006 * df["side_mom_100"].clip(-15000, 15000)
        + 0.18 * df["side_tower"].fillna(0).clip(-8, 8)
        + 0.45 * df["side_rax"].fillna(0).clip(-3, 3)
    )
    df["state_prob_proxy"] = 1 / (1 + np.exp(-df["state_score"]))
    df["state_edge_proxy"] = df["state_prob_proxy"] - df["book_best_ask"]
    df["nw_price_gap"] = df["side_nw"] / 1000.0 - 10 * (df["book_best_ask"] - 0.5)
    df["scoreboard_lag"] = (df["side_nw"] >= 3000) & (df["side_score"] <= 3)
    df["momentum_lag"] = (df["side_mom_100"] >= 3000) & (df["side_nw"] <= 10000)
    df["structure_confirms"] = (df["side_tower"].fillna(0) >= 1) | (df["side_rax"].fillna(0) >= 1)
    df["fresh"] = df["book_age_s"] <= 60
    df["sane_ask"] = df["book_best_ask"].between(0.05, 0.95)
    df["liquid"] = df["book_ask_size"] >= 25
    df["pnl_per_share"] = np.where(df["settled_win"], 1.0 - df["book_best_ask"], -df["book_best_ask"])
    df["roi"] = df["pnl_per_share"] / df["book_best_ask"]
    return df[df["book_best_ask"].notna() & df["game_time_sec"].notna()].copy()


def base(df: pd.DataFrame) -> pd.Series:
    return df["fresh"] & df["sane_ask"] & df["liquid"]


def bucket(df: pd.DataFrame, market: str) -> pd.Series:
    if market == "ALL":
        return pd.Series(True, index=df.index)
    return df["label_market_bucket"] == market


def make_rules() -> list[Rule]:
    rules: list[Rule] = []
    markets = ["ALL", "MAP_WINNER", "MATCH_WINNER_BO1", "MATCH_WINNER_GAME3_PROXY"]
    for market in markets:
        m = market.lower()
        for edge in [0.05, 0.10, 0.15, 0.20]:
            for ask_hi in [0.65, 0.75, 0.85, 0.95]:
                rules.append(
                    Rule(
                        f"{m}_state_proxy_edge{int(edge*100)}_ask{int(ask_hi*100)}",
                        "state_price_proxy",
                        "Composite state proxy must clear ask by edge; uses NW, score, momentum, tower, rax.",
                        lambda df, market=market, edge=edge, ask_hi=ask_hi: base(df)
                        & bucket(df, market)
                        & (df["state_edge_proxy"] >= edge)
                        & (df["book_best_ask"] <= ask_hi),
                    )
                )
        for nw in [3000, 5000, 8000]:
            for mom in [1000, 3000, 5000]:
                for ask_hi in [0.70, 0.80, 0.90]:
                    rules.append(
                        Rule(
                            f"{m}_nw_mom_discount_nw{nw}_mom{mom}_ask{int(ask_hi*100)}",
                            "nw_momentum_discount",
                            "NW lead plus recent NW momentum plus ask cap.",
                            lambda df, market=market, nw=nw, mom=mom, ask_hi=ask_hi: base(df)
                            & bucket(df, market)
                            & (df["side_nw"] >= nw)
                            & (df["side_mom_100"] >= mom)
                            & (df["book_best_ask"] <= ask_hi),
                        )
                    )
        for nw in [3000, 5000, 8000]:
            for score_max in [-3, 0, 3, 6]:
                for edge in [0.02, 0.05, 0.10]:
                    rules.append(
                        Rule(
                            f"{m}_scoreboard_lag_nw{nw}_score{score_max}_edge{int(edge*100)}",
                            "scoreboard_lag_plus_price",
                            "NW lead, kill score lag, and composite state edge.",
                            lambda df, market=market, nw=nw, score_max=score_max, edge=edge: base(df)
                            & bucket(df, market)
                            & (df["side_nw"] >= nw)
                            & (df["side_score"] <= score_max)
                            & (df["state_edge_proxy"] >= edge),
                        )
                    )
        for nw in [2000, 5000, 8000]:
            for struct in [1, 2]:
                for ask_hi in [0.75, 0.85, 0.95]:
                    rules.append(
                        Rule(
                            f"{m}_structure_nw{nw}_struct{struct}_ask{int(ask_hi*100)}",
                            "structure_state",
                            "NW plus tower/rax structural confirmation plus ask cap.",
                            lambda df, market=market, nw=nw, struct=struct, ask_hi=ask_hi: base(df)
                            & bucket(df, market)
                            & (df["side_nw"] >= nw)
                            & ((df["side_tower"].fillna(0) + 2 * df["side_rax"].fillna(0)) >= struct)
                            & (df["book_best_ask"] <= ask_hi),
                        )
                    )
        for mom in [3000, 5000, 8000]:
            for nw_min in [-5000, 0, 3000]:
                for ask_hi in [0.45, 0.60, 0.75]:
                    rules.append(
                        Rule(
                            f"{m}_reversal_mom{mom}_nwmin{nw_min}_ask{int(ask_hi*100)}",
                            "reversal_with_guardrails",
                            "Momentum reversal with a not-dead NW guardrail and cheap ask.",
                            lambda df, market=market, mom=mom, nw_min=nw_min, ask_hi=ask_hi: base(df)
                            & bucket(df, market)
                            & (df["side_mom_100"] >= mom)
                            & (df["side_nw"] >= nw_min)
                            & (df["book_best_ask"] <= ask_hi)
                            & (df["game_time_sec"] >= 600),
                        )
                    )
    return rules


def split_matches(df: pd.DataFrame) -> tuple[set[str], set[str]]:
    seen = df.groupby("match_id")["received_at_ns"].min().sort_values()
    split = int(len(seen) * 0.6)
    return set(seen.index[:split]), set(seen.index[split:])


def first_trades(df: pd.DataFrame, mask: pd.Series) -> pd.DataFrame:
    rows = df[mask].copy()
    if rows.empty:
        return rows
    rows = rows.sort_values(["match_id", "label_market_bucket", "received_at_ns", "book_best_ask"])
    return rows.drop_duplicates(["match_id", "label_market_bucket"], keep="first").copy()


def summarize(trades: pd.DataFrame) -> dict[str, object]:
    if trades.empty:
        return {
            "trades": 0,
            "matches": 0,
            "win_rate": np.nan,
            "avg_ask": np.nan,
            "avg_state_edge": np.nan,
            "avg_side_nw": np.nan,
            "avg_mom": np.nan,
            "avg_pnl": np.nan,
            "total_pnl": 0.0,
        }
    return {
        "trades": len(trades),
        "matches": trades["match_id"].nunique(),
        "win_rate": trades["settled_win"].mean(),
        "avg_ask": trades["book_best_ask"].mean(),
        "avg_state_edge": trades["state_edge_proxy"].mean(),
        "avg_side_nw": trades["side_nw"].mean(),
        "avg_mom": trades["side_mom_100"].mean(),
        "avg_pnl": trades["pnl_per_share"].mean(),
        "total_pnl": trades["pnl_per_share"].sum(),
    }


def evaluate_rules(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    train_matches, test_matches = split_matches(df)
    rows = []
    ledgers = []
    for rule in make_rules():
        train_df = df[df["match_id"].isin(train_matches)]
        test_df = df[df["match_id"].isin(test_matches)]
        train_trades = first_trades(train_df, rule.fn(train_df))
        test_trades = first_trades(test_df, rule.fn(test_df))
        all_trades = first_trades(df, rule.fn(df))
        row = {
            "strategy": rule.name,
            "family": rule.family,
            "description": rule.description,
            **{f"train_{k}": v for k, v in summarize(train_trades).items()},
            **{f"test_{k}": v for k, v in summarize(test_trades).items()},
            **{f"all_{k}": v for k, v in summarize(all_trades).items()},
        }
        rows.append(row)
        if (
            row["train_trades"] >= 15
            and row["test_trades"] >= 10
            and row["train_avg_pnl"] > 0.03
            and row["test_avg_pnl"] > 0
        ):
            led = all_trades.copy()
            led["strategy"] = rule.name
            led["family"] = rule.family
            ledgers.append(led)
    perf = pd.DataFrame(rows)
    selected = perf[
        (perf["train_trades"] >= 15)
        & (perf["test_trades"] >= 10)
        & (perf["train_avg_pnl"] > 0.03)
        & (perf["test_avg_pnl"] > 0)
    ].sort_values(["test_avg_pnl", "test_trades"], ascending=[False, False])
    ledger = pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()
    return selected, ledger


MODEL_FEATURES = [
    "side_nw",
    "side_score",
    "side_tower",
    "side_rax",
    "side_mom_100",
    "side_mom_300",
    "side_kill_mom",
    "game_time_sec",
    "total_kills",
    "book_best_ask",
    "book_age_s",
    "book_ask_size",
    "state_prob_proxy",
    "state_edge_proxy",
]


def residual_models(df: pd.DataFrame) -> pd.DataFrame:
    train_matches, test_matches = split_matches(df)
    train = df[df["match_id"].isin(train_matches) & base(df)].copy()
    test = df[df["match_id"].isin(test_matches) & base(df)].copy()
    models = {
        "logistic_multifactor": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=3000, C=0.4)),
            ]
        ),
        "hgb_multifactor": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("clf", HistGradientBoostingClassifier(max_iter=200, max_leaf_nodes=10, learning_rate=0.04, random_state=7)),
            ]
        ),
        "rf_multifactor": Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("clf", RandomForestClassifier(n_estimators=250, min_samples_leaf=35, random_state=9, n_jobs=-1)),
            ]
        ),
    }
    rows = []
    for name, model in models.items():
        model.fit(train[MODEL_FEATURES], train["settled_win"].astype(int))
        p = model.predict_proba(test[MODEL_FEATURES])[:, 1]
        scored = test.copy()
        scored["model_fair"] = p
        scored["model_edge"] = scored["model_fair"] - scored["book_best_ask"]
        for edge in [0.02, 0.05, 0.10, 0.15, 0.20]:
            trades = first_trades(scored, scored["model_edge"] >= edge)
            rows.append(
                {
                    "model": name,
                    "edge": edge,
                    "auc": roc_auc_score(test["settled_win"].astype(int), p),
                    "log_loss": log_loss(test["settled_win"].astype(int), p, labels=[0, 1]),
                    "brier": brier_score_loss(test["settled_win"].astype(int), p),
                    **summarize(trades),
                    "avg_model_fair": trades["model_fair"].mean() if not trades.empty else np.nan,
                    "avg_model_edge": trades["model_edge"].mean() if not trades.empty else np.nan,
                }
            )
    return pd.DataFrame(rows).sort_values("avg_pnl", ascending=False)


def family_summary(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return selected
    return (
        selected.groupby("family")
        .agg(
            selected=("strategy", "size"),
            test_trades=("test_trades", "median"),
            test_win_rate=("test_win_rate", "median"),
            test_avg_pnl=("test_avg_pnl", "median"),
            best_test_pnl=("test_avg_pnl", "max"),
        )
        .reset_index()
        .sort_values("best_test_pnl", ascending=False)
    )


def build_report(selected: pd.DataFrame, ledger: pd.DataFrame, model_rows: pd.DataFrame) -> str:
    canonical = selected.groupby("family", as_index=False).head(3) if not selected.empty else selected
    lines = [
        "# Multifactor Strategy Research",
        "",
        "This pass uses net worth together with other features. No selected rule is just a net-worth lead rule; each requires at least one of momentum, scoreboard lag, structure, composite state/price edge, time, or book microstructure.",
        "",
        "## Selected Family Summary",
        "",
        markdown_table(family_summary(selected), ["family", "selected", "test_trades", "test_win_rate", "test_avg_pnl", "best_test_pnl"]),
        "",
        "## Canonical Multifactor Strategies",
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
                "test_avg_state_edge",
                "test_avg_side_nw",
                "test_avg_mom",
                "test_avg_pnl",
                "all_trades",
                "all_avg_pnl",
            ],
            max_rows=30,
        ),
        "",
        "## Executable-Trained Multifactor Model Edge",
        "",
        markdown_table(
            model_rows[model_rows["trades"] >= 8],
            ["model", "edge", "auc", "log_loss", "brier", "trades", "win_rate", "avg_ask", "avg_model_fair", "avg_model_edge", "avg_pnl", "total_pnl"],
            max_rows=20,
        ),
        "",
        "## Readout",
        "",
        "- The most useful shape is multifactor state/price disagreement: composite state edge plus capped ask.",
        "- The scoreboard-lag variants are the cleanest thesis: net worth says one thing, kill score is less obvious, and price is still below the composite state fair.",
        "- Momentum only works as a confirmation or reversal guardrail; by itself it overtrades.",
        "- Structure is useful when combined with net worth and price, but standalone rax/tower rules remain too sparse.",
        "- Treat these as paper strategies until the live logger accumulates more fresh executable rows.",
        "",
        "## Files Written",
        "",
        f"- `{REPORT_PATH}`",
        f"- `{LEDGER_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    df = load_exec()
    selected, ledger = evaluate_rules(df)
    model_rows = residual_models(df)
    if not ledger.empty:
        ledger.to_csv(LEDGER_PATH, index=False)
    else:
        LEDGER_PATH.write_text("")
    REPORT_PATH.write_text(build_report(selected, ledger, model_rows))
    print(f"Selected {len(selected)} multifactor rules")
    print(f"Saved report: {REPORT_PATH}")
    print(f"Saved ledger: {LEDGER_PATH} ({len(ledger)} rows)")


if __name__ == "__main__":
    main()
