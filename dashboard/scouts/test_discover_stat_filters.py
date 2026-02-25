"""
Quick test for Discover stat filters: load data, aggregate, apply stat filters, assert.
Run from project root: python -m dashboard.scouts.test_discover_stat_filters
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

from dashboard.utils.data import load_enriched_season_stats, compute_percentiles
from dashboard.utils.scope import filter_to_default_scope

# Replicate aggregate + percentile logic from Discover
AGG_PER90_AND_RATIOS = [
    "expectedGoals_per90", "expectedAssists_per90", "keyPass_per90", "totalTackle_per90",
    "duelWon_per90", "interceptionWon_per90", "ballRecovery_per90", "totalShots_per90",
    "onTargetScoringAttempt_per90", "touches_per90", "aerialWon_per90", "totalPass_per90",
    "pass_accuracy", "pass_accuracy_pct", "duel_win_rate", "aerial_win_rate", "tackle_success_rate",
    "bigChanceCreated_per90", "blockedScoringAttempt_per90", "totalClearance_per90",
    "saves_per90", "goodHighClaim_per90", "savedShotsFromInsideTheBox_per90",
]


def aggregate_one_row_per_player(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "player_id" not in df.columns:
        return df
    group_cols = ["player_id", "season"]
    if "season" not in df.columns:
        group_cols = ["player_id"]
    idx_primary = df.groupby(group_cols)["total_minutes"].idxmax()
    primary_cols = ["player_id", "season", "player_name", "player_position", "team", "league_name", "age_at_season_start"]
    primary = df.loc[idx_primary, [c for c in primary_cols if c in df.columns]].set_index(group_cols)
    sum_cols = [c for c in ["appearances", "total_minutes", "goals", "assists"] if c in df.columns]
    sums = df.groupby(group_cols)[sum_cols].sum()
    out = primary.join(sums, how="left")
    if "avg_rating" in df.columns and "total_minutes" in df.columns:
        r = df.assign(_w=df["avg_rating"] * df["total_minutes"]).groupby(group_cols).agg(
            _sum_w=("_w", "sum"), _mins=("total_minutes", "sum")
        )
        out = out.join((r["_sum_w"] / r["_mins"].replace(0, np.nan)).to_frame(name="avg_rating"), how="left")
    if "total_minutes" in out.columns and "goals" in out.columns:
        mins = out["total_minutes"].astype(float).replace(0, np.nan)
        out["goals_per90"] = 90 * out["goals"] / mins
    for col in AGG_PER90_AND_RATIOS:
        if col not in df.columns or "total_minutes" not in df.columns:
            continue
        tmp = df.assign(_w=df[col].fillna(0) * df["total_minutes"]).groupby(group_cols).agg(
            _wx=("_w", "sum"), _mins=("total_minutes", "sum")
        )
        out[col] = tmp["_wx"] / tmp["_mins"].replace(0, np.nan)
    out = out.reset_index()
    return out


def apply_stat_filters(df: pd.DataFrame, raw_filters: list, pct_filters: list) -> pd.DataFrame:
    out = df
    for rule in raw_filters:
        stat = rule.get("stat")
        if not stat or stat not in out.columns:
            continue
        min_val, max_val = rule.get("min"), rule.get("max")
        if min_val is not None:
            out = out[out[stat].fillna(-np.inf) >= min_val]
        if max_val is not None:
            out = out[out[stat].fillna(np.inf) <= max_val]
    for rule in pct_filters:
        stat = rule.get("stat")
        pct_col = f"{stat}_pct" if stat else None
        if not pct_col or pct_col not in out.columns:
            continue
        min_pct, max_pct = rule.get("min_pct"), rule.get("max_pct")
        if min_pct is not None and min_pct > 0:
            out = out[out[pct_col].fillna(-1) >= min_pct]
        if max_pct is not None and max_pct < 100:
            out = out[out[pct_col].fillna(101) <= max_pct]
    return out


def main():
    print("Loading data...")
    df_all = load_enriched_season_stats()
    if df_all.empty:
        print("SKIP: No data (run pipeline first)")
        return 0

    df_filtered = filter_to_default_scope(df_all)
    df_agg = aggregate_one_row_per_player(df_filtered)
    if not df_agg.empty and "player_position" in df_agg.columns:
        pct_group = ["season", "player_position"] if "season" in df_agg.columns else ["player_position"]
        pct_stats = [
            c for c in [
                "avg_rating", "goals_per90", "expectedGoals_per90", "expectedAssists_per90",
                "keyPass_per90", "totalTackle_per90", "duelWon_per90", "totalShots_per90",
                "pass_accuracy_pct", "duel_win_rate",
            ]
            if c in df_agg.columns
        ]
        if pct_stats:
            df_agg = compute_percentiles(df_agg, pct_group, pct_stats)

    n_before = len(df_agg)
    print(f"Aggregated rows (before stat filters): {n_before}")

    # Test 1: no filters -> unchanged
    out = apply_stat_filters(df_agg, [], [])
    assert len(out) == n_before, "No filters should leave df unchanged"
    print("  OK: No filters -> unchanged")

    # Test 2: raw min filter (xG/90 >= 0.3) if column exists
    if "expectedGoals_per90" in df_agg.columns:
        raw_filters = [{"stat": "expectedGoals_per90", "min": 0.3, "max": None}]
        out = apply_stat_filters(df_agg, raw_filters, [])
        assert len(out) <= n_before
        if len(out) > 0:
            assert (out["expectedGoals_per90"] >= 0.3).all(), "All rows should have xG/90 >= 0.3"
        print(f"  OK: xG/90 >= 0.3 -> {len(out)} rows (all have xG/90 >= 0.3)")
    else:
        print("  SKIP: expectedGoals_per90 not in df_agg")

    # Test 3: percentile filter (e.g. avg_rating_pct >= 80)
    if "avg_rating_pct" in df_agg.columns:
        pct_filters = [{"stat": "avg_rating", "min_pct": 80, "max_pct": 100}]
        out = apply_stat_filters(df_agg, [], pct_filters)
        assert len(out) <= n_before
        if len(out) > 0:
            assert (out["avg_rating_pct"] >= 80).all()
        print(f"  OK: Rating %ile >= 80 -> {len(out)} rows")
    else:
        print("  SKIP: avg_rating_pct not in df_agg")

    # Test 4: unknown stat -> no change
    out = apply_stat_filters(df_agg, [{"stat": "nonexistent_stat", "min": 1, "max": None}], [])
    assert len(out) == n_before
    print("  OK: Unknown stat -> unchanged")

    print("All stat filter tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
