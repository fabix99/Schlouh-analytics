"""
6.1 Percentile bar - Player's per-90 metrics as percentiles vs peers.
Usage: python viz/scripts/19_percentile.py [player_slug]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from viz.config import DATA_SOURCE_FOOTNOTE, DEFAULT_PLAYER_SLUG, OUTPUT_DIR, OUTPUT_FORMAT, DPI
from viz.data_utils import load_appearances, load_player


def plot_percentile(
    player_slug: str,
    competition: str = "spain-laliga",
    position_filter: str = "F",
    min_minutes: int = 450,
) -> Path:
    out_dir = OUTPUT_DIR / "06_percentile"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_appearances(competition)
    if df.empty:
        raise FileNotFoundError("player_appearances.parquet not found or empty")

    total_mins = df.groupby("player_id")["stat_minutesPlayed"].sum()
    eligible = total_mins[total_mins >= min_minutes].index
    df = df[df["player_id"].isin(eligible)]
    if position_filter:
        df = df[df["player_position"] == position_filter]

    metrics = [
        ("stat_expectedGoals", "xG/90"),
        ("stat_expectedAssists", "xA/90"),
        ("stat_totalShots", "Shots/90"),
        ("stat_keyPass", "Key passes/90"),
        ("stat_totalProgressiveBallCarriesDistance", "Prog carries/90"),
        ("stat_duelWon", "Duels won/90"),
    ]

    agg = df.groupby("player_id", group_keys=False).apply(
        lambda g: pd.Series(
            {
                **{c: g[c].sum() / g["stat_minutesPlayed"].sum() * 90 for c, _ in metrics},
                "stat_rating": g["stat_rating"].mean(),
            }
        ),
        include_groups=False,
    ).reset_index()

    # Add rating to metrics for percentile
    all_metrics = [("stat_rating", "Rating")] + metrics

    player_df = load_player(player_slug)
    pid = int(player_df["player_id"].iloc[0])
    name = player_df["player_shortName"].iloc[0] if "player_shortName" in player_df.columns else player_slug

    player_row = agg[agg["player_id"] == pid]
    if player_row.empty:
        raise ValueError(f"Player {player_slug} not in {competition} with min {min_minutes} min")

    percentiles = []
    labels = []
    for col, label in all_metrics:
        vals = agg[col].dropna()
        pval = player_row[col].iloc[0]
        pct = (vals < pval).sum() / len(vals) * 100 if len(vals) > 0 else 50
        percentiles.append(pct)
        labels.append(label)

    n_peers = len(agg)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["green" if p >= 50 else "orange" for p in percentiles]
    ax.barh(labels, percentiles, color=colors, alpha=0.8)
    ax.axvline(50, color="gray", linestyle="--", label="Median (50th)")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Percentile (vs peers)")
    ax.set_title(f"{name} — Percentiles vs {competition} {position_filter}s (min {min_minutes} min)\nn={n_peers} peers")
    ax.legend(loc="lower right")
    fig.text(0.5, 0.01, f"{DATA_SOURCE_FOOTNOTE} Green = ≥50th, Orange = <50th.", ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])

    out_path = out_dir / f"percentile_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_percentile(player)
    print(f"Saved: {p}")
