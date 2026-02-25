"""
4.4 Scatter comparison - xG vs xA, 2 players highlighted, others faint.
Usage: python viz/scripts/15_scatter_compare.py [player1_slug] [player2_slug]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd

from viz.config import (
    DATA_SOURCE_FOOTNOTE,
    DEFAULT_PLAYER_SLUG,
    DEFAULT_PLAYER_SLUG_2,
    OUTPUT_DIR,
    OUTPUT_FORMAT,
    DPI,
)
from viz.data_utils import load_appearances, load_player


def plot_scatter_compare(
    player1_slug: str,
    player2_slug: str,
    competition: str = "spain-laliga",
    min_minutes: int = 450,
) -> Path:
    out_dir = OUTPUT_DIR / "04_comparison"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_appearances(competition)
    if df.empty:
        raise FileNotFoundError("player_appearances.parquet not found or empty")

    total_mins = df.groupby("player_id")["stat_minutesPlayed"].sum()
    eligible = total_mins[total_mins >= min_minutes].index
    df = df[df["player_id"].isin(eligible)]

    agg = df.groupby("player_id", group_keys=False).apply(
        lambda g: pd.Series(
            {
                "xg_per90": g["stat_expectedGoals"].sum() / g["stat_minutesPlayed"].sum() * 90,
                "xa_per90": g["stat_expectedAssists"].sum() / g["stat_minutesPlayed"].sum() * 90,
                "player_slug": g["player_slug"].iloc[0] if "player_slug" in g.columns else "",
                "player_name": g["player_shortName"].iloc[0] if "player_shortName" in g.columns else "",
            }
        ),
        include_groups=False,
    ).reset_index()

    df1 = load_player(player1_slug)
    df2 = load_player(player2_slug)
    pid1 = int(df1["player_id"].iloc[0])
    pid2 = int(df2["player_id"].iloc[0])
    name1 = df1["player_shortName"].iloc[0] if "player_shortName" in df1.columns else player1_slug
    name2 = df2["player_shortName"].iloc[0] if "player_shortName" in df2.columns else player2_slug

    others = agg[~agg["player_id"].isin([pid1, pid2])]
    p1_row = agg[agg["player_id"] == pid1].iloc[0]
    p2_row = agg[agg["player_id"] == pid2].iloc[0]

    med_xg = others["xg_per90"].median()
    med_xa = others["xa_per90"].median()

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(others["xg_per90"], others["xa_per90"], c="gray", alpha=0.35, s=25, label=f"Others (n={len(others)})")
    ax.axvline(med_xg, color="gray", linestyle=":", alpha=0.6, linewidth=1)
    ax.axhline(med_xa, color="gray", linestyle=":", alpha=0.6, linewidth=1)
    ax.scatter(p1_row["xg_per90"], p1_row["xa_per90"], c="steelblue", s=180, label=name1, edgecolors="black", linewidths=1.5, zorder=5)
    ax.scatter(p2_row["xg_per90"], p2_row["xa_per90"], c="coral", s=180, label=name2, edgecolors="black", linewidths=1.5, zorder=5)
    # Annotate player names next to points
    ax.annotate(name1, (p1_row["xg_per90"], p1_row["xa_per90"]), xytext=(6, 6), textcoords="offset points", fontsize=9, fontweight="bold", color="steelblue")
    ax.annotate(name2, (p2_row["xg_per90"], p2_row["xa_per90"]), xytext=(6, 6), textcoords="offset points", fontsize=9, fontweight="bold", color="coral")
    ax.set_xlabel("xG/90")
    ax.set_ylabel("xA/90")
    ax.set_title(f"{name1} vs {name2} — xG vs xA\n{competition}, min {min_minutes} min · dotted = league median")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.text(0.5, 0.01, DATA_SOURCE_FOOTNOTE, ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])

    out_path = out_dir / f"scatter_compare_{player1_slug}_vs_{player2_slug}.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    p1 = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PLAYER_SLUG
    p2 = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PLAYER_SLUG_2
    p = plot_scatter_compare(p1, p2)
    print(f"Saved: {p}")
