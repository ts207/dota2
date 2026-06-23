"""Dataset extraction/loading helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "datasets"


def _safe_extract(zip_path: Path, dest: Path) -> list[Path]:
    extracted: list[Path] = []
    dest = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if not str(target).startswith(str(dest)):
                raise ValueError(f"unsafe zip member path: {member.filename}")
            zf.extract(member, dest)
            extracted.append(target)
    return extracted


def extract_datasets(root: Path = ROOT, dataset_dir: Path = DATASET_DIR) -> dict[str, int]:
    dataset_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for zip_name in [
        "clean_executable_backtest_dataset_20260623.zip",
        "pattern_discovery_dataset_20260623.zip",
    ]:
        zip_path = root / zip_name
        if not zip_path.exists():
            counts[zip_name] = 0
            continue
        counts[zip_name] = len(_safe_extract(zip_path, dataset_dir))
    return counts


def clean_dataset_path(dataset_dir: Path = DATASET_DIR) -> Path:
    return dataset_dir / "clean_executable_backtest_dataset" / "clean_backtest_side_snapshots.parquet"


def pattern_dataset_path(dataset_dir: Path = DATASET_DIR) -> Path:
    return dataset_dir / "pattern_discovery_dataset" / "pattern_snapshots.parquet"


def load_clean_side_snapshots(dataset_dir: Path = DATASET_DIR) -> pd.DataFrame:
    path = clean_dataset_path(dataset_dir)
    if not path.exists():
        raise FileNotFoundError(f"missing clean dataset: {path}")
    return pd.read_parquet(path)


def load_pattern_snapshots(dataset_dir: Path = DATASET_DIR) -> pd.DataFrame:
    path = pattern_dataset_path(dataset_dir)
    if not path.exists():
        raise FileNotFoundError(f"missing pattern dataset: {path}")
    return pd.read_parquet(path)
