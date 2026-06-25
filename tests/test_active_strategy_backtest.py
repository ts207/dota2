from __future__ import annotations

from dota2bot.active_strategy_backtest import format_active_strategy_backtest


def test_format_active_strategy_backtest_is_single_strategy_summary():
    result = {
        "strategy": "market_nw_kill_momentum_logistic",
        "entry_threshold": 0.10,
        "eligibility_mode": "live_executable",
        "input_rows": 10,
        "raw_signal_rows": 3,
        "settled_trades": 2,
        "matches": 2,
        "win_rate": 0.5,
        "avg_ask": 0.4,
        "pnl": 0.2,
        "pnl_1c": 0.18,
        "pnl_2c": 0.16,
    }

    text = format_active_strategy_backtest(result)

    assert "Active Strategy Backtest" in text
    assert "market_nw_kill_momentum_logistic" in text
    assert "pnl 1c: +0.1800" in text


def test_format_active_strategy_threshold_sweep():
    result = {
        "strategy": "market_nw_kill_momentum_logistic",
        "eligibility_mode": "live_executable",
        "input_rows": 10,
        "thresholds": [
            {
                "entry_threshold": 0.10,
                "settled_trades": 2,
                "matches": 2,
                "win_rate": 0.5,
                "avg_ask": 0.4,
                "pnl": 0.2,
                "pnl_1c": 0.18,
                "pnl_2c": 0.16,
            }
        ],
    }

    text = format_active_strategy_backtest(result)

    assert "Active Strategy Threshold Backtest" in text
    assert "| 0.10 | 2 | 2 | 50.0% | 0.4000 | +0.2000 | +0.1800 | +0.1600 |" in text
