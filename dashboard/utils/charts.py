"""Reusable Plotly chart builders."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from dashboard.utils.constants import PLAYER_COLORS

_BG       = "#0D1117"
_GRID     = "#3D4450"   # Increased contrast for better visibility
_TEXT     = "#E6EDF3"
_SUB_TEXT = "#8B949E"
_GOLD     = "#C9A840"   # Schlouh brand gold


def _hex_to_rgba(hex_color: str, alpha: float = 0.2) -> str:
    """Convert 6-digit hex to rgba string (Plotly does not accept 8-digit hex)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _base_layout(**kwargs) -> dict:
    base = dict(
        paper_bgcolor=_BG,
        plot_bgcolor=_BG,
        font=dict(color=_TEXT, family="DM Sans, Inter, sans-serif"),
        margin=dict(l=44, r=44, t=52, b=44),
    )
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Radar chart
# ---------------------------------------------------------------------------
# Scale convention: This chart is for PERCENTILE or 0–100 INDEX data only.
# Clamping to [0, 100] is correct here because percentiles/indices are defined
# on that scale. Do NOT use this chart for raw metrics (e.g. goals/90, xG/90)
# on a data-driven scale—those need range=[0, max] or per-axis scaling; clamping
# would truncate real values and distort comparisons.


def radar_chart(
    radar_df: pd.DataFrame,
    stat_labels: list[str],
    title: str = "Player Comparison",
) -> go.Figure:
    """
    Radar for percentile (or 0–100 index) data. Radial axis = pct; raw shown in hover.

    radar_df: columns = [player_name, stat, pct, raw]
    stat_labels: list of display names for each stat (same order as stat keys)
    """
    players = radar_df["player_name"].unique()
    stats_order = radar_df["stat"].unique().tolist()

    # Validate minimum stats for meaningful radar (need at least 3 for polygon)
    if len(stats_order) < 3:
        fig = go.Figure()
        fig.update_layout(
            **_base_layout(title=dict(text=f"{title} — Insufficient Data", font=dict(size=14))),
            paper_bgcolor=_BG,
            plot_bgcolor=_BG,
            annotations=[dict(
                text=f"Need at least 3 stats for radar chart<br>(found: {len(stats_order)})",
                showarrow=False,
                font=dict(size=14, color=_SUB_TEXT),
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
            )],
            height=400,
        )
        return fig

    fig = go.Figure()

    categories = stat_labels + [stat_labels[0]]  # close the polygon

    for i, player in enumerate(players):
        sub = radar_df[radar_df["player_name"] == player].set_index("stat")
        values = [sub.loc[s, "pct"] if s in sub.index else None for s in stats_order]
        raw_vals = [sub.loc[s, "raw"] if s in sub.index else None for s in stats_order]

        # Handle missing values: use mean of available values, or 50 (neutral) if all missing
        valid_values = [v for v in values if v is not None and pd.notna(v) and np.isfinite(v)]
        fill_value = sum(valid_values) / len(valid_values) if valid_values else 50.0
        values = [fill_value if (v is None or pd.isna(v) or not np.isfinite(v)) else float(v) for v in values]
        # Clamp to [0, 100] so radar scale is never broken
        values = [max(0.0, min(100.0, v)) for v in values]

        valid_raw = [v for v in raw_vals if v is not None and pd.notna(v) and np.isfinite(v)]
        fill_raw = sum(valid_raw) / len(valid_raw) if valid_raw else 0.0
        raw_vals = [fill_raw if (v is None or pd.isna(v) or not np.isfinite(v)) else float(v) for v in raw_vals]

        values_closed = values + [values[0]]
        raw_closed = raw_vals + [raw_vals[0]]

        # Build hover text, marking imputed values
        hover_text = []
        for label, v, r in zip(stat_labels, values, raw_vals):
            imputed_note = "<br><i>(estimated)</i>" if v == fill_value and fill_value != 50 else ""
            hover_text.append(
                f"<b>{player}</b><br>{label}<br>Percentile: {v:.0f}{imputed_note}<br>Value: {r:.2f}"
            )
        hover_text.append(f"<b>{player}</b><br>{stat_labels[0]}<br>Percentile: {values[0]:.0f}")

        color = PLAYER_COLORS[i % len(PLAYER_COLORS)]
        fig.add_trace(
            go.Scatterpolar(
                r=values_closed,
                theta=categories,
                fill="toself",
                fillcolor=_hex_to_rgba(color),
                line=dict(color=color, width=2),
                name=player,
                hovertext=hover_text,
                hoverinfo="text",
            )
        )

    fig.update_layout(
        **_base_layout(title=dict(text=title, font=dict(size=16))),
        polar=dict(
            bgcolor=_BG,
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                showticklabels=True,
                tickvals=[0, 25, 50, 75, 100],
                ticktext=["0", "25", "50", "75", "100"],
                tickfont=dict(size=10, color=_SUB_TEXT),
                gridcolor=_GRID,
                linecolor=_GRID,
            ),
            angularaxis=dict(
                gridcolor=_GRID,
                linecolor=_GRID,
                tickfont=dict(size=14, color=_TEXT, family="DM Sans, Inter, sans-serif"),
            ),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5,
            font=dict(size=12),
        ),
        height=480,
    )
    return fig


