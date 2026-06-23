"""Live logger for Polymarket books, Steam game state, and clean side rows."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from .live_sources import fetch_active_gamma_markets, fetch_clob_book, fetch_top_live_games, filter_dota_gamma_markets, gamma_market_token_rows
from .logging_store import BotLogs
from .market_state import load_market_sides, token_ids_from_markets
from .schemas import SIDE_SNAPSHOT_COLUMNS


async def run_live_logger(
    *,
    markets_path: Path = Path("datasets/clean_executable_backtest_dataset/clean_markets.parquet"),
    logs_root: Path = Path("logs"),
    interval_sec: float = 5.0,
    once: bool = False,
    book_only: bool = False,
    max_tokens: int | None = None,
    discover_dota: bool = False,
    discover_active: bool = False,
) -> dict[str, int]:
    logs = BotLogs(root=logs_root)
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        counters = {
            "book_rows": 0,
            "game_rows": 0,
            "live_side_rows": 0,
            "tokens": 0,
            "market_side_rows": 0,
            "discover_dota": int(discover_dota),
            "discover_active": int(discover_active),
        }
        if not (discover_dota or discover_active):
            markets = load_market_sides(markets_path)
            token_ids = token_ids_from_markets(markets)
            if max_tokens:
                token_ids = token_ids[:max_tokens]
            counters["tokens"] = len(token_ids)
            counters["market_side_rows"] = int(len(markets))
        else:
            markets = pd.DataFrame()
            token_ids = []

        latest_books: dict[str, dict[str, Any]] = {}
        while True:
            games = [] if book_only else await fetch_top_live_games(session)

            if discover_dota or discover_active:
                gamma_markets = await fetch_active_gamma_markets(session)
                if discover_dota:
                    gamma_markets = filter_dota_gamma_markets(gamma_markets)
                discovered_rows = gamma_market_token_rows(gamma_markets)
                markets = pd.DataFrame(discovered_rows)
                if markets.empty:
                    token_ids = []
                else:
                    markets["match_id"] = ""
                    markets["steam_radiant_team"] = ""
                    markets["steam_dire_team"] = ""
                    markets["yes_team"] = ""
                    markets["no_team"] = ""
                    markets["yes_is_radiant"] = None
                    markets["opposing_token_id"] = ""

                    for game in games:
                        match_id = str(game.get("match_id") or "")
                        rad = str(game.get("radiant_team") or "").strip().lower()
                        dire = str(game.get("dire_team") or "").strip().lower()
                        if not match_id or not rad or not dire:
                            continue
                        
                        for idx, row in markets.iterrows():
                            name = str(row.get("market_name", "")).lower()
                            if rad in name and dire in name:
                                markets.at[idx, "match_id"] = match_id
                                markets.at[idx, "steam_radiant_team"] = game.get("radiant_team")
                                markets.at[idx, "steam_dire_team"] = game.get("dire_team")

                    token_ids = sorted(set(markets["token_id"].dropna().astype(str)))
                if max_tokens:
                    token_ids = token_ids[:max_tokens]
                counters["tokens"] = len(token_ids)
                counters["market_side_rows"] = int(len(markets))

            for game in games:
                logs.live_game_snapshots.append(game)
                counters["game_rows"] += 1

            book_results = await asyncio.gather(*(fetch_clob_book(session, token) for token in token_ids))
            for book in book_results:
                if not book:
                    continue
                logs.live_book_ticks.append(book)
                latest_books[str(book["asset_id"])] = book
                counters["book_rows"] += 1

            for game in games:
                for row in _side_rows_for_game(game, markets, latest_books):
                    logs.live_side_snapshots.append(row)
                    counters["live_side_rows"] += 1

            logs.flush()
            if once:
                return counters
            await asyncio.sleep(interval_sec)


def _side_rows_for_game(
    game: dict[str, Any],
    markets: pd.DataFrame,
    latest_books: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    match_id = str(game.get("match_id") or "")
    if not match_id:
        return []
    sides = markets[markets["match_id"].astype(str).eq(match_id)]
    if sides.empty:
        return []

    out = []
    for market in sides.to_dict(orient="records"):
        book = latest_books.get(str(market["token_id"]))
        if not book:
            continue
        row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
        row.update(
            {
                "match_id": match_id,
                "market_id": market.get("market_id"),
                "condition_id": market.get("condition_id"),
                "market_name": market.get("market_name"),
                "market_type": market.get("market_type"),
                "label_market_bucket": market.get("label_market_bucket"),
                "current_game_number": market.get("current_game_number"),
                "series_type": game.get("series_type"),
                "side": market.get("side"),
                "token_id": market.get("token_id"),
                "opposing_token_id": market.get("opposing_token_id"),
                "received_at_utc": game.get("received_at_utc"),
                "received_at_ns": game.get("received_at_ns"),
                "game_time_sec": game.get("game_time_sec"),
                "book_received_at_utc": book.get("received_at_utc"),
                "book_received_at_ns": book.get("received_at_ns"),
                "book_age_ms": _age_ms(game.get("received_at_ns"), book.get("received_at_ns")),
                "book_best_bid": book.get("best_bid"),
                "book_best_ask": book.get("best_ask"),
                "book_bid_size": book.get("bid_size"),
                "book_ask_size": book.get("ask_size"),
                "book_mid": book.get("mid"),
                "book_spread": book.get("spread"),
                "settled_win": None,
                "radiant_win": None,
                "side_is_radiant": None,
                "yes_is_radiant": market.get("yes_is_radiant"),
                "radiant_lead": game.get("radiant_lead"),
                "radiant_score": game.get("radiant_score"),
                "dire_score": game.get("dire_score"),
                "radiant_net_worth": game.get("radiant_net_worth"),
                "dire_net_worth": game.get("dire_net_worth"),
                "net_worth_diff": game.get("net_worth_diff"),
                "yes_team": market.get("yes_team"),
                "no_team": market.get("no_team"),
                "steam_radiant_team": game.get("radiant_team") or market.get("steam_radiant_team"),
                "steam_dire_team": game.get("dire_team") or market.get("steam_dire_team"),
                "steam_side_mapping": market.get("steam_side_mapping"),
                "market_source_file": market.get("market_source_file"),
                "dataset_version": "live_logger_v1",
                "lobby_id": game.get("lobby_id"),
                "league_id": game.get("league_id"),
                "server_steam_id": game.get("server_steam_id"),
                "building_state": game.get("building_state"),
                "tower_state": game.get("tower_state"),
                "stream_delay_s": game.get("stream_delay_s"),
                "source_update_age_sec": game.get("source_update_age_sec"),
                "data_source": game.get("data_source"),
                "spectators": game.get("spectators"),
                "game_over": game.get("game_over"),
                "radiant_team": game.get("radiant_team"),
                "dire_team": game.get("dire_team"),
                "radiant_team_id": game.get("radiant_team_id"),
                "dire_team_id": game.get("dire_team_id"),
                "yes_token_id": market.get("yes_token_id"),
                "no_token_id": market.get("no_token_id"),
                "confidence": market.get("confidence"),
                "asset_id": book.get("asset_id"),
                "book_schema_version": "live_book_v1",
                "book_source_file": "polymarket_clob_rest",
            }
        )
        out.append(row)
    return out


def _age_ms(left_ns: Any, right_ns: Any) -> float | None:
    try:
        return (int(left_ns) - int(right_ns)) / 1_000_000.0
    except (TypeError, ValueError):
        return None


def add_live_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--markets", default="datasets/clean_executable_backtest_dataset/clean_markets.parquet")
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--book-only", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--discover-dota", action="store_true", help="discover current active Dota markets from Polymarket Gamma")
    parser.add_argument("--discover-active", action="store_true", help="discover current active Polymarket markets from Gamma")
