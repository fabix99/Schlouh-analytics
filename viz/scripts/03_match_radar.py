"""
1.3 Single-match radar - This match vs season average, spider chart.
Usage: python viz/scripts/03_match_radar.py [player_slug] [match_id]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from viz.config import (
    DATA_SOURCE_FOOTNOTE,
    DEFAULT_MATCH_ID,
    DEFAULT_PLAYER_SLUG,
    OUTPUT_DIR,
    OUTPUT_FORMAT,
    DPI,
)
from viz.data_utils import load_player, get_match_row, season_aggregates


def _radar_factory(num_vars: int):
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]
    return angles


def plot_match_radar(player_slug: str, match_id: str) -> Path:
    out_dir = OUTPUT_DIR / "01_single_game"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    row = get_match_row(df, match_id)
    name = row.get("player_shortName") or row.get("player_name") or player_slug
    season_agg = season_aggregates(df)

    metrics = ["stat_rating", "stat_expectedGoals", "stat_totalShots", "stat_keyPass", "stat_duelWon", "stat_touches"]
    labels = ["Rating", "xG", "Shots", "Key passes", "Duels won", "Touches"]

    match_vals = []
    season_vals = []
    for col in metrics:
        m = row.get(col)
        s = season_agg.get(col, 0)
        if pd.isna(m):
            m = 0
        else:
            m = float(m)
        if pd.isna(s):
            s = 0
        mins = row.get("stat_minutesPlayed") or 90
        mins = float(mins)
        if col != "stat_rating" and mins > 0:
            m = m / mins * 90
        if isinstance(s, (int, float)) and col != "stat_rating":
            s = float(s)
        match_vals.append(m)
        season_vals.append(s)

    # Normalize to 0-1 for radar (by max of both)
    max_vals = [max(m, s, 0.01) for m, s in zip(match_vals, season_vals)]
    match_norm = [m / mx for m, mx in zip(match_vals, max_vals)]
    season_norm = [s / mx for s, mx in zip(season_vals, max_vals)]

    angles = _radar_factory(len(metrics))
    match_norm += match_norm[:1]
    season_norm += season_norm[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection="polar"))
    ax.plot(angles, match_norm, "o-", linewidth=2, label="This match", color="steelblue")
    ax.fill(angles, match_norm, alpha=0.25, color="steelblue")
    ax.plot(angles, season_norm, "o--", linewidth=1.5, label="Season avg", color="gray")
    ax.fill(angles, season_norm, alpha=0.1, color="gray")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.set_title(f"{name} — Match vs season (0–1 = match vs season max)")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0))
    fig.text(0.5, 0.02, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])

    out_path = out_dir / f"match_radar_{player_slug}_{match_id}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    match = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MATCH_ID
    p = plot_match_radar(player, match)
    print(f"Saved: {p}")
