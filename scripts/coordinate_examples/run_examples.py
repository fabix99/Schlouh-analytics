"""
Generate one example per coordinate-based analysis (passes, dribbles, defensive, zones, etc.).
Uses one match's raw rating_breakdown + heatmap + shotmap. Writes HTML files to out_dir.

Run from repo root:
  python scripts/coordinate_examples/run_examples.py
"""
import json
import sys
from pathlib import Path

import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from scripts.coordinate_examples.pitch_plot import add_pitch_shapes, pitch_layout

# Sample match with rating_breakdown (Netherlands Eredivisie 2025-26)
SAMPLE_SEASON = "2025-26"
SAMPLE_COMP = "netherlands-eredivisie"
SAMPLE_MATCH_ID = "14053829"
SAMPLE_PLAYER_ID = 1130306  # has passes, dribbles, defensive, ball-carries


def load_raw(season: str, comp: str, match_id: str, player_id: int) -> dict:
    """Load rating_breakdown, heatmap, shotmap for one player in one match."""
    base = ROOT / "data" / "raw" / season / "club" / comp / match_id / "players"
    out = {}
    for name, filename in [
        ("rating_breakdown", f"rating_breakdown_{player_id}.json"),
        ("heatmap", f"heatmap_{player_id}.json"),
        ("shotmap", f"shotmap_{player_id}.json"),
    ]:
        path = base / filename
        if path.exists():
            with open(path, encoding="utf-8") as f:
                out[name] = json.load(f)
        else:
            out[name] = None
    return out


# ----- 1. Passing map (lines: accurate vs inaccurate) -----
def example_passing_map(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    passes = rb.get("passes") or []
    if not passes:
        return
    fig = go.Figure()
    for p in passes:
        pc = p.get("playerCoordinates") or {}
        pe = p.get("passEndCoordinates") or {}
        x0, y0 = pc.get("x"), pc.get("y")
        x1, y1 = pe.get("x"), pe.get("y")
        if x0 is None or y0 is None or x1 is None or y1 is None:
            continue
        accurate = p.get("outcome", False) is True
        fig.add_trace(
            go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(width=1.5, color="rgba(76,175,80,0.8)" if accurate else "rgba(244,67,54,0.8)"),
                showlegend=False,
                hovertext="Accurate" if accurate else "Inaccurate",
            )
        )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="1. Passing map — green = accurate, red = inaccurate"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 2. Dribble map (points) -----
def example_dribble_map(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    dribbles = rb.get("dribbles") or []
    if not dribbles:
        return
    xs = []
    ys = []
    for d in dribbles:
        pc = d.get("playerCoordinates") or {}
        x, y = pc.get("x"), pc.get("y")
        if x is not None and y is not None:
            xs.append(x)
            ys.append(y)
    if not xs:
        return
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=xs, y=ys, mode="markers",
            marker=dict(size=14, color="#FF9800", symbol="diamond", line=dict(width=1, color="white")),
            name="Dribble",
            hovertemplate="Dribble<br>x: %{x:.0f}<br>y: %{y:.0f}<extra></extra>",
        )
    )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="2. Dribble map — where dribbles happened"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 3. Defensive map (points + clearance lines) -----
