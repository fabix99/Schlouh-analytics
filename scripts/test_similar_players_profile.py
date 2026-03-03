"""
Test the EXACT flow the Profile page uses for Similar Players.
Run from project root: python scripts/test_similar_players_profile.py
If this fails or returns empty, the app will too.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    from dashboard.utils.data import load_enriched_season_stats, get_similar_players
    from dashboard.utils.scope import CURRENT_SEASON

    print("1. Loading df_all (same as Profile)...")
    df_all = load_enriched_season_stats()
    print(f"   df_all shape: {df_all.shape}, columns: 'season' in df_all = {'season' in df_all.columns}")

    # Kroos: player_id 26502, 2023-24 row
    player_id = 26502
    kroos = df_all[(df_all["player_id"] == player_id) & (df_all["season"].astype(str).str.contains("2023", na=False))]
    if kroos.empty:
        print("   ERROR: No Kroos 2023-xx row in df_all")
        return 1
    chosen_row = kroos.iloc[0]
    chosen_comp = chosen_row["competition_slug"]
    player_position = chosen_row["player_position"]
    chosen_season = chosen_row["season"]
    print(f"   chosen_season={repr(chosen_season)}, chosen_comp={repr(chosen_comp)}, position={repr(player_position)}")

    # Exact normalization as Profile
    _raw_ref = str(chosen_season).strip() if chosen_season is not None else CURRENT_SEASON
    reference_season = _raw_ref.replace("/", "-") if _raw_ref else CURRENT_SEASON
    print(f"   reference_season (normalized)={repr(reference_season)}")

    # First call: same as Profile with "This league only"
    print("\n2. Calling get_similar_players(season=CURRENT_SEASON, competition_slug=chosen_comp, include_all_leagues=False, reference_season=reference_season)...")
    try:
        similar = get_similar_players(
            player_id=player_id,
            season=CURRENT_SEASON,
            competition_slug=chosen_comp,
            position=player_position,
            df_all=df_all,
            n=3,
            cross_league=False,
            include_all_leagues=False,
            reference_season=reference_season,
        )
        print(f"   Result: type={type(similar)}, empty={similar.empty if similar is not None else 'N/A'}, len={len(similar) if similar is not None and not similar.empty else 0}")
        if similar is not None and not similar.empty:
            print(similar[["player_name", "competition_slug", "similarity_dist"]].to_string())
        else:
            print("   FAIL: returned empty or None")
    except Exception as e:
        print(f"   EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Fallback: All leagues (as Profile does)
    print("\n3. Fallback: get_similar_players(..., include_all_leagues=True)...")
    try:
        similar2 = get_similar_players(
            player_id=player_id,
            season=CURRENT_SEASON,
            competition_slug=chosen_comp,
            position=player_position,
            df_all=df_all,
            n=3,
            cross_league=False,
            include_all_leagues=True,
            reference_season=reference_season,
        )
        print(f"   Result: len={len(similar2) if similar2 is not None and not similar2.empty else 0}")
        if similar2 is not None and not similar2.empty:
            print(similar2[["player_name", "competition_slug", "similarity_dist"]].to_string())
        else:
            print("   FAIL: fallback also empty")
    except Exception as e:
        print(f"   EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n4. Check: seasons in df_all for 2025-26 and position M")
    pool_check = df_all[(df_all["season"].astype(str).str.strip().str.replace("/", "-", regex=False) == CURRENT_SEASON) & (df_all["player_position"] == "M")]
    print(f"   Rows in 2025-26, position M: {len(pool_check)}")
    ref_check = df_all[(df_all["player_id"] == player_id) & (df_all["season"].astype(str).str.strip().str.replace("/", "-", regex=False) == "2023-24")]
    print(f"   Kroos rows in 2023-24: {len(ref_check)}")

    return 0 if (similar is not None and not similar.empty) or (similar2 is not None and not similar2.empty) else 1

if __name__ == "__main__":
    sys.exit(main())
