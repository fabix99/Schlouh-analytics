"""
2.3 Consistency (CV) - Coefficient of variation for xG and rating + interpretation.
Usage: python viz/scripts/06_consistency.py [player_slug]
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
from viz.data_utils import load_player, cv_band


def cv(series: pd.Series) -> float:
    """Coefficient of variation (std/mean)."""
    s = series.dropna()
    if len(s) < 2 or s.mean() == 0:
        return 0
    return s.std() / abs(s.mean())


def plot_consistency(player_slug: str, min_minutes: int = 45) -> Path:
    out_dir = OUTPUT_DIR / "02_form"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    if min_minutes > 0 and "stat_minutesPlayed" in df.columns:
        df = df[df["stat_minutesPlayed"] >= min_minutes].copy()
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    n = len(df)

    # Per-match xG (raw, not per-90) and rating
    xg = df["stat_expectedGoals"].fillna(0)
    rating = df["stat_rating"].fillna(0)

    cv_xg = cv(xg)
    cv_rating = cv(rating)
    mean_xg, std_xg = xg.mean(), xg.std()
    mean_rating, std_rating = rating.mean(), rating.std()

    # Bands by CV value (Low < 0.2, Moderate 0.2–0.5, High > 0.5 for xG; for rating use same logic)
    interp_xg = cv_band(cv_xg)
    interp_rating = cv_band(cv_rating)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].hist(xg, bins=15, color="steelblue", edgecolor="white")
    axes[0].axvline(mean_xg, color="red", linestyle="--", label=f"Mean: {mean_xg:.2f}")
    axes[0].axvline(xg.quantile(0.25), color="gray", linestyle=":", alpha=0.7)
    axes[0].axvline(xg.quantile(0.75), color="gray", linestyle=":", alpha=0.7)
    axes[0].set_xlabel("xG per match")
    axes[0].set_ylabel("Count")
    axes[0].set_title(f"xG — CV={cv_xg:.2f} ({interp_xg})\nμ={mean_xg:.2f}, σ={std_xg:.2f}")
    axes[0].legend()

    axes[1].hist(rating, bins=15, color="coral", edgecolor="white", alpha=0.8)
    axes[1].axvline(mean_rating, color="darkred", linestyle="--", label=f"Mean: {mean_rating:.2f}")
    axes[1].axvline(rating.quantile(0.25), color="gray", linestyle=":", alpha=0.7)
    axes[1].axvline(rating.quantile(0.75), color="gray", linestyle=":", alpha=0.7)
    axes[1].set_xlabel("Rating per match")
    axes[1].set_ylabel("Count")
    axes[1].set_title(f"Rating — CV={cv_rating:.2f} ({interp_rating})\nμ={mean_rating:.2f}, σ={std_rating:.2f}")
    axes[1].legend()

    fig.suptitle(f"{name} — Consistency metrics (n={n} matches, min {min_minutes} min)", fontsize=12, y=1.02)
    fig.text(0.5, 0.01, f"{DATA_SOURCE_FOOTNOTE} CV = σ/μ.", ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 0.96])

    out_path = out_dir / f"consistency_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_consistency(player)
    print(f"Saved: {p}")
