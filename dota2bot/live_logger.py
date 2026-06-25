"""Live logger for Polymarket books, Steam game state, and clean side rows."""

from __future__ import annotations

import argparse
import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from .live_sources import fetch_active_gamma_markets, fetch_clob_book, fetch_live_league_map_numbers, fetch_top_live_games, filter_dota_gamma_markets, gamma_market_token_rows
from .logging_store import BotLogs
from .market_state import load_market_sides, token_ids_from_markets
from .schemas import SIDE_SNAPSHOT_COLUMNS


SOURCE_FRESH_MAX_AGE_SEC = 30.0
BOOK_FRESH_MAX_ABS_AGE_MS = 5000.0
EXECUTABLE_MAX_SPREAD = 0.10
EXECUTABLE_MIN_ASK_SIZE = 100.0

MAP_WINNER_EXPLICIT = "map_winner_explicit"
SERIES_DECIDER_EQUIVALENT = "series_decider_equivalent"
NON_TARGET_MARKET = "non_target_market"
UNKNOWN_SCOPE = "unknown_scope"
MAP_EQUIVALENT_SCOPES = {MAP_WINNER_EXPLICIT, SERIES_DECIDER_EQUIVALENT}

ACTIONABLE_REJECT_REASONS = {"missing_team_names", "no_map_number"}
EXPECTED_SKIP_REASONS = {
    "wrong_game_number",
    "series_market_not_decider",
    "unknown_series_length",
    "non_target_market",
}
TEAM_MATCH_STOPWORDS = {
    "gaming",
    "esports",
    "team",
    "club",
    "clan",
    "ex",
    "fc",
    "the",
    "back",
    "new",
    "old",
    "red",
    "blue",
    "black",
    "white",
}


