from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from dota2bot.logging_store import ParquetAppendLog
from dota2bot.schemas import SIDE_SNAPSHOT_COLUMNS


def test_side_snapshot_log_rejects_extra_columns(tmp_path: Path):
    log = ParquetAppendLog(tmp_path, "side", SIDE_SNAPSHOT_COLUMNS, batch_rows=10)
    with pytest.raises(ValueError):
        log.append({"match_id": "1", "unexpected": True})


def test_side_snapshot_log_writes_exact_columns(tmp_path: Path):
    log = ParquetAppendLog(tmp_path, "side", SIDE_SNAPSHOT_COLUMNS, batch_rows=1)
    row = {col: None for col in SIDE_SNAPSHOT_COLUMNS}
    row["match_id"] = "1"
    row["token_id"] = "tok"
    out = log.append(row)
    assert out is None
    files = list((tmp_path / "side").glob("*.parquet"))
    assert len(files) == 1
    df = pd.read_parquet(files[0])
    assert list(df.columns) == SIDE_SNAPSHOT_COLUMNS
