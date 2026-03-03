"""
Build data-derived league strength per (competition_slug, season).

Aggregates:
- 01_team_season_stats: league-level xG for/against, possession
- 02_match_summary: goals per match, xG per match
- 03_player_season_stats: mean avg_rating (sufficient_minutes only)

Output: data/processed/league_strength.parquet with strength_score (0-1, baseline = 1.0)
and component columns for validation and UI.
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # ---- 01 Team season stats: league aggregates ----
    team_path = PROCESSED_DIR / "01_team_season_stats.parquet"
    if not team_path.exists():
        print(f"Missing {team_path}", file=sys.stderr)
        sys.exit(1)
    team = pd.read_parquet(team_path)
    team["season"] = team["season"].astype(str)
    team["competition_slug"] = team["competition_slug"].astype(str)

    id_cols = ["competition_slug", "season"]
    team_league = team.groupby(id_cols).agg(
        n_teams=("team_name", "nunique"),
        matches_total=("matches_total", "sum"),
        xg_for_total=("xg_for_total", "sum"),
        xg_against_total=("xg_against_total", "sum"),
        possession_avg=("possession_avg", "mean"),
        shots_total=("shots_total", "sum"),
    ).reset_index()
    # Per match (both teams): average xG per team per match = xg_for_total / matches_total (each row is one team-match)
    team_league["xg_for_per_match"] = team_league["xg_for_total"] / team_league["matches_total"].replace(0, np.nan)
    team_league["xg_against_per_match"] = team_league["xg_against_total"] / team_league["matches_total"].replace(0, np.nan)
    team_league["possession_league"] = team_league["possession_avg"]
    team_league = team_league.drop(columns=["xg_for_total", "xg_against_total", "possession_avg"], errors="ignore")

    # ---- 02 Match summary: goals and xG per match ----
    match_path = PROCESSED_DIR / "02_match_summary.parquet"
    if not match_path.exists():
        print(f"Missing {match_path}", file=sys.stderr)
        sys.exit(1)
    ms = pd.read_parquet(match_path)
    ms["season"] = ms["season"].astype(str)
    ms["competition_slug"] = ms["competition_slug"].astype(str)
    ms["total_xg"] = ms["home_xg"].fillna(0) + ms["away_xg"].fillna(0)
    match_league = ms.groupby(id_cols).agg(
        n_matches=("match_id", "nunique"),
        goals_per_match=("total_goals", "mean"),
        xg_per_match=("total_xg", "mean"),
    ).reset_index()

    # ---- 03 Player season stats: mean rating (sufficient minutes) ----
    player_path = PROCESSED_DIR / "03_player_season_stats.parquet"
    if not player_path.exists():
        print(f"Missing {player_path}", file=sys.stderr)
        sys.exit(1)
    pl = pd.read_parquet(player_path)
    pl["season"] = pl["season"].astype(str)
    pl["competition_slug"] = pl["competition_slug"].astype(str)
    pl_sufficient = pl[pl.get("sufficient_minutes", True)].copy() if "sufficient_minutes" in pl.columns else pl
    player_league = pl_sufficient.groupby(id_cols).agg(
        n_players=("player_id", "nunique"),
        avg_rating_league=("avg_rating", "mean"),
        median_rating_league=("avg_rating", "median"),
    ).reset_index()
    if "expectedGoals_per90" in pl_sufficient.columns:
        xg90 = pl_sufficient.groupby(id_cols)["expectedGoals_per90"].mean().reset_index(name="expectedGoals_per90_league")
        player_league = player_league.merge(xg90, on=id_cols, how="left")
    else:
        player_league["expectedGoals_per90_league"] = np.nan

    # ---- Merge ----
    out = team_league.merge(match_league, on=id_cols, how="outer")
    out = out.merge(player_league, on=id_cols, how="outer")

    # ---- Composite strength ----
    # Difficulty/level: higher xg_against_per_match = tougher league. Rating level: higher avg_rating_league = higher level. Pace: goals_per_match.
    # Normalize each component to 0-1 across all league-seasons, then weighted average, then scale so reference (e.g. Premier League 2024-25) = 1.0.
    ref_slug = "england-premier-league"
    ref_season = out["season"].dropna().astype(str).max()  # latest season as default reference

    for col in ["xg_against_per_match", "avg_rating_league", "goals_per_match"]:
        if col not in out.columns:
            continue
        vals = out[col].dropna()
        if len(vals) < 2:
            out[f"{col}_norm"] = 1.0
            continue
        min_v, max_v = vals.min(), vals.max()
        if max_v > min_v:
            out[f"{col}_norm"] = (out[col] - min_v) / (max_v - min_v)
        else:
            out[f"{col}_norm"] = 1.0

    # Composite: equal weight for difficulty (xG against), rating level, and pace
    w1, w2, w3 = 0.4, 0.3, 0.3
    out["_composite_raw"] = (
        w1 * out.get("xg_against_per_match_norm", 0)
        + w2 * out.get("avg_rating_league_norm", 0)
        + w3 * out.get("goals_per_match_norm", 0)
    )
    # Scale to 0-1 with reference = 1.0
    ref_row = out[(out["competition_slug"] == ref_slug) & (out["season"] == ref_season)]
    if not ref_row.empty and ref_row["_composite_raw"].notna().any():
        ref_val = float(ref_row["_composite_raw"].iloc[0])
        if ref_val > 0:
            out["strength_score"] = out["_composite_raw"] / ref_val
        else:
            out["strength_score"] = out["_composite_raw"]
    else:
        # No reference row: use max = 1.0
        mx = out["_composite_raw"].max()
        out["strength_score"] = (out["_composite_raw"] / mx) if pd.notna(mx) and mx > 0 else out["_composite_raw"]
    out["strength_score"] = out["strength_score"].clip(0, 2.0)  # allow slightly above 1.0 for stronger leagues
    out = out.drop(columns=["_composite_raw"], errors="ignore")

    # Drop temporary norm columns for cleaner output (keep component columns)
    out = out.drop(columns=[c for c in out.columns if c.endswith("_norm")], errors="ignore")

    out_path = PROCESSED_DIR / "league_strength.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")
    print(f"  Reference: {ref_slug} {ref_season} -> strength_score = 1.0")


if __name__ == "__main__":
    main()