async def run_live_logger(
    *,
    markets_path: Path = Path("datasets/clean_executable_backtest_dataset/clean_markets.parquet"),
    logs_root: Path = Path("logs"),
    interval_sec: float = 5.0,
    flush_interval_sec: float = 60.0,
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
        last_flush_ns = time.time_ns()
        cycle = 0
        while True:
            cycle += 1
            cycle_id = f"C_{time.time_ns()}"
            if book_only:
                games, map_nums = [], {}
            else:
                games_task = asyncio.create_task(fetch_top_live_games(session))
                map_nums_task = asyncio.create_task(fetch_live_league_map_numbers(session))
                games, map_nums = await asyncio.gather(games_task, map_nums_task)
            fetched_games = list(games)

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
                    markets["market_scope"] = UNKNOWN_SCOPE
                    markets["detected_market_game_number"] = None
                    markets["parsed_series_length"] = None
                    # Clear stale book prices from previous map/game
                    latest_books.clear()
                    token_ids = []  # Reset until bound to a live game this cycle
                fetched_game_count = len(games)
                games, game_reject_rows = _filter_games_for_markets(games, markets, cycle_id)
                for reject in game_reject_rows:
                    logs.live_binding_rejects.append(reject)
            else:
                fetched_game_count = len(games)

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
            health = _cycle_health_base(
                cycle_id=cycle_id,
                fetched_games=fetched_game_count,
                fetched_game_rows=fetched_games,
                games=games_to_process,
                map_nums=map_nums,
                markets=markets,
                discover_dota=discover_dota,
                discover_active=discover_active,
            )

            if not markets.empty and (discover_dota or discover_active):
                reject_rows = _bind_discovered_markets(markets, games_to_process, map_nums, cycle_id)
                for reject in reject_rows:
                    logs.live_binding_rejects.append(reject)

                # Only fetch books for tokens we successfully bound to a live match
                bound_markets = markets[markets["match_id"] != ""]
                token_ids = sorted(set(bound_markets["token_id"].astype(str))) if not bound_markets.empty else []
                if max_tokens:
                    token_ids = token_ids[:max_tokens]
                counters["tokens"] = len(token_ids)
                counters["market_side_rows"] = int(len(markets))
                health["bound_market_rows"] = int(len(bound_markets))
                health["candidate_market_rows"] = int(len(bound_markets)) + sum(
                    1 for reject in reject_rows if reject.get("reject_bucket") == "expected_non_target_market"
                )
                health["bound_map_equivalent_rows"] = _market_scope_count(bound_markets, MAP_EQUIVALENT_SCOPES)
                health["bound_explicit_map_winner_rows"] = _market_scope_count(bound_markets, {MAP_WINNER_EXPLICIT})
                health["bound_series_decider_equivalent_rows"] = _market_scope_count(bound_markets, {SERIES_DECIDER_EQUIVALENT})
                health["expected_skip_rows"] = sum(
                    1 for reject in reject_rows if reject.get("reject_bucket") == "expected_non_target_market"
                )
                health["actionable_reject_rows"] = sum(
                    1 for reject in reject_rows if reject.get("reject_bucket") == "actionable_data_gap"
                )
                health["tokens"] = int(len(token_ids))

            for game in games_to_process:
                logs.live_game_snapshots.append(game)
                counters["game_rows"] += 1

            book_results = await asyncio.gather(*(fetch_clob_book(session, token) for token in token_ids))
            cycle_book_rows = 0
            for book in book_results:
                if not book:
                    continue
                logs.live_book_ticks.append(book)
                latest_books[str(book["asset_id"])] = book
                counters["book_rows"] += 1
                cycle_book_rows += 1

            cycle_live_side_rows = 0
            cycle_side_rows: list[dict[str, Any]] = []
            for game in games_to_process:
                for row in _side_rows_for_game(game, markets, latest_books):
                    logs.live_side_snapshots.append(row)
                    cycle_side_rows.append(row)
                    counters["live_side_rows"] += 1
                    cycle_live_side_rows += 1

            health["book_rows"] = cycle_book_rows
            health["live_side_rows"] = cycle_live_side_rows
            health["stale_bound_games"] = health["stale_games"]
            health["clock_skewed_bound_games"] = health["clock_skew_games"]
            health["two_sided_book_rows"] = sum(1 for row in cycle_side_rows if row.get("has_two_sided_book"))
            health["one_sided_book_rows"] = sum(1 for row in cycle_side_rows if not row.get("has_two_sided_book"))
            health["executable_side_rows"] = sum(1 for row in cycle_side_rows if row.get("executable_snapshot"))
            logs.live_health.append(health)
            now_ns = time.time_ns()
            should_flush = once or (now_ns - last_flush_ns >= int(flush_interval_sec * 1_000_000_000))
            if should_flush:
                logs.flush()
                last_flush_ns = now_ns
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
        book_age_ms = _age_ms(game.get("received_at_ns"), book.get("received_at_ns"))
        quality = _snapshot_quality(game, book, book_age_ms, str(market.get("market_scope") or UNKNOWN_SCOPE))
        row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
        row.update(
            {
                "match_id": match_id,
                "market_id": market.get("market_id"),
                "condition_id": market.get("condition_id"),
                "market_name": market.get("market_name"),
                "market_type": market.get("market_type"),
                "market_scope": market.get("market_scope") or UNKNOWN_SCOPE,
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
                "book_age_ms": book_age_ms,
                "book_best_bid": book.get("best_bid"),
                "book_best_ask": book.get("best_ask"),
                "book_bid_size": book.get("bid_size"),
                "book_ask_size": book.get("ask_size"),
                "book_mid": book.get("mid"),
                "book_spread": book.get("spread"),
                "source_fresh": quality["source_fresh"],
                "book_fresh": quality["book_fresh"],
                "has_two_sided_book": quality["has_two_sided_book"],
                "executable_snapshot": quality["executable_snapshot"],
                "quality_reason": quality["quality_reason"],
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
                "source_clock_skew_sec": game.get("source_clock_skew_sec"),
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


def _snapshot_quality(
    game: dict[str, Any],
    book: dict[str, Any],
    book_age_ms: float | None,
    market_scope: str,
) -> dict[str, Any]:
    source_age = _num_or_none(game.get("source_update_age_sec"))
    spread = _num_or_none(book.get("spread"))
    ask_size = _num_or_none(book.get("ask_size"))
    source_fresh = source_age is not None and source_age <= SOURCE_FRESH_MAX_AGE_SEC
    book_fresh = book_age_ms is not None and abs(book_age_ms) <= BOOK_FRESH_MAX_ABS_AGE_MS
    has_two_sided_book = book.get("best_bid") is not None and book.get("best_ask") is not None
    reasons = []
    if market_scope not in MAP_EQUIVALENT_SCOPES:
        reasons.append("non_map_equivalent")
    if not source_fresh:
        reasons.append("stale_source")
    if not book_fresh:
        reasons.append("stale_book")
    if not has_two_sided_book:
        reasons.append("one_sided_book")
    if spread is None or spread > EXECUTABLE_MAX_SPREAD:
        reasons.append("wide_spread")
    if ask_size is None or ask_size < EXECUTABLE_MIN_ASK_SIZE:
        reasons.append("small_ask_size")
    return {
        "source_fresh": source_fresh,
        "book_fresh": book_fresh,
        "has_two_sided_book": has_two_sided_book,
        "executable_snapshot": not reasons,
        "quality_reason": "ok" if not reasons else ",".join(reasons),
    }


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


def _cycle_health_base(
    *,
    cycle_id: str,
    fetched_games: int,
    fetched_game_rows: list[dict[str, Any]],
    games: list[dict[str, Any]],
    map_nums: dict[str, int],
    markets: pd.DataFrame,
    discover_dota: bool,
    discover_active: bool,
) -> dict[str, Any]:
    now_ns = time.time_ns()
    source_ages = [
        float(game.get("source_update_age_sec"))
        for game in games
        if _num_or_none(game.get("source_update_age_sec")) is not None
    ]
    source_skews = [
        float(game.get("source_clock_skew_sec"))
        for game in games
        if _num_or_none(game.get("source_clock_skew_sec")) is not None
    ]
    fetched_source_ages = [
        float(game.get("source_update_age_sec"))
        for game in fetched_game_rows
        if _num_or_none(game.get("source_update_age_sec")) is not None
    ]
    fetched_source_skews = [
        float(game.get("source_clock_skew_sec"))
        for game in fetched_game_rows
        if _num_or_none(game.get("source_clock_skew_sec")) is not None
    ]
    return {
        "received_at_utc": _utc_from_ns(now_ns),
        "received_at_ns": now_ns,
        "cycle_id": cycle_id,
        "fetched_games": fetched_games,
        "irrelevant_games": max(fetched_games - len(games), 0),
        "fetched_stale_games": sum(1 for age in fetched_source_ages if age > 30),
        "fetched_clock_skew_games": sum(1 for skew in fetched_source_skews if skew > 0),
        "max_fetched_source_update_age_sec": max(fetched_source_ages) if fetched_source_ages else None,
        "max_fetched_source_clock_skew_sec": max(fetched_source_skews) if fetched_source_skews else None,
        "games": len(games),
        "games_with_team_names": sum(1 for game in games if game.get("radiant_team") and game.get("dire_team")),
        "map_numbers": len(map_nums),
        "market_side_rows": int(len(markets)),
        "bound_market_rows": 0,
        "candidate_market_rows": 0,
        "bound_map_equivalent_rows": 0,
        "bound_explicit_map_winner_rows": 0,
        "bound_series_decider_equivalent_rows": 0,
        "expected_skip_rows": 0,
        "actionable_reject_rows": 0,
        "tokens": 0,
        "book_rows": 0,
        "live_side_rows": 0,
        "stale_bound_games": 0,
        "clock_skewed_bound_games": 0,
        "two_sided_book_rows": 0,
        "one_sided_book_rows": 0,
        "executable_side_rows": 0,
        "stale_games": sum(1 for age in source_ages if age > 30),
        "clock_skew_games": sum(1 for skew in source_skews if skew > 0),
        "max_source_update_age_sec": max(source_ages) if source_ages else None,
        "max_source_clock_skew_sec": max(source_skews) if source_skews else None,
        "discover_dota": int(discover_dota),
        "discover_active": int(discover_active),
    }


def _filter_games_for_markets(
    games: list[dict[str, Any]],
    markets: pd.DataFrame,
    cycle_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if markets.empty:
        return [], [_game_reject_row(game, "no_active_markets", cycle_id) for game in games]
    kept = []
    rejects = []
    for game in games:
        if not str(game.get("radiant_team") or "").strip() or not str(game.get("dire_team") or "").strip():
            rejects.append(_game_reject_row(game, "missing_team_names", cycle_id))
        elif _game_matches_any_market(game, markets):
            kept.append(game)
        else:
            rejects.append(_game_reject_row(game, "not_polymarket_match", cycle_id))
    return kept, rejects


def _game_matches_any_market(game: dict[str, Any], markets: pd.DataFrame) -> bool:
    match_id = str(game.get("match_id") or "")
    radiant = str(game.get("radiant_team") or "").strip()
    dire = str(game.get("dire_team") or "").strip()
    if not match_id or not radiant or not dire:
        return False
    for _, row in markets.iterrows():
        name = str(row.get("market_name", ""))
        if _team_match(radiant, name) and _team_match(dire, name):
            return True
    return False


def _bind_discovered_markets(
    markets: pd.DataFrame,
    games: list[dict[str, Any]],
    map_nums: dict[str, int],
    cycle_id: str | None = None,
) -> list[dict[str, Any]]:
    rejects: list[dict[str, Any]] = []
    for game in games:
        match_id = str(game.get("match_id") or "")
        rad = str(game.get("radiant_team") or "").strip().lower()
        dire = str(game.get("dire_team") or "").strip().lower()
        if not match_id or not rad or not dire:
            continue
        matched_any_market = False
        for idx, row in markets.iterrows():
            name = str(row.get("market_name", ""))
            if not (_team_match(game.get("radiant_team", ""), name) and _team_match(game.get("dire_team", ""), name)):
                continue
            matched_any_market = True

            map_num = map_nums.get(match_id)
            if not map_num:
                rejects.append(_binding_reject_row(row, game, "no_map_number", None, cycle_id))
                continue
            classification = _classify_market_for_live_map(row, map_num)
            markets.at[idx, "detected_market_game_number"] = classification["detected_market_game_number"]
            markets.at[idx, "parsed_series_length"] = classification["parsed_series_length"]
            markets.at[idx, "market_scope"] = classification["market_scope"]
            if not classification["bind"]:
                rejects.append(
                    _binding_reject_row(
                        row,
                        game,
                        classification["reason"],
                        map_num,
                        cycle_id,
                        classification=classification,
                    )
                )
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
        if not matched_any_market:
            rejects.append(_game_reject_row(game, "no_matching_market", cycle_id))
    return rejects


def _classify_market_for_live_map(market: pd.Series | dict[str, Any], map_num: int) -> dict[str, Any]:
    name = str(_get(market, "market_name") or "")
    market_type = str(_get(market, "market_type") or "").lower()
    detected_game = _detect_market_game_number(name)
    series_length = _parse_series_length(name)

    if detected_game is not None:
        if detected_game == map_num:
            return {
                "bind": True,
                "reason": None,
                "market_scope": MAP_WINNER_EXPLICIT,
                "detected_market_game_number": detected_game,
                "parsed_series_length": series_length,
            }
        return {
            "bind": False,
            "reason": "wrong_game_number",
            "market_scope": NON_TARGET_MARKET,
            "detected_market_game_number": detected_game,
            "parsed_series_length": series_length,
        }

    if market_type == "moneyline":
        if series_length is None:
            return {
                "bind": False,
                "reason": "unknown_series_length",
                "market_scope": UNKNOWN_SCOPE,
                "detected_market_game_number": None,
                "parsed_series_length": None,
            }
        if map_num == series_length:
            return {
                "bind": True,
                "reason": None,
                "market_scope": SERIES_DECIDER_EQUIVALENT,
                "detected_market_game_number": None,
                "parsed_series_length": series_length,
            }
        return {
            "bind": False,
            "reason": "series_market_not_decider",
            "market_scope": NON_TARGET_MARKET,
            "detected_market_game_number": None,
            "parsed_series_length": series_length,
        }

    return {
        "bind": False,
        "reason": "non_target_market",
        "market_scope": NON_TARGET_MARKET,
        "detected_market_game_number": None,
        "parsed_series_length": series_length,
    }


def _classification_from_market(market: pd.Series | dict[str, Any]) -> dict[str, Any]:
    name = str(_get(market, "market_name") or "")
    return {
        "market_scope": _get(market, "market_scope") or UNKNOWN_SCOPE,
        "detected_market_game_number": _get(market, "detected_market_game_number") or _detect_market_game_number(name),
        "parsed_series_length": _get(market, "parsed_series_length") or _parse_series_length(name),
    }


def _detect_market_game_number(name: str) -> int | None:
    m = re.search(r"(?:map|game)\s*(\d+)", name, re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _parse_series_length(name: str) -> int | None:
    patterns = [
        r"\bBO\s*(\d+)\b",
        r"\bbest\s*of\s*(\d+)\b",
        r"\bbest-of-(\d+)\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, name, re.IGNORECASE)
        if not m:
            continue
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _reject_bucket(reason: str) -> str:
    if reason in ACTIONABLE_REJECT_REASONS:
        return "actionable_data_gap"
    if reason in EXPECTED_SKIP_REASONS:
        return "expected_non_target_market"
    return "other"


def _market_scope_count(markets: pd.DataFrame, scopes: set[str]) -> int:
    if markets.empty or "market_scope" not in markets.columns:
        return 0
    return int(markets["market_scope"].isin(scopes).sum())


def _binding_reject_row(
    market: pd.Series | dict[str, Any],
    game: dict[str, Any],
    reason: str,
    map_num: int | None,
    cycle_id: str | None,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classification = classification or _classification_from_market(market)
    market_name = str(_get(market, "market_name") or "")
    return {
        "received_at_utc": game.get("received_at_utc"),
        "received_at_ns": game.get("received_at_ns"),
        "cycle_id": cycle_id,
        "match_id": game.get("match_id"),
        "market_id": _get(market, "market_id"),
        "market_name": market_name,
        "side": _get(market, "side"),
        "token_id": _get(market, "token_id"),
        "radiant_team": game.get("radiant_team"),
        "dire_team": game.get("dire_team"),
        "reason": reason,
        "reject_phase": "market_binding",
        "reject_bucket": _reject_bucket(reason),
        "current_game_number": str(map_num) if map_num else None,
        "live_game_number": str(map_num) if map_num else None,
        "detected_market_game_number": classification.get("detected_market_game_number"),
        "parsed_series_length": classification.get("parsed_series_length"),
        "market_scope": classification.get("market_scope") or UNKNOWN_SCOPE,
        "map_number_available": map_num is not None,
        "normalized_radiant_tokens": ",".join(_team_tokens(str(game.get("radiant_team") or ""))),
        "normalized_dire_tokens": ",".join(_team_tokens(str(game.get("dire_team") or ""))),
        "normalized_market_tokens": ",".join(_market_tokens(market_name)),
        "source_update_age_sec": game.get("source_update_age_sec"),
        "source_clock_skew_sec": game.get("source_clock_skew_sec"),
    }


def _game_reject_row(game: dict[str, Any], reason: str, cycle_id: str | None) -> dict[str, Any]:
    return {
        "received_at_utc": game.get("received_at_utc"),
        "received_at_ns": game.get("received_at_ns"),
        "cycle_id": cycle_id,
        "match_id": game.get("match_id"),
        "market_id": None,
        "market_name": None,
        "side": None,
        "token_id": None,
        "radiant_team": game.get("radiant_team"),
        "dire_team": game.get("dire_team"),
        "reason": reason,
        "reject_phase": "game_filter",
        "reject_bucket": _reject_bucket(reason),
        "current_game_number": None,
        "live_game_number": None,
        "detected_market_game_number": None,
        "parsed_series_length": None,
        "market_scope": UNKNOWN_SCOPE,
        "map_number_available": False,
        "normalized_radiant_tokens": ",".join(_team_tokens(str(game.get("radiant_team") or ""))),
        "normalized_dire_tokens": ",".join(_team_tokens(str(game.get("dire_team") or ""))),
        "normalized_market_tokens": "",
        "source_update_age_sec": game.get("source_update_age_sec"),
        "source_clock_skew_sec": game.get("source_clock_skew_sec"),
    }


def _side_is_radiant(market: dict[str, Any]) -> bool | None:
    direct = _bool_or_none(market.get("side_is_radiant"))
    if direct is not None:
        return direct

    side_from_name = _side_name_is_radiant(
        str(market.get("side") or ""),
        str(market.get("radiant_team") or market.get("steam_radiant_team") or ""),
        str(market.get("dire_team") or market.get("steam_dire_team") or ""),
    )
    if side_from_name is not None:
        return side_from_name

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


def _utc_from_ns(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc).isoformat()


def _num_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
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
    parser.add_argument(
        "--flush-interval-sec",
        type=float,
        default=60.0,
        help="flush buffered parquet logs at most this often; reduces WSL small-file churn",
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--book-only", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--discover-dota", action="store_true", help="discover current active Dota markets from Polymarket Gamma")
    parser.add_argument("--discover-active", action="store_true", help="discover current active Polymarket markets from Gamma")


def _team_match(steam_name: str, market_name: str) -> bool:
    steam_tokens = _team_tokens(steam_name)
    market_tokens = set(_market_tokens(market_name))

    for t in steam_tokens:
        if t in market_tokens:
            return True
        # Only allow steam token as substring of a market word, not the reverse
        if len(t) >= 4 and any(t in mt for mt in market_tokens):
            return True

    return False


def _team_tokens(name: str) -> list[str]:
    tokens = [w for w in re.findall(r"[a-z0-9]+", name.lower()) if w not in TEAM_MATCH_STOPWORDS]
    if not tokens:
        tokens = re.findall(r"[a-z0-9]+", name.lower())
    if len(tokens) > 1:
        tokens.append("".join(t[0] for t in tokens))
    return tokens


def _market_tokens(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", name.lower())
