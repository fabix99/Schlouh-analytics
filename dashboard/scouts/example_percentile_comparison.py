"""
One-off example: load real data, compute rank vs z-score percentiles,
print a table showing why z-score is more actionable.
Run from project root: python -m dashboard.scouts.example_percentile_comparison
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

from dashboard.utils.data import (
    load_enriched_season_stats,
    compute_percentiles,
    compute_percentiles_zscore,
)
from dashboard.utils.scope import filter_to_default_scope

# Same aggregation as Discover
AGG_PER90_AND_RATIOS = [
    "expectedGoals_per90", "expectedAssists_per90", "keyPass_per90", "totalTackle_per90",
    "duelWon_per90", "totalShots_per90", "pass_accuracy_pct", "duel_win_rate",
]


def aggregate_one_row_per_player(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "player_id" not in df.columns:
        return df
    group_cols = ["player_id", "season"]
    if "season" not in df.columns:
        group_cols = ["player_id"]
    idx_primary = df.groupby(group_cols)["total_minutes"].idxmax()
    primary_cols = ["player_id", "season", "player_name", "player_position", "team", "league_name"]
    primary = df.loc[idx_primary, [c for c in primary_cols if c in df.columns]].set_index(group_cols)
    sum_cols = [c for c in ["total_minutes", "goals", "assists"] if c in df.columns]
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


def main():
    print("Loading data (default scope)...")
    df_all = load_enriched_season_stats()
    if df_all.empty:
        print("No data. Run pipeline first.")
        return
    df_filtered = filter_to_default_scope(df_all)
    df_agg = aggregate_one_row_per_player(df_filtered)

    # Focus on forwards (or midfielders) and stats we care about
    pos = "F"
    if "player_position" not in df_agg.columns:
        print("No player_position in aggregated data.")
        return
    pool = df_agg[df_agg["player_position"] == pos].copy()
    if pool.empty:
        pool = df_agg.copy()  # fallback: all positions
        pos = "all"

    stat_cols = ["avg_rating", "expectedGoals_per90"]
    stat_cols = [c for c in stat_cols if c in pool.columns]
    if not stat_cols:
        print("Missing avg_rating or expectedGoals_per90.")
        return

    # Percentiles within season (and position already filtered to pos)
    group_cols = ["season"] if "season" in pool.columns else ["player_position"]

    pool_rank = compute_percentiles(pool.copy(), group_cols, stat_cols)
    pool_z = compute_percentiles_zscore(pool.copy(), group_cols, stat_cols)

    # Merge so we have both side by side (use suffixes)
    for s in stat_cols:
        pool_rank = pool_rank.rename(columns={f"{s}_pct": f"{s}_rank_pct"})
    pool_z = pool_z[["player_id", "season"] + [f"{s}_pct" for s in stat_cols if f"{s}_pct" in pool_z.columns]]
    pool_z = pool_z.rename(columns={f"{s}_pct": f"{s}_z_pct" for s in stat_cols})
    merged = pool_rank.merge(
        pool_z,
        on=["player_id", "season"],
        how="left",
    )

    # Top by xG/90 (min 500 mins if available)
    if "total_minutes" in merged.columns:
        merged = merged[merged["total_minutes"] >= 500]
    merged = merged.sort_values("expectedGoals_per90", ascending=False).head(14)

    print("\n" + "=" * 100)
    print("EXAMPLE: Why z-score percentiles are more actionable (real data, position =", pos + ")")
    print("=" * 100)
    print("\nSame raw gap (e.g. 1.0 vs 0.5 xG/90) with RANK percentiles is 100 vs 99.")
    print("With Z-SCORE percentiles the gap reflects how much better the top player is.\n")

    rows = []
    for _, r in merged.iterrows():
        name = r.get("player_name", "?")
        rating = r.get("avg_rating")
        xg = r.get("expectedGoals_per90")
        r_rank = r.get("avg_rating_rank_pct")
        r_z = r.get("avg_rating_z_pct")
        xg_rank = r.get("expectedGoals_per90_rank_pct")
        xg_z = r.get("expectedGoals_per90_z_pct")
        rows.append({
            "Player": name[:22],
            "Rating": f"{rating:.2f}" if pd.notna(rating) else "—",
            "xG/90": f"{xg:.2f}" if pd.notna(xg) else "—",
            "Rating (rank %ile)": f"{r_rank:.1f}" if pd.notna(r_rank) else "—",
            "Rating (z %ile)": f"{r_z:.1f}" if pd.notna(r_z) else "—",
            "xG/90 (rank %ile)": f"{xg_rank:.1f}" if pd.notna(xg_rank) else "—",
            "xG/90 (z %ile)": f"{xg_z:.1f}" if pd.notna(xg_z) else "—",
        })
    tbl = pd.DataFrame(rows)
    print(tbl.to_string(index=False))

    print("\n" + "-" * 100)
    print("Takeaway: Rank percentiles bunch at 99–100 for the top few. Z-score percentiles")
    print("spread them (e.g. 99.9 vs 97.5), so you can tell who is genuinely ahead.")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    main()
