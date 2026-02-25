"""Enhanced tactical components for Tactics Dashboard.

This module provides:
- Formation visualizations
- Tactical comparisons with radar charts
- Player role compatibility analysis
- Opposition scouting report generator
"""

from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Standard tactical radar axes (key, label) — raw indices are normalized to 0–100 using pool
TACTICAL_RADAR_INDICES = [
    ("possession_index", "Possession"),
    ("pressing_index", "Pressing"),
    ("directness_index", "Direct"),
    ("aerial_index", "Aerial"),
]
TACTICAL_RADAR_INDICES_FULL = [
    ("possession_index", "Possession"),
    ("directness_index", "Directness"),
    ("pressing_index", "Pressing"),
    ("aerial_index", "Aerial"),
    ("crossing_index", "Crossing"),
    ("chance_creation_index", "Chance Creation"),
    ("defensive_solidity", "Defensive"),
]


def normalize_tactical_radar_to_100(
    tac_row: Union[pd.Series, Dict[str, float]],
    pool_df: pd.DataFrame,
    index_keys: List[Tuple[str, str]],
) -> List[float]:
    """Normalize raw tactical index values to 0–100 using pool min–max per axis.

    Raw indices from 15_team_tactical_profiles are on different scales (e.g. possession 0–100,
    directness 0–1, pressing raw count). Plotly radar expects a single scale; this maps each
    axis to 0–100 within the pool so all radars render correctly.
    """
    def _get(v, k):
        if isinstance(v, dict):
            return v.get(k, np.nan)
        if hasattr(v, "index") and k in v.index:
            return v[k]
        return np.nan

    out = []
    for k, _ in index_keys:
        val = _get(tac_row, k)
        if pd.isna(val):
            out.append(50.0)
            continue
        if k not in pool_df.columns:
            out.append(50.0)
            continue
        col = pool_df[k].dropna()
        if len(col) < 1:
            out.append(50.0)
            continue
        lo, hi = float(col.min()), float(col.max())
        if hi <= lo:
            out.append(50.0)
        else:
            pct = (float(val) - lo) / (hi - lo) * 100
            out.append(max(0.0, min(100.0, pct)))
    return out


def get_tactical_percentiles(
    tac_row: Union[pd.Series, Dict[str, Any]],
    pool_df: pd.DataFrame,
    index_keys: Optional[List[Tuple[str, str]]] = None,
) -> Dict[str, float]:
    """Return percentile (0–100) per tactical index for use in threats/weaknesses/prediction.

    Uses _pct column from 15_team_tactical_profiles when present (league-relative rank),
    otherwise computes min–max percentile from pool. Raw indices are on inconsistent scales
    so fixed thresholds (e.g. pressing_index > 70) are meaningless; percentiles make comparisons valid.
    """
    if index_keys is None:
        index_keys = list(TACTICAL_RADAR_INDICES_FULL)
    out = {}
    for k, _ in index_keys:
        pct_col = k + "_pct"
        if hasattr(tac_row, "get") and tac_row.get(pct_col) is not None:
            val = tac_row.get(pct_col)
            if pd.notna(val):
                out[k] = float(val) * 100.0
                continue
        if hasattr(tac_row, "index") and pct_col in tac_row.index and pd.notna(tac_row.get(pct_col)):
            out[k] = float(tac_row[pct_col]) * 100.0
            continue
        if not pool_df.empty and k in pool_df.columns:
            val = tac_row.get(k) if hasattr(tac_row, "get") else (tac_row[k] if k in getattr(tac_row, "index", []) else np.nan)
            if pd.isna(val):
                out[k] = 50.0
            else:
                col = pool_df[k].dropna()
                if len(col) >= 1:
                    pct = (col < float(val)).sum() / len(col) * 100
                    out[k] = max(0.0, min(100.0, pct))
                else:
                    out[k] = 50.0
        else:
            out[k] = 50.0
    return out


