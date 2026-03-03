"""
Validate static LEAGUE_QUALITY_SCORES against data-derived league strength.

Loads league_strength.parquet and compares ranking by strength_score (and components)
to the order implied by projections.LEAGUE_QUALITY_SCORES. Outputs a report to stdout
and to data/processed/league_strength_validation.txt.
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR

# Avoid pulling in Streamlit via dashboard; replicate minimal lookup
_COMP_NAMES = {
    "spain-laliga": "La Liga",
    "england-premier-league": "Premier League",
    "italy-serie-a": "Serie A",
    "france-ligue-1": "Ligue 1",
    "germany-bundesliga": "Bundesliga",
    "portugal-primeira-liga": "Primeira Liga",
    "belgium-pro-league": "Pro League",
    "netherlands-eredivisie": "Eredivisie",
    "turkey-super-lig": "Süper Lig",
    "saudi-pro-league": "Saudi Pro League",
    "uefa-champions-league": "Champions League",
    "uefa-europa-league": "Europa League",
    "uefa-conference-league": "Conference League",
    "england-league-cup": "League Cup",
}
_LEAGUE_QUALITY_SCORES = {
    "Premier League": 1.00, "La Liga": 0.95, "Bundesliga": 0.93, "Serie A": 0.90,
    "Ligue 1": 0.87, "Primeira Liga": 0.78, "Eredivisie": 0.75, "Pro League": 0.72,
    "Süper Lig": 0.70, "Saudi Pro League": 0.65,
}


def _get_league_quality_score(league: str) -> float:
    if league in _LEAGUE_QUALITY_SCORES:
        return _LEAGUE_QUALITY_SCORES[league]
    for canonical, score in _LEAGUE_QUALITY_SCORES.items():
        if canonical.lower() in (league or "").lower() or (league or "").lower() in canonical.lower():
            return score
    return 0.65


def main():
    strength_path = PROCESSED_DIR / "league_strength.parquet"
    if not strength_path.exists():
        print("Run league_strength.py first.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_parquet(strength_path)
    df["season"] = df["season"].astype(str)
    df["league_name"] = df["competition_slug"].map(_COMP_NAMES).fillna(df["competition_slug"])
    df["static_score"] = df["league_name"].map(lambda n: _get_league_quality_score(n) if pd.notna(n) else np.nan)

    # Use latest season for ranking comparison (or aggregate across seasons)
    latest = df["season"].max()
    ref = df[df["season"] == latest].copy()
    ref = ref.dropna(subset=["strength_score"])
    ref = ref.sort_values("strength_score", ascending=False).reset_index(drop=True)
    ref["rank_data"] = ref.index + 1

    # Static rank: sort by static_score descending
    ref = ref.sort_values("static_score", ascending=False).reset_index(drop=True)
    ref["rank_static"] = ref.index + 1
    # Restore data order for report
    ref = ref.sort_values("strength_score", ascending=False).reset_index(drop=True)

    lines = [
        "League strength validation report",
        "=================================",
        f"Reference season: {latest}",
        f"Leagues in data: {len(ref)}",
        "",
        "Side-by-side: data-derived rank vs static score rank",
        "(Data rank = by strength_score; static rank = by LEAGUE_QUALITY_SCORES)",
        "",
    ]

    # Table: league_name, competition_slug, strength_score, rank_data, static_score, rank_static, rank_diff
    ref["rank_diff"] = ref["rank_data"] - ref["rank_static"]
    ref["rank_diff"] = ref["rank_diff"].astype(int)
    misordered = ref[ref["rank_diff"].abs() > 2]
    well_aligned = ref[ref["rank_diff"].abs() <= 1]

    lines.append(f"{'League':<25} {'slug':<28} {'strength':>8} {'r_data':>7} {'static':>7} {'r_static':>8} {'diff':>5}")
    lines.append("-" * 95)
    for _, row in ref.iterrows():
        name = (row["league_name"] or row["competition_slug"])[:24]
        slug = (row["competition_slug"] or "")[:27]
        lines.append(
            f"{name:<25} {slug:<28} {row['strength_score']:>8.3f} {int(row['rank_data']):>7} {row['static_score']:>7.2f} {int(row['rank_static']):>8} {int(row['rank_diff']):>+5}"
        )

    lines.extend([
        "",
        "Summary",
        "-------",
        f"Leagues with rank difference |diff| <= 1 (well aligned): {len(well_aligned)}",
        f"Leagues with rank difference |diff| > 2 (consider review): {len(misordered)}",
    ])
    if not misordered.empty:
        lines.append("")
        lines.append("Recommended review (static vs data order differs by >2 places):")
        for _, row in misordered.iterrows():
            lines.append(f"  - {row['league_name']} ({row['competition_slug']}): data rank {int(row['rank_data'])}, static rank {int(row['rank_static'])}")

    lines.extend([
        "",
        "Note: strength_score is scaled so england-premier-league in the reference season = 1.0.",
        "Use data-derived strength for these leagues or blend with static; fallback to static for leagues not in league_strength.parquet.",
    ])

    report = "\n".join(lines)
    print(report)

    out_path = PROCESSED_DIR / "league_strength_validation.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
