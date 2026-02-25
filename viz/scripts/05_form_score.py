"""
2.2 Form score / momentum - Recency-weighted metric over last N games vs baseline.
Usage: python viz/scripts/05_form_score.py [player_slug]
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
from viz.data_utils import load_player, season_aggregates


def plot_form_score(player_slug: str, n_recent: int = 5, recency_weights: bool = True) -> Path:
    out_dir = OUTPUT_DIR / "02_form"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    df = df.sort_values("match_date_utc").reset_index(drop=True)
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug

    season_agg = season_aggregates(df)
    baseline = float(season_agg.get("stat_rating", 0) or df["stat_rating"].mean() or 7)

    # Rolling form score: recency-weighted rating over last N games (most recent = 1.5^0, oldest = 1.5^(n-1))
    weights = np.array([1.5 ** (n_recent - 1 - i) for i in range(n_recent)]) if recency_weights else np.ones(n_recent)
    weights = weights / weights.sum()

    form_scores = []
    for i in range(len(df)):
        start = max(0, i - n_recent + 1)
        window = df.iloc[start : i + 1]["stat_rating"].values
        w = weights[-len(window) :]
        w = w / w.sum()
        form_scores.append(np.average(window, weights=w) if len(window) > 0 else np.nan)

    df = df.copy()
    df["form_score"] = form_scores

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["match_date_utc"], df["form_score"], "b-", linewidth=2, label="Form score (recency-weighted)")
    ax.axhline(baseline, color="gray", linestyle="--", label=f"Season baseline: {baseline:.2f}")
    ax.fill_between(df["match_date_utc"], baseline, df["form_score"], where=(df["form_score"] >= baseline), alpha=0.3, color="green")
    ax.fill_between(df["match_date_utc"], baseline, df["form_score"], where=(df["form_score"] < baseline), alpha=0.3, color="red")
    ax.set_ylabel("Form score")
    ax.set_xlabel("Date")
    ax.set_title(f"{name} — Momentum (last {n_recent} games, recent weighted 1.5×)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.text(0.5, 0.01, f"{DATA_SOURCE_FOOTNOTE} Form = weighted avg of rating (most recent game × 1.5).", ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])

    out_path = out_dir / f"form_score_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_form_score(player)
    print(f"Saved: {p}")
