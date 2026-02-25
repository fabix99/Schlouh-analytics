"""
3.3 Player archetype scatter - xG/90 vs key passes/90, points=players, color by position.
Usage: python viz/scripts/10_archetype_scatter.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from viz.config import DATA_SOURCE_FOOTNOTE, OUTPUT_DIR, OUTPUT_FORMAT, DPI
from viz.data_utils import load_appearances


def plot_archetype_scatter(competition: str = "spain-laliga", min_minutes: int = 450) -> Path:
    out_dir = OUTPUT_DIR / "03_profile"
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
                "kp_per90": g["stat_keyPass"].sum() / g["stat_minutesPlayed"].sum() * 90,
                "position": g["player_position"].mode().iloc[0] if "player_position" in g.columns else "?",
                "player_name": g["player_shortName"].iloc[0] if "player_shortName" in g.columns else str(g["player_id"].iloc[0]),
            }
        ),
        include_groups=False,
    ).reset_index()

    pos_map = {"G": "GK", "D": "Def", "M": "Mid", "F": "Fwd"}
    agg["pos_label"] = agg["position"].map(pos_map).fillna(agg["position"])

    fig, ax = plt.subplots(figsize=(9, 6))
    pos_order = ["GK", "Def", "Mid", "Fwd"]
    for pos in pos_order:
        sub = agg[agg["pos_label"] == pos]
        if sub.empty:
            continue
        ax.scatter(sub["xg_per90"], sub["kp_per90"], label=f"{pos} (n={len(sub)})", alpha=0.5, s=25)
    for pos in agg["pos_label"].unique():
        if pos in pos_order:
            continue
        sub = agg[agg["pos_label"] == pos]
        ax.scatter(sub["xg_per90"], sub["kp_per90"], label=pos, alpha=0.5, s=25)

    med_xg = agg["xg_per90"].median()
    med_kp = agg["kp_per90"].median()
    ax.axvline(med_xg, color="gray", linestyle=":", alpha=0.5)
    ax.axhline(med_kp, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("xG/90")
    ax.set_ylabel("Key passes/90")
    ax.set_title(f"Player archetypes — {competition} (min {min_minutes} min)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.text(0.5, 0.01, f"{DATA_SOURCE_FOOTNOTE} Dotted lines = median.", ha="center", fontsize=7, color="gray")
    plt.tight_layout(rect=[0, 0.04, 1, 1])

    out_path = out_dir / "archetype_scatter.png"
    if OUTPUT_FORMAT != "png":
        out_path = out_dir / f"archetype_scatter.{OUTPUT_FORMAT}"
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close()
    return out_path


if __name__ == "__main__":
    p = plot_archetype_scatter()
    print(f"Saved: {p}")
