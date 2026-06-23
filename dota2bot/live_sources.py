"""Public live data sources used by the logger-only bot."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import aiohttp


CLOB_BOOK_URL = "https://clob.polymarket.com/book"
GAMMA_MARKETS_URL = "https://gamma-api.polymarket.com/markets"
TOP_LIVE_URL = "https://api.steampowered.com/IDOTA2Match_570/GetTopLiveGame/v1/"


def utc_from_ns(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc).isoformat()


def utc_from_epoch_seconds(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


async def fetch_clob_book(
    session: aiohttp.ClientSession,
    token_id: str,
    timeout_ms: int = 2500,
) -> dict[str, Any] | None:
    start_ns = time.time_ns()
    try:
        async with session.get(
            CLOB_BOOK_URL,
            params={"token_id": token_id},
            headers={"Accept-Encoding": "gzip, deflate"},
            timeout=aiohttp.ClientTimeout(total=timeout_ms / 1000.0),
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
        return None

    received_at_ns = time.time_ns()
    best_bid, bid_size = _best_bid(data.get("bids") or [])
    best_ask, ask_size = _best_ask(data.get("asks") or [])
    if best_bid is None and best_ask is None:
        return None
    spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None
    mid = (best_bid + best_ask) / 2.0 if best_bid is not None and best_ask is not None else (best_ask or best_bid)
    return {
        "book_event_id": f"B_{uuid.uuid4().hex[:12]}",
        "asset_id": str(token_id),
        "received_at_utc": utc_from_ns(received_at_ns),
        "received_at_ns": received_at_ns,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "bid_size": bid_size,
        "ask_size": ask_size,
        "mid": mid,
        "spread": spread,
        "request_start_ns": start_ns,
        "refresh_latency_ns": received_at_ns - start_ns,
        "source": "polymarket_clob_rest",
    }


async def fetch_top_live_games(session: aiohttp.ClientSession, steam_api_key: str | None = None) -> list[dict[str, Any]]:
    key = steam_api_key or os.environ.get("STEAM_API_KEY")
    if not key:
        return []
    received_at_ns = time.time_ns()
    out: dict[str, dict[str, Any]] = {}

    async def fetch_partner(partner: int) -> None:
        try:
            async with session.get(
                TOP_LIVE_URL,
                params={"key": key, "partner": partner},
                timeout=aiohttp.ClientTimeout(total=6.0),
            ) as resp:
                if resp.status != 200:
                    return
                payload = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, json.JSONDecodeError):
            return
        for raw in payload.get("game_list", []) or []:
            row = normalize_top_live_game(raw, received_at_ns)
            mid = row["match_id"]
            if not mid:
                continue
            # Partner 0 is canonical — always wins; others only fill gaps
            if partner == 0 or mid not in out:
                out[mid] = row

    await asyncio.gather(*(fetch_partner(p) for p in range(4)))
    return list(out.values())


async def fetch_live_league_map_numbers(session: aiohttp.ClientSession, steam_api_key: str | None = None) -> dict[str, int]:
    key = steam_api_key or os.environ.get("STEAM_API_KEY")
    if not key:
        return {}
    
    url = "https://api.steampowered.com/IDOTA2Match_570/GetLiveLeagueGames/v1/"
    try:
        async with session.get(
            url,
            params={"key": key},
            timeout=aiohttp.ClientTimeout(total=6.0),
        ) as resp:
            if resp.status != 200:
                return {}
            payload = await resp.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError, json.JSONDecodeError):
        return {}
        
    out = {}
    for raw in payload.get("result", {}).get("games", []):
        match_id = str(raw.get("match_id") or "")
        if match_id:
            r_wins = int(raw.get("radiant_series_wins") or 0)
            d_wins = int(raw.get("dire_series_wins") or 0)
            out[match_id] = r_wins + d_wins + 1
    return out


async def fetch_active_gamma_markets(session: aiohttp.ClientSession, limit: int = 1000) -> list[dict[str, Any]]:
    urls_params = [
        {"active": "true", "closed": "false", "limit": str(limit)},
        {"active": "true", "closed": "false", "limit": str(limit), "series_slug": "dota-2"},
    ]
    seen_event_ids: set[str] = set()
    events: list[dict[str, Any]] = []
    for params in urls_params:
        try:
            async with session.get(
                "https://gamma-api.polymarket.com/events",
                params=params,
                headers={"Accept-Encoding": "gzip, deflate"},
                timeout=aiohttp.ClientTimeout(total=10.0),
            ) as resp:
                if resp.status == 200:
                    resp_json = await resp.json()
                    if isinstance(resp_json, list):
                        for ev in resp_json:
                            eid = str(ev.get("id") or "")
                            if eid and eid not in seen_event_ids:
                                seen_event_ids.add(eid)
                                events.append(ev)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, json.JSONDecodeError):
            pass

    out = []
    for event in events:
        teams_text = " ".join(t.get("name", "") for t in event.get("teams", []))
        for market in event.get("markets", []):
            if isinstance(market, dict):
                market["groupItemTitle"] = str(market.get("groupItemTitle") or "") + " " + teams_text
                market["events"] = [event]
                out.append(market)
    return out


def filter_dota_gamma_markets(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keywords = ["dota", "dota 2", "dreamleague", "the international", "esl one", "blast slam"]
    out = []
    for market in markets:
        text = " ".join(
            str(market.get(k) or "")
            for k in ["question", "title", "slug", "description", "groupItemTitle"]
        ).lower()
        events = market.get("events") or []
        if isinstance(events, list):
            text += " " + " ".join(str(e.get(k) or "") for e in events for k in ["title", "slug", "description"]).lower()
        if any(keyword in text for keyword in keywords):
            out.append(market)
    return out


def gamma_market_token_rows(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for market in markets:
        token_ids = _json_list(market.get("clobTokenIds"))
        outcomes = _json_list(market.get("outcomes"))
        if len(token_ids) < 2:
            continue
        yes_team = str(outcomes[0]) if len(outcomes) >= 1 else "Yes"
        no_team = str(outcomes[1]) if len(outcomes) >= 2 else "No"
        for idx, token_id in enumerate(token_ids[:2]):
            outcome = str(outcomes[idx]) if idx < len(outcomes) else ("Yes" if idx == 0 else "No")
            opposing_id = str(token_ids[1] if idx == 0 else token_ids[0]) if len(token_ids) >= 2 else ""
            yes_token_id = str(token_ids[0]) if len(token_ids) >= 1 else ""
            no_token_id = str(token_ids[1]) if len(token_ids) >= 2 else ""
            
            rows.append(
                {
                    "market_id": str(market.get("id") or ""),
                    "condition_id": str(market.get("conditionId") or ""),
                    "market_name": str(market.get("question") or market.get("title") or market.get("slug") or ""),
                    "market_type": str(market.get("sportsMarketType") or ""),
                    "token_id": str(token_id),
                    "opposing_token_id": opposing_id,
                    "yes_token_id": yes_token_id,
                    "no_token_id": no_token_id,
                    "yes_team": yes_team,
                    "no_team": no_team,
                    "side": outcome.upper(),
                    "active": bool(market.get("active")),
                    "closed": bool(market.get("closed")),
                    "accepting_orders": bool(market.get("acceptingOrders")),
                    "best_bid_hint": market.get("bestBid"),
                    "best_ask_hint": market.get("bestAsk"),
                    "source": "polymarket_gamma",
                }
            )
    return rows


def normalize_top_live_game(raw: dict[str, Any], received_at_ns: int) -> dict[str, Any]:
    radiant_lead = _int_or_none(raw.get("radiant_lead"))
    source_last_update = _float_or_none(raw.get("last_update_time"))
    source_update_age_sec = None
    source_clock_skew_sec = None
    source_last_update_utc = None
    if source_last_update is not None:
        signed_age_sec = received_at_ns / 1_000_000_000.0 - source_last_update
        source_update_age_sec = max(signed_age_sec, 0.0)
        source_clock_skew_sec = max(-signed_age_sec, 0.0)
        source_last_update_utc = utc_from_epoch_seconds(source_last_update)
    broadcast_delay_s = _int_or_none(raw.get("delay"))
    deactivate_time = _float_or_none(raw.get("deactivate_time"))
    received_at_sec = received_at_ns / 1_000_000_000.0
    return {
        "received_at_utc": utc_from_ns(received_at_ns),
        "received_at_ns": received_at_ns,
        "match_id": str(raw.get("match_id") or raw.get("lobby_id") or ""),
        "lobby_id": str(raw.get("lobby_id") or ""),
        "league_id": str(raw.get("league_id") or ""),
        "server_steam_id": str(raw.get("server_steam_id") or ""),
        "game_time_sec": _int_or_none(raw.get("game_time")),
        "radiant_lead": radiant_lead,
        "radiant_score": _int_or_none(raw.get("radiant_score")),
        "dire_score": _int_or_none(raw.get("dire_score")),
        "building_state": _int_or_none(raw.get("building_state")),
        "tower_state": None,
        "stream_delay_s": broadcast_delay_s,
        "broadcast_delay_s": broadcast_delay_s,
        "source_last_update_utc": source_last_update_utc,
        "source_update_age_sec": source_update_age_sec,
        "source_clock_skew_sec": source_clock_skew_sec,
        "data_source": "steam_top_live",
        "spectators": _int_or_none(raw.get("spectators")),
        "game_over": bool(deactivate_time and deactivate_time <= received_at_sec),
        "radiant_team": raw.get("team_name_radiant"),
        "dire_team": raw.get("team_name_dire"),
        "radiant_team_id": str(raw.get("team_id_radiant") or ""),
        "dire_team_id": str(raw.get("team_id_dire") or ""),
        "radiant_net_worth": None,
        "dire_net_worth": None,
        "net_worth_diff": radiant_lead,
        "state_hash": _state_hash(raw),
        "state_changed": None,
        "seconds_since_state_change": None,
        "raw_json": json.dumps(raw, separators=(",", ":"), sort_keys=True),
    }


def _best_bid(levels: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    parsed = _parse_levels(levels)
    return max(parsed, key=lambda x: x[0]) if parsed else (None, None)


def _best_ask(levels: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    parsed = _parse_levels(levels)
    return min(parsed, key=lambda x: x[0]) if parsed else (None, None)


def _parse_levels(levels: list[dict[str, Any]]) -> list[tuple[float, float]]:
    parsed: list[tuple[float, float]] = []
    for level in levels:
        try:
            price = float(level["price"])
            size = float(level.get("size") or 0.0)
        except (TypeError, ValueError, KeyError):
            continue
        if size > 0:
            parsed.append((price, size))
    return parsed


def _int_or_none(value: Any) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _state_hash(raw: dict[str, Any]) -> str:
    state = {
        key: raw.get(key)
        for key in [
            "match_id",
            "game_time",
            "radiant_lead",
            "radiant_score",
            "dire_score",
            "building_state",
            "deactivate_time",
        ]
    }
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []
