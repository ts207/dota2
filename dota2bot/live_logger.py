"""Live logger for Polymarket books, Steam game state, and clean side rows."""

from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from .live_sources import fetch_active_gamma_markets, fetch_clob_book, fetch_live_league_map_numbers, fetch_top_live_games, filter_dota_gamma_markets, gamma_market_token_rows
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
        last_seen_games: dict[str, dict[str, Any]] = {}
        last_state_hash_by_match: dict[str, str] = {}
        last_state_change_ns_by_match: dict[str, int] = {}
        while True:
            if book_only:
                games, map_nums = [], {}
            else:
                games_task = asyncio.create_task(fetch_top_live_games(session))
                map_nums_task = asyncio.create_task(fetch_live_league_map_numbers(session))
                games, map_nums = await asyncio.gather(games_task, map_nums_task)

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
                    if "yes_team" not in markets.columns:
                        markets["yes_team"] = ""
                    if "no_team" not in markets.columns:
                        markets["no_team"] = ""
                    markets["yes_is_radiant"] = None
                    markets["side_is_radiant"] = None
                    markets["steam_side_mapping"] = None
                    markets["confidence"] = None
                    # Clear stale book prices from previous map/game
                    latest_books.clear()
                    token_ids = []  # Reset until bound to a live game this cycle

            current_match_ids = {str(g.get("match_id")) for g in games if g.get("match_id")}
            ended_games = []
            if games:
                for m_id, old_game in last_seen_games.items():
                    if m_id not in current_match_ids:
                        old_game_copy = dict(old_game)
                        old_game_copy["game_over"] = True
                        ended_games.append(old_game_copy)
                for game in games:
                    m_id = str(game.get("match_id") or "")
                    if m_id:
                        last_seen_games[m_id] = game
                for eg in ended_games:
                    m_id = str(eg.get("match_id") or "")
                    if m_id in last_seen_games:
                        del last_seen_games[m_id]
            
            games_to_process = games + ended_games
            _annotate_state_changes(
                games_to_process,
                last_state_hash_by_match,
                last_state_change_ns_by_match,
            )

            if not markets.empty and (discover_dota or discover_active):
                _bind_discovered_markets(markets, games_to_process, map_nums)

                # Only fetch books for tokens we successfully bound to a live match
                bound_markets = markets[markets["match_id"] != ""]
                token_ids = sorted(set(bound_markets["token_id"].astype(str))) if not bound_markets.empty else []
                if max_tokens:
                    token_ids = token_ids[:max_tokens]
                counters["tokens"] = len(token_ids)
                counters["market_side_rows"] = int(len(markets))

            for game in games_to_process:
                logs.live_game_snapshots.append(game)
                counters["game_rows"] += 1

            book_results = await asyncio.gather(*(fetch_clob_book(session, token) for token in token_ids))
            for book in book_results:
                if not book:
                    continue
                logs.live_book_ticks.append(book)
                latest_books[str(book["asset_id"])] = book
                counters["book_rows"] += 1

            for game in games_to_process:
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
    if markets.empty or "match_id" not in markets.columns:
        return []
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
                "side_is_radiant": _side_is_radiant(market),
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
                "broadcast_delay_s": game.get("broadcast_delay_s"),
                "source_last_update_utc": game.get("source_last_update_utc"),
                "source_update_age_sec": game.get("source_update_age_sec"),
                "state_hash": game.get("state_hash"),
                "state_changed": game.get("state_changed"),
                "seconds_since_state_change": game.get("seconds_since_state_change"),
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
    """How many ms after the game snapshot was the book received. Positive = book is newer."""
    try:
        return (int(right_ns) - int(left_ns)) / 1_000_000.0
    except (TypeError, ValueError):
        return None


def _annotate_state_changes(
    games: list[dict[str, Any]],
    last_state_hash_by_match: dict[str, str],
    last_state_change_ns_by_match: dict[str, int],
) -> None:
    for game in games:
        match_id = str(game.get("match_id") or "")
        state_hash = str(game.get("state_hash") or "")
        if not match_id or not state_hash:
            game["state_changed"] = None
            game["seconds_since_state_change"] = None
            continue
        try:
            received_ns = int(game.get("received_at_ns"))
        except (TypeError, ValueError):
            game["state_changed"] = None
            game["seconds_since_state_change"] = None
            continue

        previous_hash = last_state_hash_by_match.get(match_id)
        changed = previous_hash != state_hash
        if changed:
            last_state_hash_by_match[match_id] = state_hash
            last_state_change_ns_by_match[match_id] = received_ns

        last_change_ns = last_state_change_ns_by_match.get(match_id, received_ns)
        game["state_changed"] = changed
        game["seconds_since_state_change"] = (received_ns - last_change_ns) / 1_000_000_000.0