# =============================================================================
# FORMATION VISUALIZATIONS
# =============================================================================

def render_formation_pitch(
    formation: str,
    players: List[Dict[str, Any]],
    width: int = 800,
    height: int = 600,
    highlight_player: Optional[str] = None
) -> None:
    """Render a tactical formation on a football pitch visualization.

    Args:
        formation: Formation string (e.g., '4-3-3', '3-4-3')
        players: List of player dicts with 'name', 'position', 'rating', 'role'
        width: Plot width in pixels
        height: Plot height in pixels
        highlight_player: Player name to highlight
    """
    # Define standard positions for common formations
    formation_positions = {
        '4-3-3': {
            'GK': [(50, 5)],
            'D': [(15, 25), (38, 22), (62, 22), (85, 25)],
            'M': [(25, 50), (50, 45), (75, 50)],
            'F': [(20, 75), (50, 80), (80, 75)],
        },
        '4-4-2': {
            'GK': [(50, 5)],
            'D': [(15, 25), (38, 22), (62, 22), (85, 25)],
            'M': [(15, 55), (38, 50), (62, 50), (85, 55)],
            'F': [(35, 80), (65, 80)],
        },
        '3-4-3': {
            'GK': [(50, 5)],
            'D': [(25, 22), (50, 20), (75, 22)],
            'M': [(15, 50), (38, 48), (62, 48), (85, 50)],
            'F': [(20, 78), (50, 82), (80, 78)],
        },
        '5-3-2': {
            'GK': [(50, 5)],
            'D': [(10, 22), (30, 18), (50, 16), (70, 18), (90, 22)],
            'M': [(25, 50), (50, 48), (75, 50)],
            'F': [(35, 80), (65, 80)],
        },
        '4-2-3-1': {
            'GK': [(50, 5)],
            'D': [(15, 25), (38, 22), (62, 22), (85, 25)],
            'M': [(30, 45), (70, 45)],  # DM
            'AM': [(20, 65), (50, 68), (80, 65)],  # AM
            'F': [(50, 85)],
        },
    }

    # Create pitch figure
    fig = go.Figure()

    # Pitch background
    fig.add_shape(
        type="rect",
        x0=0, y0=0, x1=100, y1=100,
        fillcolor="#2E7D32",
        line=dict(color="#1B5E20", width=2),
        layer="below"
    )

    # Pitch lines
    # Center line
    fig.add_shape(type="line", x0=0, y0=50, x1=100, y1=50,
                  line=dict(color="white", width=2), layer="below")
    # Center circle
    fig.add_shape(type="circle", x0=40, y0=45, x1=60, y1=55,
                  line=dict(color="white", width=2), layer="below", fillcolor="#2E7D32")
    # Penalty boxes (simplified)
    fig.add_shape(type="rect", x0=20, y0=0, x1=80, y1=15,
                  line=dict(color="white", width=2), layer="below")
    fig.add_shape(type="rect", x0=20, y0=85, x1=80, y1=100,
                  line=dict(color="white", width=2), layer="below")

    # Get positions for formation
    positions = formation_positions.get(formation, formation_positions['4-3-3'])

    # Plot players
    for player in players:
        pos = player.get('position', 'F')
        # Map position to formation slot
        slot = 'F'
        if pos == 'G':
            slot = 'GK'
        elif pos == 'D':
            slot = 'D'
        elif pos == 'M':
            slot = 'M'
        elif pos == 'F':
            slot = 'F'

        # Get coordinates
        coords_list = positions.get(slot, [(50, 50)])
        # Assign based on player index for that position
        idx = sum(1 for p in players[:players.index(player)] if p.get('position') == pos)
        x, y = coords_list[min(idx, len(coords_list) - 1)]

        # Determine player marker properties
        rating = player.get('rating', 6.5)
        name = player.get('name', 'Unknown')
        role = player.get('role', '')

        # Color based on rating
        if rating >= 7.5:
            color = "#FFD700"  # Gold
            size = 20
        elif rating >= 7.0:
            color = "#C9A840"  # Highlight
            size = 18
        elif rating >= 6.5:
            color = "#58A6FF"  # Blue
            size = 16
        else:
            color = "#8B949E"  # Gray
            size = 14

        # Highlight if requested
        if highlight_player and name == highlight_player:
            color = "#FF6B6B"
            size = 24
            fig.add_shape(
                type="circle",
                x0=x-8, y0=y-8, x1=x+8, y1=y+8,
                line=dict(color="#FF6B6B", width=3),
                fillcolor="rgba(255, 107, 107, 0.2)",
                layer="above"
            )

        # Add player marker
        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode='markers+text',
            marker=dict(size=size, color=color, line=dict(color="white", width=2)),
            text=[name.split()[-1] if ' ' in name else name],  # Last name only
            textposition="top center",
            textfont=dict(size=10, color="white"),
            hovertemplate=f"<b>{name}</b><br>Position: {pos}<br>Rating: {rating:.2f}<br>Role: {role}<extra></extra>",
            showlegend=False
        ))

    # Layout
    fig.update_layout(
        width=width,
        height=height,
        xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(range=[0, 100], showgrid=False, showticklabels=False, zeroline=False),
        plot_bgcolor="#2E7D32",
        paper_bgcolor="#0D1117",
        margin=dict(l=20, r=20, t=40, b=20),
        title=dict(
            text=f"Formation: {formation}",
            font=dict(size=16, color="white"),
            x=0.5
        ),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_formation_selector(
    available_formations: List[str],
    default: str = '4-3-3',
    key: str = 'formation_select'
) -> str:
    """Render a visual formation selector.

    Args:
        available_formations: List of formation strings
        default: Default selected formation
        key: Streamlit key

    Returns:
        Selected formation string
    """
    st.markdown("**Select Formation**")

    # Display formations as selectable cards
    cols = st.columns(min(len(available_formations), 6))

    if key not in st.session_state:
        st.session_state[key] = default

    for i, formation in enumerate(available_formations):
        with cols[i % 6]:
            is_selected = st.session_state[key] == formation

            # Card styling
            bg_color = "#C9A840" if is_selected else "#21262D"
            text_color = "#0D1117" if is_selected else "#F0F6FC"
            border = "3px solid #C9A840" if is_selected else "1px solid #30363D"

            st.markdown(
                f"""
                <div style="
                    background: {bg_color};
                    color: {text_color};
                    padding: 15px 10px;
                    border-radius: 8px;
                    text-align: center;
                    cursor: pointer;
                    border: {border};
                    font-weight: 600;
                    font-size: 1.1rem;
                ">
                    {formation}
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button(f"Select {formation}", key=f"{key}_{formation}", use_container_width=True):
                st.session_state[key] = formation
                st.rerun()

    return st.session_state[key]


def render_tactical_roles_matrix(
    players: pd.DataFrame,
    roles: List[str],
    compatibility_scores: Optional[pd.DataFrame] = None
) -> None:
    """Render a matrix showing player-role compatibility.

    Args:
        players: DataFrame with player data
        roles: List of tactical role names
        compatibility_scores: Optional DataFrame of player-role compatibility (0-100)
    """
    if compatibility_scores is None:
        # Generate mock compatibility scores
        np.random.seed(42)
        compatibility_scores = pd.DataFrame(
            np.random.randint(40, 95, size=(len(players), len(roles))),
            index=players['player_name'].values if 'player_name' in players.columns else range(len(players)),
            columns=roles
        )

    st.markdown("**Player-Role Compatibility Matrix**")

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=compatibility_scores.values,
        x=compatibility_scores.columns,
        y=compatibility_scores.index,
        colorscale=[
            [0, "#F85149"],      # Red (low)
            [0.5, "#C9A840"],    # Yellow (medium)
            [1, "#3FB950"]       # Green (high)
        ],
        zmin=0,
        zmax=100,
        text=compatibility_scores.values.astype(int),
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate="Player: %{y}<br>Role: %{x}<br>Score: %{z:.0f}<extra></extra>",
    ))

    fig.update_layout(
        width=800,
        height=400,
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10)),
        paper_bgcolor="#0D1117",
        plot_bgcolor="#161B22",
        font=dict(color="#F0F6FC"),
    )

    st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TACTICAL COMPARISONS
# =============================================================================

def render_tactical_radar_comparison(
    team1_data: Dict[str, float],
    team2_data: Dict[str, float],
    team1_name: str,
    team2_name: str,
    indices: Optional[List[Tuple[str, str]]] = None,
    pool_df: Optional[pd.DataFrame] = None,
) -> None:
    """Render a radar chart comparing two teams.

    Values are normalized to 0–100 using pool_df min–max per axis so the radar renders
    correctly (raw tactical indices are on different scales). If pool_df is None, normalization
    is skipped and raw values are used (may appear broken if scales differ).

    Args:
        team1_data: First team tactical indices (raw)
        team2_data: Second team tactical indices (raw)
        team1_name: First team name
        team2_name: Second team name
        indices: List of (index_key, label) tuples
        pool_df: Pool of teams (same season/comp) for min–max normalization; required for correct scale
    """
    if indices is None:
        indices = list(TACTICAL_RADAR_INDICES_FULL)

    # Normalize to 0–100 using pool so all axes are comparable
    if pool_df is not None and not pool_df.empty:
        team1_vals = normalize_tactical_radar_to_100(team1_data, pool_df, indices)
        team2_vals = normalize_tactical_radar_to_100(team2_data, pool_df, indices)
    else:
        def _safe_radar_val(v):
            if v is None or (isinstance(v, float) and not np.isfinite(v)):
                return 50.0
            return max(0.0, min(100.0, float(v)))
        team1_vals = [_safe_radar_val(team1_data.get(k, 50)) for k, _ in indices]
        team2_vals = [_safe_radar_val(team2_data.get(k, 50)) for k, _ in indices]
    labels = [l for _, l in indices]

    def _comment(v: float) -> str:
        if v >= 70:
            return "Strong in this area"
        if v >= 50:
            return "League average or above"
        if v >= 30:
            return "Below league average"
        return "Weak in this area"

    # One shared tooltip per axis: show both teams so hovering either polygon gives full comparison
    # customdata: [label, v1, v2, comment1, comment2, team1_name, team2_name]
    combined = [
        [lab, round(v1, 0), round(v2, 0), _comment(v1), _comment(v2), team1_name, team2_name]
        for lab, v1, v2 in zip(labels, team1_vals, team2_vals)
    ]
    combined.append(combined[0])  # close polygon

    hovertemplate = (
        "<b>%{customdata[0]}</b><br>"
        "<span style='color:#C9A840'>%{customdata[5]}</span>: %{customdata[1]:.0f}/100 — %{customdata[3]}<br>"
        "<span style='color:#58A6FF'>%{customdata[6]}</span>: %{customdata[2]:.0f}/100 — %{customdata[4]}"
        "<extra></extra>"
    )

    # Create radar chart (values already in [0, 100] from normalize or _safe_radar_val)
    fig = go.Figure()

    # Team 1
    fig.add_trace(go.Scatterpolar(
        r=team1_vals + [team1_vals[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor="rgba(201,168,64,0.2)",
        line=dict(color="#C9A840", width=2),
        name=team1_name,
        customdata=combined,
        hovertemplate=hovertemplate,
    ))

    # Team 2
    fig.add_trace(go.Scatterpolar(
        r=team2_vals + [team2_vals[0]],
        theta=labels + [labels[0]],
        fill="toself",
        fillcolor="rgba(88,166,255,0.2)",
        line=dict(color="#58A6FF", width=2),
        name=team2_name,
        customdata=combined,
        hovertemplate=hovertemplate,
    ))

    fig.update_layout(
        polar=dict(
            bgcolor="#0D1117",
            radialaxis=dict(visible=True, range=[0, 100], showticklabels=False, gridcolor="#30363D"),
            angularaxis=dict(gridcolor="#30363D", tickfont=dict(size=11, color="#E6EDF3")),
        ),
        paper_bgcolor="#0D1117",
        plot_bgcolor="#0D1117",
        font=dict(color="#E6EDF3"),
        margin=dict(l=44, r=44, t=40, b=40),
        height=400,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
    )

    st.plotly_chart(fig, use_container_width=True)


def _safe_stat(v):
    """Return float or None if missing/NaN/zero (for no-data detection)."""
    if v is None:
        return None
    if hasattr(v, "item"):
        v = v.item()
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _format_stat_value(val: Optional[float], label: str) -> str:
    """Format value for display: add % for percentage metrics, else one decimal."""
    if val is None:
        return "—"
    if "%" in label or "Possession" in label or "Pass" in label or "Completion" in label:
        return f"{val:.1f}%"
    if val == int(val):
        return str(int(val))
    return f"{val:.1f}"


def render_head_to_head_comparison(
    team1_stats: pd.Series,
    team2_stats: pd.Series,
    team1_name: str,
    team2_name: str,
    metrics: Optional[List[Tuple[str, str]]] = None
) -> None:
    """Render head-to-head stat comparison as a compact table with leader highlighted.

    Percent-style metrics (Possession, Pass Completion) and count metrics are shown
    in a scannable table; the higher value per row is highlighted.
    """
    if metrics is None:
        metrics = [
            ("possession_pct", "Possession % (avg)"),
            ("shots_per_match", "Shots per match (avg)"),
            ("xg_for_total", "Total xG (season total)"),
            ("goals_for", "Goals (season total)"),
            ("pass_completion_pct", "Pass completion % (avg)"),
            ("tackles_per_match", "Tackles per match (avg)"),
        ]

    rows: List[Tuple[str, Optional[float], Optional[float]]] = []
    for col, label in metrics:
        v1 = team1_stats.get(col, None) if hasattr(team1_stats, "get") else None
        v2 = team2_stats.get(col, None) if hasattr(team2_stats, "get") else None
        val1 = _safe_stat(v1)
        val2 = _safe_stat(v2)
        rows.append((label, val1, val2))

    # Build a compact table: Metric | Team1 | Team2, with leader highlighted
    table_html = [
        "<table style='width:100%; border-collapse: collapse; font-size: 0.9rem;'>",
        "<thead><tr style='border-bottom: 1px solid #30363D;'>",
        f"<th style='text-align:left; padding: 6px 8px; color: #8B949E;'>Metric</th>",
        f"<th style='text-align:center; padding: 6px 8px; color: #C9A840;'>{team1_name[:20]}{'…' if len(team1_name) > 20 else ''}</th>",
        f"<th style='text-align:center; padding: 6px 8px; color: #58A6FF;'>{team2_name[:20]}{'…' if len(team2_name) > 20 else ''}</th>",
        "</tr></thead><tbody>",
    ]
    for label, val1, val2 in rows:
        no_data = (val1 is None or val1 == 0) and (val2 is None or val2 == 0)
        d1 = _format_stat_value(val1, label)
        d2 = _format_stat_value(val2, label)
        if no_data:
            td1 = f"<td style='text-align:center; padding: 6px 8px; color: #6E7681;'>—</td>"
            td2 = f"<td style='text-align:center; padding: 6px 8px; color: #6E7681;'>—</td>"
        else:
            v1 = val1 or 0
            v2 = val2 or 0
            # Higher is better for all these metrics
            win1 = v1 > v2
            win2 = v2 > v1
            td1 = (
                f"<td style='text-align:center; padding: 6px 8px; font-weight: 600; background: rgba(201,168,64,0.15); border-radius: 4px; color: #C9A840;'>{d1}</td>"
                if win1
                else f"<td style='text-align:center; padding: 6px 8px; color: #E6EDF3;'>{d1}</td>"
            )
            td2 = (
                f"<td style='text-align:center; padding: 6px 8px; font-weight: 600; background: rgba(88,166,255,0.15); border-radius: 4px; color: #58A6FF;'>{d2}</td>"
                if win2
                else f"<td style='text-align:center; padding: 6px 8px; color: #E6EDF3;'>{d2}</td>"
            )
        table_html.append(
            f"<tr style='border-bottom: 1px solid #21262D;'>"
            f"<td style='padding: 6px 8px; color: #8B949E;'>{label}</td>{td1}{td2}</tr>"
        )
    table_html.append("</tbody></table>")
    st.markdown(
        "<div style='margin-top: 4px;'>" + "".join(table_html) + "</div>",
        unsafe_allow_html=True,
    )


# =============================================================================
# SCOUTING REPORTS
# =============================================================================

def _render_player_watch_row(player: Dict[str, Any]) -> None:
    """Render a single player row (name, position, rating, threat badge). Fills column width."""
    name = player.get('name', 'Unknown')
    pos = player.get('position', '?')
    rating = player.get('rating', 0)
    threat = player.get('threat_level', 'Medium')
    threat_color = {"High": "#F85149", "Medium": "#C9A840", "Low": "#3FB950"}.get(threat, "#8B949E")
    st.markdown(
        f"""
        <div style="
            width: 100%;
            box-sizing: border-box;
            background: #21262D;
            padding: 10px;
            border-radius: 6px;
            margin: 4px 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        ">
            <div style="min-width: 0;">
                <div style="font-weight: 600; color: #F0F6FC;">{name}</div>
                <div style="font-size: 0.75rem; color: #8B949E;">{pos} • Rating: {rating:.2f}</div>
            </div>
            <div style="flex-shrink: 0; background: {threat_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem;">
                {threat} Threat
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_opposition_scouting_card(
    opponent_name: str,
    formation: str,
    key_players: List[Dict[str, Any]],
    threats: List[str],
    weaknesses: List[str],
    predicted_tactics: str,
    lowest_rated_starters: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Render a comprehensive opposition scouting card.

    Args:
        opponent_name: Name of opponent team
        formation: Expected formation
        key_players: List of key player dicts (top threats)
        threats: List of tactical threats
        weaknesses: List of opponent weaknesses
        predicted_tactics: Description of predicted tactics
        lowest_rated_starters: Optional list of usual starters with lowest ratings (to exploit)
    """
    with st.container():
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #161B22 0%, #0D1117 100%);
                border: 2px solid #C9A840;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <div>
                        <div style="font-size: 1.3rem; font-weight: 700; color: #F0F6FC;">
                            🔍 Opposition Report: {opponent_name}
                        </div>
                        <div style="font-size: 0.9rem; color: #C9A840;">Formation: {formation}</div>
                    </div>
                    <div style="background: #C9A840; color: #0D1117; padding: 5px 15px; border-radius: 20px; font-weight: 600;">
                        Priority: High
                    </div>
                </div>
            """,
            unsafe_allow_html=True
        )

        # Predicted tactics
        st.markdown("**📋 Predicted Tactics**")
        st.markdown(f"<div style='background: #21262D; padding: 10px; border-radius: 6px; color: #E6EDF3;'>{predicted_tactics}</div>", unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        _card_style = "width: 100%; box-sizing: border-box; padding: 8px 12px; margin: 6px 0; border-radius: 0 4px 4px 0; color: #F0F6FC; font-size: 0.9rem;"
        _player_card_style = "width: 100%; box-sizing: border-box; background: #21262D; padding: 8px 10px; border-radius: 6px; margin: 4px 0; font-size: 0.9rem; color: #E6EDF3;"

        with col1:
            st.markdown("<div style='width:100%;'>", unsafe_allow_html=True)
            st.markdown("**⚠️ Key Threats**")
            for threat in threats:
                st.markdown(
                    f"""<div style="{_card_style} background: #F8514920; border-left: 3px solid #F85149;">{threat}</div>""",
                    unsafe_allow_html=True
                )
            st.markdown("**🎯 Key Players to Watch**")
            st.caption("Threat is based on season rating: **High** >7.5 · **Medium** >7.0 · **Low** ≤7.0")
            for player in key_players:
                _render_player_watch_row(player)
            st.markdown("</div>", unsafe_allow_html=True)

        with col2:
            st.markdown("<div style='width:100%;'>", unsafe_allow_html=True)
            st.markdown("**💪 Exploitable Weaknesses**")
            for weakness in weaknesses:
                st.markdown(
                    f"""<div style="{_card_style} background: #3FB95020; border-left: 3px solid #3FB950;">{weakness}</div>""",
                    unsafe_allow_html=True
                )
            if lowest_rated_starters:
                st.markdown("**📉 Lowest-rated starters**")
                st.caption("Usual starters (enough minutes) with lowest season rating — potential targets.")
                for p in lowest_rated_starters:
                    name = p.get("name", "?")
                    pos = p.get("position", "?")
                    rating = p.get("rating", 0)
                    st.markdown(
                        f"""<div style="{_player_card_style}"><span style="font-weight: 600;">{name}</span><span style="color: #8B949E;"> · {pos} · Rating {rating:.2f}</span></div>""",
                        unsafe_allow_html=True
                    )
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


def render_match_prediction_card(
    team1_name: str,
    team2_name: str,
    win_prob: Tuple[float, float, float],  # team1, draw, team2
    predicted_score: str,
    confidence: str,
    key_factors: List[str]
) -> None:
    """Render a match prediction card.

    Args:
        team1_name: First team name
        team2_name: Second team name
        win_prob: Tuple of win probabilities (team1, draw, team2)
        predicted_score: Predicted scoreline
        confidence: Confidence level (High/Medium/Low)
        key_factors: List of key predictive factors
    """
    t1_prob, draw_prob, t2_prob = win_prob

    conf_colors = {"High": "#3FB950", "Medium": "#C9A840", "Low": "#F85149"}
    conf_color = conf_colors.get(confidence, "#8B949E")

    with st.container():
        st.markdown(
            f"""
            <div style="
                background: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
            ">
                <div style="text-align: center; margin-bottom: 20px;">
                    <div style="font-size: 0.85rem; color: #8B949E; margin-bottom: 5px;">Match Prediction</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: #F0F6FC;">
                        {team1_name} vs {team2_name}
                    </div>
                </div>
            """,
            unsafe_allow_html=True
        )

        # Probabilities
        cols = st.columns(3)

        with cols[0]:
            st.markdown(
                f"""
                <div style="text-align: center;">
                    <div style="font-size: 0.8rem; color: #8B949E;">{team1_name}</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #C9A840;">{t1_prob:.0f}%</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with cols[1]:
            st.markdown(
                f"""
                <div style="text-align: center;">
                    <div style="font-size: 0.8rem; color: #8B949E;">Draw</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #8B949E;">{draw_prob:.0f}%</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with cols[2]:
            st.markdown(
                f"""
                <div style="text-align: center;">
                    <div style="font-size: 0.8rem; color: #8B949E;">{team2_name}</div>
                    <div style="font-size: 1.8rem; font-weight: 700; color: #58A6FF;">{t2_prob:.0f}%</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Predicted score
        st.markdown("---")
        st.markdown(
            f"""
            <div style="text-align: center; font-size: 0.8rem; color: #8B949E; margin-bottom: 4px;">Expected xG (us–them)</div>
            <div style="display: flex; justify-content: center; align-items: center; gap: 20px; margin: 15px 0;">
                <div style="font-size: 2rem; font-weight: 700; color: #C9A840;">{predicted_score}</div>
                <div style="background: {conf_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;">
                    {confidence} Confidence
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Key factors
        st.markdown("**Key Factors**")
        for factor in key_factors:
            st.markdown(f"• {factor}")

        st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# LEAGUE TRENDS
# =============================================================================

def render_league_trends_dashboard(
    trends_data: pd.DataFrame,
    selected_metric: str = "possession"
) -> None:
    """Render league trends dashboard with multiple visualizations.

    Args:
        trends_data: DataFrame with league trend data
        selected_metric: Metric to highlight
    """
    # Metric over time
    st.markdown("**Trend Over Time**")

    fig = go.Figure()

    for league in trends_data['league'].unique():
        league_data = trends_data[trends_data['league'] == league]
        fig.add_trace(go.Scatter(
            x=league_data['season'],
            y=league_data[selected_metric],
            mode='lines+markers',
            name=league,
            line=dict(width=3),
        ))

    fig.update_layout(
        xaxis=dict(title="Season", tickangle=-45),
        yaxis=dict(title=selected_metric.replace('_', ' ').title()),
        paper_bgcolor="#0D1117",
        plot_bgcolor="#161B22",
        font=dict(color="#F0F6FC"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_tactical_style_evolution(
    team_data: pd.DataFrame,
    style_columns: List[str],
    team_name: str
) -> None:
    """Render evolution of tactical style over time.

    Args:
        team_data: DataFrame with team data over multiple seasons
        style_columns: List of style index columns
        team_name: Team name for title
    """
    st.markdown(f"**{team_name} Tactical Evolution**")

    # Create stacked area chart
    fig = go.Figure()

    for col in style_columns:
        label = col.replace('_index', '').title()
        fig.add_trace(go.Scatter(
            x=team_data['season'],
            y=team_data[col],
            mode='lines',
            stackgroup='one',
            name=label,
            fill='tonexty',
        ))

    fig.update_layout(
        xaxis=dict(title="Season", tickangle=-45),
        yaxis=dict(title="Tactical Index Value", range=[0, 100]),
        paper_bgcolor="#0D1117",
        plot_bgcolor="#161B22",
        font=dict(color="#F0F6FC"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_team_similarity_matrix(
    teams_data: pd.DataFrame,
    team_names: List[str],
    similarity_metric: str = "euclidean"
) -> None:
    """Render team similarity matrix.

    Args:
        teams_data: DataFrame with team tactical data
        team_names: List of team names to compare
        similarity_metric: Metric for similarity calculation
    """
    from scipy.spatial.distance import pdist, squareform
    from scipy.cluster.hierarchy import linkage, dendrogram

    # Filter to selected teams and style columns
    style_cols = [c for c in teams_data.columns if 'index' in c or c in ['defensive_solidity']]
    team_vectors = teams_data[teams_data['team_name'].isin(team_names)][style_cols].fillna(50)

    if len(team_vectors) < 2:
        st.info("Need at least 2 teams for similarity comparison")
        return

    # Calculate distance matrix
    distances = pdist(team_vectors.values, metric=similarity_metric)
    dist_matrix = squareform(distances)

    # Convert to similarity (inverse of distance, normalized)
    max_dist = dist_matrix.max() if dist_matrix.max() > 0 else 1
    similarity = 1 - (dist_matrix / max_dist)

    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        z=similarity,
        x=team_names,
        y=team_names,
        colorscale="RdYlGn",
        zmin=0,
        zmax=1,
        text=np.round(similarity, 2),
        texttemplate="%{text:.2f}",
        hovertemplate="Team 1: %{y}<br>Team 2: %{x}<br>Similarity: %{z:.2f}<extra></extra>",
    ))

    fig.update_layout(
        title="Team Tactical Similarity Matrix",
        width=600,
        height=600,
        xaxis=dict(tickangle=-45),
        paper_bgcolor="#0D1117",
        plot_bgcolor="#161B22",
        font=dict(color="#F0F6FC"),
    )

    st.plotly_chart(fig, use_container_width=True)
