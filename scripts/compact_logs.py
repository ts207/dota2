"""Compact live log directories: merge many tiny part-*.parquet files into one.

Usage:
    python scripts/compact_logs.py [--logs-root logs] [--dry-run] [--min-files 100]

This script is safe to run while the bot is NOT writing (i.e. between sessions).
Do not run it while live-log is active or you may corrupt in-flight part files.

Why:
    live-log flushes a new part-*.parquet every flush_interval_sec (default 60s).
    After days of running this produces tens of thousands of tiny files.
    Every read_parquet(glob) call must open each file individually, loading all
    of them into RAM. Compacting merges them into a single ~64 MB file per table
    so DuckDB can stream-read with minimal memory overhead.
"""

from __future__ import annotations

import argparse
import shutil
import time
from pathlib import Path

import duckdb


TARGET_SIZE_MB = 64  # aim for ~64 MB compressed parts


def compact_dir(path: Path, *, dry_run: bool, min_files: int) -> dict:
    files = sorted(path.glob("part-*.parquet"))
    if len(files) < min_files:
        return {"table": path.name, "files_before": len(files), "skipped": True, "reason": f"< {min_files} files"}

    total_bytes = sum(f.stat().st_size for f in files)
    print(f"  {path.name}: {len(files)} files, {total_bytes / 1_048_576:.1f} MB on disk")

    if dry_run:
        return {"table": path.name, "files_before": len(files), "total_mb": total_bytes / 1_048_576, "skipped": True, "reason": "dry_run"}

    glob = str(path.resolve() / "part-*.parquet")
    tmp = path / f"_compact_{time.time_ns()}.parquet"
    tmp_abs = str(tmp.resolve())
    try:
        con = duckdb.connect()
        # DuckDB only supports ? params for FROM sources, not for COPY TO paths.
        con.execute(
            f"COPY (SELECT * FROM read_parquet(?, union_by_name=true)) "
            f"TO '{tmp_abs}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)",
            [glob],
        )
        compacted_bytes = tmp.stat().st_size
        print(f"    → compacted to {compacted_bytes / 1_048_576:.1f} MB")

        # Rename tmp into place, then delete old parts.
        final = path / f"part-compacted-{time.time_ns()}.parquet"
        tmp.rename(final)
        for f in files:
            f.unlink(missing_ok=True)

        return {
            "table": path.name,
            "files_before": len(files),
            "files_after": 1,
            "before_mb": total_bytes / 1_048_576,
            "after_mb": compacted_bytes / 1_048_576,
            "ratio": total_bytes / compacted_bytes if compacted_bytes else None,
        }
    except Exception as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return {"table": path.name, "files_before": len(files), "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compact live log parquet directories")
    parser.add_argument("--logs-root", default="logs", help="Path to logs root directory")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be done without changing files")
    parser.add_argument("--min-files", type=int, default=100, help="Skip directories with fewer than this many part files")
    parser.add_argument("--tables", nargs="*", default=None, help="Only compact these table names (default: all)")
    args = parser.parse_args()

    logs_root = Path(args.logs_root)
    if not logs_root.exists():
        print(f"ERROR: logs root not found: {logs_root}")
        return

    tables = sorted(d for d in logs_root.iterdir() if d.is_dir())
    if args.tables:
        tables = [t for t in tables if t.name in args.tables]

    print(f"Compacting {len(tables)} table(s) in {logs_root}/ {'[DRY RUN]' if args.dry_run else ''}")
    results = []
    for table_dir in tables:
        result = compact_dir(table_dir, dry_run=args.dry_run, min_files=args.min_files)
        results.append(result)

    print("\n=== Summary ===")
    for r in results:
        if r.get("skipped"):
            print(f"  SKIP  {r['table']}: {r['reason']}")
        elif r.get("error"):
            print(f"  ERROR {r['table']}: {r['error']}")
        else:
            ratio = r.get("ratio")
            ratio_str = f" ({ratio:.1f}x compression)" if ratio else ""
            print(f"  OK    {r['table']}: {r['files_before']} files → 1  |  {r['before_mb']:.1f} MB → {r['after_mb']:.1f} MB{ratio_str}")


if __name__ == "__main__":
    main()
