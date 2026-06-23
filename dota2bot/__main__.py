from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .datasets import extract_datasets
from .live_logger import add_live_args, run_live_logger
from .replay_bot import run_replay


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


if __name__ == "__main__":
    main()
