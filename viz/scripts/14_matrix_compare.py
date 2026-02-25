"""
4.3 Head-to-head matrix - Heatmap: who's better on each metric.
Usage: python viz/scripts/14_matrix_compare.py [player1_slug] [player2_slug]
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
from viz.data_utils import load_player, season_aggregates, get_season_competition


def plot_matrix_compare(player1_slug: str, player2_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "04_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)

    df1 = load_player(player1_slug)
    df2 = load_player(player2_slug)
    agg1 = season_aggregates(df1)
    agg2 = season_aggregates(df2)

    name1 = df1["player_shortName"].iloc[0] if "player_shortName" in df1.columns else player1_slug
    name2 = df2["player_shortName"].iloc[0] if "player_shortName" in df2.columns else player2_slug

    metrics = [
        ("stat_rating", "Rating"),
        ("stat_expectedGoals", "xG/90"),
        ("stat_expectedAssists", "xA/90"),
        ("stat_totalShots", "Shots/90"),
        ("stat_keyPass", "Key passes/90"),
        ("stat_totalBallCarriesDistance", "Carry dist/90"),
        ("stat_duelWon", "Duels won/90"),
    ]

    if "stat_rating" in df1.columns:
        agg1 = agg1.copy()
        agg1["stat_rating"] = df1["stat_rating"].mean()
    if "stat_rating" in df2.columns:
        agg2 = agg2.copy()
        agg2["stat_rating"] = df2["stat_rating"].mean()

    labels = [m[1] for m in metrics]
    cols = [m[0] for m in metrics]
    v1 = [float(agg1.get(c, 0) or 0) for c in cols]
    v2 = [float(agg2.get(c, 0) or 0) for c in cols]

    # Matrix: +1 if p1 better, -1 if p2 better, 0 tie; effect size for display
    diff = np.array([1 if a > b else (-1 if a < b else 0) for a, b in zip(v1, v2)])
    mat = np.array([[d] for d in diff])
    effect = []
    for a, b in zip(v1, v2):
        if a == b:
            effect.append("")
        else:
            pct = 100 * (a - b) / (b or 1)
            effect.append(f" ({pct:+.0f}%)")

    season1, comp1 = get_season_competition(df1)
    season2, comp2 = get_season_competition(df2)
    context = f" — {comp1}" if (comp1 and comp2 and comp1 == comp2) else ""

    fig, ax = plt.subplots(figsize=(5, 6))
    cmap = plt.cm.RdYlGn
    im = ax.imshow(mat, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks([0])
    ax.set_xticklabels(["Winner"])
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for i, d in enumerate(diff):
        txt = (name1 if d > 0 else (name2 if d < 0 else "Tie")) + effect[i]
        ax.text(0, i, txt, ha="center", va="center", fontsize=8)
    ax.set_title(f"{name1} vs {name2} — Head-to-head{context}")
    plt.colorbar(im, ax=ax, shrink=0.5, label=f"{name1} wins / Tie / {name2} wins")
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])

    out_path = out_dir / f"matrix_compare_{player1_slug}_vs_{player2_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    p1 = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p2 = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PLAYER_SLUG_2
    p = plot_matrix_compare(p1, p2)
    print(f"Saved: {p}")
