"""Read-only audit reports for live parquet logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow.dataset as ds


MAP_EQUIVALENT_SCOPES = {"map_winner_explicit", "series_decider_equivalent"}


def run_audit_logs(
    *,
    logs_root: Path = Path("logs"),
    market_scope: str = "map-equivalent",
    output_format: str = "text",
) -> str:
    report = build_audit_report(logs_root=logs_root, market_scope=market_scope)
    if output_format == "json":
        return json.dumps(report, indent=2, sort_keys=True, default=str)
    return format_text_report(report)


def build_audit_report(*, logs_root: Path, market_scope: str) -> dict[str, Any]:
    con = duckdb.connect()
    report: dict[str, Any] = {
        "logs_root": str(logs_root),
        "market_scope": market_scope,
        "datasets": {},
        "health": {},
        "rejects": {},
        "side_snapshots": {},
        "books": {},
    }
    for name in [
        "live_health",
        "live_game_snapshots",
        "live_binding_rejects",
        "live_book_ticks",
        "live_side_snapshots",
        "strategy_decisions",
        "clean_side_snapshots",
    ]:
        report["datasets"][name] = _dataset_meta(logs_root / name)

    if report["datasets"]["live_health"]["files"]:
        report["health"] = _one(
            con,
            f"""
            select count(*) as cycles,
                   min(received_at_utc) as first_ts,
                   max(received_at_utc) as last_ts,
                   avg(fetched_games) as avg_fetched_games,
                   avg(games) as avg_bound_games,
                   avg(live_side_rows) as avg_live_side_rows,
                   sum(case when games = 0 then 1 else 0 end) as zero_bound_game_cycles,
                   sum(case when live_side_rows = 0 then 1 else 0 end) as zero_side_row_cycles,
                   sum(case when max_source_update_age_sec > 30 then 1 else 0 end) as cycles_source_age_gt30,
                   max(max_source_update_age_sec) as worst_source_age_sec
            from read_parquet('{_glob(logs_root, "live_health")}', union_by_name=true)
            """,
        )

    if report["datasets"]["live_binding_rejects"]["files"]:
        reject_bucket = _reject_bucket_expr(_columns(logs_root / "live_binding_rejects"))
        report["rejects"]["by_bucket_reason"] = _rows(
            con,
            f"""
            select {reject_bucket} as reject_bucket,
                   reason,
                   count(*) as rows,
                   count(distinct match_id) as matches,
                   count(distinct market_id) as markets
            from read_parquet('{_glob(logs_root, "live_binding_rejects")}', union_by_name=true)
            group by 1, 2
            order by rows desc
            """,
        )

    if report["datasets"]["live_side_snapshots"]["files"]:
        side_cols = _columns(logs_root / "live_side_snapshots")
        scope_expr = _scope_expr(side_cols)
        quality_expr = _quality_expr(scope_expr)
        report["side_snapshots"]["summary"] = _one(
            con,
            f"""
            with s as (
              select *,
                     {scope_expr} as audit_market_scope,
                     {quality_expr} as audit_executable_snapshot
              from read_parquet('{_glob(logs_root, "live_side_snapshots")}', union_by_name=true)
            )
            select count(*) as rows,
                   count(distinct match_id) as matches,
                   count(distinct market_id) as markets,
                   count(distinct token_id) as tokens,
                   sum(case when audit_market_scope in ('map_winner_explicit', 'series_decider_equivalent') then 1 else 0 end) as map_equivalent_rows,
                   sum(case when audit_market_scope = 'map_winner_explicit' then 1 else 0 end) as explicit_map_winner_rows,
                   sum(case when audit_market_scope = 'series_decider_equivalent' then 1 else 0 end) as series_decider_equivalent_rows,
                   sum(case when audit_executable_snapshot then 1 else 0 end) as executable_rows,
                   avg(book_spread) as avg_spread,
                   max(source_update_age_sec) as worst_source_age_sec
            from s
            """,
        )
        report["side_snapshots"]["by_scope"] = _rows(
            con,
            f"""
            with s as (
              select *,
                     {scope_expr} as audit_market_scope,
                     {quality_expr} as audit_executable_snapshot
              from read_parquet('{_glob(logs_root, "live_side_snapshots")}', union_by_name=true)
            )
            select audit_market_scope as market_scope,
                   count(*) as rows,
                   count(distinct match_id) as matches,
                   count(distinct market_id) as markets,
                   sum(case when audit_executable_snapshot then 1 else 0 end) as executable_rows
            from s
            group by 1
            order by rows desc
            """,
        )

    if report["datasets"]["live_book_ticks"]["files"]:
        report["books"] = _one(
            con,
            f"""
            select count(*) as rows,
                   count(distinct asset_id) as assets,
                   sum(case when best_bid is null then 1 else 0 end) as null_bid_rows,
                   sum(case when best_ask is null then 1 else 0 end) as null_ask_rows,
                   sum(case when best_bid is not null and best_ask is not null then 1 else 0 end) as two_sided_rows,
                   avg(spread) as avg_spread,
                   max(spread) as max_spread,
                   avg(refresh_latency_ns) / 1000000.0 as avg_refresh_ms,
                   max(refresh_latency_ns) / 1000000.0 as max_refresh_ms
            from read_parquet('{_glob(logs_root, "live_book_ticks")}', union_by_name=true)
            """,
        )
    return report


def format_text_report(report: dict[str, Any]) -> str:
    lines = [
        f"Log audit: {report['logs_root']}",
        f"Market scope: {report['market_scope']}",
        "",
        "Datasets:",
    ]
    for name, meta in report["datasets"].items():
        lines.append(f"- {name}: files={meta['files']} rows={meta['rows']} size_mb={meta['size_mb']:.1f}")
    if report["health"]:
        h = report["health"]
        lines += [
            "",
            "Health:",
            f"- cycles={h['cycles']} first={h['first_ts']} last={h['last_ts']}",
            f"- avg_fetched_games={h['avg_fetched_games']:.2f} avg_bound_games={h['avg_bound_games']:.2f} avg_live_side_rows={h['avg_live_side_rows']:.2f}",
            f"- zero_bound_game_cycles={h['zero_bound_game_cycles']} zero_side_row_cycles={h['zero_side_row_cycles']} cycles_source_age_gt30={h['cycles_source_age_gt30']}",
        ]
    if report["side_snapshots"]:
        s = report["side_snapshots"]["summary"]
        lines += [
            "",
            "Side snapshots:",
            f"- rows={s['rows']} matches={s['matches']} markets={s['markets']} tokens={s['tokens']}",
            f"- map_equivalent_rows={s['map_equivalent_rows']} explicit_map_winner_rows={s['explicit_map_winner_rows']} series_decider_equivalent_rows={s['series_decider_equivalent_rows']}",
            f"- executable_rows={s['executable_rows']} avg_spread={_fmt(s['avg_spread'])} worst_source_age_sec={_fmt(s['worst_source_age_sec'])}",
            "- by scope:",
        ]
        for row in report["side_snapshots"]["by_scope"]:
            lines.append(
                f"  {row['market_scope']}: rows={row['rows']} matches={row['matches']} markets={row['markets']} executable={row['executable_rows']}"
            )
    if report["rejects"]:
        lines += ["", "Rejects:"]
        for row in report["rejects"]["by_bucket_reason"]:
            lines.append(
                f"- {row['reject_bucket']} / {row['reason']}: rows={row['rows']} matches={row['matches']} markets={row['markets']}"
            )
    if report["books"]:
        b = report["books"]
        lines += [
            "",
            "Books:",
            f"- rows={b['rows']} assets={b['assets']} two_sided_rows={b['two_sided_rows']} null_bid_rows={b['null_bid_rows']} null_ask_rows={b['null_ask_rows']}",
            f"- avg_spread={_fmt(b['avg_spread'])} max_spread={_fmt(b['max_spread'])} avg_refresh_ms={_fmt(b['avg_refresh_ms'])} max_refresh_ms={_fmt(b['max_refresh_ms'])}",
        ]
    return "\n".join(lines)


def add_audit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--market-scope", default="map-equivalent", choices=["map-equivalent"])
    parser.add_argument("--format", default="text", choices=["text", "json"])


def _dataset_meta(path: Path) -> dict[str, Any]:
    files = sorted(path.glob("*.parquet"))
    size = sum(f.stat().st_size for f in files)
    rows = 0
    if files:
        rows = ds.dataset(str(path), format="parquet").count_rows()
    return {"files": len(files), "rows": int(rows), "size_mb": size / 1024 / 1024}


def _columns(path: Path) -> set[str]:
    if not list(path.glob("*.parquet")):
        return set()
    return set(ds.dataset(str(path), format="parquet").schema.names)


def _glob(root: Path, name: str) -> str:
    return str(root / name / "*.parquet")


def _reject_bucket_expr(cols: set[str]) -> str:
    if "reject_bucket" in cols:
        return "coalesce(reject_bucket, 'other')"
    return """
    case
      when reason in ('missing_team_names', 'no_map_number') then 'actionable_data_gap'
      when reason in ('wrong_game_number', 'series_market_without_game3', 'series_market_not_decider', 'unknown_series_length', 'non_target_market') then 'expected_non_target_market'
      else 'other'
    end
    """


def _scope_expr(cols: set[str]) -> str:
    legacy_scope = """
    case
      when market_type = 'child_moneyline'
           and try_cast(nullif(regexp_extract(lower(market_name), '(?:map|game)[ ]*([0-9]+)', 1), '') as integer)
               = try_cast(nullif(current_game_number, '') as integer)
        then 'map_winner_explicit'
      when market_type = 'child_moneyline'
           and try_cast(nullif(current_game_number, '') as integer) is null
        then 'unknown_scope'
      when market_type = 'moneyline'
           and try_cast(nullif(regexp_extract(upper(market_name), 'BO[ ]*([0-9]+)', 1), '') as integer)
               = try_cast(nullif(current_game_number, '') as integer)
        then 'series_decider_equivalent'
      when market_type = 'moneyline'
           and try_cast(nullif(regexp_extract(upper(market_name), 'BO[ ]*([0-9]+)', 1), '') as integer) is null
        then 'unknown_scope'
      else 'non_target_market'
    end
    """
    if "market_scope" in cols:
        return f"coalesce(market_scope, {legacy_scope})"
    return legacy_scope


def _quality_expr(scope_expr: str) -> str:
    return f"""
    ({scope_expr}) in ('map_winner_explicit', 'series_decider_equivalent')
      and source_update_age_sec <= 30
      and abs(book_age_ms) <= 5000
      and book_best_bid is not null
      and book_best_ask is not null
      and book_spread <= 0.10
      and book_ask_size >= 100
    """


def _one(con: duckdb.DuckDBPyConnection, sql: str) -> dict[str, Any]:
    rows = _rows(con, sql)
    return rows[0] if rows else {}


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    return con.execute(sql).fetchdf().to_dict(orient="records")


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)
