from __future__ import annotations

import pandas as pd

from market_residual_gettoplive_analysis import (
    add_future_prices,
    concentration_tables,
    fold_robustness_table,
    market_calibration_table,
    market_models,
    model_summary_table,
    prediction_output,
    residual_bucket_tables,
    trade_output,
    trade_uncertainty_table,
    transition_entry_event_study,
    wilson_interval,
)


def test_market_calibration_table_uses_ask_bucket_residual_metrics():
    frame = _frame()

    table = market_calibration_table(frame)

    assert set(table["table"]) == {"market_calibration"}
    assert {"ask_bucket", "rows", "matches", "avg_ask", "win_rate_minus_avg_ask", "avg_pnl"}.issubset(table.columns)
    assert table["rows"].sum() == len(frame)


def test_market_models_include_feature_family_ablations():
    assert {
        "market_only_logistic",
        "market_nw_logistic",
        "market_momentum_logistic",
        "market_kill_momentum_logistic",
        "market_nw_kill_momentum_logistic",
        "market_score_logistic",
        "market_structure_logistic",
        "market_gettoplive_logistic",
        "market_transition_nw_logistic",
        "market_transition_kill_logistic",
        "market_transition_nw_kill_logistic",
        "market_transition_catchup_logistic",
    }.issubset(set(market_models()))


def test_residual_bucket_tables_include_required_state_dimensions():
    table = residual_bucket_tables(_frame())

    assert {
        "side_nw_bucket",
        "side_mom_100_bucket",
        "side_kill_mom_bucket",
        "side_transition_kill_delta_bucket",
        "side_transition_nw_delta_bucket",
        "score_nw_lag_type",
        "transition_signal_type",
        "side_score_bucket",
        "structure_score_bucket",
        "game_time_bucket",
    }.issubset(set(table["state_bucket_type"]))
    assert {"robust_residual_bucket", "robust_gate_reason"}.issubset(table.columns)


def test_residual_bucket_tables_mark_broad_positive_cells_robust():
    frame = pd.concat([_frame(match_id=f"m{i}", ask=0.30, settled_win=True) for i in range(10)], ignore_index=True)

    table = residual_bucket_tables(frame)
    robust = table[table["robust_residual_bucket"]]

    assert not robust.empty
    assert set(robust["robust_gate_reason"]) == {"pass"}


def test_add_future_prices_uses_same_token_stream_at_or_after_horizon():
    frame = _frame()

    priced = add_future_prices(frame, horizons=[15, 60])

    first = priced[priced["game_time_sec"] == 600].iloc[0]
    assert pd.isna(first["future_bid_15s"])
    assert first["future_bid_60s"] == 0.55
    assert first["future_mid_60s"] == 0.56
    assert first["future_delay_60s"] == 60


def test_prediction_and_trade_outputs_are_fixed_width_for_empty_frames():
    pred = prediction_output(_frame().assign(stage="x", fold=1, model_name="m", model_version="v", edge=0.1, entry_threshold=0.1, signal=False))
    trades = trade_output(pd.DataFrame())

    assert "market_prob" in pred.columns
    assert "condition_id" not in trades.columns
    assert "pnl_slip_2c" in trades.columns


def test_concentration_tables_group_trade_pnl_by_context():
    trades = _frame().assign(stage="walk_forward", model_name="market_gettoplive_logistic", league_id="l1")

    by_bucket, by_match, by_league = concentration_tables(trades)

    assert by_bucket.loc[0, "label_market_bucket"] == "MAP_WINNER"
    assert by_bucket.loc[0, "trades"] == 3
    assert by_match.loc[0, "match_id"] == "m1"
    assert by_match.loc[0, "buckets"] == 1
    assert by_league.loc[0, "league_id"] == "l1"


def test_transition_entry_event_study_reports_settlement_and_future_bid_clv():
    frame = _frame().assign(
        score_changed_without_nw=[True, False, False],
        nw_changed_without_score=[False, True, False],
        score_nw_changed_together=[False, False, True],
        score_nw_lag_type=["score_only", "score_then_nw", "same_snapshot"],
        transition_signal_type=["first_score_change", "score_then_nw_catchup", "confirmed_transition"],
    )

    table = transition_entry_event_study(frame).set_index("entry_timing")

    assert {"first_score_change", "score_then_nw_catchup", "confirmed_transition"}.issubset(table.index)
    assert "future_bid_clv_60s" in table.columns
    assert table.loc["first_score_change", "trades"] == 1
    assert table.loc["first_score_change", "raw_pnl"] == -0.53


def test_trade_uncertainty_uses_wilson_interval():
    trades = _frame().assign(stage="walk_forward", model_name="market_gettoplive_logistic")

    table = trade_uncertainty_table(trades)
    low, high = wilson_interval(2, 3)

    assert table.loc[0, "wins"] == 2
    assert table.loc[0, "win_rate_ci_low"] == low
    assert table.loc[0, "win_rate_ci_high"] == high


