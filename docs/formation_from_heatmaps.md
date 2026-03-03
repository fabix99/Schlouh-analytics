# Formation and Starting XI from Heatmaps — Analysis & Design

This document describes how we can **approximate a team’s formation (schema) and starting XI positions** using only **heatmap data** (touch/position points per player per match), so that we can draw formation diagrams like “Formation: 4-3-3” with players placed on the pitch from their actual activity rather than from nominal positions.

---

## 1. Goal

- **Input**: For a given match and team (home or away), we have:
  - Heatmap points: many `(x, y)` coordinates per player (from `18_heatmap_points.parquet` or raw `players/heatmap_{id}.json`).
  - Lineup metadata: who played, `side`, `player_id`, `player_name`, `position`, `substitute`, `stat_minutesPlayed` (from raw `lineups.csv`).
- **Output**:
  1. **Formation string** (e.g. `"4-3-3"`, `"4-2-3-1"`) inferred from where players actually spent time.
  2. **Starting XI** with a **representative position** `(x, y)` per player and a **role label** (GK / D / M / F and left/centre/right where useful) so we can render a formation pitch like the reference image.

No dependency on nominal `position` for formation shape — we derive both formation and positions from heatmaps; nominal position can still be used for display or fallback.

---

## 2. Data We Have

| Source | Content |
|--------|--------|
| `18_heatmap_points.parquet` | `match_id`, `player_id`, `x`, `y` (one row per point; Opta-style 0–100 pitch) |
| Raw `lineups.csv` per match | `match_id`, `side`, `team`, `player_id`, `player_name`, `position`, `substitute`, `stat_minutesPlayed`, … |
| Pitch convention (dashboard) | **x** = width (0–100, left to right), **y** = length (0–100); low y = one goal line, high y = other. Formation viz uses GK at low y, forwards at high y. |

We need to **join** heatmap points with lineups on `(match_id, player_id)` and filter by `side` to get one team at a time. “Starting XI” can be defined as: 11 players with heatmap data, preferring `substitute == False`, then by `stat_minutesPlayed` descending.

---

## 3. Pipeline Overview

1. **Select 11 players** for the team (match + side): from lineups, keep players that have heatmap data; take 11 by “starter then minutes”.
2. **Representative position per player**: From each player’s heatmap points, compute one `(cx, cy)` (e.g. median or mean). Prefer **median** to be robust to outliers and rare runs into the box.
3. **Orientation**: Assume the heatmap is in a consistent orientation (e.g. one goal at low y, the other at high y). The **lowest-y** outfield player is usually the goalkeeper; the rest are outfield. We use **y** as the “length” axis (defensive → attacking).
4. **Formation inference**: From the 10 outfield `(cx, cy)` points, infer how many players are in each “line” (defensive / midfield / attack). Options: **k-means (k=3)** on y (or on (x,y)), or **percentile bands**, or **gap-based** splitting after sorting by y. Map the resulting counts `(n_d, n_m, n_f)` to the nearest standard formation (4-3-3, 4-4-2, 3-4-3, 5-3-2, 4-2-3-1).
5. **Slot assignment**: Assign each of the 11 a **slot**: GK, and for outfield (D/M/F) a **left/centre/right** index by sorting by **x** within each line. This gives a full formation with coordinates and labels for drawing.

---

## 4. Detailed Design

### 4.1 Representative position (centroid)

- **Median (recommended)**: `cx = median(x)`, `cy = median(y)`.
  - Robust to a few extreme points (e.g. set-pieces in the box).
- **Mean**: Simpler but sensitive to outliers.
- **Density-weighted**: e.g. 2D histogram, then centroid of top bins or mode bin. More representative of “where they spent most time” but heavier to implement; can be a later improvement.

We use **median** in the first version.

### 4.2 Which 11 players?

- Restrict to players that have **at least one heatmap point** for that match.
- From lineups for that match + side, sort by:
  1. Starters first: `substitute == False` (if available), then
  2. `stat_minutesPlayed` descending.
- Take the **top 11**. If fewer than 11 have heatmaps, we can still run the algorithm on N players and still infer formation from the outfield subset (e.g. 10), or fall back to “not enough data”.

### 4.3 Formation inference (outfield 10)

We have 10 outfield points `(cx, cy)`. We only need to assign each to one of three lines (D / M / F) and then count.

**Option A — K-means (k=3) on y only**

- Run k-means with `k=3` on the 10 `cy` values (or on `(cx, cy)` and then order clusters by mean `cy`).
- Label clusters by ascending mean `cy`: line 1 = D, line 2 = M, line 3 = F.
- Counts `(n_d, n_m, n_f)` → map to nearest formation.

**Option B — Percentile bands on y**

- Sort outfield players by `cy` ascending.
- Assign: bottom 40% → D, middle 30% → M, top 30% → F (percentile of *count*, not strict y thresholds).
- Gives fixed 4-3-3 if we use 4 / 3 / 3; more flexible: use band boundaries from data (e.g. 33rd and 66th percentile of `cy`).

**Option C — Gap-based lines**

- Sort by `cy`, compute gaps between consecutive players. Large gaps suggest a new “line”. Threshold (e.g. 1.5× median gap) to split into 3–4 lines. Then map line counts to formation (e.g. 4-3-3, 4-4-2).

**Recommendation**: Start with **K-means k=3 on (cx, cy)** (so horizontal spread can help separate full-backs from wingers), then label clusters by mean `cy` (ascending = D, M, F). This is simple, data-driven, and works well for typical shapes. If we need to support back-five, we can later try k=4 and map (e.g. GK + 3 lines → 5-3-2 vs 4-3-3).

