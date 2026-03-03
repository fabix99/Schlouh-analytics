"""
Infer team formation and starting XI positions from heatmap data.

Uses heatmap points (x, y) per player to compute a representative position (median),
then clusters outfield players into defensive / midfield / forward lines and maps
counts to a standard formation (4-3-3, 4-4-2, etc.). Returns formation string and
per-player (cx, cy, slot_type, slot_index) for drawing formation diagrams.

See docs/formation_from_heatmaps.md for full analysis and design.
"""

from __future__ import annotations

__all__ = [
    "formation_from_heatmaps",
    "formation_from_heatmaps_season",
    "formation_from_heatmaps_to_render_args",
    "load_lineups_for_match",
    "FormationFromHeatmapsResult",
    "PlayerFormationSlot",
]


from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Formation templates: (formation_name, n_defenders, n_midfielders, n_forwards)
# Outfield 10 only; GK is separate.
# 4-2-3-1 is (4, 2, 3, 1) but we use (4, 5, 1) when we only have D/M/F (AM merged into M).
FORMATION_TEMPLATES = [
    ("4-3-3", 4, 3, 3),
    ("4-4-2", 4, 4, 2),
    ("3-4-3", 3, 4, 3),
    ("5-3-2", 5, 3, 2),
    ("4-2-3-1", 4, 5, 1),
]


@dataclass
class PlayerFormationSlot:
    """One player in the formation: id, name, representative (x,y), slot type and index."""
    player_id: int
    player_name: str
    cx: float
    cy: float
    slot_type: str  # "GK", "D", "M", "F"
    slot_index: int  # 0-based within slot (e.g. 0=left, 1=centre, 2=right for back 3)
    nominal_position: Optional[str] = None


@dataclass
class FormationFromHeatmapsResult:
    """Result of inferring formation and XI from heatmaps for one team."""
    formation: str
    players: List[PlayerFormationSlot]
    side: str
    team_name: str


