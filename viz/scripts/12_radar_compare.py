"""
4.1 Side-by-side radar - Same axes, two overlays (e.g. Mbappé vs Lewandowski).
Usage: python viz/scripts/12_radar_compare.py [player1_slug] [player2_slug]
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
    DEFAULT_PLAYER_SLUG,
    DEFAULT_PLAYER_SLUG_2,
    OUTPUT_DIR,
    OUTPUT_FORMAT,
    DPI,
)
from viz.data_utils import load_player, season_aggregates, get_season_competition, FORWARD_RADAR_COLS


def _radar_angles(n: int):
    return np.linspace(0, 2 * np.pi, n, endpoint=False).tolist() + [0]


def plot_radar_compare(player1_slug: str, player2_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "04_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)

    df1 = load_player(player1_slug)
    df2 = load_player(player2_slug)
    agg1 = season_aggregates(df1, stat_cols=FORWARD_RADAR_COLS)
    agg2 = season_aggregates(df2, stat_cols=FORWARD_RADAR_COLS)

    name1 = df1["player_shortName"].iloc[0] if "player_shortName" in df1.columns else player1_slug
    name2 = df2["player_shortName"].iloc[0] if "player_shortName" in df2.columns else player2_slug

    labels = ["xG", "Shots", "Key passes", "Carries dist", "Progressive carries", "Duels won"]
    cols = FORWARD_RADAR_COLS
    vals1 = [float(agg1.get(c, 0) or 0) for c in cols]
    vals2 = [float(agg2.get(c, 0) or 0) for c in cols]

    maxes = [1.5, 6, 4, 200, 150, 12]
    vals1_norm = [min(v / m, 1.0) for v, m in zip(vals1, maxes)]
    vals2_norm = [min(v / m, 1.0) for v, m in zip(vals2, maxes)]

    angles = _radar_angles(len(labels))
    v1 = vals1_norm + [vals1_norm[0]]
    v2 = vals2_norm + [vals2_norm[0]]

    season1, comp1 = get_season_competition(df1)
    season2, comp2 = get_season_competition(df2)
    # Only show league if both players have same competition (avoid e.g. "spain-laliga" when one is Ligue 1)
    if comp1 and comp2 and comp1 == comp2:
        context = f" — {comp1}"
        if season1 and season2 and season1 == season2:
            context = f" {season1}" + context
    else:
        context = " (same scale; data may be from different leagues)"

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection="polar"))
    ax.plot(angles, v1, "o-", linewidth=2, label=name1, color="steelblue")
    ax.fill(angles, v1, alpha=0.2, color="steelblue")
    ax.plot(angles, v2, "o-", linewidth=2, label=name2, color="coral")
    ax.fill(angles, v2, alpha=0.2, color="coral")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.set_title(f"{name1} vs {name2}\n0–1 = same scale{context}")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0))
    fig.text(0.5, 0.02, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])

    out_path = out_dir / f"radar_compare_{player1_slug}_vs_{player2_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    p1 = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p2 = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PLAYER_SLUG_2
    p = plot_radar_compare(p1, p2)
    print(f"Saved: {p}")
