#!/usr/bin/env python3
"""
Archive old raw seasons to reduce file count and disk use.
Keeps the current and previous season unpacked; archives the rest as data/raw_archives/{season}.tar.gz.

Usage:
  python scripts/archive_old_seasons.py              # keep last 2 seasons, archive the rest
  python scripts/archive_old_seasons.py --dry-run    # show what would be archived
  python scripts/archive_old_seasons.py --keep 2024-25 2025-26  # explicit keep list

To restore a season later: python scripts/unpack_archived_season.py 2022-23
"""

import argparse
import re
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

# Season dirs are named like 2022-23, 2023-24, etc.
SEASON_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def get_season_dirs():
    """Yield (season_name, path) for each season directory under raw_base."""
    if not RAW_BASE.exists():
        return
    for p in sorted(RAW_BASE.iterdir()):
        if p.is_dir() and not p.name.startswith(".") and SEASON_PATTERN.match(p.name):
            yield p.name, p


def main():
    ap = argparse.ArgumentParser(description="Archive old raw seasons (keep current + previous)")
    ap.add_argument("--dry-run", action="store_true", help="Only print what would be done")
    ap.add_argument("--keep", nargs="+", metavar="SEASON", help="Seasons to keep (e.g. 2024-25 2025-26). Default: last 2 by name.")
    args = ap.parse_args()

    seasons = list(get_season_dirs())
    if not seasons:
        print("No season directories found under", RAW_BASE)
        return 0

    if args.keep:
        keep_set = set(args.keep)
        to_archive = [(s, p) for s, p in seasons if s not in keep_set]
        kept = [s for s, _ in seasons if s in keep_set]
    else:
        # Keep last 2 seasons (current + previous)
        sorted_seasons = [s for s, _ in seasons]
        keep_count = 2
        kept = sorted_seasons[-keep_count:] if len(sorted_seasons) >= keep_count else sorted_seasons
        keep_set = set(kept)
        to_archive = [(s, p) for s, p in seasons if s not in keep_set]

    if not to_archive:
        print("Nothing to archive. Kept seasons:", kept)
        return 0

    ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)

    print("Keeping unpacked:", kept)
    print("To archive:", [s for s, _ in to_archive])
    if args.dry_run:
        for season, path in to_archive:
            print(f"  [dry-run] would archive {path} -> {ARCHIVES_DIR / (season + '.tar.gz')}")
        return 0

    for season, season_path in to_archive:
        archive_path = ARCHIVES_DIR / f"{season}.tar.gz"
        print(f"Archiving {season} -> {archive_path} ...")
        with tarfile.open(archive_path, "w:gz") as tf:
            tf.add(season_path, arcname=season_path.name)
        # Remove unpacked dir only after archive was created successfully
        import shutil
        shutil.rmtree(season_path)
        print(f"  Removed {season_path}")

    print("Done. To restore a season: python scripts/unpack_archived_season.py <season>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