def example_defensive_map(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    defensive = rb.get("defensive") or []
    if not defensive:
        return
    fig = go.Figure()
    colors = {"tackle": "#2196F3", "interception": "#9C27B0", "ball-recovery": "#4CAF50", "clearance": "#FF5722"}
    for d in defensive:
        pc = d.get("playerCoordinates") or {}
        pe = d.get("passEndCoordinates") or {}
        x0, y0 = pc.get("x"), pc.get("y")
        if x0 is None or y0 is None:
            continue
        action = d.get("eventActionType") or "other"
        c = colors.get(action, "#757575")
        if pe and pe.get("x") is not None and pe.get("y") is not None:
            fig.add_trace(
                go.Scatter(
                    x=[x0, pe["x"]], y=[y0, pe["y"]],
                    mode="lines", line=dict(width=2, color=c),
                    showlegend=False, hovertext=action,
                )
            )
        fig.add_trace(
            go.Scatter(
                x=[x0], y=[y0], mode="markers",
                marker=dict(size=10, color=c, symbol="circle", line=dict(width=1, color="white")),
                showlegend=False, hovertext=action,
            )
        )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="3. Defensive map — tackles, interceptions, recoveries, clearances"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 4. Ball carries / progression (lines) -----
def example_ball_carries_map(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    carries = rb.get("ball-carries") or []
    if not carries:
        return
    fig = go.Figure()
    for c in carries:
        pc = c.get("playerCoordinates") or {}
        pe = c.get("passEndCoordinates") or {}
        x0, y0 = pc.get("x"), pc.get("y")
        x1, y1 = pe.get("x"), pe.get("y")
        if x0 is None or y0 is None or x1 is None or y1 is None:
            continue
        fig.add_trace(
            go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(width=2, color="rgba(33,150,243,0.7)"),
                showlegend=False,
            )
        )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="4. Ball carries — run with ball (start → end)"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 5. Zone-based: pass volume by zone (6×4 grid) -----
def example_zone_pass_volume(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    passes = rb.get("passes") or []
    if not passes:
        return
    # 6 (length) x 4 (width) zones; assign by pass start
    nx, ny = 6, 4
    counts = [[0] * ny for _ in range(nx)]
    for p in passes:
        pc = p.get("playerCoordinates") or {}
        x, y = pc.get("x"), pc.get("y")
        if x is None or y is None:
            continue
        ix = min(int(x / 100 * nx), nx - 1)
        iy = min(int(y / 100 * ny), ny - 1)
        counts[ix][iy] += 1
    # Heatmap of counts
    z = [counts[ix][iy] for iy in range(ny) for ix in range(nx)]
    z = [z[i * nx : (i + 1) * nx] for i in range(ny)]
    fig = go.Figure(
        go.Heatmap(
            z=z, x=[f"L{i+1}" for i in range(nx)], y=[f"W{j+1}" for j in range(ny)],
            colorscale="Blues", showscale=True,
            hovertemplate="Zone: L%{x} W%{y}<br>Passes: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title="5. Zone-based — pass volume by zone (6×4 grid, from pass start)",
        xaxis_title="Length (L1=def → L6=att)",
        yaxis_title="Width",
        template="plotly_dark",
        height=360,
    )
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 6. Progressive passes only (forward passes) -----
def example_progressive_passes(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    passes = rb.get("passes") or []
    # Progressive = pass moves ball toward opponent goal. Infer attack direction from pass end distribution (median).
    all_y1 = []
    for p in passes:
        pe = p.get("passEndCoordinates") or {}
        y1 = pe.get("y")
        if y1 is not None:
            all_y1.append(y1)
    if not all_y1:
        return
    median_goal = sum(all_y1) / len(all_y1)
    # If most passes end in lower y, team attacks toward low y; progressive = end_y < start_y (and meaningful distance)
    progressive = []
    for p in passes:
        pc = p.get("playerCoordinates") or {}
        pe = p.get("passEndCoordinates") or {}
        x0, y0 = pc.get("x"), pc.get("y")
        x1, y1 = pe.get("x"), pe.get("y")
        if x0 is None or y0 is None or x1 is None or y1 is None:
            continue
        dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        if dist < 5:
            continue
        # Progressive = moves toward the "goal" end (where most passes go)
        if median_goal < 50:
            is_forward = y1 < y0
        else:
            is_forward = y1 > y0
        if is_forward:
            progressive.append((x0, y0, x1, y1, p.get("outcome", False)))
    if not progressive:
        return
    fig = go.Figure()
    for x0, y0, x1, y1, acc in progressive:
        fig.add_trace(
            go.Scatter(
                x=[x0, x1], y=[y0, y1],
                mode="lines",
                line=dict(width=1.8, color="rgba(255,193,7,0.9)" if acc else "rgba(255,152,0,0.6)"),
                showlegend=False,
            )
        )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="6. Progressive passes — passes that move ball forward (yellow = accurate)"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 7. Width & average position (centroid + spread) -----
def example_width_and_position(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    passes = rb.get("passes") or []
    xs, ys = [], []
    for p in passes:
        pc = p.get("playerCoordinates") or {}
        x, y = pc.get("x"), pc.get("y")
        if x is not None and y is not None:
            xs.append(x)
            ys.append(y)
    if not xs:
        return
    import numpy as np
    ax = sum(xs) / len(xs)
    ay = sum(ys) / len(ys)
    sx = np.std(xs)
    sy = np.std(ys)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=xs, y=ys, mode="markers",
            marker=dict(size=4, color="rgba(33,150,243,0.4)"),
            name="Pass start",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[ax], y=[ay], mode="markers",
            marker=dict(size=18, color="#E91E63", symbol="star", line=dict(width=2, color="white")),
            name=f"Average position (σx={sx:.0f}, σy={sy:.0f})",
        )
    )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="7. Width & average position — pass start locations + centroid"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 8. Pressing / defensive actions by zone -----
def example_pressing_zones(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    defensive = rb.get("defensive") or []
    if not defensive:
        return
    nx, ny = 6, 4
    counts = [[0] * ny for _ in range(nx)]
    for d in defensive:
        pc = d.get("playerCoordinates") or {}
        x, y = pc.get("x"), pc.get("y")
        if x is None or y is None:
            continue
        ix = min(int(x / 100 * nx), nx - 1)
        iy = min(int(y / 100 * ny), ny - 1)
        counts[ix][iy] += 1
    z = [counts[ix][iy] for iy in range(ny) for ix in range(nx)]
    z = [z[i * nx : (i + 1) * nx] for i in range(ny)]
    fig = go.Figure(
        go.Heatmap(
            z=z, x=[f"L{i+1}" for i in range(nx)], y=[f"W{j+1}" for j in range(ny)],
            colorscale="Reds", showscale=True,
            hovertemplate="Zone<br>Defensive actions: %{z}<extra></extra>",
        )
    )
    fig.update_layout(
        title="8. Pressing / defensive actions by zone",
        xaxis_title="Length", yaxis_title="Width",
        template="plotly_dark", height=360,
    )
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 9. Shot map (if shotmap available) -----
def example_shot_map(data: dict, out_path: Path) -> None:
    shotmap = data.get("shotmap") or {}
    shots = shotmap.get("shotmap") if isinstance(shotmap, dict) else []
    if not shots:
        return
    xs, ys, xgs, labels = [], [], [], []
    for s in shots:
        pc = s.get("playerCoordinates") or {}
        x, y = pc.get("x"), pc.get("y")
        if x is not None and y is not None:
            xs.append(x)
            ys.append(y)
            xgs.append(s.get("xg") or 0)
            labels.append(f"xG: {s.get('xg', 0):.2f} — {s.get('shotType', '')}")
    if not xs:
        return
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=xs, y=ys, mode="markers",
            marker=dict(size=[max(8, 8 + g * 20) for g in xgs], color=xgs, colorscale="Reds", showscale=True, colorbar=dict(title="xG")),
            text=labels, hovertemplate="%{text}<extra></extra>",
        )
    )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="9. Shot map — location & xG (size = xG)"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


# ----- 10. Combined action map (passes + dribbles + defensive) -----
def example_combined_action_map(data: dict, out_path: Path) -> None:
    rb = data.get("rating_breakdown") or {}
    fig = go.Figure()
    # Passes (lines, thin)
    for p in (rb.get("passes") or [])[:40]:
        pc, pe = p.get("playerCoordinates") or {}, p.get("passEndCoordinates") or {}
        x0, y0 = pc.get("x"), pc.get("y")
        x1, y1 = pe.get("x"), pe.get("y")
        if x0 is not None and y0 is not None and x1 is not None and y1 is not None:
            fig.add_trace(
                go.Scatter(x=[x0, x1], y=[y0, y1], mode="lines", line=dict(width=1, color="rgba(76,175,80,0.5)"), showlegend=False)
            )
    # Dribbles (orange diamonds)
    dribbles = rb.get("dribbles") or []
    dx = [d.get("playerCoordinates", {}).get("x") for d in dribbles]
    dy = [d.get("playerCoordinates", {}).get("y") for d in dribbles]
    dx = [x for x in dx if x is not None]
    dy = [y for y in dy if y is not None]
    if dx and dy:
        fig.add_trace(
            go.Scatter(x=dx, y=dy, mode="markers", marker=dict(size=10, color="#FF9800", symbol="diamond"), name="Dribbles")
        )
    # Defensive (blue dots)
    defs = rb.get("defensive") or []
    fx = [d.get("playerCoordinates", {}).get("x") for d in defs]
    fy = [d.get("playerCoordinates", {}).get("y") for d in defs]
    fx = [x for x in fx if x is not None]
    fy = [y for y in fy if y is not None]
    if fx and fy:
        fig.add_trace(
            go.Scatter(x=fx, y=fy, mode="markers", marker=dict(size=8, color="#2196F3", symbol="circle"), name="Defensive")
        )
    add_pitch_shapes(fig)
    fig.update_layout(**pitch_layout(title="10. Combined — passes (green) + dribbles (orange) + defensive (blue)"))
    fig.write_html(str(out_path))
    print(f"Wrote {out_path}")


def main():
    out_dir = ROOT / "report" / "coordinate_examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    data = load_raw(SAMPLE_SEASON, SAMPLE_COMP, SAMPLE_MATCH_ID, SAMPLE_PLAYER_ID)
    if not data.get("rating_breakdown"):
        print("No rating_breakdown found. Ensure data/raw/.../players/rating_breakdown_*.json exists.")
        return

    examples = [
        (example_passing_map, "01_passing_map.html"),
        (example_dribble_map, "02_dribble_map.html"),
        (example_defensive_map, "03_defensive_map.html"),
        (example_ball_carries_map, "04_ball_carries_map.html"),
        (example_zone_pass_volume, "05_zone_pass_volume.html"),
        (example_progressive_passes, "06_progressive_passes.html"),
        (example_width_and_position, "07_width_and_position.html"),
        (example_pressing_zones, "08_pressing_zones.html"),
        (example_shot_map, "09_shot_map.html"),
        (example_combined_action_map, "10_combined_action_map.html"),
    ]
    for fn, filename in examples:
        try:
            fn(data, out_dir / filename)
        except Exception as e:
            print(f"Skip {filename}: {e}")

    print(f"\nDone. Open files in {out_dir} (e.g. open report/coordinate_examples/01_passing_map.html)")


if __name__ == "__main__":
    main()
