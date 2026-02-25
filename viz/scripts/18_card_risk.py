"""
5.3 Card risk - Cards per 90 over time; fouls/90 vs cards/90 (numeric axes).
Usage: python viz/scripts/18_card_risk.py [player_slug]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from viz.config import DATA_SOURCE_FOOTNOTE, DEFAULT_PLAYER_SLUG, OUTPUT_DIR, OUTPUT_FORMAT, DPI
from viz.data_utils import load_player


def plot_card_risk(player_slug: str) -> Path:
    out_dir = OUTPUT_DIR / "05_incidents"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_player(player_slug)
    df = df.sort_values("match_date_utc").copy()
    name = df["player_shortName"].iloc[0] if "player_shortName" in df.columns else player_slug

    yellow = df.get("incident_yellow_cards", 0)
    red = df.get("incident_red_cards", 0)
    if hasattr(yellow, "fillna"):
        yellow = yellow.fillna(0)
    if hasattr(red, "fillna"):
        red = red.fillna(0)
    cards = yellow + red
    fouls = df["stat_fouls"].fillna(0)
    mins = df["stat_minutesPlayed"].fillna(90).replace(0, 1)
    cards_per90 = (cards / mins * 90).values
    fouls_per90 = (fouls / mins * 90).values

    # Two subplots: (1) cards/90 vs date, (2) fouls/90 vs cards/90 — do NOT share x so bottom has numeric Fouls/90
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=False)

    axes[0].plot(df["match_date_utc"], cards_per90, "o-", color="orange", markersize=4)
    avg_c = pd.Series(cards_per90).mean()
    axes[0].axhline(avg_c, color="gray", linestyle="--", label=f"Avg: {avg_c:.2f}/90")
    axes[0].set_ylabel("Cards/90")
    axes[0].set_xlabel("Date")
    axes[0].set_title(f"{name} — Card risk over time")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].scatter(fouls_per90, cards_per90, alpha=0.6, s=40)
    axes[1].set_xlabel("Fouls/90")
    axes[1].set_ylabel("Cards/90")
    axes[1].set_title("Fouls vs cards (per match)")
    axes[1].grid(True, alpha=0.3)

    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 0.98])
    out_path = out_dir / f"card_risk_{player_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    player = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p = plot_card_risk(player)
    print(f"Saved: {p}")
