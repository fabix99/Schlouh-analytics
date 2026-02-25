"""
3.1 Radar (position-specific) - 6-8 metrics per 90, forward profile.
Usage: python viz/scripts/08_radar_profile.py [player_slug]
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
from viz.data_utils import load_player, season_aggregates, FORWARD_RADAR_COLS


def _radar_angles(n: int):
    return np.linspace(0, 2 * np.pi, n, endpoint=False).tolist() + [0]


def plot_radar_profile(player_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "03_profile"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    agg = season_aggregates(df, stat_cols=FORWARD_RADAR_COLS)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug

    # Order: attacking first, then ball-carrying, then duels
    labels = ["Shots", "xG", "Key passes", "Carries dist", "Progressive carries", "Duels won"]
    cols = [
        "stat_totalShots",
        "stat_expectedGoals",
        "stat_keyPass",
        "stat_totalBallCarriesDistance",
        "stat_totalProgressiveBallCarriesDistance",
        "stat_duelWon",
    ]
    vals = [float(agg.get(c, 0) or 0) for c in cols]

    # Normalize to 0-1 by reasonable maxes for forwards (scale definition in title)
    maxes = [6, 1.5, 4, 200, 150, 12]
    vals_norm = [min(v / m, 1.0) for v, m in zip(vals, maxes)]

    angles = _radar_angles(len(labels))
    vals_norm_closed = vals_norm + [vals_norm[0]]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection="polar"))
    ax.plot(angles, vals_norm_closed, "o-", linewidth=2, color="steelblue")
    ax.fill(angles, vals_norm_closed, alpha=0.25, color="steelblue")
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.set_title(f"{name} — Season profile (per 90)\n0–1 = scaled by forward maxes")
    fig.text(0.5, 0.02, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])

    out_path = out_dir / f"radar_profile_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_radar_profile(player)
    print(f"Saved: {p}")
