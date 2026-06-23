"""Market mapping helpers for live logging."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_market_sides(path: Path = Path("datasets/clean_executable_backtest_dataset/clean_markets.parquet")) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing market file: {path}")
    markets = pd.read_parquet(path)
    required = {"match_id", "market_id", "yes_token_id", "no_token_id", "yes_team", "no_team"}
    missing = sorted(required - set(markets.columns))
    if missing:
        raise ValueError(f"market file missing columns: {missing}")

    rows = []
    for row in markets.to_dict(orient="records"):
        base = dict(row)
        rows.append({**base, "side": "YES", "token_id": str(row["yes_token_id"]), "opposing_token_id": str(row["no_token_id"])})
        rows.append({**base, "side": "NO", "token_id": str(row["no_token_id"]), "opposing_token_id": str(row["yes_token_id"])})
    out = pd.DataFrame(rows)
    out["match_id"] = out["match_id"].astype(str)
    out["token_id"] = out["token_id"].astype(str)
    return out


def token_ids_from_markets(markets: pd.DataFrame) -> list[str]:
    return sorted(set(markets["token_id"].dropna().astype(str)))
