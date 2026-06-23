from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .audit_logs import add_audit_args, run_audit_logs
from .datasets import extract_datasets
from .live_logger import add_live_args, run_live_logger
from .replay_bot import run_replay
from .settle_live import add_settle_args, run_settle_live, run_settle_live_loop


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    load_env_file(Path(".env"))

    parser = argparse.ArgumentParser(prog="dota2bot")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("extract", help="extract local dataset zips into datasets/")

    replay = sub.add_parser("replay", help="replay clean executable dataset and log rows")
    replay.add_argument("--limit", type=int, default=None)
    replay.add_argument("--logs-root", default="logs")

    live = sub.add_parser("live-log", help="log live Polymarket books and optional Steam TopLive state")
    add_live_args(live)

    audit = sub.add_parser("audit-logs", help="summarize live parquet log quality")
    add_audit_args(audit)

    settle = sub.add_parser("settle-live", help="join final match outcomes into live side snapshots")
    add_settle_args(settle)

    args = parser.parse_args()
    if args.command == "extract":
        print(json.dumps(extract_datasets(), indent=2, sort_keys=True))
    elif args.command == "replay":
        result = run_replay(limit=args.limit, logs_root=Path(args.logs_root))
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "live-log":
        import asyncio

        result = asyncio.run(
            run_live_logger(
                markets_path=Path(args.markets),
                logs_root=Path(args.logs_root),
                interval_sec=args.interval_sec,
                once=args.once,
                book_only=args.book_only,
                max_tokens=args.max_tokens,
                discover_dota=args.discover_dota,
                discover_active=args.discover_active,
            )
        )
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "audit-logs":
        print(
            run_audit_logs(
                logs_root=Path(args.logs_root),
                market_scope=args.market_scope,
                output_format=args.format,
            )
        )
    elif args.command == "settle-live":
        if args.loop:
            run_settle_live_loop(
                logs_root=Path(args.logs_root),
                output_name=args.output_name,
                outcomes_name=args.outcomes_name,
                concurrency=args.concurrency,
                interval_sec=args.interval_sec,
            )
            return
        print(
            json.dumps(
                run_settle_live(
                    logs_root=Path(args.logs_root),
                    output_name=args.output_name,
                    outcomes_name=args.outcomes_name,
                    concurrency=args.concurrency,
                ),
                indent=2,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
