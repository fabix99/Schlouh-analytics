"""
Build league adjustment factors from transfer analysis.

(1) Loads team lookup from player_appearances.parquet and 03_player_season_stats.parquet.
(2) Runs analyze_transfer_effects (optionally cross-league only).
(3) Computes and saves adjustment factors to data/processed/league_adjustment_factors.json.
(4) Prints sample sizes per (from_comp, to_comp) and a short recommendation.
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR, DERIVED_DIR
from dashboard.utils.projections import (
    analyze_transfer_effects,
    calculate_league_adjustment_factors_from_transfers,
    save_adjustment_factors,
)


def load_team_lookup() -> pd.DataFrame:
    """Build player_id x season x competition_slug -> team from player_appearances."""
    path = DERIVED_DIR / "player_appearances.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path, columns=["player_id", "season", "competition_slug", "team"])
    lookup = (
        df.groupby(["player_id", "season", "competition_slug"])["team"]
        .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "Unknown")
        .reset_index()
    )
    return lookup


def main():
    cross_league_only = "--cross-league" in sys.argv

    team_lookup = load_team_lookup()
    if team_lookup.empty:
        print("No team lookup (player_appearances.parquet missing or empty).", file=sys.stderr)
        sys.exit(1)

    season_stats = pd.read_parquet(PROCESSED_DIR / "03_player_season_stats.parquet")
    season_stats["season"] = season_stats["season"].astype(str)
    season_stats["competition_slug"] = season_stats["competition_slug"].astype(str)
    team_lookup["season"] = team_lookup["season"].astype(str)
    team_lookup["competition_slug"] = team_lookup["competition_slug"].astype(str)

    transfers = analyze_transfer_effects(
        team_lookup=team_lookup,
        season_stats=season_stats,
        min_minutes_before=450,
        min_minutes_after=270,
    )
    if transfers.empty:
        print("No transfers inferred (zero records after filters).")
        save_adjustment_factors({}, filepath=str(ROOT / "data/processed/league_adjustment_factors.json"))
        print("Wrote empty league_adjustment_factors.json")
        return

    if cross_league_only:
        transfers = transfers[transfers["from_comp"] != transfers["to_comp"]].copy()
        print(f"Cross-league transfers only: {len(transfers)} records")
    else:
        print(f"All transfers (including same league): {len(transfers)} records")

    # Sample sizes per (from_comp, to_comp)
    counts = transfers.groupby(["from_comp", "to_comp"]).size().reset_index(name="n")
    counts = counts.sort_values("n", ascending=False)
    print("\nSample sizes (from_comp -> to_comp):")
    print(counts.to_string(index=False))
    cross = counts[counts["from_comp"] != counts["to_comp"]]
    if cross.empty:
        print("\nNo cross-league pairs with data. Recommendation: use static or data-derived league strength for projections; transfer factors insufficient.")
    else:
        print(f"\nCross-league pairs with data: {len(cross)} (total moves: {cross['n'].sum()})")

    stat_columns = ["avg_rating", "goals_per90", "assists_per90", "expectedGoals_per90", "expectedAssists_per90"]
    stat_columns = [c for c in stat_columns if f"before_{c}" in transfers.columns]
    if not stat_columns:
        stat_columns = ["avg_rating", "goals_per90", "assists_per90"]

    position_column = "before_player_position" if "before_player_position" in transfers.columns else None
    if position_column:
        factors = calculate_league_adjustment_factors_from_transfers(
            transfers, stat_columns=stat_columns, position_column=position_column
        )
    else:
        factors = calculate_league_adjustment_factors_from_transfers(
            transfers, stat_columns=stat_columns
        )

    out_path = ROOT / "data/processed/league_adjustment_factors.json"
    save_adjustment_factors(factors, filepath=str(out_path))
    print(f"\nWrote {len(factors)} adjustment factors to {out_path}")

    if len(cross) < 5 or cross["n"].sum() < 50:
        print("Recommendation: few cross-league transfers; prefer data-derived league_strength.parquet or static LEAGUE_QUALITY_SCORES for projections; use transfer factors only when both from_comp and to_comp have enough moves.")
    else:
        print("Recommendation: consider using transfer factors in project_stat_to_baseline when a factor exists for (from_comp, to_comp, stat), else fall back to quality-ratio.")


if __name__ == "__main__":
    main()