def _representative_position(x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    """Compute representative (cx, cy) from heatmap points. Uses median for robustness."""
    if x.size == 0 or y.size == 0:
        return float("nan"), float("nan")
    cx = float(np.nanmedian(x))
    cy = float(np.nanmedian(y))
    return cx, cy


def _cluster_outfield_by_y(
    cy_outfield: np.ndarray,
    n_d: int = 4,
    n_m: int = 3,
    n_f: int = 3,
) -> np.ndarray:
    """
    Assign each outfield player to line D/M/F by y position.
    Sorts by cy ascending: first n_d = D, next n_m = M, last n_f = F.
    If n_d + n_m + n_f != len(cy_outfield), scales counts proportionally.
    Returns 1D array of labels: 0 = D, 1 = M, 2 = F (same order as input).
    """
    n = len(cy_outfield)
    if n == 0:
        return np.array([], dtype=int)
    total = n_d + n_m + n_f
    if total != n:
        # Scale to n: keep ratios roughly D:M:F
        n_d = max(1, round(n * n_d / total))
        n_f = max(1, round(n * n_f / total))
        n_m = n - n_d - n_f
        n_m = max(0, n_m)
        if n_d + n_m + n_f != n:
            n_f = n - n_d - n_m
    order = np.argsort(cy_outfield)
    labels = np.empty(n, dtype=int)
    idx = 0
    for _ in range(n_d):
        if idx < n:
            labels[order[idx]] = 0
            idx += 1
    for _ in range(n_m):
        if idx < n:
            labels[order[idx]] = 1
            idx += 1
    for _ in range(n_f):
        if idx < n:
            labels[order[idx]] = 2
            idx += 1
    return labels


def _infer_formation_from_counts(n_d: int, n_m: int, n_f: int) -> str:
    """Map (n_d, n_m, n_f) to nearest standard formation name."""
    best_name, best_dist = "4-3-3", 999
    for name, d, m, f in FORMATION_TEMPLATES:
        dist = abs(n_d - d) + abs(n_m - m) + abs(n_f - f)
        if dist < best_dist:
            best_dist, best_name = dist, name
    return best_name


def _infer_line_counts_from_y(cy_outfield: np.ndarray) -> Tuple[int, int, int]:
    """
    Infer (n_d, n_m, n_f) from 10 outfield cy values using gap-based splitting.
    Sort by cy; find the two largest gaps between consecutive (sorted) values;
    use them as boundaries to form 3 groups. Count each group.
    """
    if len(cy_outfield) != 10:
        return 4, 3, 3
    sorted_cy = np.sort(cy_outfield)
    gaps = np.diff(sorted_cy)
    # Two largest gaps -> three lines
    gap_inds = np.argsort(gaps)[::-1][:2]
    split_at = sorted(gap_inds + 1)
    n_d = split_at[0]
    n_m = split_at[1] - split_at[0]
    n_f = 10 - split_at[1]
    # Clamp to sensible range and ensure sum = 10
    n_d = max(2, min(5, n_d))
    n_m = max(2, min(5, n_m))
    n_f = 10 - n_d - n_m
    n_f = max(1, min(4, n_f))
    if n_d + n_m + n_f != 10:
        n_m = 10 - n_d - n_f
    return n_d, n_m, n_f


def _select_xi_with_heatmaps(
    lineups_df: pd.DataFrame,
    heatmap_player_ids: set,
    side: str,
) -> pd.DataFrame:
    """
    From lineups for one side, keep only players that have heatmap data;
    sort by starter first (substitute==False), then by minutes descending;
    return top 11 rows.
    """
    side_normalized = lineups_df["side"].astype(str).str.strip().str.lower()
    side_df = lineups_df[side_normalized == side.lower()].copy()
    has_hm = side_df["player_id"].astype(int).isin(heatmap_player_ids)
    side_df = side_df[has_hm]
    if side_df.empty:
        return side_df
    # Prefer starters, then minutes
    if "substitute" in side_df.columns:
        side_df["_starter"] = side_df["substitute"].fillna(True).eq(False).astype(int)
    else:
        side_df["_starter"] = 1
    mins = "stat_minutesPlayed"
    if mins not in side_df.columns:
        side_df["_mins"] = 90
    else:
        side_df["_mins"] = pd.to_numeric(side_df[mins], errors="coerce").fillna(0)
    side_df = side_df.sort_values(["_starter", "_mins"], ascending=[False, False])
    return side_df.head(11).drop(columns=["_starter", "_mins"], errors="ignore")


def formation_from_heatmaps(
    match_id: str,
    side: str,
    lineups_df: pd.DataFrame,
    heatmap_df: pd.DataFrame,
    team_name: Optional[str] = None,
) -> Optional[FormationFromHeatmapsResult]:
    """
    Infer formation and starting XI positions from heatmap data for one team in one match.

    Args:
        match_id: Match identifier (string).
        side: "home" or "away".
        lineups_df: DataFrame with columns match_id, side, player_id, player_name, position (optional),
                    substitute (optional), stat_minutesPlayed (optional). One row per player per match.
        heatmap_df: DataFrame with columns match_id, player_id, x, y (one row per heatmap point).
        team_name: Optional team name for display (otherwise taken from lineups_df if present).

    Returns:
        FormationFromHeatmapsResult with formation string and list of PlayerFormationSlot,
        or None if insufficient data (fewer than 11 players with heatmaps, or missing columns).
    """
    match_id_str = str(match_id)
    hm_match = heatmap_df[heatmap_df["match_id"].astype(str) == match_id_str]
    if hm_match.empty or "player_id" not in hm_match.columns or "x" not in hm_match.columns or "y" not in hm_match.columns:
        return None
    heatmap_player_ids = set(hm_match["player_id"].astype(int).unique())

    lineup_match = lineups_df[lineups_df["match_id"].astype(str) == match_id_str]
    if lineup_match.empty:
        return None
    team_name = team_name or (lineup_match["team"].iloc[0] if "team" in lineup_match.columns else "")

    xi_df = _select_xi_with_heatmaps(lineup_match, heatmap_player_ids, side)
    if xi_df.empty or len(xi_df) < 11:
        # Still try with however many we have (e.g. 7); we need at least 1 for GK and a few outfield
        if len(xi_df) < 4:
            return None
    n_players = len(xi_df)
    player_ids = xi_df["player_id"].astype(int).tolist()

    # Representative position per player
    id_to_xy: Dict[int, Tuple[float, float]] = {}
    for pid in player_ids:
        pts = hm_match[hm_match["player_id"] == pid]
        x = pts["x"].values
        y = pts["y"].values
        cx, cy = _representative_position(x, y)
        if np.isfinite(cx) and np.isfinite(cy):
            id_to_xy[pid] = (cx, cy)
    if len(id_to_xy) < 4:
        return None

    # Build list of (player_id, cx, cy) in same order as xi_df, only those with valid xy
    rows_xy: List[Tuple[int, str, float, float, Optional[str]]] = []
    for _, row in xi_df.iterrows():
        pid = int(row["player_id"])
        if pid not in id_to_xy:
            continue
        cx, cy = id_to_xy[pid]
        name = str(row.get("player_name", row.get("player_shortName", "")) or "")
        pos = row.get("position") or row.get("player_position")
        if pd.isna(pos):
            pos = None
        else:
            pos = str(pos).strip() or None
        rows_xy.append((pid, name, cx, cy, pos))

    if len(rows_xy) < 4:
        return None
    return _infer_formation_and_slots_from_xy_rows(rows_xy, team_name, side)


def _infer_formation_and_slots_from_xy_rows(
    rows_xy: List[Tuple[int, str, float, float, Optional[str]]],
    team_name: str,
    side: str = "",
) -> Optional[FormationFromHeatmapsResult]:
    """Given list of (player_id, name, cx, cy, position), infer formation and slot assignment."""
    if len(rows_xy) < 4:
        return None
    cy_all = np.array([r[3] for r in rows_xy])
    gk_idx = int(np.argmin(cy_all))
    gk_row = rows_xy[gk_idx]
    outfield_rows = [r for i, r in enumerate(rows_xy) if i != gk_idx]
    cy_outfield = np.array([r[3] for r in outfield_rows])
    if len(outfield_rows) < 3:
        return None
    n_out = len(outfield_rows)
    if n_out == 10:
        n_d, n_m, n_f = _infer_line_counts_from_y(cy_outfield)
    else:
        n_d, n_m, n_f = 4, 3, 3
    formation = _infer_formation_from_counts(n_d, n_m, n_f)
    for name, d, m, f in FORMATION_TEMPLATES:
        if name == formation:
            n_d, n_m, n_f = d, m, f
            break
    else:
        n_d, n_m, n_f = 4, 3, 3
    labels = _cluster_outfield_by_y(cy_outfield, n_d, n_m, n_f)
    slot_names = ["D", "M", "F"]
    outfield_with_slots: List[Tuple[int, str, float, float, Optional[str], str, int]] = []
    for line_id in (0, 1, 2):
        mask = labels == line_id
        line_rows = [outfield_rows[i] for i in range(len(outfield_rows)) if mask[i]]
        line_rows.sort(key=lambda r: r[2])
        for slot_idx, r in enumerate(line_rows):
            pid, name, cx, cy, pos = r[0], r[1], r[2], r[3], r[4]
            outfield_with_slots.append((pid, name, cx, cy, pos, slot_names[line_id], slot_idx))
    players_out: List[PlayerFormationSlot] = []
    players_out.append(
        PlayerFormationSlot(
            player_id=gk_row[0],
            player_name=gk_row[1],
            cx=gk_row[2],
            cy=gk_row[3],
            slot_type="GK",
            slot_index=0,
            nominal_position=gk_row[4],
        )
    )
    for t in outfield_with_slots:
        players_out.append(
            PlayerFormationSlot(
                player_id=t[0],
                player_name=t[1],
                cx=t[2],
                cy=t[3],
                slot_type=t[5],
                slot_index=t[6],
                nominal_position=t[4],
            )
        )
    return FormationFromHeatmapsResult(
        formation=formation,
        players=players_out,
        side=side,
        team_name=team_name,
    )


def formation_from_heatmaps_season(
    team_name: str,
    season: str,
    competition_slugs: List[str],
    match_summary_df: pd.DataFrame,
    heatmap_df: pd.DataFrame,
    team_players_df: pd.DataFrame,
) -> Optional[FormationFromHeatmapsResult]:
    """
    Infer formation and XI positions from season-aggregated heatmap data (median position per player
    across all matches in scope). Uses top 11 players by minutes; each must have at least one
    heatmap point in the team's matches that have heatmap data.

    Args:
        team_name: Team name (must match home_team_name / away_team_name in match_summary).
        season: Season string (e.g. "2025-26").
        competition_slugs: List of competition_slug to include.
        match_summary_df: Match summary with match_id, home_team_name, away_team_name, season, competition_slug.
        heatmap_df: Heatmap points (match_id, player_id, x, y).
        team_players_df: Players for this team/season/comp with player_id, player_name, total_minutes,
                         and optionally player_position. Will use top 11 by total_minutes among those with heatmap data.

    Returns:
        FormationFromHeatmapsResult or None if insufficient data.
    """
    if heatmap_df.empty or "match_id" not in heatmap_df.columns or "player_id" not in heatmap_df.columns:
        return None
    if team_players_df.empty or "player_id" not in team_players_df.columns or "total_minutes" not in team_players_df.columns:
        return None
    hm_match_ids = set(heatmap_df["match_id"].astype(str).unique())
    ms = match_summary_df
    if ms.empty or "match_id" not in ms.columns:
        return None
    # Match team name flexibly (strip, case-insensitive) so "Real Madrid" matches "Real Madrid " etc.
    _tn = str(team_name).strip().lower()
    _home = ms["home_team_name"].fillna("").astype(str).str.strip().str.lower()
    _away = ms["away_team_name"].fillna("").astype(str).str.strip().str.lower()
    _team_mask = (_home == _tn) | (_away == _tn)
    team_matches = ms[
        _team_mask &
        (ms["season"].astype(str) == str(season)) &
        (ms["competition_slug"].isin(competition_slugs))
    ]
    team_match_ids = set(team_matches["match_id"].astype(str).unique()) & hm_match_ids
    if not team_match_ids:
        return None
    hm_team = heatmap_df[heatmap_df["match_id"].astype(str).isin(team_match_ids)]
    # Top 11 by minutes; we need at least 11 players that have at least one heatmap point
    team_players_df = team_players_df.sort_values("total_minutes", ascending=False).reset_index(drop=True)
    player_ids_with_hm = set(hm_team["player_id"].astype(int).unique())
    xi_ids: List[int] = []
    for _, row in team_players_df.iterrows():
        pid = int(row["player_id"])
        if pid in player_ids_with_hm:
            xi_ids.append(pid)
            if len(xi_ids) >= 11:
                break
    if len(xi_ids) < 11:
        return None
    xi_ids = xi_ids[:11]
    name_col = "player_name" if "player_name" in team_players_df.columns else "player_shortName"
    pos_col = "player_position" if "player_position" in team_players_df.columns else "position"
    id_to_name = dict(zip(team_players_df["player_id"].astype(int), team_players_df[name_col].astype(str)))
    id_to_pos = {}
    if pos_col in team_players_df.columns:
        for _, row in team_players_df.iterrows():
            id_to_pos[int(row["player_id"])] = row[pos_col]
    rows_xy: List[Tuple[int, str, float, float, Optional[str]]] = []
    for pid in xi_ids:
        pts = hm_team[hm_team["player_id"] == pid]
        if pts.empty:
            continue
        x = pts["x"].values
        y = pts["y"].values
        cx, cy = _representative_position(x, y)
        if not np.isfinite(cx) or not np.isfinite(cy):
            continue
        name = id_to_name.get(pid, str(pid))
        pos = id_to_pos.get(pid)
        if pd.notna(pos):
            pos = str(pos).strip() or None
        else:
            pos = None
        rows_xy.append((pid, name, cx, cy, pos))
    if len(rows_xy) < 11:
        return None
    rows_xy = rows_xy[:11]
    return _infer_formation_and_slots_from_xy_rows(rows_xy, team_name, side="")


def formation_from_heatmaps_to_render_args(
    result: FormationFromHeatmapsResult,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Convert FormationFromHeatmapsResult to the shape expected by formation pitch renderers:
    (formation_string, list of player dicts with name, position, and optional x, y for custom placement).

    Returns:
        (formation, players) where players have keys: name, position, slot_type, slot_index, cx, cy,
        and optionally rating if you add it later. The renderer can use (cx, cy) to place markers
        instead of template positions.
    """
    formation = result.formation
    players = []
    for p in result.players:
        players.append({
            "player_id": p.player_id,
            "name": p.player_name,
            "position": p.nominal_position or p.slot_type,
            "slot_type": p.slot_type,
            "slot_index": p.slot_index,
            "cx": p.cx,
            "cy": p.cy,
        })
    return formation, players


def load_lineups_for_match(match_dir: Any) -> Optional[pd.DataFrame]:
    """
    Load lineups.csv from a raw match directory (Path or str). Returns DataFrame with match_id, side,
    player_id, player_name, position, substitute, stat_minutesPlayed, team, etc., or None if missing.
    """
    from pathlib import Path
    p = Path(match_dir) / "lineups.csv"
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p)
        df["match_id"] = df["match_id"].astype(str)
        return df
    except Exception:
        return None
