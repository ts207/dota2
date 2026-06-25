from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .active_strategy_backtest import (
    add_backtest_active_strategy_args,
    format_active_strategy_backtest,
    parse_thresholds,
    run_active_strategy_backtest,
    run_active_strategy_threshold_sweep,
)
from .audit_logs import add_audit_args, run_audit_logs
from .calibration_report import add_paper_calibration_args, run_paper_calibration_report
from .datasets import extract_datasets
from .decision_reports import (
    add_report_decision_args,
    add_settle_decision_args,
    run_report_decisions,
    run_settle_decisions,
    run_settle_decisions_loop,
)
from .live_logger import add_live_args, run_live_logger
from .paper_strategy_logger import (
    add_freeze_paper_model_args,
    add_paper_log_args,
    run_paper_log,
    run_paper_log_loop,
    train_and_save_paper_model_bundle,
)
from .replay_bot import run_replay
from .runtime_supervisor import add_runtime_args, format_runtime_result, run_runtime_command
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

    paper = sub.add_parser("paper-log", help="score live side snapshots into a paper decision ledger")
    add_paper_log_args(paper)

    freeze_paper = sub.add_parser("freeze-paper-model", help="train and save the active paper model artifact")
    add_freeze_paper_model_args(freeze_paper)

    paper_calibration = sub.add_parser("paper-calibration", help="report frozen paper model calibration by ask and edge bucket")
    add_paper_calibration_args(paper_calibration)

    runtime = sub.add_parser("runtime", help="start, stop, restart, or check the bot runtime loops")
    add_runtime_args(runtime)
    runtime.add_argument("--format", choices=["json", "text"], default="json")

    settle_decisions = sub.add_parser("settle-decisions", help="join settled side outcomes into paper decisions")
    add_settle_decision_args(settle_decisions)

    report_decisions = sub.add_parser("report-decisions", help="summarize paper decision performance")
    add_report_decision_args(report_decisions)

    backtest_active = sub.add_parser("backtest-active-strategy", help="simple historical backtest for the single active strategy")
    add_backtest_active_strategy_args(backtest_active)

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
                flush_interval_sec=args.flush_interval_sec,
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
    elif args.command == "paper-log":
        if args.loop:
            run_paper_log_loop(
                logs_root=Path(args.logs_root),
                input_name=args.input_name,
                output_name=args.output_name,
                artifact_dir=Path(args.artifact_dir),
                batch_rows=args.batch_rows,
                signals_only=args.signals_only,
                limit=args.limit,
                min_received_at_ns=args.min_received_at_ns,
                interval_sec=args.interval_sec,
            )
            return
        print(
            json.dumps(
                run_paper_log(
                    logs_root=Path(args.logs_root),
                    input_name=args.input_name,
                    output_name=args.output_name,
                    artifact_dir=Path(args.artifact_dir),
                    batch_rows=args.batch_rows,
                    signals_only=args.signals_only,
                    limit=args.limit,
                    min_received_at_ns=args.min_received_at_ns,
                    force_full_rescore=args.force_full_rescore,
                ),
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "freeze-paper-model":
        print(
            json.dumps(
                train_and_save_paper_model_bundle(
                    executable_path=Path(args.executable_path),
                    artifact_dir=Path(args.artifact_dir),
                ),
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "paper-calibration":
        print(
            run_paper_calibration_report(
                executable_path=Path(args.executable_path),
                artifact_dir=Path(args.artifact_dir),
                eligibility_mode=args.eligibility_mode,
                output_format=args.format,
            )
        )
    elif args.command == "runtime":
        print(
            format_runtime_result(
                run_runtime_command(
                    action=args.action,
                    logs_root=Path(args.logs_root),
                    wait_sec=args.wait_sec,
                ),
                output_format=args.format,
            )
        )
    elif args.command == "settle-decisions":
        if args.loop:
            run_settle_decisions_loop(
                logs_root=Path(args.logs_root),
                decisions_name=args.decisions_name,
                settled_side_name=args.settled_side_name,
                output_name=args.output_name,
                interval_sec=args.interval_sec,
            )
            return
        print(
            json.dumps(
                run_settle_decisions(
                    logs_root=Path(args.logs_root),
                    decisions_name=args.decisions_name,
                    settled_side_name=args.settled_side_name,
                    output_name=args.output_name,
                ),
                indent=2,
                sort_keys=True,
            )
        )
    elif args.command == "report-decisions":
        print(
            run_report_decisions(
                logs_root=Path(args.logs_root),
                decisions_name=args.decisions_name,
                output_format=args.format,
            )
        )
    elif args.command == "backtest-active-strategy":
        thresholds = parse_thresholds(args.thresholds)
        if thresholds is None:
            result = run_active_strategy_backtest(
                executable_path=Path(args.executable_path),
                live_settled_path=Path(args.live_settled_path),
                include_live=not args.no_live,
            )
        else:
            result = run_active_strategy_threshold_sweep(
                thresholds=thresholds,
                executable_path=Path(args.executable_path),
                live_settled_path=Path(args.live_settled_path),
                include_live=not args.no_live,
            )
        print(format_active_strategy_backtest(result, output_format=args.format))


if __name__ == "__main__":
    main()
