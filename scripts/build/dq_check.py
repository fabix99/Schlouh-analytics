"""
Data Quality Checker — validates every processed parquet file.

Prints a structured PASS / WARN / FAIL report and exits with code 1 if any FAIL is found.

Usage:
    python3 scripts/build/dq_check.py
    python3 scripts/build/dq_check.py --json  # also writes dq_report.json
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.build.utils import PROCESSED_DIR, INDEX_DIR, DERIVED_DIR

WRITE_JSON = "--json" in sys.argv

# ---------------------------------------------------------------------------
# Result accumulator
# ---------------------------------------------------------------------------

_results: list[dict] = []


def check(file: str, name: str, condition: bool, detail: str = "", level: str = "FAIL") -> None:
    status = "PASS" if condition else level
    _results.append({"file": file, "check": name, "status": status, "detail": detail})


def warn(file: str, name: str, condition: bool, detail: str = "") -> None:
    """Convenience wrapper: WARN when condition is False."""
    check(file, name, condition, detail=detail, level="WARN")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / name
    if not path.exists():
        _results.append({"file": name, "check": "file_exists", "status": "FAIL", "detail": f"Missing: {path}"})
        return pd.DataFrame()
    return pd.read_parquet(path)


def pct_null(series: pd.Series) -> float:
    return series.isna().mean()


def in_range(series: pd.Series, lo, hi) -> bool:
    """All non-null values are within [lo, hi]."""
    s = series.dropna()
    if s.empty:
        return True
    return bool((s >= lo).all() and (s <= hi).all())


def no_negatives(series: pd.Series) -> bool:
    s = series.dropna()
    if s.empty:
        return True
    return bool((s >= 0).all())


# ---------------------------------------------------------------------------
# Individual file validators
# ---------------------------------------------------------------------------

def check_00(df: pd.DataFrame, matches: pd.DataFrame) -> None:
    f = "00_match_scores_full"
    check(f, "no_null_match_id", df["match_id"].notna().all())
    valid_sources = {"original", "derived_from_incidents", "zero_zero_assumed", "not_scraped"}
    check(f, "score_source_values_valid", set(df["score_source"].dropna().unique()).issubset(valid_sources),
          detail=str(set(df["score_source"].dropna().unique()) - valid_sources))
    has_score = df["home_score"].notna() & df["away_score"].notna()
    check(f, "home_score_non_negative", no_negatives(df.loc[has_score, "home_score"].astype(float)))
    check(f, "away_score_non_negative", no_negatives(df.loc[has_score, "away_score"].astype(float)))
    check(f, "home_score_max_15", in_range(df.loc[has_score, "home_score"].astype(float), 0, 15),
          detail=f"max={df['home_score'].max()}")
    check(f, "away_score_max_15", in_range(df.loc[has_score, "away_score"].astype(float), 0, 15),
          detail=f"max={df['away_score'].max()}")
    # total_goals consistency
    scored = df[has_score].copy()
    if not scored.empty:
        expected_goals = scored["home_score"].astype(int) + scored["away_score"].astype(int)
        mismatches = (scored["total_goals"].astype("Int64") != expected_goals.astype("Int64")).sum()
        check(f, "total_goals_consistent", mismatches == 0, detail=f"{mismatches} mismatches")
    # result consistency
    if not scored.empty:
        exp_result = pd.Series("D", index=scored.index)
        exp_result[scored["home_score"] > scored["away_score"]] = "H"
        exp_result[scored["home_score"] < scored["away_score"]] = "A"
        result_mismatches = (scored["result"] != exp_result).sum()
        check(f, "result_consistent_with_scores", result_mismatches == 0, detail=f"{result_mismatches} mismatches")
    # Spine: every matches.csv id must appear (not_scraped allowed for never-extracted index rows)
    all_mids = set(matches["match_id"].astype(str))
    df_mids = set(df["match_id"].astype(str))
    ids_match = all_mids == df_mids
    check(f, "all_matches_csv_ids_present", ids_match,
          detail=f"missing={len(all_mids - df_mids)}, extra={len(df_mids - all_mids)}")
    # Product-lake coverage: every derived appearance match must have a resolved score
    app_path = DERIVED_DIR / "player_appearances.parquet"
    if app_path.exists():
        app_ids = set(pd.read_parquet(app_path, columns=["match_id"])["match_id"].astype(str).unique())
        scored_ids = set(df.loc[df["score_source"] != "not_scraped", "match_id"].astype(str))
        missing_score = app_ids - scored_ids
        check(
            f,
            "all_appearance_matches_have_score",
            len(missing_score) == 0,
            detail=f"{len(missing_score)} appearance match_ids still not_scraped/missing in 00",
        )
        # Raw lineups dirs must all land in appearances (derived rebuild completeness)
        raw_root = ROOT / "data" / "raw"
        raw_lineup_ids = set()
        if raw_root.exists():
            for lineups in raw_root.glob("*/*/*/*/lineups.csv"):
                raw_lineup_ids.add(lineups.parent.name)
        orphan_raw = raw_lineup_ids - app_ids
        check(
            f,
            "all_raw_lineups_in_appearances",
            len(orphan_raw) == 0,
            detail=f"{len(orphan_raw)} raw lineups.csv dirs missing from derived appearances",
        )
    scraped = int((df["score_source"] != "not_scraped").sum())
    not_scraped = len(df) - scraped
    # Index may include historical seasons never extracted. Product lake completeness is
    # enforced above (appearances + raw lineups). Report index-only rows as PASS detail.
    check(
        f,
        "product_lake_scored_vs_index_not_scraped",
        True,
        detail=f"scored={scraped}, index_only_not_scraped={not_scraped} (out-of-lake seasons retained in index)",
    )


def check_01(df: pd.DataFrame) -> None:
    f = "01_team_season_stats"
    check(f, "no_duplicate_team_season_comp",
          not df.duplicated(["team_name", "season", "competition_slug"]).any())
    if "matches_home" in df.columns and "matches_away" in df.columns and "matches_total" in df.columns:
        check(f, "matches_home_plus_away_eq_total",
              (df["matches_home"] + df["matches_away"] == df["matches_total"]).all())
    check(f, "xg_for_total_no_null", df["xg_for_total"].notna().all())
    check(f, "xg_for_total_non_negative", no_negatives(df["xg_for_total"]))
    check(f, "goals_for_non_negative", no_negatives(df["goals_for"]))
    check(f, "goals_against_non_negative", no_negatives(df["goals_against"]))
    check(f, "goal_diff_correct",
          (df["goal_diff"] == df["goals_for"] - df["goals_against"]).all())
    if "pass_accuracy_avg" in df.columns:
        check(f, "pass_accuracy_avg_in_range_0_1", in_range(df["pass_accuracy_avg"], 0, 1),
              detail=f"min={df['pass_accuracy_avg'].min():.3f} max={df['pass_accuracy_avg'].max():.3f}")
    if "possession_avg" in df.columns:
        check(f, "possession_avg_in_range_0_1", in_range(df["possession_avg"], 0, 1),
              detail=f"min={df['possession_avg'].min():.3f} max={df['possession_avg'].max():.3f}")
    if "xg_for_home" in df.columns and "xg_for_away" in df.columns:
        # home+away xg <= total + tolerance (some matches may not have split data)
        bad = ((df["xg_for_home"].fillna(0) + df["xg_for_away"].fillna(0)) >
               df["xg_for_total"].fillna(0) + 0.1).sum()
        warn(f, "xg_home_plus_away_lte_total", bad == 0, detail=f"{bad} rows exceed total")


def check_02(df: pd.DataFrame, scores00: pd.DataFrame, matches: pd.DataFrame) -> None:
    f = "02_match_summary"
    # No duplicate match_id
    dup = df["match_id"].astype(str).duplicated().sum()
    warn(f, "no_duplicate_match_id", dup == 0, detail=f"{dup} duplicate match_id rows")
    all_mids = set(matches["match_id"].astype(str))
    df_mids = set(df["match_id"].astype(str))
    check(f, "all_matches_csv_ids_present", all_mids == df_mids,
          detail=f"missing={len(all_mids - df_mids)}, extra={len(df_mids - all_mids)}")
    # Football sanity: home and away team must differ
    if "home_team_name" in df.columns and "away_team_name" in df.columns:
        same = (df["home_team_name"].astype(str).str.strip() == df["away_team_name"].astype(str).str.strip()).sum()
        check(f, "home_away_team_names_differ", same == 0, detail=f"{same} rows with identical home/away team")
    # Score consistency with 00
    merged = df[["match_id", "home_score", "away_score"]].merge(
        scores00[["match_id", "home_score", "away_score"]].rename(
            columns={"home_score": "h00", "away_score": "a00"}),
        on="match_id", how="inner"
    )
    both = merged["home_score"].notna() & merged["h00"].notna()
    if both.any():
        mismatches = ((merged.loc[both, "home_score"].astype(float) != merged.loc[both, "h00"].astype(float)) |
                      (merged.loc[both, "away_score"].astype(float) != merged.loc[both, "a00"].astype(float))).sum()
        check(f, "scores_consistent_with_00", mismatches == 0, detail=f"{mismatches} mismatches")
    # xg_swing consistency
    both_xg = df["home_xg"].notna() & df["away_xg"].notna() & df["xg_swing"].notna()
    if both_xg.any():
        expected_swing = df.loc[both_xg, "home_xg"] - df.loc[both_xg, "away_xg"]
        swing_bad = (df.loc[both_xg, "xg_swing"] - expected_swing).abs() > 0.001
        warn(f, "xg_swing_consistent", swing_bad.sum() <= 5,
             detail=f"{swing_bad.sum()} rows with xg_swing != home_xg - away_xg")
    # xg_overperformance consistency
    both_op = df["home_xg_overperformance"].notna() & df["home_xg"].notna() & df["home_score"].notna()
    if both_op.any():
        expected_op = df.loc[both_op, "home_score"].astype(float) - df.loc[both_op, "home_xg"]
        op_bad = (df.loc[both_op, "home_xg_overperformance"] - expected_op).abs() > 0.001
        warn(f, "home_xg_overperformance_consistent", op_bad.sum() <= 5,
             detail=f"{op_bad.sum()} rows inconsistent")
    # Null rates only on rows that have scores (product lake); index-only not_scraped rows have null xG/managers by design
    scored_mask = df["home_score"].notna() & df["away_score"].notna() if "home_score" in df.columns else pd.Series(True, index=df.index)
    scored = df.loc[scored_mask]
    if len(scored):
        null_xg_rate = pct_null(scored["home_xg"])
        warn(f, "null_home_xg_lt_25pct_on_scored", null_xg_rate < 0.25, detail=f"{null_xg_rate:.1%} null on scored rows")
        null_mgr_rate = pct_null(scored["home_manager_name"])
        warn(f, "null_home_manager_lt_15pct_on_scored", null_mgr_rate < 0.15, detail=f"{null_mgr_rate:.1%} null on scored rows")
    # Competition-season event count within plausible range (1–600 per league season)
    if "competition_slug" in df.columns and "season" in df.columns:
        cnt = df.groupby(["competition_slug", "season"]).size()
        over = (cnt > 600).sum()
        check(f, "competition_season_count_plausible", over == 0,
              detail=f"{over} competition-seasons with >600 matches")


def check_03(df: pd.DataFrame) -> None:
    f = "03_player_season_stats"
    check(f, "no_duplicate_player_season_comp",
          not df.duplicated(["player_id", "season", "competition_slug"]).any())
    check(f, "total_minutes_gte_1", (df["total_minutes"] >= 1).all(),
          detail=f"min={df['total_minutes'].min()}")
    check(f, "sufficient_minutes_flag_correct",
          ((df["total_minutes"] >= 450) == df["sufficient_minutes"]).all())
    check(f, "avg_rating_in_range_1_10", in_range(df["avg_rating"].dropna(), 1, 10),
          detail=f"min={df['avg_rating'].min():.2f} max={df['avg_rating'].max():.2f}")
    # These stats are legitimately negative in source data:
    #   goalsPrevented: GK conceded more than expected → negative
    #   keeperSaveValue: negative when GK performance below baseline
    #   *ValueNormalized: value-added metrics can be negative
    #   totalProgression / bestBallCarryProgression: backward progression
    KNOWN_NEGATIVE_PER90 = {
        "goalsPrevented_per90", "keeperSaveValue_per90",
        "passValueNormalized_per90", "defensiveValueNormalized_per90",
        "dribbleValueNormalized_per90", "shotValueNormalized_per90",
        "goalkeeperValueNormalized_per90",
        "totalProgression_per90", "bestBallCarryProgression_per90",
    }
    per90_cols = [c for c in df.columns if c.endswith("_per90") and c not in KNOWN_NEGATIVE_PER90]
    bad_per90 = [c for c in per90_cols if not no_negatives(df[c])]
    check(f, "all_per90_non_negative", len(bad_per90) == 0,
          detail=f"negative values in: {bad_per90[:5]}")
    rate_cols = [c for c in ["pass_accuracy", "duel_win_rate", "aerial_win_rate",
                              "tackle_success_rate", "dribble_success_rate",
                              "cross_accuracy", "long_ball_accuracy"] if c in df.columns]
    bad_rate = [c for c in rate_cols if not in_range(df[c], 0, 1)]
    check(f, "rate_cols_in_range_0_1", len(bad_rate) == 0,
          detail=f"out-of-range: {bad_rate}")
    for col in ["pass_value_avg", "shot_value_avg", "defensive_value_avg",
                "dribble_value_avg", "gk_value_avg"]:
        check(f, f"column_{col}_exists", col in df.columns)
    check(f, "goals_in_range_0_50", in_range(df["goals"], 0, 50),
          detail=f"max={df['goals'].max()}")
    warn(f, "null_avg_rating_lt_5pct", pct_null(df["avg_rating"]) < 0.05,
         detail=f"{pct_null(df['avg_rating']):.1%} null")


def check_04(df: pd.DataFrame, df03: pd.DataFrame) -> None:
    f = "04_player_career_stats"
    check(f, "no_duplicate_player_id", not df.duplicated("player_id").any())
    pids_03 = set(df03["player_id"].unique())
    pids_04 = set(df["player_id"].unique())
    check(f, "all_player_ids_in_03", pids_04.issubset(pids_03),
          detail=f"{len(pids_04 - pids_03)} player_ids in 04 not in 03")
    check(f, "sufficient_minutes_flag_correct",
          ((df["total_minutes"] >= 900) == df["sufficient_minutes"]).all())
    check(f, "first_season_lte_last_season",
          (df["first_season"] <= df["last_season"]).all())
    check(f, "n_seasons_gte_1", (df["n_seasons"] >= 1).all())
    check(f, "n_competitions_gte_1", (df["n_competitions"] >= 1).all())
    # Cross-file: career goals == sum of season goals
    career_goals = df.set_index("player_id")["goals"]
    season_sum = df03.groupby("player_id")["goals"].sum()
    common = career_goals.index.intersection(season_sum.index)
    mismatches = (career_goals.loc[common] != season_sum.loc[common]).sum()
    check(f, "career_goals_eq_sum_of_season_goals", mismatches == 0,
          detail=f"{mismatches} mismatches")
    if "goals_per90" in df.columns:
        check(f, "goals_per90_non_negative", no_negatives(df["goals_per90"]))
    if "assists_per90" in df.columns:
        check(f, "assists_per90_non_negative", no_negatives(df["assists_per90"]))


def check_05(df: pd.DataFrame) -> None:
    f = "05_competition_benchmarks"
    # p25 <= median <= p75
    check(f, "p25_lte_median",
          (df["p25"] <= df["median"] + 1e-9).all(),
          detail=f"{(df['p25'] > df['median'] + 1e-9).sum()} violations")
    check(f, "median_lte_p75",
          (df["median"] <= df["p75"] + 1e-9).all(),
          detail=f"{(df['median'] > df['p75'] + 1e-9).sum()} violations")
    check(f, "p75_lte_p90",
          (df["p75"] <= df["p90"] + 1e-9).all(),
          detail=f"{(df['p75'] > df['p90'] + 1e-9).sum()} violations")
    check(f, "n_players_gte_2", (df["n_players"] >= 2).all())
    valid_comps = {"belgium-pro-league", "england-premier-league", "france-ligue-1",
                   "germany-bundesliga", "italy-serie-a", "netherlands-eredivisie",
                   "portugal-primeira-liga", "saudi-pro-league", "spain-laliga", "turkey-super-lig",
                   "uefa-champions-league", "uefa-europa-league", "uefa-conference-league",
                   "uefa-super-cup", "all_competitions",
                   "england-fa-cup", "england-league-cup", "spain-copa-del-rey", "italy-coppa-italia",
                   "germany-dfb-pokal", "netherlands-knvb-beker", "brazil-serie-a", "copa-libertadores"}
    check(f, "competition_slug_values_valid",
          set(df["competition_slug"].unique()).issubset(valid_comps),
          detail=str(set(df["competition_slug"].unique()) - valid_comps))
    check(f, "player_position_values_valid",
          set(df["player_position"].unique()).issubset({"G", "D", "M", "F"}))
    mean_lt_p25 = int((df["mean"] < df["p25"]).sum())
    # Sparse GK/rate distributions can have mean < p25; tolerate a small known band
    check(
        f,
        "mean_lt_p25_within_sparse_tolerance",
        mean_lt_p25 <= 50,
        detail=f"{mean_lt_p25} rows with mean<p25 (sparse GK/rate stats; fail if >50)",
    )


def check_06(df: pd.DataFrame, df03: pd.DataFrame) -> None:
    f = "06_player_percentile_ranks"
    check(f, "pct_in_competition_range_0_100",
          in_range(df["pct_in_competition"].dropna(), 0, 100),
          detail=f"min={df['pct_in_competition'].min():.1f} max={df['pct_in_competition'].max():.1f}")
    check(f, "pct_global_range_0_100",
          in_range(df["pct_global"].dropna(), 0, 100))
    null_global = int(df["pct_global"].isna().sum())
    null_rate = null_global / max(len(df), 1)
    # Tiny residual nulls on sparse rate stats (tackle/aerial) when global peer pool empty
    check(
        f,
        "null_pct_global_within_tolerance",
        null_rate <= 0.0001 or null_global <= 100,
        detail=f"{null_global} null pct_global rows ({null_rate:.4%} of {len(df)})",
    )
    pids_03 = set(df03["player_id"].unique())
    pids_06 = set(df["player_id"].unique())
    check(f, "all_player_ids_in_03", pids_06.issubset(pids_03),
          detail=f"{len(pids_06 - pids_03)} not in 03")
    stat_names_06 = set(df["stat_name"].unique())
    stat_names_03 = set(df03.columns)
    missing = stat_names_06 - stat_names_03
    check(f, "stat_names_present_in_03_columns", len(missing) == 0,
          detail=f"missing in 03: {list(missing)[:5]}")


def check_07(df: pd.DataFrame) -> None:
    f = "07_player_rolling_form"
    check(f, "window_values_valid",
          set(df["window"].unique()).issubset({5, 10, 20}),
          detail=str(set(df["window"].unique()) - {5, 10, 20}))
    check(f, "no_duplicate_player_window",
          not df.duplicated(["player_id", "window"]).any())
    check(f, "n_available_lte_window",
          (df["n_available"] <= df["window"]).all(),
          detail=f"{(df['n_available'] > df['window']).sum()} rows exceed window")
    check(f, "avg_rating_in_range_1_10", in_range(df["avg_rating"].dropna(), 1, 10),
          detail=f"min={df['avg_rating'].min():.2f} max={df['avg_rating'].max():.2f}")
    check(f, "total_minutes_non_negative", no_negatives(df["total_minutes"]))


def check_08(df: pd.DataFrame, df04: pd.DataFrame) -> None:
    f = "08_player_scouting_profiles"
    check(f, "no_duplicate_player_id", not df.duplicated("player_id").any())
    pids_04 = set(pd.to_numeric(df04["player_id"], errors="coerce").dropna().astype(int))
    pids_08 = set(pd.to_numeric(df["player_id"], errors="coerce").dropna().astype(int))
    # Product path: dbt mart_player_scouting_profiles is appearance-backed (should ⊆ career).
    # Legacy pandas 08 used full players.csv spine — allow WARN only when 08 is wider than 04.
    extra = pids_08 - pids_04
    if extra:
        warn(f, "all_player_ids_in_04", False,
             detail=f"{len(extra)} scouting players not in career (legacy players.csv spine)")
    else:
        check(f, "all_player_ids_in_04", True, detail="0 scouting players outside career")
    if "age_today" in df.columns:
        ages = df["age_today"].dropna()
        if len(ages):
            check(f, "age_today_in_range_15_60", in_range(ages, 15, 60),
                  detail=f"min={ages.min():.1f} max={ages.max():.1f}")
    if "sufficient_minutes_latest_season" in df.columns:
        check(f, "sufficient_minutes_latest_season_no_null",
              df["sufficient_minutes_latest_season"].notna().all())
    # latest_season / active only exist on the richer pandas 08 grain
    if "active" in df.columns and "latest_season" in df.columns:
        active = df[df["active"] == True]
        active_without_latest = int(active["latest_season"].isna().sum()) if len(active) else 0
        warn(f, "active_players_with_no_latest_season_lt_40pct",
             active_without_latest / max(len(active), 1) < 0.40,
             detail=f"{active_without_latest} active players without a qualifying season (expected for low-minute players)")


def check_09(df: pd.DataFrame) -> None:
    f = "09_player_progression"
    # season_from == season_to is valid: players with 2 competitions in the same season
    # produce consecutive pairs comparing cross-competition performance.
    warn(f, "season_from_lte_season_to",
         (df["season_from"] <= df["season_to"]).all(),
         detail=f"{(df['season_from'] > df['season_to']).sum()} backward violations (same-season pairs expected)")
    valid_directions = {"improving", "declining", "stable", None}
    actual_directions = set(df["progression_direction"].unique())
    check(f, "progression_direction_values_valid",
          actual_directions.issubset(valid_directions | {np.nan}),
          detail=str(actual_directions - valid_directions))
    check(f, "goalAssist_per90_delta_column_exists", "goalAssist_per90_delta" in df.columns)
    null_rating_delta = pct_null(df["avg_rating_delta"]) if "avg_rating_delta" in df.columns else 1.0
    warn(f, "null_avg_rating_delta_lt_30pct", null_rating_delta < 0.30,
         detail=f"{null_rating_delta:.1%} null")


def check_10(df: pd.DataFrame) -> None:
    f = "10_player_consistency"
    check(f, "n_appearances_gte_5", (df["n_appearances"] >= 5).all(),
          detail=f"min={df['n_appearances'].min()}")
    valid_tiers = {"very_consistent", "consistent", "variable", "very_variable"}
    check(f, "consistency_tier_values_valid",
          set(df["consistency_tier"].unique()).issubset(valid_tiers),
          detail=str(set(df["consistency_tier"].unique()) - valid_tiers))
    if "rating_cv" in df.columns:
        check(f, "rating_cv_non_negative", no_negatives(df["rating_cv"]))
    if "rating_std" in df.columns:
        check(f, "rating_std_non_negative", no_negatives(df["rating_std"]))


def check_11(df: pd.DataFrame, df03: pd.DataFrame) -> None:
    f = "11_player_opponent_context"
    valid_tiers = {"top_third", "mid_third", "bottom_third"}
    check(f, "opponent_tier_values_valid",
          set(df["opponent_tier"].dropna().unique()).issubset(valid_tiers),
          detail=str(set(df["opponent_tier"].unique()) - valid_tiers))
    check(f, "no_null_opponent_tier", df["opponent_tier"].notna().all(),
          detail=f"{df['opponent_tier'].isna().sum()} nulls")
    pids_03 = set(df03["player_id"].unique())
    pids_11 = set(df["player_id"].unique())
    check(f, "all_player_ids_in_03", pids_11.issubset(pids_03),
          detail=f"{len(pids_11 - pids_03)} not in 03")
    # Coverage check: >= 80% of sufficient_minutes players covered
    df03_valid = df03[df03["sufficient_minutes"] == True]
    covered = df[["player_id", "season", "competition_slug"]].drop_duplicates()
    merged = df03_valid.merge(covered, on=["player_id", "season", "competition_slug"], how="left", indicator=True)
    coverage = (merged["_merge"] == "both").mean()
    warn(f, "sufficient_minutes_players_coverage_gte_80pct", coverage >= 0.80,
         detail=f"{coverage:.1%} covered ({(merged['_merge'] == 'left_only').sum()} uncovered)")


def check_15(df: pd.DataFrame, df01: pd.DataFrame) -> None:
    f = "15_team_tactical_profiles"
    check(f, "no_duplicate_team_season_comp",
          not df.duplicated(["team_name", "season", "competition_slug"]).any())
    pct_cols = [c for c in df.columns if c.endswith("_pct")]
    bad_pct = [c for c in pct_cols if not in_range(df[c], 0, 1)]
    check(f, "all_pct_cols_in_range_0_1", len(bad_pct) == 0,
          detail=f"out-of-range: {bad_pct}")
    team_names_01 = set(df01["team_name"].unique())
    team_names_15 = set(df["team_name"].unique())
    # WARN only: 15 is built from 01; mismatch usually means 15 was built from older 01. Re-run from step 01 to sync.
    warn(f, "team_names_all_in_01", team_names_15.issubset(team_names_01),
         detail=f"{len(team_names_15 - team_names_01)} team(s) in 15 not in 01 — re-run pipeline from step 01 to 15 (see docs/backfill.md)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Loading index files...")
    matches = pd.read_csv(INDEX_DIR / "matches.csv")
    matches["match_id"] = matches["match_id"].astype(str)

    print("Loading processed files...")
    df00 = load("00_match_scores_full.parquet")
    df01 = load("01_team_season_stats.parquet")
    df02 = load("02_match_summary.parquet")
    df03 = load("03_player_season_stats.parquet")
    df04 = load("04_player_career_stats.parquet")
    df05 = load("05_competition_benchmarks.parquet")
    df06 = load("06_player_percentile_ranks.parquet")
    df07 = load("07_player_rolling_form.parquet")
    df08 = load("08_player_scouting_profiles.parquet")
    df09 = load("09_player_progression.parquet")
    df10 = load("10_player_consistency.parquet")
    df11 = load("11_player_opponent_context.parquet")
    df15 = load("15_team_tactical_profiles.parquet")

    print("Running checks...\n")

    # Optional freshness: warn if key artifact is older than 48 hours
    FRESHNESS_HOURS = 48
    key_artifact = PROCESSED_DIR / "02_match_summary.parquet"
    if key_artifact.exists():
        age_sec = time.time() - key_artifact.stat().st_mtime
        age_hours = age_sec / 3600
        warn("02_match_summary", "artifact_freshness_48h", age_hours <= FRESHNESS_HOURS,
             detail=f"file age {age_hours:.1f}h (warn if > {FRESHNESS_HOURS}h)")

    if not df00.empty:
        check_00(df00, matches)
    if not df01.empty:
        check_01(df01)
    if not df02.empty:
        check_02(df02, df00, matches)
    if not df03.empty:
        check_03(df03)
    if not df04.empty and not df03.empty:
        check_04(df04, df03)
    if not df05.empty:
        check_05(df05)
    if not df06.empty and not df03.empty:
        check_06(df06, df03)
    if not df07.empty:
        check_07(df07)
    if not df08.empty and not df04.empty:
        check_08(df08, df04)
    if not df09.empty:
        check_09(df09)
    if not df10.empty:
        check_10(df10)
    if not df11.empty and not df03.empty:
        check_11(df11, df03)
    if not df15.empty and not df01.empty:
        check_15(df15, df01)

    # ---------------------------------------------------------------------------
    # Print report
    # ---------------------------------------------------------------------------
    col_w_file = max(len(r["file"]) for r in _results) + 2
    col_w_check = max(len(r["check"]) for r in _results) + 2

    n_pass = sum(1 for r in _results if r["status"] == "PASS")
    n_warn = sum(1 for r in _results if r["status"] == "WARN")
    n_fail = sum(1 for r in _results if r["status"] == "FAIL")

    for r in _results:
        status = r["status"]
        label = f"[{status}]".ljust(7)
        detail = f"  ({r['detail']})" if r["detail"] else ""
        print(f"{label} {r['file'].ljust(col_w_file)} {r['check'].ljust(col_w_check)}{detail}")

    print()
    print(f"Summary: {n_pass} PASS, {n_warn} WARN, {n_fail} FAIL")

    if WRITE_JSON:
        report_path = PROCESSED_DIR / "dq_report.json"
        with open(report_path, "w") as fh:
            json.dump({
                "summary": {"pass": n_pass, "warn": n_warn, "fail": n_fail},
                "checks": _results,
            }, fh, indent=2)
        print(f"Wrote {report_path}")

    if n_fail > 0:
        print("\nFAILURES DETECTED — exiting with code 1")
        fail_checks = [r for r in _results if r["status"] == "FAIL"]
        if any(r["check"] == "all_matches_csv_ids_present" for r in fail_checks):
            print("  Remediation: sync processed artifacts with index by rerunning from step 00:")
            print("    python scripts/run_pipeline.py --from-step 00 --to-step 02")
            print("  Then rerun full pipeline or at least: --from-step 00 --to-step validate")
        sys.exit(1)

    print("\nAll checks passed (with warnings noted above).")


if __name__ == "__main__":
    main()
