"""
4.2 Comparison bar chart - Horizontal bars for 6-8 per-90 metrics.
Usage: python viz/scripts/13_bar_compare.py [player1_slug] [player2_slug]
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


def plot_bar_compare(player1_slug: str, player2_slug: str) -> Path:
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

    labels = [m[1] for m in metrics]
    cols = [m[0] for m in metrics]
    v1 = [float(agg1.get(c, 0) or 0) for c in cols]
    v2 = [float(agg2.get(c, 0) or 0) for c in cols]

    # Rating is not per-90, use raw mean
    if "stat_rating" in df1.columns:
        v1[0] = float(df1["stat_rating"].mean())
    if "stat_rating" in df2.columns:
        v2[0] = float(df2["stat_rating"].mean())

    season1, comp1 = get_season_competition(df1)
    context = f" — {comp1}" if comp1 else ""
    if season1:
        context = f" {season1}" + context

    # Split so Carry dist/90 doesn't dominate scale: panel 1 = Rating, xG, xA, Shots, Key passes; panel 2 = Carry dist, Duels
    attacking_metrics = [
        ("stat_rating", "Rating"),
        ("stat_expectedGoals", "xG/90"),
        ("stat_expectedAssists", "xA/90"),
        ("stat_totalShots", "Shots/90"),
        ("stat_keyPass", "Key passes/90"),
    ]
    other_metrics = [
        ("stat_totalBallCarriesDistance", "Carry dist/90"),
        ("stat_duelWon", "Duels won/90"),
    ]
    idx_att = [labels.index(m[1]) for m in attacking_metrics]
    idx_oth = [labels.index(m[1]) for m in other_metrics]
    v1_att = [v1[i] for i in idx_att]
    v2_att = [v2[i] for i in idx_att]
    v1_oth = [v1[i] for i in idx_oth]
    v2_oth = [v2[i] for i in idx_oth]
    lab_att = [labels[i] for i in idx_att]
    lab_oth = [labels[i] for i in idx_oth]

    x_max_att = max(max(v1_att), max(v2_att), 1) * 1.15
    x_max_oth = max(max(v1_oth), max(v2_oth), 1) * 1.15

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    w = 0.35

    for ax, x_vals, y_vals, x_max, sub_title in [
        (axes[0], np.arange(len(lab_att)), lab_att, x_max_att, "Attacking & rating"),
        (axes[1], np.arange(len(lab_oth)), lab_oth, x_max_oth, "Carry & duels"),
    ]:
        if ax == axes[0]:
            va1, va2 = v1_att, v2_att
        else:
            va1, va2 = v1_oth, v2_oth
        ax.barh(x_vals - w / 2, va1, w, label=name1, color="steelblue")
        ax.barh(x_vals + w / 2, va2, w, label=name2, color="coral")
        ax.set_yticks(x_vals)
        ax.set_yticklabels(y_vals)
        ax.set_xlim(0, x_max)
        ax.set_xlabel("Value (per 90 except Rating)")
        ax.set_title(sub_title)
        ax.grid(True, axis="x", alpha=0.3)
    axes[0].legend(loc="lower right")
    axes[1].legend(loc="lower right")

    fig.suptitle(f"{name1} vs {name2} — Season per 90{context}", fontsize=12, y=1.02)
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    out_path = out_dir / f"bar_compare_{player1_slug}_vs_{player2_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    p1 = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p2 = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PLAYER_SLUG_2
    p = plot_bar_compare(p1, p2)
    print(f"Saved: {p}")