def test_fold_robustness_counts_positive_slippage_folds():
    metrics = pd.DataFrame(
        [
            {"stage": "walk_forward", "fold": 1, "model_name": "m", "trade_trades": 2, "trade_total_pnl": 1.0, "trade_total_pnl_slip_1c": 0.5, "trade_total_pnl_slip_2c": 0.3},
            {"stage": "walk_forward", "fold": 2, "model_name": "m", "trade_trades": 1, "trade_total_pnl": -0.2, "trade_total_pnl_slip_1c": -0.3, "trade_total_pnl_slip_2c": -0.4},
        ]
    )

    table = fold_robustness_table(metrics)

    assert table.loc[0, "folds"] == 2
    assert table.loc[0, "folds_with_trades"] == 2
    assert table.loc[0, "folds_positive_1c"] == 1


def test_model_summary_uses_fold_support_and_uncertainty_for_verdicts():
    metrics = pd.DataFrame(
        [
            {
                "stage": "walk_forward",
                "fold": 1,
                "model_name": "candidate_model",
                "selected_threshold": 0.05,
                "pred_rows": 10,
                "auc": 0.6,
                "log_loss": 0.5,
                "brier": 0.2,
                "trade_trades": 2,
                "trade_matches": 2,
                "trade_win_rate": 0.5,
                "trade_avg_ask": 0.4,
                "trade_avg_edge": 0.1,
                "trade_avg_pnl": 0.1,
                "trade_total_pnl": 0.4,
                "trade_total_pnl_slip_1c": 0.3,
                "trade_total_pnl_slip_2c": 0.2,
            },
            {
                "stage": "walk_forward",
                "fold": 2,
                "model_name": "candidate_model",
                "selected_threshold": 0.05,
                "pred_rows": 10,
                "auc": 0.7,
                "log_loss": 0.4,
                "brier": 0.1,
                "trade_trades": 1,
                "trade_matches": 1,
                "trade_win_rate": 1.0,
                "trade_avg_ask": 0.5,
                "trade_avg_edge": 0.2,
                "trade_avg_pnl": 0.5,
                "trade_total_pnl": 0.5,
                "trade_total_pnl_slip_1c": 0.4,
                "trade_total_pnl_slip_2c": 0.3,
            },
            {
                "stage": "walk_forward",
                "fold": 3,
                "model_name": "candidate_model",
                "selected_threshold": 0.05,
                "pred_rows": 10,
                "auc": 0.7,
                "log_loss": 0.4,
                "brier": 0.1,
                "trade_trades": 1,
                "trade_matches": 1,
                "trade_win_rate": 1.0,
                "trade_avg_ask": 0.5,
                "trade_avg_edge": 0.2,
                "trade_avg_pnl": 0.5,
                "trade_total_pnl": 0.5,
                "trade_total_pnl_slip_1c": 0.4,
                "trade_total_pnl_slip_2c": 0.3,
            },
            {
                "stage": "walk_forward",
                "fold": 4,
                "model_name": "candidate_model",
                "selected_threshold": 0.05,
                "pred_rows": 10,
                "auc": 0.7,
                "log_loss": 0.4,
                "brier": 0.1,
                "trade_trades": 1,
                "trade_matches": 1,
                "trade_win_rate": 1.0,
                "trade_avg_ask": 0.5,
                "trade_avg_edge": 0.2,
                "trade_avg_pnl": 0.5,
                "trade_total_pnl": 0.5,
                "trade_total_pnl_slip_1c": 0.4,
                "trade_total_pnl_slip_2c": 0.3,
            },
            {
                "stage": "walk_forward",
                "fold": 1,
                "model_name": "thin_model",
                "selected_threshold": 0.05,
                "pred_rows": 10,
                "auc": 0.6,
                "log_loss": 0.5,
                "brier": 0.2,
                "trade_trades": 2,
                "trade_matches": 2,
                "trade_win_rate": 1.0,
                "trade_avg_ask": 0.4,
                "trade_avg_edge": 0.1,
                "trade_avg_pnl": 0.2,
                "trade_total_pnl": 0.4,
                "trade_total_pnl_slip_1c": 0.3,
                "trade_total_pnl_slip_2c": 0.2,
            },
            {
                "stage": "walk_forward",
                "fold": 2,
                "model_name": "thin_model",
                "selected_threshold": 0.05,
                "pred_rows": 10,
                "auc": 0.6,
                "log_loss": 0.5,
                "brier": 0.2,
                "trade_trades": 0,
                "trade_matches": 0,
                "trade_win_rate": float("nan"),
                "trade_avg_ask": float("nan"),
                "trade_avg_edge": float("nan"),
                "trade_avg_pnl": float("nan"),
                "trade_total_pnl": 0.0,
                "trade_total_pnl_slip_1c": 0.0,
                "trade_total_pnl_slip_2c": 0.0,
            },
            {
                "stage": "walk_forward",
                "fold": 1,
                "model_name": "reject_model",
                "selected_threshold": 0.05,
                "pred_rows": 10,
                "auc": 0.6,
                "log_loss": 0.5,
                "brier": 0.2,
                "trade_trades": 1,
                "trade_matches": 1,
                "trade_win_rate": 0.0,
                "trade_avg_ask": 0.4,
                "trade_avg_edge": 0.1,
                "trade_avg_pnl": -0.4,
                "trade_total_pnl": -0.4,
                "trade_total_pnl_slip_1c": -0.41,
                "trade_total_pnl_slip_2c": -0.42,
            },
        ]
    )

    trades = pd.DataFrame(
        [
            {"stage": "walk_forward", "model_name": "candidate_model", "settled_win": True, "book_best_ask": 0.20, "pnl_per_share": 0.80, "pnl_slip_1c": 0.79, "pnl_slip_2c": 0.78},
            {"stage": "walk_forward", "model_name": "candidate_model", "settled_win": True, "book_best_ask": 0.20, "pnl_per_share": 0.80, "pnl_slip_1c": 0.79, "pnl_slip_2c": 0.78},
            {"stage": "walk_forward", "model_name": "candidate_model", "settled_win": True, "book_best_ask": 0.20, "pnl_per_share": 0.80, "pnl_slip_1c": 0.79, "pnl_slip_2c": 0.78},
            {"stage": "walk_forward", "model_name": "candidate_model", "settled_win": True, "book_best_ask": 0.20, "pnl_per_share": 0.80, "pnl_slip_1c": 0.79, "pnl_slip_2c": 0.78},
            {"stage": "walk_forward", "model_name": "thin_model", "settled_win": True, "book_best_ask": 0.60, "pnl_per_share": 0.40, "pnl_slip_1c": 0.39, "pnl_slip_2c": 0.38},
            {"stage": "walk_forward", "model_name": "thin_model", "settled_win": True, "book_best_ask": 0.60, "pnl_per_share": 0.40, "pnl_slip_1c": 0.39, "pnl_slip_2c": 0.38},
            {"stage": "walk_forward", "model_name": "reject_model", "settled_win": False, "book_best_ask": 0.40, "pnl_per_share": -0.40, "pnl_slip_1c": -0.41, "pnl_slip_2c": -0.42},
        ]
    )

    table = model_summary_table(metrics, trades).set_index("model_name")

    assert table.loc["candidate_model", "verdict"] == "candidate"
    assert table.loc["thin_model", "verdict"] == "research_only"
    assert table.loc["reject_model", "verdict"] == "reject"
    assert table.loc["thin_model", "uncertainty_reason"] == "ci_low_not_above_breakeven"


