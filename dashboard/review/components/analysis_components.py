"""Enhanced analysis components for Review Dashboard.

Pre-match and post-match analysis tools:
- Match preview cards
- H2H (head-to-head) analysis
- Form trend charts
- Momentum indicators
- Key battles identification
- Post-match reports
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def render_match_preview_card(
    home_team: str,
    away_team: str,
    league: str,
    match_date: Any,
    home_form: str,
    away_form: str,
    home_stats: Optional[pd.Series] = None,
    away_stats: Optional[pd.Series] = None,
    importance: str = "Medium"
) -> None:
    """Render a comprehensive match preview card.

    Args:
        home_team: Home team name
        away_team: Away team name
        league: League/competition name
        match_date: Match datetime
        home_form: Home team form string (e.g., 'WWDLW')
        away_form: Away team form string
        home_stats: Optional home team stats Series
        away_stats: Optional away team stats Series
        importance: Match importance level
    """
    from dashboard.utils.constants import COMP_FLAGS, COMP_NAMES

    # Parse date
    if match_date and hasattr(match_date, 'strftime'):
        date_str = match_date.strftime("%A, %B %d, %Y at %H:%M")
    else:
        date_str = str(match_date) if match_date else "TBC"

    # Determine importance color
    importance_colors = {"High": "#F85149", "Medium": "#C9A840", "Low": "#8B949E"}
    importance_color = importance_colors.get(importance, "#8B949E")

    with st.container():
        st.markdown(
            f"""
            <div style="
                background: linear-gradient(135deg, #161B22 0%, #0D1117 100%);
                border: 2px solid {importance_color};
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 20px;
            ">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;">
                    <div>
                        <div style="font-size: 0.9rem; color: #8B949E; margin-bottom: 4px;">
                            {COMP_FLAGS.get(league, '🏆')} {COMP_NAMES.get(league, league)}
                        </div>
                        <div style="font-size: 1.3rem; font-weight: 700; color: #F0F6FC;">
                            Match Preview
                        </div>
                    </div>
                    <div style="background: {importance_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;">
                        {importance} Priority
                    </div>
                </div>
            """,
            unsafe_allow_html=True
        )

        # Teams and VS
        team_cols = st.columns([2, 1, 2])

        with team_cols[0]:
            st.markdown(
                f"""
                <div style="text-align: center;">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #C9A840;">{home_team}</div>
                    <div style="font-size: 0.8rem; color: #8B949E; margin-top: 4px;">Home</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Home form
            form_html = render_form_string(home_form)
            st.markdown(f"<div style='text-align: center; margin-top: 10px;'>{form_html}</div>", unsafe_allow_html=True)

        with team_cols[1]:
            st.markdown(
                f"""
                <div style="text-align: center;">
                    <div style="font-size: 2rem; color: #8B949E; font-weight: 300;">VS</div>
                    <div style="font-size: 0.75rem; color: #8B949E; margin-top: 8px;">{date_str}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        with team_cols[2]:
            st.markdown(
                f"""
                <div style="text-align: center;">
                    <div style="font-size: 1.8rem; font-weight: 700; color: #58A6FF;">{away_team}</div>
                    <div style="font-size: 0.8rem; color: #8B949E; margin-top: 4px;">Away</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Away form
            form_html = render_form_string(away_form)
            st.markdown(f"<div style='text-align: center; margin-top: 10px;'>{form_html}</div>", unsafe_allow_html=True)

        # Stats comparison if available
        if home_stats is not None and away_stats is not None:
            st.markdown("---")
            st.markdown("**Season Stats Comparison**")

            stats = [
                ("League Position", "position_ordinal", "#"),
                ("Points", "points", ""),
                ("Goals For", "goals_for", ""),
                ("Goals Against", "goals_against", ""),
                ("Form (Last 5)", "form_points", "pts"),
            ]

            for stat_name, stat_key, suffix in stats:
                if stat_key in home_stats.index and stat_key in away_stats.index:
                    home_val = home_stats[stat_key]
                    away_val = away_stats[stat_key]

                    # Highlight advantage
                    if stat_key == "position_ordinal":
                        home_better = home_val < away_val
                        away_better = away_val < home_val
                    else:
                        home_better = home_val > away_val
                        away_better = away_val > home_val

                    home_color = "#3FB950" if home_better else "#F0F6FC"
                    away_color = "#3FB950" if away_better else "#F0F6FC"

                    stat_cols = st.columns([1, 1, 1, 1, 1])
                    with stat_cols[0]:
                        st.markdown(f"<div style='text-align: right; color: {home_color}; font-weight: 600;'>{home_val}{suffix}</div>", unsafe_allow_html=True)
                    with stat_cols[1]:
                        st.markdown(f"<div style='text-align: center; color: #8B949E; font-size: 0.8rem;'>{stat_name}</div>", unsafe_allow_html=True)
                    with stat_cols[2]:
                        # Visual bar
                        total = home_val + away_val
                        if total > 0:
                            home_pct = (home_val / total) * 100
                            st.markdown(
                                f"""
                                <div style="display: flex; height: 6px; border-radius: 3px; overflow: hidden;">
                                    <div style="width: {home_pct}%; background: #C9A840;"></div>
                                    <div style="width: {100-home_pct}%; background: #58A6FF;"></div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                    with stat_cols[3]:
                        st.markdown(f"<div style='text-align: left; color: {away_color}; font-weight: 600;'>{away_val}{suffix}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


def render_form_string(form_string: str) -> str:
    """Render form indicator HTML from form string.

    Args:
        form_string: String of W/D/L characters

    Returns:
        HTML string for form indicator
    """
    colors = {
        'W': '#28a745',
        'D': '#ffc107',
        'L': '#dc3545',
    }

    form_html = ""
    for result in form_string.upper()[:5]:  # Last 5
        color = colors.get(result, '#6c757d')
        form_html += f"""
            <span style="
                background: {color};
                color: white;
                padding: 3px 8px;
                border-radius: 4px;
                margin: 0 2px;
                font-size: 12px;
                font-weight: 700;
            ">{result}</span>
        """

    return form_html


def render_momentum_indicator(
    form_data: pd.DataFrame,
    team_name: str,
    matches: int = 5
) -> None:
    """Render a momentum chart showing recent form trends.

    Args:
        form_data: DataFrame with match results over time
        team_name: Team name for title
        matches: Number of recent matches to show
    """
    if form_data.empty:
        st.info("No form data available")
        return

    # Calculate momentum (points from last 5)
    recent = form_data.tail(matches)

    # Map results to points
    points_map = {'W': 3, 'D': 1, 'L': 0}
    recent['points'] = recent['result'].map(points_map)
    recent['cumulative'] = recent['points'].cumsum()

    # Calculate moving average trend
    recent['trend'] = recent['points'].rolling(window=3, min_periods=1).mean()

    # Create chart
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.1,
                        row_heights=[0.6, 0.4])

    # Match results as bars
    colors = recent['result'].map({'W': '#28a745', 'D': '#ffc107', 'L': '#dc3545'})

    fig.add_trace(
        go.Bar(
            x=recent['date'] if 'date' in recent.columns else range(len(recent)),
            y=recent['points'],
            marker_color=colors,
            name='Points',
            showlegend=False,
        ),
        row=1, col=1
    )

    # Trend line
    fig.add_trace(
        go.Scatter(
            x=recent['date'] if 'date' in recent.columns else range(len(recent)),
            y=recent['trend'],
            mode='lines+markers',
            line=dict(color='#C9A840', width=3),
            name='3-Game Trend',
            showlegend=False,
        ),
        row=2, col=1
    )

    fig.update_layout(
        title=f"{team_name} - Last {matches} Matches",
        paper_bgcolor="#0D1117",
        plot_bgcolor="#161B22",
        font=dict(color="#F0F6FC"),
        margin=dict(l=40, r=40, t=50, b=40),
        height=350,
    )

    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#30363D", row=1)
    fig.update_yaxes(showgrid=True, gridcolor="#30363D", title="Trend", row=2)

    st.plotly_chart(fig, use_container_width=True)

    # Momentum score
    avg_points = recent['points'].mean()
    if avg_points >= 2.0:
        momentum = "🔥 Excellent"
        momentum_color = "#3FB950"
    elif avg_points >= 1.5:
        momentum = "📈 Good"
        momentum_color = "#C9A840"
    elif avg_points >= 1.0:
        momentum = "➡️ Average"
        momentum_color = "#8B949E"
    else:
        momentum = "📉 Poor"
        momentum_color = "#F85149"

    st.markdown(
        f"""
        <div style="text-align: center; padding: 10px; background: #161B22; border-radius: 6px;">
            <span style="color: #8B949E; font-size: 0.85rem;">Momentum: </span>
            <span style="color: {momentum_color}; font-weight: 600;">{momentum}</span>
            <span style="color: #8B949E; font-size: 0.85rem;"> ({avg_points:.1f} pts/game)</span>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_h2h_analysis(
    h2h_data: pd.DataFrame,
    home_team: str,
    away_team: str
) -> None:
    """Render head-to-head analysis.

    Args:
        h2h_data: DataFrame with historical H2H results
        home_team: Home team name
        away_team: Away team name
    """
    if h2h_data.empty:
        st.info("No head-to-head history available")
        return

    st.markdown(f"**Head-to-Head History (Last {len(h2h_data)} meetings)**")

    # Calculate H2H stats
    home_wins = len(h2h_data[h2h_data['winner'] == home_team])
    away_wins = len(h2h_data[h2h_data['winner'] == away_team])
    draws = len(h2h_data[h2h_data['winner'].isna() | (h2h_data['winner'] == 'Draw')])

    total = len(h2h_data)

    if total > 0:
        home_pct = (home_wins / total) * 100
        away_pct = (away_wins / total) * 100
        draw_pct = (draws / total) * 100

        # Visual breakdown
        st.markdown(
            f"""
            <div style="display: flex; height: 30px; border-radius: 8px; overflow: hidden; margin: 15px 0;">
                <div style="width: {home_pct}%; background: #C9A840; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 0.9rem;">
                    {home_wins} H
                </div>
                <div style="width: {draw_pct}%; background: #8B949E; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 0.9rem;">
                    {draws} D
                </div>
                <div style="width: {away_pct}%; background: #58A6FF; display: flex; align-items: center; justify-content: center; color: white; font-weight: 600; font-size: 0.9rem;">
                    {away_wins} A
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Recent meetings
        st.markdown("**Recent Meetings:**")
        for _, match in h2h_data.head(5).iterrows():
            date_str = match['date'].strftime("%b %Y") if hasattr(match['date'], 'strftime') else str(match['date'])
            home_goals = match.get('home_goals', 0)
            away_goals = match.get('away_goals', 0)

            winner = match.get('winner', 'Unknown')
            if winner == home_team:
                result_color = "#C9A840"
            elif winner == away_team:
                result_color = "#58A6FF"
            else:
                result_color = "#8B949E"

            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; padding: 8px; background: #161B22; border-radius: 4px; margin: 4px 0; font-size: 0.85rem;">
                    <span style="color: #8B949E;">{date_str}</span>
                    <span style="color: #F0F6FC;">{match.get('home_team', 'Home')} {home_goals}-{away_goals} {match.get('away_team', 'Away')}</span>
                    <span style="color: {result_color}; font-weight: 500;">{winner}</span>
                </div>
                """,
                unsafe_allow_html=True
            )


def render_key_battles(
    home_players: pd.DataFrame,
    away_players: pd.DataFrame,
    battles: List[Tuple[str, str, str]]  # [(home_player, away_player, battle_type)]
) -> None:
    """Render key individual battles.

    Args:
        home_players: Home team players DataFrame
        away_players: Away team players DataFrame
        battles: List of (home_player, away_player, battle_type) tuples
    """
    st.markdown("**Key Individual Battles**")

    for home_p, away_p, battle_type in battles:
        # Get player data
        home_data = home_players[home_players['player_name'] == home_p]
        away_data = away_players[away_players['player_name'] == away_p]

        home_rating = home_data['avg_rating'].values[0] if not home_data.empty else 6.5
        away_rating = away_data['avg_rating'].values[0] if not away_data.empty else 6.5

        # Determine advantage
        if home_rating > away_rating + 0.3:
            home_advantage = True
            away_advantage = False
        elif away_rating > home_rating + 0.3:
            home_advantage = False
            away_advantage = True
        else:
            home_advantage = False
            away_advantage = False

        with st.container():
            st.markdown(
                f"""
                <div style="background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 15px; margin: 10px 0;">
                    <div style="text-align: center; font-size: 0.75rem; color: #8B949E; margin-bottom: 10px;">{battle_type}</div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="text-align: center; flex: 1;">
                            <div style="font-weight: 600; color: {'#C9A840' if home_advantage else '#F0F6FC'};">{home_p}</div>
                            <div style="font-size: 0.9rem; color: {('#3FB950' if home_advantage else '#8B949E')}; font-weight: 500;">{home_rating:.2f}</div>
                        </div>
                        <div style="color: #8B949E; font-size: 1.2rem; margin: 0 20px;">VS</div>
                        <div style="text-align: center; flex: 1;">
                            <div style="font-weight: 600; color: {'#58A6FF' if away_advantage else '#F0F6FC'};">{away_p}</div>
                            <div style="font-size: 0.9rem; color: {('#3FB950' if away_advantage else '#8B949E')}; font-weight: 500;">{away_rating:.2f}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


def render_post_match_report(
    match_data: Dict[str, Any],
    home_stats: pd.Series,
    away_stats: pd.Series,
    key_moments: List[str],
    tactical_analysis: str
) -> None:
    """Render a comprehensive post-match report.

    Args:
        match_data: Match data dict with score, possession, etc.
        home_stats: Home team match stats
        away_stats: Away team match stats
        key_moments: List of key match moments
        tactical_analysis: Tactical analysis text
    """
    home_team = match_data.get('home_team', 'Home')
    away_team = match_data.get('away_team', 'Away')
    home_goals = match_data.get('home_goals', 0)
    away_goals = match_data.get('away_goals', 0)

    with st.container():
        st.markdown(
            f"""
            <div style="
                background: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 20px;
            ">
                <div style="text-align: center; margin-bottom: 20px;">
                    <div style="font-size: 0.85rem; color: #8B949E; margin-bottom: 8px;">Full Time</div>
                    <div style="font-size: 2.5rem; font-weight: 700; color: #F0F6FC;">
                        <span style="color: #C9A840;">{home_goals}</span>
                        <span style="color: #8B949E; margin: 0 15px;">-</span>
                        <span style="color: #58A6FF;">{away_goals}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; max-width: 300px; margin: 15px auto 0;">
                        <span style="color: #C9A840; font-weight: 600;">{home_team}</span>
                        <span style="color: #58A6FF; font-weight: 600;">{away_team}</span>
                    </div>
                </div>
            """,
            unsafe_allow_html=True
        )

        # Match stats comparison
        st.markdown("**Match Statistics**")

        stats_to_compare = [
            ("Possession %", 'possession_pct', "%"),
            ("Shots", 'shots', ""),
            ("Shots on Target", 'shots_on_target', ""),
            ("Corners", 'corners', ""),
            ("Fouls", 'fouls', ""),
        ]

        for stat_name, stat_key, suffix in stats_to_compare:
            home_val = home_stats.get(stat_key, 0) if hasattr(home_stats, 'get') else 0
            away_val = away_stats.get(stat_key, 0) if hasattr(away_stats, 'get') else 0
            total = home_val + away_val

            if total > 0:
                home_pct = (home_val / total) * 100

                cols = st.columns([1, 1, 1])
                with cols[0]:
                    st.markdown(f"<div style='text-align: right; font-weight: 600; color: #C9A840;'>{home_val}{suffix}</div>", unsafe_allow_html=True)
                with cols[1]:
                    st.markdown(
                        f"""
                        <div style="text-align: center; font-size: 0.75rem; color: #8B949E;">{stat_name}</div>
                        <div style="display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 4px;">
                            <div style="width: {home_pct}%; background: #C9A840;"></div>
                            <div style="width: {100-home_pct}%; background: #58A6FF;"></div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                with cols[2]:
                    st.markdown(f"<div style='text-align: left; font-weight: 600; color: #58A6FF;'>{away_val}{suffix}</div>", unsafe_allow_html=True)

        # Key moments
        st.markdown("---")
        st.markdown("**Key Moments**")
        for moment in key_moments:
            st.markdown(f"• {moment}")

        # Tactical analysis
        st.markdown("---")
        st.markdown("**Tactical Analysis**")
        st.markdown(f"<div style='background: #21262D; padding: 15px; border-radius: 6px; line-height: 1.6;'>{tactical_analysis}</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


def render_match_notebook(
    notes: List[Dict[str, Any]],
    on_delete: Optional[callable] = None
) -> None:
    """Render a collection of match notes.

    Args:
        notes: List of note dicts with timestamp, content, tags
        on_delete: Callback when note is deleted
    """
    if not notes:
        st.info("No notes saved yet. Add notes from Pre-Match or Post-Match pages.")
        return

    st.markdown(f"**{len(notes)} Notes Saved**")

    for i, note in enumerate(notes):
        with st.container():
            timestamp = note.get('timestamp', 'Unknown date')
            if isinstance(timestamp, str) and len(timestamp) > 10:
                timestamp = timestamp[:10]

            note_type = note.get('type', 'general').replace('-', ' ').title()
            match_info = f"{note.get('home', 'Team A')} vs {note.get('away', 'Team B')}"

            st.markdown(
                f"""
                <div style="background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 15px; margin: 10px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div>
                            <span style="background: #C9A840; color: #0D1117; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">{note_type}</span>
                            <span style="color: #F0F6FC; font-weight: 500; margin-left: 10px;">{match_info}</span>
                        </div>
                        <span style="color: #8B949E; font-size: 0.75rem;">{timestamp}</span>
                    </div>
                    <div style="color: #E6EDF3; line-height: 1.5;">{note.get('notes', '')}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            col1, col2 = st.columns([5, 1])
            with col2:
                if st.button("🗑️ Delete", key=f"delete_note_{i}"):
                    if on_delete:
                        on_delete(i)


def export_analysis_report(
    match_data: Dict[str, Any],
    analysis_sections: List[Tuple[str, str]],  # [(section_title, content)]
    format: str = "markdown"
) -> str:
    """Generate an exportable analysis report.

    Args:
        match_data: Match data dict
        analysis_sections: List of (title, content) tuples
        format: Export format ('markdown' or 'html')

    Returns:
        Report string
    """
    home = match_data.get('home_team', 'Home')
    away = match_data.get('away_team', 'Away')
    date = match_data.get('date', datetime.now().strftime("%Y-%m-%d"))

    if format == "markdown":
        report = f"""# Match Analysis Report

**Match:** {home} vs {away}  
**Date:** {date}  
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}

---

"""
        for title, content in analysis_sections:
            report += f"## {title}\n\n{content}\n\n---\n\n"

        return report

    elif format == "html":
        report = f"""<!DOCTYPE html>
<html>
<head>
    <title>Match Analysis - {home} vs {away}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
    </style>
</head>
<body>
    <h1>Match Analysis Report</h1>
    <p><strong>Match:</strong> {home} vs {away}</p>
    <p><strong>Date:</strong> {date}</p>
    <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    <hr>
"""
        for title, content in analysis_sections:
            report += f"<h2>{title}</h2>\n<p>{content}</p>\n<hr>\n"

        report += "</body></html>"
        return report

    return ""
