"""Small repo-local supervisor for the paper-validation runtime loops."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paper_strategy_logger import DEFAULT_MODEL_ARTIFACT_DIR, validate_paper_model_artifact
from .paper_exit_logger import DEFAULT_OUTPUT_NAME as DEFAULT_EXIT_OUTPUT_NAME
from .strategy_contract import ACTIVE_PAPER_DECISIONS_NAME, ACTIVE_SETTLED_PAPER_DECISIONS_NAME


@dataclass(frozen=True)
class RuntimeProcess:
    name: str
    pid_file: str
    log_file: str
    args: tuple[str, ...]


def runtime_processes(logs_root: Path) -> tuple[RuntimeProcess, ...]:
    logs = str(logs_root)
    return (
        RuntimeProcess(
            name="live-log",
            pid_file="live_logger.pid",
            log_file="live_logger.out",
            args=(
                sys.executable,
                "-m",
                "dota2bot",
                "live-log",
                "--discover-dota",
                "--logs-root",
                logs,
                "--flush-interval-sec",
                "60",
            ),
        ),
        RuntimeProcess(
            name="settle-live",
            pid_file="settle_live.pid",
            log_file="settle_live.out",
            args=(
                sys.executable,
                "-m",
                "dota2bot",
                "settle-live",
                "--logs-root",
                logs,
                "--loop",
                "--interval-sec",
                "120",
            ),
        ),
        RuntimeProcess(
            name="paper-log",
            pid_file="paper_log.pid",
            log_file="paper_log.out",
            args=(
                sys.executable,
                "-m",
                "dota2bot",
                "paper-log",
                "--logs-root",
                logs,
                "--output-name",
                ACTIVE_PAPER_DECISIONS_NAME,
                "--loop",
                "--interval-sec",
                "300",
            ),
        ),
        RuntimeProcess(
            name="settle-decisions",
            pid_file="settle_decisions.pid",
            log_file="settle_decisions.out",
            args=(
                sys.executable,
                "-m",
                "dota2bot",
                "settle-decisions",
                "--logs-root",
                logs,
                "--decisions-name",
                ACTIVE_PAPER_DECISIONS_NAME,
                "--output-name",
                ACTIVE_SETTLED_PAPER_DECISIONS_NAME,
                "--loop",
                "--interval-sec",
                "300",
            ),
        ),
        RuntimeProcess(
            name="paper-position-log",
            pid_file="paper_position_log.pid",
            log_file="paper_position_log.out",
            args=(
                sys.executable,
                "-m",
                "dota2bot",
                "paper-position-log",
                "--logs-root",
                logs,
                "--input-name",
                ACTIVE_SETTLED_PAPER_DECISIONS_NAME,
                "--output-name",
                "paper_positions",
                "--mode",
                "rebuild",
                "--loop",
                "--interval-sec",
                "300",
            ),
        ),
        RuntimeProcess(
            name="paper-exit-log",
            pid_file="paper_exit_log.pid",
            log_file="paper_exit_log.out",
            args=(
                sys.executable,
                "-m",
                "dota2bot",
                "paper-exit-log",
                "--logs-root",
                logs,
                "--input-name",
                "paper_positions",
                "--output-name",
                DEFAULT_EXIT_OUTPUT_NAME,
                "--loop",
                "--interval-sec",
                "300",
            ),
        ),
    )


def run_runtime_command(*, action: str, logs_root: Path = Path("logs"), wait_sec: float = 2.0) -> dict[str, Any]:
    logs_root.mkdir(parents=True, exist_ok=True)
    processes = runtime_processes(logs_root)
    if action == "status":
        return {"action": action, "processes": [_status(process, logs_root) for process in processes]}
    if action == "start":
        artifact = validate_paper_model_artifact(artifact_dir=DEFAULT_MODEL_ARTIFACT_DIR)
        return {"action": action, "artifact": artifact, "processes": [_start(process, logs_root) for process in processes]}
    if action == "stop":
        return {"action": action, "processes": [_stop(process, logs_root, wait_sec=wait_sec) for process in processes]}
    if action == "restart":
        artifact = validate_paper_model_artifact(artifact_dir=DEFAULT_MODEL_ARTIFACT_DIR)
        stopped = [_stop(process, logs_root, wait_sec=wait_sec) for process in processes]
        started = [_start(process, logs_root) for process in processes]
        return {"action": action, "artifact": artifact, "stopped": stopped, "processes": started}
    raise ValueError(f"unknown runtime action: {action}")


def add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("action", choices=["start", "stop", "restart", "status"])
    parser.add_argument("--logs-root", default="logs")
    parser.add_argument("--wait-sec", type=float, default=2.0)


def format_runtime_result(result: dict[str, Any], *, output_format: str = "json") -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, sort_keys=True)
    rows = result.get("processes", [])
    lines = [f"runtime {result.get('action')}"]
    for row in rows:
        state = "running" if row.get("running") else "stopped"
        lines.append(f"{row.get('name')}: {state} pid={row.get('pid')}")
    return "\n".join(lines)


def _start(process: RuntimeProcess, logs_root: Path) -> dict[str, Any]:
    current = _status(process, logs_root)
    if current["running"]:
        current["changed"] = False
        return current
    log_path = logs_root / process.log_file
    with log_path.open("ab") as log_fh:
        child = subprocess.Popen(
            process.args,
            cwd=Path.cwd(),
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    _pid_path(process, logs_root).write_text(str(child.pid), encoding="utf-8")
    row = _status(process, logs_root)
    row["changed"] = True
    return row


def _stop(process: RuntimeProcess, logs_root: Path, *, wait_sec: float) -> dict[str, Any]:
    pid = _read_pid(process, logs_root)
    if pid is None:
        return {"name": process.name, "pid": None, "running": False, "changed": False}
    if not _is_running(pid):
        return {"name": process.name, "pid": pid, "running": False, "changed": False}
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return {"name": process.name, "pid": pid, "running": False, "changed": False}
    deadline = time.monotonic() + wait_sec
    while time.monotonic() < deadline:
        if not _is_running(pid):
            return {"name": process.name, "pid": pid, "running": False, "changed": True}
        time.sleep(0.1)
    if _is_running(pid):
        os.killpg(pid, signal.SIGKILL)
    return {"name": process.name, "pid": pid, "running": _is_running(pid), "changed": True}


def _status(process: RuntimeProcess, logs_root: Path) -> dict[str, Any]:
    pid = _read_pid(process, logs_root)
    return {
        "name": process.name,
        "pid": pid,
        "running": bool(pid is not None and _is_running(pid)),
        "pid_file": str(_pid_path(process, logs_root)),
        "log_file": str(logs_root / process.log_file),
        "args": list(process.args),
    }


def _read_pid(process: RuntimeProcess, logs_root: Path) -> int | None:
    path = _pid_path(process, logs_root)
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _pid_path(process: RuntimeProcess, logs_root: Path) -> Path:
    return logs_root / process.pid_file


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
