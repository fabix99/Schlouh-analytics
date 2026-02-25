"""
Step 11: Player performance vs opponent tier (top/mid/bottom third by xg_against).
Output: data/processed/11_player_opponent_context.parquet
"""

import sys
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import DERIVED_DIR, PROCESSED_DIR, INDEX_DIR


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    app = pd.read_parquet(DERIVED_DIR / "player_appearances.parquet")
    team_stats = pd.read_parquet(PROCESSED_DIR / "01_team_season_stats.parquet")
    if "xg_against_total" not in team_stats.columns:
        print("01_team_season_stats has no xg_against_total, skipping opponent context")
        pd.DataFrame().to_parquet(PROCESSED_DIR / "11_player_opponent_context.parquet", index=False)
        return
    app["match_id"] = app["match_id"].astype(str)
    matches = pd.read_csv(INDEX_DIR / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)
    app = app.merge(matches[["match_id", "home_team_name", "away_team_name", "season", "competition_slug"]], on=["match_id"], how="left", suffixes=("", "_m"))
    app["opponent"] = np.where(app["side"] == "home", app["away_team_name"], app["home_team_name"])
    def tier_competition(group):
        """
        Assign opponent strength tier per competition-season.
        Primary: qcut into top/mid/bottom thirds (requires >= 3 distinct values).
        Fallback for small competitions: binary split above/below median
        (top_third / bottom_third only, no mid_third).
        """
        vals = group.dropna()
        if len(vals) < 2:
            return pd.Series(np.nan, index=group.index)
        if vals.nunique() >= 3 and len(vals) >= 3:
            try:
                cut = pd.qcut(vals, 3, labels=["top_third", "mid_third", "bottom_third"], duplicates="drop")
                result = pd.Series(np.nan, index=group.index, dtype=object)
                result.loc[cut.index] = cut.values.astype(object)
                return result
            except Exception:
                pass
        # Fallback: binary split on median (covers competitions with < 3 unique xg values)
        med = vals.median()
        result = pd.Series(np.nan, index=group.index, dtype=object)
        result.loc[vals.index] = np.where(vals > med, "top_third", "bottom_third")
        return result

    team_stats["tier"] = team_stats.groupby(["season", "competition_slug"])["xg_against_total"].transform(tier_competition)
    opp_tier = team_stats[["team_name", "season", "competition_slug", "tier"]].rename(columns={"team_name": "opponent"})
    app = app.merge(opp_tier, on=["opponent", "season", "competition_slug"], how="left")
    app = app.rename(columns={"tier": "opponent_tier"})
    rows = []
    for (player_id, player_name, position, season, competition_slug, opponent_tier), g in app.groupby(["player_id", "player_name", "player_position", "season", "competition_slug", "opponent_tier"]):
        if pd.isna(opponent_tier):
            continue
        mins = g["stat_minutesPlayed"].fillna(0).sum()
        if mins < 90:
            continue
        rows.append({
            "player_id": player_id,
            "player_name": player_name,
            "player_position": position,
            "season": season,
            "competition_slug": competition_slug,
            "opponent_tier": opponent_tier,
            "n_appearances": len(g),
            "avg_rating": g["stat_rating"].mean(),
            "goals": g["stat_goals"].sum() if "stat_goals" in g.columns else 0,
            "xg_total": g["stat_expectedGoals"].sum() if "stat_expectedGoals" in g.columns else np.nan,
            "xg_per90": (g["stat_expectedGoals"].sum() / mins * 90) if "stat_expectedGoals" in g.columns and mins else np.nan,
            "key_passes_per90": (g["stat_keyPass"].sum() / mins * 90) if "stat_keyPass" in g.columns and mins else np.nan,
            "tackles_per90": (g["stat_totalTackle"].sum() / mins * 90) if "stat_totalTackle" in g.columns and mins else np.nan,
        })
    out = pd.DataFrame(rows)
    if out.empty:
        out = pd.DataFrame(columns=["player_id", "player_name", "player_position", "season", "competition_slug", "opponent_tier", "n_appearances", "avg_rating", "goals", "xg_total", "xg_per90", "key_passes_per90", "tackles_per90"])
    out_path = PROCESSED_DIR / "11_player_opponent_context.parquet"
    out.to_parquet(out_path, index=False)
    print(f"Wrote {out_path} ({len(out)} rows)")

    # Player-season summary: rating_vs_top, rating_vs_bottom, big_game_rating_delta
    if not out.empty and "opponent_tier" in out.columns and "avg_rating" in out.columns:
        pivot = out.pivot_table(
            index=["player_id", "player_name", "player_position", "season", "competition_slug"],
            columns="opponent_tier",
            values="avg_rating",
            aggfunc="mean",
        ).reset_index()
        pivot["rating_vs_top"] = pivot["top_third"] if "top_third" in pivot.columns else np.nan
        pivot["rating_vs_bottom"] = pivot["bottom_third"] if "bottom_third" in pivot.columns else np.nan
        pivot["big_game_rating_delta"] = pd.to_numeric(pivot["rating_vs_top"], errors="coerce") - pd.to_numeric(pivot["rating_vs_bottom"], errors="coerce")
        summary_cols = ["player_id", "player_name", "player_position", "season", "competition_slug", "rating_vs_top", "rating_vs_bottom", "big_game_rating_delta"]
        summary = pivot[summary_cols]
        summary_path = PROCESSED_DIR / "11_player_opponent_context_summary.parquet"
        summary.to_parquet(summary_path, index=False)
        print(f"Wrote {summary_path} ({len(summary)} rows)")


if __name__ == "__main__":
    main()