def _frame(*, match_id: str = "m1", ask: float | None = None, settled_win: bool | None = None) -> pd.DataFrame:
    rows = []
    for idx, game_time in enumerate([600, 660, 720], start=1):
        row_ask = ask if ask is not None else 0.50 + idx * 0.03
        row_settled_win = (idx != 1) if settled_win is None else settled_win
        rows.append(
            {
                "match_id": match_id,
                "market_id": "market1",
                "label_market_bucket": "MAP_WINNER",
                "token_id": "token_yes",
                "side": "YES",
                "received_at_utc": f"t{idx}",
                "received_at_ns": idx * 1000,
                "game_time_sec": game_time,
                "settled_win": row_settled_win,
                "market_prob": row_ask,
                "calibrated_prob": 0.60,
                "book_best_ask": row_ask,
                "book_best_bid": 0.48 + idx * 0.035,
                "book_mid": 0.49 + idx * 0.035,
                "book_spread": 0.03,
                "book_ask_size": 100,
                "book_age_ms": 1000,
                "tradable": True,
                "side_nw": idx * 3000,
                "side_mom_100": idx * 2000,
                "side_mom_300": idx * 2500,
                "side_kill_mom": idx,
                "side_score": idx,
                "side_tower": 0,
                "side_rax": 0,
                "structure_score": 0,
                "side_transition_nw_delta": idx * 500,
                "side_transition_score_delta": idx,
                "side_transition_kill_delta": idx,
                "side_transition_nw_per_sec": idx * 10.0,
                "side_transition_kill_per_sec": idx / 60.0,
                "transition_dt_sec": 60,
                "score_changed_without_nw": idx == 1,
                "nw_changed_without_score": idx == 2,
                "score_nw_changed_together": idx == 3,
                "score_leads_nw_sec": 0,
                "nw_leads_score_sec": 0,
                "score_nw_lag_type": "same_snapshot" if idx == 3 else "no_change",
                "transition_signal_type": "confirmed_transition" if idx == 3 else "no_transition",
                "pnl_per_share": (1 - row_ask) if row_settled_win else -row_ask,
                "pnl_slip_1c": (1 - (row_ask + 0.01)) if row_settled_win else -(row_ask + 0.01),
                "pnl_slip_2c": (1 - (row_ask + 0.02)) if row_settled_win else -(row_ask + 0.02),
                "total_kills": idx,
                "building_state": idx,
            }
        )
    return pd.DataFrame(rows)