# ---------------------------------------------------------------------------
# Horizontal bar chart comparison
# ---------------------------------------------------------------------------

def bar_comparison(
    player_names: list[str],
    stat_label: str,
    values: list[float],
    title: str = "",
) -> go.Figure:
    colors = [PLAYER_COLORS[i % len(PLAYER_COLORS)] for i in range(len(player_names))]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=player_names,
            orientation="h",
            marker_color=colors,
            text=[f"{v:.2f}" if isinstance(v, float) else str(v) for v in values],
            textposition="outside",
            cliponaxis=False,
        )
    )
    fig.update_layout(
        **_base_layout(title=dict(text=title or stat_label, font=dict(size=14))),
        xaxis=dict(gridcolor=_GRID, zeroline=False),
        yaxis=dict(gridcolor=_GRID, categoryorder="total ascending"),
        height=max(200, 60 * len(player_names) + 80),
        showlegend=False,
    )
    return fig


def multi_bar_comparison(
    df_compare: pd.DataFrame,
    stat_cols: list,  # list of (col_name, display_label) tuples
    max_cols: int = 3,
) -> go.Figure:
    """Small-multiples bar comparison across multiple stats."""
    n = len(stat_cols)
    ncols = min(n, max_cols)
    nrows = int(np.ceil(n / ncols))

    fig = make_subplots(
        rows=nrows,
        cols=ncols,
        subplot_titles=[label for _, label in stat_cols],
        horizontal_spacing=0.08,
        vertical_spacing=0.14,
    )

    for idx, (col, label) in enumerate(stat_cols):
        row = idx // ncols + 1
        col_pos = idx % ncols + 1
        if col not in df_compare.columns:
            continue

        players = df_compare["player_name"].tolist()
        vals = df_compare[col].fillna(0).tolist()
        colors = [PLAYER_COLORS[i % len(PLAYER_COLORS)] for i in range(len(players))]

        fig.add_trace(
            go.Bar(
                x=players,
                y=vals,
                marker_color=colors,
                showlegend=False,
                text=[f"{v:.2f}" for v in vals],
                textposition="outside",
                cliponaxis=False,
                hovertemplate="%{x}<br>" + label + ": %{y:.2f}<extra></extra>",
            ),
            row=row,
            col=col_pos,
        )

    fig.update_layout(
        **_base_layout(),
        height=280 * nrows,
    )
    fig.update_xaxes(showgrid=False, tickfont=dict(size=10))
    fig.update_yaxes(gridcolor=_GRID, zeroline=False)
    # Style subplot titles
    for ann in fig.layout.annotations:
        ann.font.update(size=12, color=_TEXT)

    return fig


