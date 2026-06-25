from __future__ import annotations

from pathlib import Path

from dota2bot.runtime_supervisor import RuntimeProcess, run_runtime_command


def test_runtime_status_reports_stopped_for_missing_pid_files(tmp_path: Path):
    result = run_runtime_command(action="status", logs_root=tmp_path)

    assert result["action"] == "status"
    assert len(result["processes"]) == 4
    assert not any(row["running"] for row in result["processes"])


def test_runtime_start_is_idempotent_when_pid_is_running(tmp_path: Path, monkeypatch):
    spec = RuntimeProcess("demo", "demo.pid", "demo.out", ("demo",))
    monkeypatch.setattr("dota2bot.runtime_supervisor.runtime_processes", lambda logs_root: (spec,))
    monkeypatch.setattr("dota2bot.runtime_supervisor._is_running", lambda pid: pid == 12345)
    (tmp_path / "demo.pid").write_text("12345", encoding="utf-8")

    result = run_runtime_command(action="start", logs_root=tmp_path)

    assert result["processes"] == [
        {
            "name": "demo",
            "pid": 12345,
            "running": True,
            "pid_file": str(tmp_path / "demo.pid"),
            "log_file": str(tmp_path / "demo.out"),
            "args": ["demo"],
            "changed": False,
        }
    ]