### 4.4 Mapping (n_d, n_m, n_f) → formation string

Reuse the same logic as `infer_formation_from_players` in `tactical_components.py`: define a small set of formations and (d, m, f) templates, then choose the one that minimizes Manhattan distance in (n_d, n_m, n_f):

- 4-3-3: (4, 3, 3)
- 4-4-2: (4, 4, 2)
- 3-4-3: (3, 4, 3)
- 5-3-2: (5, 3, 2)
- 4-2-3-1: (4, 2, 3, 1) — can be (4, 5, 1) if we merge AM and M.

So the output of the clustering step is (n_d, n_m, n_f); we map to the closest of these and return that formation string.

### 4.5 Left / centre / right within each line

Within each group (D, M, F), sort players by `cx` (ascending = left to right). Assign slot index 0, 1, 2, … so that we know “left back”, “left centre”, “right centre”, “right back” etc. for drawing. The existing formation renderer uses fixed (x, y) per slot; here we can either:

- **Use heatmap-derived (cx, cy) directly** for each player (most faithful to data), or
- **Snap to a template**: keep the inferred formation and slot indices, but place dots at the same template coordinates as today (so only the *assignment* of which player is in which slot is from heatmaps). Hybrid approach: use (cx, cy) for positioning so the diagram reflects actual average positions.

### 4.6 Goalkeeper

The **lowest-y** player among the 11 is treated as the goalkeeper (assuming standard pitch orientation). If we have nominal `position` and it says GK, we can use that to validate or override. Otherwise, assigning the minimum-y player as GK is a safe heuristic.

### 4.7 Pitch orientation (home vs away)

Heatmaps are usually in a **fixed** pitch frame (e.g. one goal at x=0 or y=0). For both teams, the same (x, y) convention applies. So “low y = defensive end” might be true for one team and reversed for the other if the provider flips by team. In practice, we can:

- Assume **one** orientation for all (e.g. low y = one goal). Then for both teams, “lowest y” = player closest to that goal → we treat them as GK; the rest are outfield. Formation inference (D/M/F) is then consistent.
- If we later have metadata like “team attacks toward y=100”, we can flip one team’s y to `100 - y` so both teams are “attacking upward” in the diagram. For the first version, we do not flip; we only use the single global orientation.

---

## 5. Edge Cases

- **Fewer than 11 players with heatmaps**: Infer formation from the outfield players we have (e.g. 7); still return formation string and slot assignment for those N. UI can show “Based on N players with heatmap data”.
- **Substitutes with many minutes**: Our “top 11 by starter + minutes” already includes them; they will get a (cx, cy) and a slot. No change.
- **Very asymmetric heatmaps** (e.g. full-back always in opposition half): Median still gives a reasonable “average” position; formation might look like 3-5-2 or 2-5-3. We allow any (n_d, n_m, n_f) that comes from clustering and map to nearest standard formation.
- **Missing lineups.csv**: Cannot know `side` or player names; we can still compute formation from heatmap player_ids if we have at least match_id and can get lineups from another source (e.g. `player_appearances` from derived data). The module should accept lineup data as an argument so callers can pass it from raw or from processed.

---

## 6. Integration Points

- **Tactical Profile / Opponent Prep**: For “Formation Analysis”, add an option: “Infer from heatmaps (this match)” when a single match is selected, or “Infer from heatmaps (season aggregate)” by aggregating heatmap points per player over the season and then running the same pipeline (one representative point per player from season heatmap).
- **Post-Match / Review**: After a match, show “Formation from heatmaps” next to the nominal formation, with the same formation pitch component but fed by heatmap-derived positions and formation.
- **Data layer**: New helper in `dashboard/utils/` that:
  - Takes `match_id`, `side`, and optionally pre-loaded `lineups_df` and `heatmap_df`.
  - Returns `{ "formation": "4-3-3", "players": [ { "player_id", "player_name", "cx", "cy", "slot_type", "slot_index", "position" } ] }` so the existing `render_formation_pitch` can be extended to accept “positions from heatmaps” instead of template positions.

---

## 7. Summary

| Step | Action |
|------|--------|
| 1 | Load lineups for match; load heatmap points for match (from parquet or raw). |
| 2 | For the chosen side, take 11 players with heatmap data (starters first, then by minutes). |
| 3 | For each player, compute representative position (median x, median y). |
| 4 | Identify GK = argmin(cy). Outfield = remaining 10. |
| 5 | Gap-based splitting on outfield y: sort by cy, two largest gaps → three lines; count → (n_d, n_m, n_f). |
| 6 | Map (n_d, n_m, n_f) to nearest formation string (4-3-3, 4-4-2, …). |
| 7 | Within each line, sort by cx → left/centre/right slot index. |
| 8 | Return formation + list of 11 with (player_id, name, cx, cy, slot_type, slot_index) for drawing. |

---

## 8. Usage (implementation)

The module `dashboard/utils/formation_from_heatmaps.py` implements the pipeline: **formation_from_heatmaps(match_id, side, lineups_df, heatmap_df)** returns `FormationFromHeatmapsResult` or None; **formation_from_heatmaps_to_render_args(result)** returns `(formation, players)` for renderers; **load_lineups_for_match(match_dir)** loads raw `lineups.csv`. Callers use `18_heatmap_points.parquet` and lineups from raw (e.g. via `get_raw_match_dir_for_match_id`).

This gives a clear, implementable path to “formation and starting XI from heatmaps” that fits the existing data and dashboard components.
