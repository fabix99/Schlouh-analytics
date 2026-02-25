"""
2.1 Rolling form - Rolling 5-game average for rating, xG, goals vs season avg.
Usage: python viz/scripts/04_rolling_form.py [player_slug]
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
from viz.data_utils import load_player, rolling_mean, rolling_std, season_aggregates


def plot_rolling_form(
    player_slug: str, window: int = 5, min_minutes_per_game: int = 45
) -> Path:
    out_dir = OUTPUT_DIR / "02_form"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    if min_minutes_per_game > 0 and "stat_minutesPlayed" in df.columns:
        df = df[df["stat_minutesPlayed"] >= min_minutes_per_game].copy()
    df = df.sort_values("match_date_utc").reset_index(drop=True)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug
    n = len(df)

    df["roll_rating"] = rolling_mean(df, "stat_rating", window=window, per_90=False)
    df["roll_xg"] = rolling_mean(df, "stat_expectedGoals", window=window, per_90=True)
    df["roll_goals"] = rolling_mean(df, "stat_goals", window=window, per_90=True)
    roll_rating_std = rolling_std(df, "stat_rating", window=window)

    season_agg = season_aggregates(df)
    season_rating = float(df["stat_rating"].mean())
    season_xg = float(season_agg.get("stat_expectedGoals", 0) or 0)
    season_goals = float(season_agg.get("stat_goals", 0) or 0)

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True)

    # Rating with ±1 SE band
    axes[0].plot(df["match_date_utc"], df["roll_rating"], "b-", linewidth=2, label=f"Rolling {window}G")
    se = roll_rating_std / np.sqrt(np.minimum(np.arange(len(df)) + 1, window))
    axes[0].fill_between(
        df["match_date_utc"],
        df["roll_rating"] - se,
        df["roll_rating"] + se,
        alpha=0.2,
        color="blue",
    )
    axes[0].axhline(season_rating, color="gray", linestyle="--", label=f"Season avg: {season_rating:.2f}")
    axes[0].set_ylabel("Rating")
    axes[0].set_title(f"{name} — Form over time (rolling {window}G, min {min_minutes_per_game} min/match)")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(df["match_date_utc"], df["roll_xg"], "g-", linewidth=2, label=f"Rolling {window}G")
    axes[1].axhline(season_xg, color="gray", linestyle="--", label=f"Season avg: {season_xg:.2f}")
    axes[1].set_ylabel("xG/90")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(df["match_date_utc"], df["roll_goals"], color="orange", linewidth=2, label=f"Rolling {window}G")
    axes[2].axhline(season_goals, color="gray", linestyle="--", label=f"Season avg: {season_goals:.2f}")
    axes[2].set_ylabel("Goals/90")
    axes[2].set_xlabel("Date")
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    fig.text(0.5, 0.01, f"{DATA_SOURCE_FOOTNOTE} n={n} matches.", ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.03, 1, 0.98])
    out_path = out_dir / f"rolling_form_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_rolling_form(player)
    print(f"Saved: {p}")
