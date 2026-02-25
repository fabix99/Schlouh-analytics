#!/usr/bin/env python3
"""
Print full progress table: ALL competitions from scope × all seasons.
Uses data/index/extraction_progress.csv for run data; rows not yet run show —.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE_YAML = ROOT / "config" / "scope.yaml"
PROGRESS_CSV = ROOT / "data" / "index" / "extraction_progress.csv"


def load_scope():
    import yaml
    with open(SCOPE_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    seasons = data.get("seasons", [])
    comps = []
    for realm_key, comps_dict in [("club", data.get("club", {})), ("national", data.get("national", []))]:
        if realm_key == "club" and isinstance(comps_dict, dict):
            for _group, slugs in comps_dict.items():
                comps.extend(slugs)
        elif realm_key == "national" and isinstance(comps_dict, list):
            comps.extend(comps_dict)
    return comps, seasons


def load_progress():
    if not PROGRESS_CSV.exists():
        return {}
    out = {}
    with open(PROGRESS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["competition_slug"], r["season"])
            out[key] = {
                "total": int(r["total"]),
                "extracted": int(r["extracted"]),
                "skipped": int(r["skipped"]),
                "errors": int(r["errors"]),
            }
    return out


def main():
    comps, seasons = load_scope()
    progress = load_progress()

    # Header
    print("FULL EXTRACTION PROGRESS — All scope competitions × seasons")
    print("(— = not run yet; extraction_progress.csv only has runs for the 9 leagues so far)")
    print()
    col_comp = 36
    col_season = 10
    col_total = 8
    col_ext = 10
    col_skip = 8
    col_err = 8
    col_miss = 8
    col_pct = 8
    header = (
        f"{'Competition':<{col_comp}} {'Season':<{col_season}} "
        f"{'Total':>{col_total}} {'Extracted':>{col_ext}} {'Skipped':>{col_skip}} {'Errors':>{col_err}} "
        f"{'Missing':>{col_miss}} {'%':>{col_pct}}"
    )
    print(header)
    print("-" * len(header))

    for comp in comps:
        for season in seasons:
            key = (comp, season)
            p = progress.get(key)
            if p is None:
                total = extracted = skipped = err = missing = "—"
                pct = "—"
            else:
                total = p["total"]
                extracted = p["extracted"]
                skipped = p["skipped"]
                err = p["errors"]
                missing = total - extracted
                pct = (100.0 * extracted / total) if total else 0
                pct = f"{pct:.1f}%"
            print(
                f"{comp:<{col_comp}} {season:<{col_season}} "
                f"{str(total):>{col_total}} {str(extracted):>{col_ext}} {str(skipped):>{col_skip}} {str(err):>{col_err}} "
                f"{str(missing):>{col_miss}} {str(pct):>{col_pct}}"
            )


if __name__ == "__main__":
    main()