def _bind_discovered_markets(
    markets: pd.DataFrame,
    games: list[dict[str, Any]],
    map_nums: dict[str, int],
) -> None:
    for game in games:
        match_id = str(game.get("match_id") or "")
        rad = str(game.get("radiant_team") or "").strip().lower()
        dire = str(game.get("dire_team") or "").strip().lower()
        if not match_id or not rad or not dire:
            continue
        for idx, row in markets.iterrows():
            name = str(row.get("market_name", ""))
            if not (_team_match(game.get("radiant_team", ""), name) and _team_match(game.get("dire_team", ""), name)):
                continue

            map_num = map_nums.get(match_id)
            if not map_num:
                continue
            m = re.search(r"(?:map|game)\s*(\d+)", name, re.IGNORECASE)
            if not m:
                # Game 3 of a BO3: Match Winner == Game 3 winner, so allow it.
                if map_num != 3:
                    continue
            else:
                target_map = int(m.group(1))
                if target_map != map_num:
                    continue

            markets.at[idx, "match_id"] = match_id
            markets.at[idx, "steam_radiant_team"] = game.get("radiant_team")
            markets.at[idx, "steam_dire_team"] = game.get("dire_team")
            markets.at[idx, "current_game_number"] = str(map_num)
            mapping = _infer_market_side_mapping(row, game)
            markets.at[idx, "side_is_radiant"] = mapping["side_is_radiant"]
            markets.at[idx, "yes_is_radiant"] = mapping["yes_is_radiant"]
            markets.at[idx, "steam_side_mapping"] = mapping["steam_side_mapping"]
            markets.at[idx, "confidence"] = mapping["confidence"]


def _side_is_radiant(market: dict[str, Any]) -> bool | None:
    direct = _bool_or_none(market.get("side_is_radiant"))
    if direct is not None:
        return direct

    yes_is_radiant = _bool_or_none(market.get("yes_is_radiant"))
    if yes_is_radiant is None:
        return None

    side = str(market.get("side") or "").upper()
    token_id = str(market.get("token_id") or "")
    yes_token_id = str(market.get("yes_token_id") or "")
    no_token_id = str(market.get("no_token_id") or "")
    if side == "YES" or (yes_token_id and token_id == yes_token_id):
        return yes_is_radiant
    if side == "NO" or (no_token_id and token_id == no_token_id):
        return not yes_is_radiant
    return None


def _infer_market_side_mapping(market: pd.Series | dict[str, Any], game: dict[str, Any]) -> dict[str, Any]:
    radiant = str(game.get("radiant_team") or "")
    dire = str(game.get("dire_team") or "")
    side = str(_get(market, "side") or "")
    side_is_radiant = _side_name_is_radiant(side, radiant, dire)

    yes_team = str(_get(market, "yes_team") or "")
    no_team = str(_get(market, "no_team") or "")
    yes_is_radiant = _side_name_is_radiant(yes_team, radiant, dire)
    if yes_is_radiant is None and _side_name_is_radiant(no_team, radiant, dire) is not None:
        yes_is_radiant = not _side_name_is_radiant(no_team, radiant, dire)

    token_id = str(_get(market, "token_id") or "")
    yes_token_id = str(_get(market, "yes_token_id") or "")
    no_token_id = str(_get(market, "no_token_id") or "")
    if yes_is_radiant is None and side_is_radiant is not None:
        if yes_token_id and token_id == yes_token_id:
            yes_is_radiant = side_is_radiant
        elif no_token_id and token_id == no_token_id:
            yes_is_radiant = not side_is_radiant

    return {
        "side_is_radiant": side_is_radiant,
        "yes_is_radiant": yes_is_radiant,
        "steam_side_mapping": ("normal" if yes_is_radiant else "reversed") if yes_is_radiant is not None else None,
        "confidence": "1.0" if side_is_radiant is not None and yes_is_radiant is not None else None,
    }


def _side_name_is_radiant(name: str, radiant: str, dire: str) -> bool | None:
    if not name:
        return None
    radiant_match = _team_match(radiant, name)
    dire_match = _team_match(dire, name)
    if radiant_match and not dire_match:
        return True
    if dire_match and not radiant_match:
        return False
    return None


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _get(row: pd.Series | dict[str, Any], key: str) -> Any:
    return row.get(key) if hasattr(row, "get") else None


def add_live_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--markets", default="datasets/clean_executable_backtest_dataset/clean_markets.parquet")
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--interval-sec", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--book-only", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--discover-dota", action="store_true", help="discover current active Dota markets from Polymarket Gamma")
    parser.add_argument("--discover-active", action="store_true", help="discover current active Polymarket markets from Gamma")


def _team_match(steam_name: str, market_name: str) -> bool:
    stopwords = {"gaming", "esports", "team", "club", "clan", "ex", "fc", "the",
                 "back", "new", "old", "red", "blue", "black", "white"}

    steam_tokens = [w for w in re.findall(r"[a-z0-9]+", steam_name.lower()) if w not in stopwords]
    market_tokens = set(re.findall(r"[a-z0-9]+", market_name.lower()))

    if not steam_tokens:
        steam_tokens = re.findall(r"[a-z0-9]+", steam_name.lower())

    if len(steam_tokens) > 1:
        acronym = "".join(t[0] for t in steam_tokens)
        steam_tokens.append(acronym)

    for t in steam_tokens:
        if t in market_tokens:
            return True
        # Only allow steam token as substring of a market word, not the reverse
        if len(t) >= 4 and any(t in mt for mt in market_tokens):
            return True

    return False
