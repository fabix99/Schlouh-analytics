#!/usr/bin/env python3
"""
Assess data gaps vs plan using data/index/extraction_progress.csv.
Plan = total matches per (competition_slug, season). Have = extracted.
Output: per league, per competition/season, and overall.
"""
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent.parent
PROGRESS_CSV = ROOT / "data" / "index" / "extraction_progress.csv"

# Human-readable league names
LEAGUE_NAMES = {
    "spain-laliga": "Spain La Liga",
    "england-premier-league": "England Premier League",
    "italy-serie-a": "Italy Serie A",
    "france-ligue-1": "France Ligue 1",
    "germany-bundesliga": "Germany Bundesliga",
    "portugal-primeira-liga": "Portugal Primeira Liga",
    "belgium-pro-league": "Belgium Pro League",
    "netherlands-eredivisie": "Netherlands Eredivisie",
    "turkey-super-lig": "Turkey Super Lig",
}


def main():
    if not PROGRESS_CSV.exists():
        print(f"Not found: {PROGRESS_CSV}")
        return

    rows = []
    with open(PROGRESS_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            total = int(r["total"])
            extracted = int(r["extracted"])
            skipped = int(r["skipped"])
            errors = int(r["errors"])
            missing = total - extracted
            pct = (100.0 * extracted / total) if total else 0
            rows.append({
                "competition_slug": r["competition_slug"],
                "season": r["season"],
                "total": total,
                "extracted": extracted,
                "skipped": skipped,
                "errors": errors,
                "missing": missing,
                "pct": pct,
            })

    # Deduplicate by (competition_slug, season) — keep last
    seen = {}
    for r in rows:
        key = (r["competition_slug"], r["season"])
        seen[key] = r
    rows = list(seen.values())

    # Sort by league then season
    rows.sort(key=lambda r: (r["competition_slug"], r["season"]))

    # --- Per competition/season ---
    print("=" * 80)
    print("DATA GAP ASSESSMENT (Plan vs Extracted)")
    print("Source: data/index/extraction_progress.csv")
    print("Missing = total - extracted (skipped + errors are not yet in your data)")
    print("=" * 80)

    print("\n--- Per competition & season ---\n")
    print(f"{'League':<28} {'Season':<10} {'Total':>8} {'Extracted':>10} {'Missing':>8} {'%':>8}  Notes")
    print("-" * 90)

    for r in rows:
        name = LEAGUE_NAMES.get(r["competition_slug"], r["competition_slug"])
        notes = ""
        if r["errors"] > 0:
            notes = f" ({r['errors']} errors)"
        elif r["skipped"] > 0 and r["extracted"] == 0:
            notes = " (all skipped)"
        print(f"{name:<28} {r['season']:<10} {r['total']:>8} {r['extracted']:>10} {r['missing']:>8} {r['pct']:>7.1f}%{notes}")

    # --- Per league (competition) ---
    from collections import defaultdict
    by_league = defaultdict(lambda: {"total": 0, "extracted": 0, "missing": 0})
    for r in rows:
        c = r["competition_slug"]
        by_league[c]["total"] += r["total"]
        by_league[c]["extracted"] += r["extracted"]
        by_league[c]["missing"] += r["missing"]

    print("\n--- Per league (all seasons) ---\n")
    print(f"{'League':<32} {'Total':>10} {'Extracted':>10} {'Missing':>10} {'%':>8}")
    print("-" * 75)

    for comp in sorted(by_league.keys()):
        d = by_league[comp]
        name = LEAGUE_NAMES.get(comp, comp)
        pct = (100.0 * d["extracted"] / d["total"]) if d["total"] else 0
        print(f"{name:<32} {d['total']:>10} {d['extracted']:>10} {d['missing']:>10} {pct:>7.1f}%")

    # --- Overall ---
    total_all = sum(r["total"] for r in rows)
    extracted_all = sum(r["extracted"] for r in rows)
    missing_all = total_all - extracted_all
    pct_all = (100.0 * extracted_all / total_all) if total_all else 0

    print("\n--- Overall ---\n")
    print(f"  Planned (total matches):  {total_all:,}")
    print(f"  Extracted (have):        {extracted_all:,}")
    print(f"  Missing:                 {missing_all:,}")
    print(f"  Coverage:                {pct_all:.1f}%")


if __name__ == "__main__":
    main()
