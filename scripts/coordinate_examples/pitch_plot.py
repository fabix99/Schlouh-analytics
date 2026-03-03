"""Minimal pitch drawing for coordinate examples (Opta 0–100). No dashboard dependency."""
import plotly.graph_objects as go

PITCH_COLOR = "#2E7D32"
LINE_COLOR = "rgba(255,255,255,0.9)"
FIG_BG = "#0D1117"
TEXT_COLOR = "#E6EDF3"


def add_pitch_shapes(
    fig: go.Figure,
    pitch_color: str = PITCH_COLOR,
    line_color: str = LINE_COLOR,
) -> None:
    """Add football pitch lines (Opta 0–100). x = length, y = width."""
    fig.add_shape(
        type="rect", x0=0, y0=0, x1=100, y1=100,
        line=dict(color=line_color, width=2), fillcolor=pitch_color, layer="below",
    )
    fig.add_shape(type="line", x0=50, y0=0, x1=50, y1=100, line=dict(color=line_color, width=2), layer="above")
    fig.add_shape(type="circle", x0=40, y0=40, x1=60, y1=60, line=dict(color=line_color, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="circle", x0=49.4, y0=49.4, x1=50.6, y1=50.6, line=dict(color=line_color, width=1), fillcolor=line_color, layer="above")
    fig.add_shape(type="rect", x0=0, y0=20, x1=15, y1=80, line=dict(color=line_color, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="rect", x0=85, y0=20, x1=100, y1=80, line=dict(color=line_color, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="rect", x0=0, y0=37, x1=5, y1=63, line=dict(color=line_color, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="rect", x0=95, y0=37, x1=100, y1=63, line=dict(color=line_color, width=2), fillcolor="rgba(0,0,0,0)", layer="above")
    fig.add_shape(type="path", path="M 41 15 A 9 9 0 0 0 59 15", line=dict(color=line_color, width=2), layer="above")
    fig.add_shape(type="path", path="M 41 85 A 9 9 0 0 1 59 85", line=dict(color=line_color, width=2), layer="above")
    for path in ["M 0 2 A 2 2 0 0 1 2 0", "M 98 0 A 2 2 0 0 1 100 2", "M 0 98 A 2 2 0 0 1 2 100", "M 98 100 A 2 2 0 0 1 100 98"]:
        fig.add_shape(type="path", path=path, line=dict(color=line_color, width=2), layer="above")
    fig.add_shape(type="circle", x0=10.2, y0=49.2, x1=11.8, y1=50.8, line=dict(color=line_color, width=1), fillcolor=line_color, layer="above")
    fig.add_shape(type="circle", x0=88.2, y0=49.2, x1=89.8, y1=50.8, line=dict(color=line_color, width=1), fillcolor=line_color, layer="above")


def pitch_layout(height: int = 420, title: str = "") -> dict:
    return dict(
        paper_bgcolor=FIG_BG,
        plot_bgcolor=PITCH_COLOR,
        font=dict(color=TEXT_COLOR),
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, showticklabels=False),
        height=height,
        margin=dict(l=44, r=44, t=48, b=44),
        title=dict(text=title, x=0.5, xanchor="center") if title else {},
    )
