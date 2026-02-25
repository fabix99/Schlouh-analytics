"""
2.4 Distribution - Histogram + optional KDE for rating and xG per match.
Usage: python viz/scripts/07_distribution.py [player_slug]
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
from viz.data_utils import load_player


def _add_kde(ax, series, color, x_range=None):
    """Overlay KDE on histogram (scaled to count axis)."""
    try:
        from scipy import stats
    except ImportError:
        return
    s = series.dropna()
    if len(s) < 3:
        return
    x = x_range if x_range is not None else np.linspace(s.min(), s.max(), 200)
    kde = stats.gaussian_kde(s)
    dens = kde(x)
    # Scale to match histogram height (approx)
    hist_max = ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1
    dens = dens / (dens.max() + 1e-9) * hist_max * 0.8
    ax.plot(x, dens, color=color, linewidth=2, label="Density")


def plot_distribution(player_slug: str, min_minutes: int = 45) -> tuple[Path, Path]:
    out_dir = OUTPUT_DIR / "02_form"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    if min_minutes > 0 and "stat_minutesPlayed" in df.columns:
        df = df[df["stat_minutesPlayed"] >= min_minutes].copy()
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    n = len(df)

    rating = df["stat_rating"].dropna()
    xg = df["stat_expectedGoals"].fillna(0)

    paths = []

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(rating, bins=15, color="steelblue", edgecolor="white", density=False)
    ax.axvline(rating.mean(), color="red", linestyle="--", label=f"Mean: {rating.mean():.2f}")
    ax.axvline(rating.median(), color="orange", linestyle=":", label=f"Median: {rating.median():.2f}")
    _add_kde(ax, rating, "navy")
    ax.set_xlabel("Rating")
    ax.set_ylabel("Matches")
    ax.set_title(f"{name} — Rating distribution (n={n})")
    ax.legend()
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    p1 = out_dir / f"distribution_rating_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(p1, dpi=DPI, bbox_inches="tight")
    plt.close()
    paths.append(p1)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(xg, bins=15, color="coral", edgecolor="white", alpha=0.8)
    ax.axvline(xg.mean(), color="darkred", linestyle="--", label=f"Mean: {xg.mean():.2f}")
    ax.axvline(xg.median(), color="orange", linestyle=":", label=f"Median: {xg.median():.2f}")
    _add_kde(ax, xg, "darkred")
    ax.set_xlabel("xG per match")
    ax.set_ylabel("Matches")
    ax.set_title(f"{name} — xG distribution (n={n})")
    ax.legend()
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])
    p2 = out_dir / f"distribution_xg_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(p2, dpi=DPI, bbox_inches="tight")
    plt.close()
    paths.append(p2)

    return tuple(paths)


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p1, p2 = plot_distribution(player)
    print(f"Saved: {p1}, {p2}")
