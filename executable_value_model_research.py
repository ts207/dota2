"""Executable map-equivalent value-model research.

This script uses the historical executable research definition:
- clean nearest-prior book rows that pass tradable_research
- map-equivalent markets only
- one trade per match/map
- no opposite-side re-entry
- 2c slippage accounting
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from dota2bot.paper_strategy_logger import EXECUTABLE_BACKTEST_PATH, prepare_paper_feature_frame


LIVE_SETTLED_PATH = Path("logs/live_settled_side_snapshots/latest.parquet")
SUMMARY_PATH = Path("executable_value_model_summary.csv")
TRADES_PATH = Path("executable_value_model_trades.csv")
LOCKBOX_PATH = Path("executable_value_model_lockbox.csv")
INVENTORY_PATH = Path("executable_value_model_inventory.csv")
REPORT_PATH = Path("executable_value_model_report.md")
MAP_EQUIVALENT_SCOPES = {"map_winner_explicit", "series_decider_equivalent"}
SLIPPAGE = 0.02
MIN_TRAIN_MATCHES = 20
LOCKBOX_FRACTION = 0.20
MIN_SELECTION_FOLDS = 4
MIN_SELECTION_TRADES = 15

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
PROB_THRESHOLDS = [0.48, 0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65]
VALUE_THRESHOLDS = [-0.02, 0.00, 0.02, 0.04, 0.06, 0.08, 0.10]
ASK_FILTERS = {
    "ask_15_70": (0.15, 0.70),
    "ask_20_50": (0.20, 0.50),
    "ask_20_60": (0.20, 0.60),
    "ask_25_55": (0.25, 0.55),
}


@dataclass(frozen=True)
class ModelSpec:
    name: str
    model: Pipeline
    score_kind: str


@dataclass(frozen=True)
class Candidate:
    model_name: str
    score_kind: str
    ask_filter: str
    threshold: float


def main() -> None:
    frame, inventory = load_frame()
    dev_frame, lockbox_frame = split_dev_lockbox(frame)
    results, trades = run_walk_forward(dev_frame)
    selected = select_candidate(results)
    lockbox = run_lockbox_grid(dev_frame, lockbox_frame, results)
    promoted = select_promotion_candidate(results, lockbox)
    results.to_csv(SUMMARY_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    lockbox.to_csv(LOCKBOX_PATH, index=False)
    inventory.to_csv(INVENTORY_PATH, index=False)
    REPORT_PATH.write_text(
        format_report(results, lockbox, selected, promoted, inventory, frame, dev_frame, lockbox_frame),
        encoding="utf-8",
    )
    print(f"Saved summary: {SUMMARY_PATH} ({len(results)} rows)")
    print(f"Saved trades: {TRADES_PATH} ({len(trades)} rows)")
    print(f"Saved lockbox: {LOCKBOX_PATH} ({len(lockbox)} rows)")
    print(f"Saved inventory: {INVENTORY_PATH} ({len(inventory)} rows)")
    print(f"Saved report: {REPORT_PATH}")
    print(results.sort_values("pnl_2c", ascending=False).head(20).to_string(index=False))
    if selected is not None:
        print("Selected candidate:", selected)
        if not lockbox.empty:
            print(lockbox.to_string(index=False))
    if promoted is None:
        print("Promotion verdict: no retrained candidate passed development plus lockbox criteria.")
    else:
        print("Promotion candidate:", promoted)


def load_frame() -> tuple[pd.DataFrame, pd.DataFrame]:
    clean = pd.read_parquet(EXECUTABLE_BACKTEST_PATH)
    clean["_research_source"] = "clean_artifact"
    frames = [clean]
    if LIVE_SETTLED_PATH.exists():
        live = pd.read_parquet(LIVE_SETTLED_PATH)
        live["_research_source"] = "live_settled"
        frames.append(live)
    raw = pd.concat(frames, ignore_index=True, sort=False)
    identity = [col for col in ["match_id", "market_id", "token_id", "received_at_ns"] if col in raw.columns]
    inventory_rows = [
        inventory_row("raw_clean_artifact", clean),
        inventory_row("raw_live_settled", frames[1] if len(frames) > 1 else pd.DataFrame()),
        inventory_row("raw_combined", raw),
    ]
    if identity:
        raw = raw.drop_duplicates(identity, keep="first")
    inventory_rows.append(inventory_row("dedup_identity_combined", raw))

    frame = prepare_paper_feature_frame(raw)
    frame["_research_source"] = raw["_research_source"].to_numpy() if "_research_source" in raw.columns else "unknown"
    frame = add_map_exposure_id(frame)
    inventory_rows.extend(inventory_rows_for_feature_frame(frame))
    historical_executable = (
        frame["settled_win"].notna()
        & frame["tradable_research"].fillna(False).astype(bool)
        & frame["market_scope"].isin(MAP_EQUIVALENT_SCOPES)
    )
    frame = frame[
        historical_executable
    ].copy()
    for col in FEATURES:
        if col not in frame.columns:
            frame[col] = np.nan
    ask = pd.to_numeric(frame["book_best_ask"], errors="coerce")
    win = frame["settled_win"].fillna(False).astype(bool)
    frame["pnl_2c"] = np.where(win, 1.0 - (ask + SLIPPAGE), -(ask + SLIPPAGE))
    frame["profitable_after_2c"] = frame["pnl_2c"] > 0
    frame["value_after_2c"] = frame["settled_win"].astype(int) - ask - SLIPPAGE
    frame["match_sort_time"] = pd.to_datetime(frame["received_at_utc"], errors="coerce", utc=True)
    return frame.sort_values(["match_sort_time", "received_at_ns"]).reset_index(drop=True), pd.DataFrame(inventory_rows)


def inventory_row(step: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"step": step, "rows": 0, "matches": 0, "map_exposures": 0}
    out = frame.copy()
    if "current_game_number" in out.columns:
        game = out["current_game_number"].astype("string").fillna("").str.strip()
        game = game.mask(game.eq("") | game.str.lower().isin(["nan", "none", "<na>"]), "MAPEQUIV")
        map_exposure = out["match_id"].astype(str) + "::" + game.astype(str)
    else:
        map_exposure = out["match_id"].astype(str)
    return {
        "step": step,
        "rows": int(len(out)),
        "matches": int(out["match_id"].nunique()) if "match_id" in out.columns else 0,
        "map_exposures": int(map_exposure.nunique()),
    }


def inventory_rows_for_feature_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    settled = frame["settled_win"].notna()
    map_equiv = frame["market_scope"].isin(MAP_EQUIVALENT_SCOPES)
    executable = frame["executable_snapshot"].map(lambda value: str(value).lower() in {"true", "1", "yes"})
    research = frame["tradable_research"].fillna(False).astype(bool)
    historical_executable = settled & map_equiv & research
    live_executable_intersection = settled & map_equiv & executable & research
    return [
        inventory_row("feature_frame", frame),
        inventory_row("settled", frame[settled]),
        inventory_row("map_equivalent_scope", frame[map_equiv]),
        inventory_row("executable_snapshot", frame[executable]),
        inventory_row("tradable_research", frame[research]),
        inventory_row("live_executable_and_research_same_row", frame[live_executable_intersection]),
        inventory_row("final_historical_executable_universe", frame[historical_executable]),
    ]


def run_walk_forward(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    matches = ordered_matches(frame)
    if len(matches) <= MIN_TRAIN_MATCHES + 5:
        raise ValueError(f"not enough matches for walk-forward: {len(matches)}")

    folds = make_folds(matches)
    rows: list[dict[str, Any]] = []
    trade_frames: list[pd.DataFrame] = []
    specs = model_specs()
    for fold_num, (train_matches, test_matches) in enumerate(folds, start=1):
        train = frame[frame["match_id"].astype(str).isin(train_matches)].copy()
        test = frame[frame["match_id"].astype(str).isin(test_matches)].copy()
        if train.empty or test.empty:
            continue
        for spec in specs:
            model = clone_pipeline(spec.model)
            y_col = "profitable_after_2c" if spec.score_kind == "value_class" else "settled_win"
            model.fit(train[FEATURES], train[y_col].astype(int))
            scored = test.copy()
            prob = model.predict_proba(scored[FEATURES])[:, 1]
            scored["model_name"] = spec.name
            scored["fold"] = fold_num
            scored["score_kind"] = spec.score_kind
            scored["model_score"] = prob
            scored["expected_value_2c"] = prob - scored["book_best_ask"] - SLIPPAGE
            for ask_name, (min_ask, max_ask) in ASK_FILTERS.items():
                ask_mask = scored["book_best_ask"].between(min_ask, max_ask)
                thresholds = VALUE_THRESHOLDS if spec.score_kind == "win_prob" else PROB_THRESHOLDS
                score_col = "expected_value_2c" if spec.score_kind == "win_prob" else "model_score"
                for threshold in thresholds:
                    signal = scored[ask_mask & (scored[score_col] >= threshold)].copy()
                    trades = first_map_trades(signal)
                    if trades.empty:
                        continue
                    summary = summarize_trades(trades)
                    rows.append(
                        {
                            "fold": fold_num,
                            "model_name": spec.name,
                            "score_kind": spec.score_kind,
                            "ask_filter": ask_name,
                            "threshold": threshold,
                            **summary,
                        }
                    )
                    trades = trades.copy()
                    trades["ask_filter"] = ask_name
                    trades["threshold"] = threshold
                    trade_frames.append(trades)
    results = pd.DataFrame(rows)
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    if results.empty:
        return results, trades
    aggregate_cols = ["model_name", "score_kind", "ask_filter", "threshold"]
    aggregate = (
        results.groupby(aggregate_cols, as_index=False)
        .agg(
            folds=("fold", "nunique"),
            trades=("trades", "sum"),
            wins=("wins", "sum"),
            pnl=("pnl", "sum"),
            pnl_1c=("pnl_1c", "sum"),
            pnl_2c=("pnl_2c", "sum"),
            avg_ask_weighted=("avg_ask_x_trades", "sum"),
        )
    )
    aggregate["win_rate"] = aggregate["wins"] / aggregate["trades"]
    aggregate["avg_ask"] = aggregate["avg_ask_weighted"] / aggregate["trades"]
    aggregate = aggregate.drop(columns=["avg_ask_weighted"])
    return aggregate.sort_values("pnl_2c", ascending=False), trades


def split_dev_lockbox(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    matches = ordered_matches(frame)
    lockbox_count = max(5, int(round(len(matches) * LOCKBOX_FRACTION)))
    if len(matches) <= MIN_TRAIN_MATCHES + lockbox_count:
        raise ValueError(f"not enough matches for dev/lockbox split: {len(matches)}")
    dev_matches = set(matches[:-lockbox_count])
    lockbox_matches = set(matches[-lockbox_count:])
    dev = frame[frame["match_id"].astype(str).isin(dev_matches)].copy()
    lockbox = frame[frame["match_id"].astype(str).isin(lockbox_matches)].copy()
    return dev, lockbox


def ordered_matches(frame: pd.DataFrame) -> list[str]:
    return (
        frame.groupby("match_id", as_index=False)
        .agg(first_time=("match_sort_time", "min"))
        .sort_values("first_time")
        ["match_id"]
        .astype(str)
        .tolist()
    )


def select_candidate(results: pd.DataFrame) -> Candidate | None:
    if results.empty:
        return None
    eligible = results[
        (results["folds"] >= MIN_SELECTION_FOLDS)
        & (results["trades"] >= MIN_SELECTION_TRADES)
        & (results["pnl_2c"] > 0)
    ].copy()
    if eligible.empty:
        eligible = results[(results["trades"] >= MIN_SELECTION_TRADES) & (results["pnl_2c"] > 0)].copy()
    if eligible.empty:
        eligible = results[results["pnl_2c"] > 0].copy()
    if eligible.empty:
        return None
    row = eligible.sort_values(["pnl_2c", "folds", "trades"], ascending=[False, False, False]).iloc[0]
    return Candidate(
        model_name=str(row["model_name"]),
        score_kind=str(row["score_kind"]),
        ask_filter=str(row["ask_filter"]),
        threshold=float(row["threshold"]),
    )


def select_promotion_candidate(results: pd.DataFrame, lockbox: pd.DataFrame) -> Candidate | None:
    if results.empty or lockbox.empty:
        return None
    merged = results.merge(
        lockbox,
        on=["model_name", "score_kind", "ask_filter", "threshold"],
        suffixes=("_dev", "_lockbox"),
    )
    eligible = merged[
        (merged["folds"] >= MIN_SELECTION_FOLDS)
        & (merged["trades_dev"] >= MIN_SELECTION_TRADES)
        & (merged["trades_lockbox"] >= 4)
        & (merged["pnl_2c_dev"] > 0)
        & (merged["pnl_2c_lockbox"] > 0)
    ].copy()
    if eligible.empty:
        return None
    eligible["pnl_2c_total"] = eligible["pnl_2c_dev"] + eligible["pnl_2c_lockbox"]
    row = eligible.sort_values("pnl_2c_total", ascending=False).iloc[0]
    return Candidate(
        model_name=str(row["model_name"]),
        score_kind=str(row["score_kind"]),
        ask_filter=str(row["ask_filter"]),
        threshold=float(row["threshold"]),
    )


def run_lockbox_grid(dev: pd.DataFrame, lockbox: pd.DataFrame, results: pd.DataFrame) -> pd.DataFrame:
    if results.empty or lockbox.empty:
        return pd.DataFrame()
    wanted = results[["model_name", "score_kind", "ask_filter", "threshold"]].drop_duplicates()
    rows: list[dict[str, Any]] = []
    for spec in model_specs():
        wanted_for_model = wanted[wanted["model_name"] == spec.name]
        if wanted_for_model.empty:
            continue
        model = clone_pipeline(spec.model)
        y_col = "profitable_after_2c" if spec.score_kind == "value_class" else "settled_win"
        model.fit(dev[FEATURES], dev[y_col].astype(int))
        scored = lockbox.copy()
        prob = model.predict_proba(scored[FEATURES])[:, 1]
        scored["model_name"] = spec.name
        scored["score_kind"] = spec.score_kind
        scored["model_score"] = prob
        scored["expected_value_2c"] = prob - scored["book_best_ask"] - SLIPPAGE
        score_col = "expected_value_2c" if spec.score_kind == "win_prob" else "model_score"
        for row in wanted_for_model.to_dict(orient="records"):
            ask_name = str(row["ask_filter"])
            min_ask, max_ask = ASK_FILTERS[ask_name]
            threshold = float(row["threshold"])
            signal = scored[
                scored["book_best_ask"].between(min_ask, max_ask)
                & (scored[score_col] >= threshold)
            ].copy()
            trades = first_map_trades(signal)
            summary = summarize_trades(trades) if not trades.empty else empty_trade_summary()
            rows.append(
                {
                    "model_name": spec.name,
                    "score_kind": spec.score_kind,
                    "ask_filter": ask_name,
                    "threshold": threshold,
                    "lockbox_matches": int(lockbox["match_id"].nunique()),
                    "raw_signal_rows": int(len(signal)),
                    **{key: value for key, value in summary.items() if key != "avg_ask_x_trades"},
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("pnl_2c", ascending=False).reset_index(drop=True)


def make_folds(matches: list[str], n_folds: int = 5) -> list[tuple[list[str], list[str]]]:
    test_count = max(3, len(matches) // (n_folds + 1))
    folds = []
    for fold in range(n_folds):
        train_end = MIN_TRAIN_MATCHES + fold * test_count
        test_end = min(len(matches), train_end + test_count)
        if test_end <= train_end:
            break
        folds.append((matches[:train_end], matches[train_end:test_end]))
    return folds


def model_specs() -> list[ModelSpec]:
    return [
        ModelSpec("value_logistic", logistic_pipeline(), "value_class"),
        ModelSpec("winprob_logistic", logistic_pipeline(), "win_prob"),
        ModelSpec("value_hgb", hgb_pipeline(), "value_class"),
        ModelSpec("winprob_hgb", hgb_pipeline(), "win_prob"),
    ]


def logistic_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC_FEATURES),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("pre", pre), ("clf", LogisticRegression(max_iter=3000, C=0.5))])


def hgb_pipeline() -> Pipeline:
    pre = ColumnTransformer(
        [
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), NUMERIC_FEATURES),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("pre", pre), ("clf", HistGradientBoostingClassifier(max_iter=200, learning_rate=0.04, max_leaf_nodes=12, random_state=7))])


def clone_pipeline(model: Pipeline) -> Pipeline:
    import sklearn.base

    return sklearn.base.clone(model)


def first_map_trades(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    return (
        rows.sort_values(["map_exposure_id", "received_at_ns"])
        .drop_duplicates("map_exposure_id", keep="first")
        .reset_index(drop=True)
    )


def summarize_trades(trades: pd.DataFrame) -> dict[str, Any]:
    ask = pd.to_numeric(trades["book_best_ask"], errors="coerce")
    win = trades["settled_win"].fillna(False).astype(bool)
    pnl = np.where(win, 1.0 - ask, -ask)
    pnl_1c = np.where(win, 1.0 - (ask + 0.01), -(ask + 0.01))
    pnl_2c = np.where(win, 1.0 - (ask + 0.02), -(ask + 0.02))
    return {
        "trades": int(len(trades)),
        "wins": int(win.sum()),
        "win_rate": float(win.mean()) if len(trades) else np.nan,
        "avg_ask": float(ask.mean()) if len(trades) else np.nan,
        "avg_ask_x_trades": float(ask.mean() * len(trades)) if len(trades) else 0.0,
        "pnl": float(pnl.sum()),
        "pnl_1c": float(pnl_1c.sum()),
        "pnl_2c": float(pnl_2c.sum()),
    }


def empty_trade_summary() -> dict[str, Any]:
    return {
        "trades": 0,
        "wins": 0,
        "win_rate": np.nan,
        "avg_ask": np.nan,
        "avg_ask_x_trades": 0.0,
        "pnl": 0.0,
        "pnl_1c": 0.0,
        "pnl_2c": 0.0,
    }


def add_map_exposure_id(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    game = out["current_game_number"].astype("string").fillna("").str.strip()
    game = game.mask(game.eq("") | game.str.lower().isin(["nan", "none", "<na>"]), "MAPEQUIV")
    out["map_exposure_id"] = out["match_id"].astype(str) + "::" + game.astype(str)
    return out


def format_report(
    results: pd.DataFrame,
    lockbox: pd.DataFrame,
    selected: Candidate | None,
    promoted: Candidate | None,
    inventory: pd.DataFrame,
    all_frame: pd.DataFrame,
    dev_frame: pd.DataFrame,
    lockbox_frame: pd.DataFrame,
) -> str:
    lines = [
        "# Executable Value Model Research",
        "",
        "Final accounting: historical executable research gate, map-equivalent, one trade per match/map, 2c slippage.",
        "",
        "## Inventory",
        "",
        "| step | rows | matches | map exposures |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in inventory.to_dict(orient="records"):
        lines.append(f"| {row['step']} | {row['rows']} | {row['matches']} | {row['map_exposures']} |")
    lines.extend(
        [
            "",
            f"Rows: {len(all_frame)} total, {len(dev_frame)} development, {len(lockbox_frame)} lockbox.",
            f"Matches: {all_frame['match_id'].nunique()} total, {dev_frame['match_id'].nunique()} development, {lockbox_frame['match_id'].nunique()} lockbox.",
            "",
            "## Promotion Verdict",
            "",
        ]
    )
    if promoted is None:
        lines.extend(
            [
                "Do not switch the running paper bot to a retrained model from this run.",
                "",
                f"Promotion requires folds >= {MIN_SELECTION_FOLDS}, development trades >= {MIN_SELECTION_TRADES}, lockbox trades >= 4, and positive 2c PnL on both development and lockbox.",
                "No retrained candidate passed that combined test.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"Promote candidate: `{promoted.model_name}` / `{promoted.ask_filter}` / threshold `{promoted.threshold:.2f}`.",
                "",
            ]
        )
    lines.extend(
        [
            "## Development Selection",
            "",
        ]
    )
    if results.empty:
        return "\n".join(lines + ["No results."])
    if selected is not None:
        lines.extend(
            [
                "## Selected Candidate",
                "",
                f"`{selected.model_name}` / `{selected.ask_filter}` / threshold `{selected.threshold:.2f}`.",
                "",
            ]
        )
        if not lockbox.empty:
            selected_mask = (
                (lockbox["model_name"] == selected.model_name)
                & (lockbox["ask_filter"] == selected.ask_filter)
                & (lockbox["threshold"].round(10) == round(selected.threshold, 10))
            )
            row = lockbox[selected_mask].iloc[0] if selected_mask.any() else lockbox.iloc[0]
            lines.extend(
                [
                    "| split | trades | win | avg ask | pnl | pnl 1c | pnl 2c |",
                    "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
                    f"| lockbox | {int(row['trades'])} | {row['win_rate'] * 100:.1f}% | {row['avg_ask']:.3f} | "
                    f"{row['pnl']:+.4f} | {row['pnl_1c']:+.4f} | {row['pnl_2c']:+.4f} |",
                    "",
                ]
            )
    if not lockbox.empty:
        lines.extend(
            [
                "## Top Lockbox Candidates",
                "",
                "| model | kind | ask filter | threshold | trades | win | avg ask | pnl 2c |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in lockbox.sort_values("pnl_2c", ascending=False).head(20).to_dict(orient="records"):
            win = "n/a" if pd.isna(row["win_rate"]) else f"{row['win_rate'] * 100:.1f}%"
            avg_ask = "n/a" if pd.isna(row["avg_ask"]) else f"{row['avg_ask']:.3f}"
            lines.append(
                f"| {row['model_name']} | {row['score_kind']} | {row['ask_filter']} | {row['threshold']:.2f} | "
                f"{row['trades']} | {win} | {avg_ask} | {row['pnl_2c']:+.4f} |"
            )
        lines.append("")
    robust = results[
        (results["folds"] >= MIN_SELECTION_FOLDS)
        & (results["trades"] >= MIN_SELECTION_TRADES)
        & (results["pnl_2c"] > 0)
    ].sort_values("pnl_2c", ascending=False)
    if not robust.empty:
        lines.extend(
            [
                "## Robust Development Candidates",
                "",
                "| model | kind | ask filter | threshold | folds | trades | win | avg ask | pnl 2c |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in robust.head(20).to_dict(orient="records"):
            lines.append(
                f"| {row['model_name']} | {row['score_kind']} | {row['ask_filter']} | {row['threshold']:.2f} | "
                f"{row['folds']} | {row['trades']} | {row['win_rate'] * 100:.1f}% | {row['avg_ask']:.3f} | {row['pnl_2c']:+.4f} |"
            )
        lines.append("")
    top = results.sort_values("pnl_2c", ascending=False).head(20)
    lines.extend(
        [
            "## Top Development Candidates",
            "",
            "| model | kind | ask filter | threshold | folds | trades | win | avg ask | pnl 2c |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top.to_dict(orient="records"):
        lines.append(
            f"| {row['model_name']} | {row['score_kind']} | {row['ask_filter']} | {row['threshold']:.2f} | "
            f"{row['folds']} | {row['trades']} | {row['win_rate'] * 100:.1f}% | {row['avg_ask']:.3f} | {row['pnl_2c']:+.4f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
