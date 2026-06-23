"""Parquet append logs with strict schema normalization."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from .schemas import DECISION_COLUMNS, LIVE_BINDING_REJECT_COLUMNS, LIVE_BOOK_COLUMNS, LIVE_GAME_COLUMNS, LIVE_HEALTH_COLUMNS, SIDE_SNAPSHOT_COLUMNS


class ParquetAppendLog:
    def __init__(self, root: Path, name: str, columns: list[str], batch_rows: int = 5000):
        self.path = root / name
        self.columns = columns
        self.batch_rows = batch_rows
        self._buffer: list[dict] = []
        self.path.mkdir(parents=True, exist_ok=True)

    def append(self, row: Mapping) -> None:
        normalized = {col: row.get(col) for col in self.columns}
        extra = sorted(set(row.keys()) - set(self.columns))
        if extra:
            raise ValueError(f"unexpected columns for {self.path.name}: {extra[:10]}")
        self._buffer.append(normalized)
        if len(self._buffer) >= self.batch_rows:
            self.flush()

    def extend(self, rows: Iterable[Mapping]) -> None:
        for row in rows:
            self.append(row)

    def flush(self) -> Path | None:
        if not self._buffer:
            return None
        out = self.path / f"part-{time.time_ns()}.parquet"
        df = pd.DataFrame(self._buffer, columns=self.columns)
        df.to_parquet(out, index=False, compression="zstd")
        self._buffer.clear()
        return out


class BotLogs:
    def __init__(self, root: Path = Path("logs"), batch_rows: int = 5000):
        root.mkdir(parents=True, exist_ok=True)
        self.side_snapshots = ParquetAppendLog(
            root=root,
            name="clean_side_snapshots",
            columns=SIDE_SNAPSHOT_COLUMNS,
            batch_rows=batch_rows,
        )
        self.decisions = ParquetAppendLog(
            root=root,
            name="strategy_decisions",
            columns=DECISION_COLUMNS,
            batch_rows=batch_rows,
        )
        self.live_book_ticks = ParquetAppendLog(
            root=root,
            name="live_book_ticks",
            columns=LIVE_BOOK_COLUMNS,
            batch_rows=batch_rows,
        )
        self.live_game_snapshots = ParquetAppendLog(
            root=root,
            name="live_game_snapshots",
            columns=LIVE_GAME_COLUMNS,
            batch_rows=batch_rows,
        )
        self.live_side_snapshots = ParquetAppendLog(
            root=root,
            name="live_side_snapshots",
            columns=SIDE_SNAPSHOT_COLUMNS,
            batch_rows=batch_rows,
        )
        self.live_health = ParquetAppendLog(
            root=root,
            name="live_health",
            columns=LIVE_HEALTH_COLUMNS,
            batch_rows=batch_rows,
        )
        self.live_binding_rejects = ParquetAppendLog(
            root=root,
            name="live_binding_rejects",
            columns=LIVE_BINDING_REJECT_COLUMNS,
            batch_rows=batch_rows,
        )

    def flush(self) -> None:
        self.side_snapshots.flush()
        self.decisions.flush()
        self.live_book_ticks.flush()
        self.live_game_snapshots.flush()
        self.live_side_snapshots.flush()
        self.live_health.flush()
        self.live_binding_rejects.flush()
