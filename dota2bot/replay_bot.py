"""Replay runner that logs with the clean executable data contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .datasets import load_clean_side_snapshots
from .logging_store import BotLogs
from .schemas import SIDE_SNAPSHOT_COLUMNS
from .strategies import LeaderMidgameProbe, decision_id


def run_replay(limit: int | None = None, logs_root: Path = Path("logs")) -> dict[str, int]:
    df = load_clean_side_snapshots()
    if limit:
        df = df.head(limit)

    for col in SIDE_SNAPSHOT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    logs = BotLogs(root=logs_root)
    strategy = LeaderMidgameProbe()

    decision_rows = 0
    signal_rows = 0
    for row in df[SIDE_SNAPSHOT_COLUMNS].to_dict(orient="records"):
        logs.side_snapshots.append(row)
        decision = strategy.evaluate(row)
        if decision.signal:
            signal_rows += 1
        logs.decisions.append(
            {
                "decision_id": decision_id(strategy.name, row),
                "strategy_name": strategy.name,
                "match_id": row.get("match_id"),
                "market_id": row.get("market_id"),
                "token_id": row.get("token_id"),
                "side": row.get("side"),
                "received_at_utc": row.get("received_at_utc"),
                "received_at_ns": row.get("received_at_ns"),
                "game_time_sec": row.get("game_time_sec"),
                "ask": row.get("book_best_ask"),
                "bid": row.get("book_best_bid"),
                "book_age_ms": row.get("book_age_ms"),
                "signal": decision.signal,
                "reason": decision.reason,
                "score": decision.score,
                "settled_win": row.get("settled_win"),
                "paper_pnl_per_share": row.get("hold_to_settlement_pnl_per_share") if decision.signal else None,
            }
        )
        decision_rows += 1

    logs.flush()
    return {
        "input_rows": int(len(df)),
        "logged_side_snapshot_rows": int(len(df)),
        "decision_rows": decision_rows,
        "signal_rows": signal_rows,
        "matches": int(pd.Series(df["match_id"]).nunique()),
    }
