#!/usr/bin/env python3
"""
Unpack a season from data/raw_archives/{season}.tar.gz back to data/raw/{season}/.
Use this when you need to run the pipeline on an older season that was archived.

Usage:
  python scripts/unpack_archived_season.py 2022-23
  python scripts/unpack_archived_season.py 2023-24
"""

import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
try:
    from src.config import RAW_BASE
except ImportError:
    RAW_BASE = ROOT / "data" / "raw"

ARCHIVES_DIR = ROOT / "data" / "raw_archives"


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/unpack_archived_season.py <season>")
        print("Example: python scripts/unpack_archived_season.py 2022-23")
        return 1
    season = sys.argv[1].strip()
    archive_path = ARCHIVES_DIR / f"{season}.tar.gz"
    if not archive_path.exists():
        print(f"Archive not found: {archive_path}")
        return 1
    RAW_BASE.mkdir(parents=True, exist_ok=True)
    dest = RAW_BASE
    print(f"Unpacking {archive_path} -> {dest}")
    with tarfile.open(archive_path, "r:gz") as tf:
        tf.extractall(dest)
    print(f"Done. data/raw/{season}/ is available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