# ---------------------------------------------------------------------------
# Rating trend (line chart)
# ---------------------------------------------------------------------------

def rating_trend(match_log: pd.DataFrame, player_name: str, color: str = "#C9A840") -> go.Figure:
    """Line chart of per-match rating over time."""
    log = match_log.dropna(subset=["stat_rating"]).sort_values("match_date_utc")
    if log.empty:
        return go.Figure()

    hover = log.apply(
        lambda r: f"vs {r['opponent']}<br>Rating: {r['stat_rating']:.1f}<br>Goals: {int(r['stat_goals'] or 0)}",
        axis=1,
    )

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=log["match_date_utc"],
            y=log["stat_rating"],
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            name="Rating",
            text=hover,
            hoverinfo="text",
        )
    )
    avg = log["stat_rating"].mean()
    fig.add_hline(y=avg, line_dash="dash", line_color=_SUB_TEXT, annotation_text=f"Avg {avg:.2f}")

    fig.update_layout(
        **_base_layout(title=dict(text=f"{player_name} — Match Rating", font=dict(size=14))),
        xaxis=dict(gridcolor=_GRID, title=""),
        yaxis=dict(gridcolor=_GRID, title="Rating", range=[4, 10.5]),
        height=320,
    )
    return fig


def xg_trend(match_log: pd.DataFrame, player_name: str, color: str = "#C9A840") -> go.Figure:
    """Bar chart of xG per match, with goals overlaid."""
    log = match_log.dropna(subset=["stat_expectedGoals"]).sort_values("match_date_utc")
    if log.empty:
        return go.Figure()

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=log["match_date_utc"],
            y=log["stat_expectedGoals"],
            name="xG",
            marker_color=f"{color}66",
            hovertemplate="xG: %{y:.2f}<extra></extra>",
        )
    )
    goal_matches = log[log["stat_goals"].fillna(0) > 0]
    if not goal_matches.empty:
        fig.add_trace(
            go.Scatter(
                x=goal_matches["match_date_utc"],
                y=goal_matches["stat_goals"],
                mode="markers",
                name="Goals",
                marker=dict(symbol="star", size=12, color="#FFD93D"),
                hovertemplate="Goals: %{y}<extra></extra>",
            )
        )

    fig.update_layout(
        **_base_layout(title=dict(text=f"{player_name} — xG per Match", font=dict(size=14))),
        xaxis=dict(gridcolor=_GRID, title=""),
        yaxis=dict(gridcolor=_GRID, title="xG"),
        height=300,
        legend=dict(orientation="h", yanchor="top", y=-0.1),
    )
    return fig


# ---------------------------------------------------------------------------
# Distribution chart (histogram / box)
# ---------------------------------------------------------------------------

def distribution_hist(
    series: pd.Series,
    title: str,
    xlabel: str,
    color: str = "#C9A840",
    highlight_values: dict = None,
) -> go.Figure:
    clean = series.dropna()
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=clean,
            nbinsx=40,
            marker_color=_hex_to_rgba(color, 0.53),
            marker_line=dict(width=0.5, color=color),
            hovertemplate=f"{xlabel}: %{{x:.2f}}<br>Count: %{{y}}<extra></extra>",
        )
    )
    if highlight_values:
        for name, val in highlight_values.items():
            fig.add_vline(
                x=val,
                line_color=PLAYER_COLORS[list(highlight_values.keys()).index(name) % len(PLAYER_COLORS)],
                line_dash="dash",
                annotation_text=name,
                annotation_position="top right",
                annotation_font=dict(size=10),
            )
    fig.update_layout(
        **_base_layout(title=dict(text=title, font=dict(size=14))),
        xaxis=dict(gridcolor=_GRID, title=xlabel),
        yaxis=dict(gridcolor=_GRID, title="Players"),
        height=300,
    )
    return fig
