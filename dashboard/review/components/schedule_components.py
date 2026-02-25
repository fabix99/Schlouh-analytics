"""Enhanced schedule components for Review Dashboard.

This module provides:
- Calendar grid view of matches
- Match cards with form indicators
- Schedule export (ICS/CSV)
- Visual stat comparisons
"""

import io
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import calendar

import pandas as pd
import streamlit as st


def render_calendar_grid(
    matches_df: pd.DataFrame,
    start_date: datetime,
    end_date: datetime,
    date_col: str = "match_date_utc",
    home_col: str = "home_team_name",
    away_col: str = "away_team_name",
    on_match_click: Optional[callable] = None
) -> None:
    """Render matches in a calendar grid view.

    Args:
        matches_df: DataFrame with match data
        start_date: Start date for calendar
        end_date: End date for calendar
        date_col: Column containing match dates
        home_col: Column containing home team names
        away_col: Column containing away team names
        on_match_click: Callback when match is clicked
    """
    # Generate calendar weeks
    current_date = start_date
    weeks = []

    while current_date <= end_date:
        week_start = current_date - timedelta(days=current_date.weekday())
        week = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_matches = matches_df[
                pd.to_datetime(matches_df[date_col]).dt.date == day.date()
            ] if not matches_df.empty else pd.DataFrame()

            week.append({
                'date': day,
                'matches': day_matches.to_dict('records') if not day_matches.empty else [],
                'is_current_month': day.month == start_date.month
            })
        weeks.append(week)
        current_date = week_start + timedelta(days=7)

    # Render calendar
    st.subheader("📅 Match Calendar")

    # Day headers
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    header_cols = st.columns(7)
    for i, day in enumerate(days):
        with header_cols[i]:
            st.markdown(
                f"<div style='text-align: center; font-weight: bold; color: #8B949E;'>{day}</div>",
                unsafe_allow_html=True
            )

    # Calendar grid
    for week in weeks:
        week_cols = st.columns(7)
        for i, day_data in enumerate(week):
            with week_cols[i]:
                day = day_data['date']
                matches = day_data['matches']
                is_today = day.date() == datetime.now().date()

                # Day cell styling
                opacity = "1.0" if day_data['is_current_month'] else "0.4"
                border_color = "#00D4AA" if is_today else "#30363D"
                bg_color = "#161B22" if not is_today else "#0D3B2E"

                cell_html = f"""
                <div style="
                    border: 2px solid {border_color};
                    border-radius: 8px;
                    padding: 8px;
                    min-height: 100px;
                    background: {bg_color};
                    opacity: {opacity};
                ">
                    <div style="font-weight: bold; margin-bottom: 4px; color: #F0F6FC;">{day.day}</div>
                """

                # Match indicators
                for match in matches[:3]:  # Show max 3 matches per cell
                    home = match.get(home_col, 'TBD')[:3]
                    away = match.get(away_col, 'TBD')[:3]
                    cell_html += f"""
                    <div style="
                        font-size: 9px;
                        background: #0068c9;
                        color: white;
                        padding: 2px 4px;
                        border-radius: 3px;
                        margin: 2px 0;
                        white-space: nowrap;
                        overflow: hidden;
                        text-overflow: ellipsis;
                    ">{home} v {away}</div>
                    """

                if len(matches) > 3:
                    cell_html += f"<div style='font-size: 8px; color: #8B949E;'>+{len(matches)-3} more</div>"

                cell_html += "</div>"
                st.markdown(cell_html, unsafe_allow_html=True)

        st.markdown("<div style='margin: 4px 0;'></div>", unsafe_allow_html=True)


def render_match_list(
    matches_df: pd.DataFrame,
    date_col: str = "match_date_utc",
    home_col: str = "home_team_name",
    away_col: str = "away_team_name",
    show_form: bool = True,
    on_analyze: Optional[callable] = None
) -> None:
    """Render matches as a detailed list.

    Args:
        matches_df: DataFrame with match data
        date_col: Column containing match dates
        home_col: Column containing home team names
        away_col: Column containing away team names
        show_form: Whether to show form indicators
        on_analyze: Callback for analyze button
    """
    if matches_df.empty:
        st.info("No matches to display")
        return

    for date, day_matches in matches_df.groupby(pd.to_datetime(matches_df[date_col]).dt.date):
        st.subheader(date.strftime("%A, %B %d, %Y"))

        for _, match in day_matches.iterrows():
            with st.container():
                render_match_card(
                    match,
                    date_col=date_col,
                    home_col=home_col,
                    away_col=away_col,
                    show_form=show_form,
                    on_analyze=on_analyze
                )


def render_match_card(
    match: Dict[str, Any],
    date_col: str = "match_date_utc",
    home_col: str = "home_team_name",
    away_col: str = "away_team_name",
    compact: bool = False,
    show_form: bool = True,
    on_analyze: Optional[callable] = None
) -> None:
    """Render a rich match card with form indicators.

    Args:
        match: Match data dictionary
        date_col: Column containing match date
        home_col: Column containing home team name
        away_col: Column containing away team name
        compact: Whether to render in compact mode
        show_form: Whether to show form indicators
        on_analyze: Callback for analyze button
    """
    from dashboard.utils.constants import COMP_FLAGS, COMP_NAMES

    home = match.get(home_col, 'TBD')
    away = match.get(away_col, 'TBD')
    league = match.get('competition_slug', '')
    match_date = match.get(date_col)
    match_id = match.get('match_id', 0)

    # Get match time
    match_time = "TBC"
    if match_date and hasattr(match_date, 'strftime'):
        match_time = match_date.strftime("%H:%M")

    # Form indicators
    home_form = match.get('home_form', 'WWDLW')
    away_form = match.get('away_form', 'LLWWD')

    # Days until match
    days_until = 0
    if match_date:
        if isinstance(match_date, str):
            match_date = pd.to_datetime(match_date)
        # Use timezone-aware "now" when match_date is tz-aware to avoid subtraction error
        now = pd.Timestamp.now(tz=match_date.tz) if getattr(match_date, "tz", None) is not None else datetime.now()
        days_until = (match_date - now).days

    days_text = "TODAY" if days_until == 0 else "TOMORROW" if days_until == 1 else f"In {days_until} days"
    days_color = "#ff4b4b" if days_until <= 1 else "#8B949E"

    with st.container():
        # Card container
        st.markdown("""
            <div style="
                background: #161B22;
                border: 1px solid #30363D;
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 12px;
            ">
        """, unsafe_allow_html=True)

        # Header with competition and time
        header_cols = st.columns([1, 3, 1])

        with header_cols[0]:
            comp_emoji = COMP_FLAGS.get(league, '🏆')
            st.markdown(f"<div style='font-size: 24px;'>{comp_emoji}</div>", unsafe_allow_html=True)

        with header_cols[1]:
            matchday = match.get('matchday', 'N/A')
            st.caption(f"{COMP_NAMES.get(league, league)} • Matchday {matchday}")

        with header_cols[2]:
            st.markdown(f"<div style='text-align: right;'>⏰ {match_time}</div>", unsafe_allow_html=True)

        # Teams section
        teams_cols = st.columns([2, 1, 2])

        with teams_cols[0]:
            st.markdown(f"<div style='font-size: 1.2rem; font-weight: 600;'>{home}</div>", unsafe_allow_html=True)

            if show_form:
                form_html = render_form_indicator(home_form)
                st.markdown(f"**Form (last 5):** {form_html}", unsafe_allow_html=True)

            home_pos = match.get('home_position', '-')
            if home_pos != '-':
                st.caption(f"📊 Position: {home_pos}")

        with teams_cols[1]:
            st.markdown(f"""
                <div style="text-align: center;">
                    <div style="font-size: 1.5rem; font-weight: bold; color: #8B949E;">VS</div>
                    <div style="color: {days_color}; font-size: 0.85rem; font-weight: 600;">{days_text}</div>
                </div>
            """, unsafe_allow_html=True)

        with teams_cols[2]:
            st.markdown(f"<div style='font-size: 1.2rem; font-weight: 600; text-align: right;'>{away}</div>", unsafe_allow_html=True)

            if show_form:
                form_html = render_form_indicator(away_form)
                st.markdown(f"<div style='text-align: right;'><b>Form (last 5):</b> {form_html}</div>", unsafe_allow_html=True)

            away_pos = match.get('away_position', '-')
            if away_pos != '-':
                st.caption(f"📊 Position: {away_pos}")

        # Stats comparison (if not compact)
        if not compact:
            st.divider()
            render_stats_comparison(match)

        # Action buttons
        st.divider()
        action_cols = st.columns(4)

        with action_cols[0]:
            if st.button("📊 Pre-Match", key=f"pre_{match_id}", use_container_width=True):
                if on_analyze:
                    on_analyze(match, "pre")

        with action_cols[1]:
            if st.button("📋 Post-Match", key=f"post_{match_id}", use_container_width=True):
                if on_analyze:
                    on_analyze(match, "post")

        with action_cols[2]:
            if st.button("📋 Checklist", key=f"check_{match_id}", use_container_width=True):
                pass  # Placeholder for checklist

        with action_cols[3]:
            if st.button("🔔 Remind", key=f"remind_{match_id}", use_container_width=True):
                pass  # Placeholder for reminder

        st.markdown("</div>", unsafe_allow_html=True)


def render_form_indicator(form_string: str) -> str:
    """Render form indicator HTML from form string (e.g., 'WWDLW').

    Args:
        form_string: String of W/D/L characters

    Returns:
        HTML string for form indicator
    """
    colors = {
        'W': '#28a745',  # Green for win
        'D': '#ffc107',  # Yellow for draw
        'L': '#dc3545',  # Red for loss
    }

    form_html = ""
    for result in form_string.upper():
        color = colors.get(result, '#6c757d')
        form_html += f"""
            <span style="
                background: {color};
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                margin: 0 2px;
                font-size: 12px;
                font-weight: 600;
            ">{result}</span>
        """

    return form_html


def render_stats_comparison(match: Dict[str, Any]) -> None:
    """Render visual stat comparison between teams.

    Args:
        match: Match data dictionary
    """
    # Get stats
    comparisons = [
        ('PPG', match.get('home_ppg', 0), match.get('away_ppg', 0)),
        ('xG', match.get('home_xg', 0), match.get('away_xg', 0)),
        ('Goals', match.get('home_goals', 0), match.get('away_goals', 0)),
        ('Clean Sheets', match.get('home_cs', 0), match.get('away_cs', 0)),
    ]

    stats_cols = st.columns(len(comparisons))

    for col, (label, home_val, away_val) in zip(stats_cols, comparisons):
        with col:
            st.write(f"**{label}**")

            # Visual comparison bar
            total = home_val + away_val
            if total > 0:
                home_pct = (home_val / total) * 100
                bar_html = f"""
                    <div style="
                        display: flex;
                        height: 20px;
                        border-radius: 4px;
                        overflow: hidden;
                        font-size: 11px;
                    ">
                        <div style="
                            width: {home_pct}%;
                            background: #0068c9;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                        ">{home_val:.1f}</div>
                        <div style="
                            width: {100-home_pct}%;
                            background: #ff9500;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            color: white;
                        ">{away_val:.1f}</div>
                    </div>
                """
                st.markdown(bar_html, unsafe_allow_html=True)


def generate_ical_event(match: Dict[str, Any]) -> str:
    """Generate iCal (.ics) format for a match.

    Args:
        match: Match data dictionary

    Returns:
        iCal formatted string
    """
    match_id = match.get('match_id', 'unknown')
    home = match.get('home_team_name', 'TBD')
    away = match.get('away_team_name', 'TBD')
    league = match.get('competition_slug', '')
    matchday = match.get('matchday', 'N/A')
    match_date = match.get('match_date_utc')

    # Generate UIDs and timestamps
    uid = f"{match_id}@schlouh-analytics.com"
    created = datetime.now().strftime('%Y%m%dT%H%M%SZ')

    # Format match datetime
    if match_date:
        if isinstance(match_date, str):
            match_date = pd.to_datetime(match_date)
        dtstart = match_date.strftime('%Y%m%dT%H%M%S')
        dtend = (match_date + timedelta(hours=2)).strftime('%Y%m%dT%H%M%S')
    else:
        dtstart = datetime.now().strftime('%Y%m%dT120000')
        dtend = (datetime.now() + timedelta(hours=2)).strftime('%Y%m%dT140000')

    # Build description
    home_form = match.get('home_form', 'N/A')
    away_form = match.get('away_form', 'N/A')
    home_ppg = match.get('home_ppg', 'N/A')
    away_ppg = match.get('away_ppg', 'N/A')

    ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Schlouh Analytics//Match Schedule//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{created}
DTSTART;TZID=Europe/London:{dtstart}
DTEND;TZID=Europe/London:{dtend}
SUMMARY:{home} vs {away}
DESCRIPTION:Competition: {league}\\nMatchday: {matchday}\\n\\nKey Stats:\\n- {home} PPG: {home_ppg}\\n- {away} PPG: {away_ppg}\\n\\nForm (last 5):\\n- {home}: {home_form}\\n- {away}: {away_form}
LOCATION:{match.get('venue', 'TBD')}
STATUS:CONFIRMED
BEGIN:VALARM
ACTION:DISPLAY
DESCRIPTION:Match starting in 1 hour: {home} vs {away}
TRIGGER:-PT1H
END:VALARM
END:VEVENT
END:VCALENDAR"""

    return ical


def export_schedule_csv(matches_df: pd.DataFrame) -> str:
    """Export schedule as CSV string.

    Args:
        matches_df: DataFrame with match data

    Returns:
        CSV formatted string
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Date', 'Time', 'Home Team', 'Away Team', 'Competition',
        'Home Form', 'Away Form', 'Home Position', 'Away Position',
        'Importance', 'Venue', 'Match ID'
    ])

    # Data rows
    for _, match in matches_df.iterrows():
        match_date = match.get('match_date_utc', '')
        if hasattr(match_date, 'strftime'):
            date_str = match_date.strftime('%Y-%m-%d')
            time_str = match_date.strftime('%H:%M')
        else:
            date_str = str(match_date)[:10] if match_date else ''
            time_str = ''

        writer.writerow([
            date_str,
            time_str,
            match.get('home_team_name', ''),
            match.get('away_team_name', ''),
            match.get('competition_slug', ''),
            match.get('home_form', ''),
            match.get('away_form', ''),
            match.get('home_position', ''),
            match.get('away_position', ''),
            match.get('importance', 'Medium'),
            match.get('venue', 'TBD'),
            match.get('match_id', ''),
        ])

    return output.getvalue()


def render_export_section(matches_df: pd.DataFrame) -> None:
    """Render export options section.

    Args:
        matches_df: DataFrame with match data
    """
    st.divider()
    st.subheader("📥 Export Schedule")

    export_cols = st.columns(3)

    with export_cols[0]:
        # CSV Export
        if not matches_df.empty:
            csv_data = export_schedule_csv(matches_df)
            st.download_button(
                "📄 Download CSV",
                data=csv_data,
                file_name=f"match_schedule_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.button("📄 Download CSV", disabled=True, use_container_width=True)

    with export_cols[1]:
        # iCal Export
        if not matches_df.empty:
            ical_data = ""
            for _, match in matches_df.iterrows():
                ical_data += generate_ical_event(match.to_dict()) + "\n"

            st.download_button(
                "📅 Download iCal (.ics)",
                data=ical_data,
                file_name=f"match_schedule_{datetime.now().strftime('%Y%m%d')}.ics",
                mime="text/calendar",
                use_container_width=True
            )
        else:
            st.button("📅 Download iCal", disabled=True, use_container_width=True)

    with export_cols[2]:
        # Summary stats
        if not matches_df.empty:
            total = len(matches_df)
            high_importance = len(matches_df[matches_df.get('importance', 'Medium') == 'High'])

            st.metric("Total Matches", total)
            if high_importance > 0:
                st.caption(f"🔴 {high_importance} high priority")
        else:
            st.metric("Total Matches", 0)

    # Google Calendar integration hint
    st.info("💡 **Tip:** Import the .ics file into Google Calendar or Outlook to get match reminders!")


def render_schedule_summary(matches_df: pd.DataFrame) -> None:
    """Render schedule summary statistics.

    Args:
        matches_df: DataFrame with match data
    """
    if matches_df.empty:
        return

    total = len(matches_df)

    # Count matches by time period
    today = datetime.now().date()
    this_week = today + timedelta(days=7)

    date_col = 'match_date_utc'
    if date_col in matches_df.columns:
        dates = pd.to_datetime(matches_df[date_col]).dt.date
        this_week_count = len(matches_df[dates <= this_week])
    else:
        this_week_count = 0

    # High importance
    high_importance = len(matches_df[matches_df.get('importance', 'Medium') == 'High'])

    # Display metrics
    cols = st.columns(4)
    with cols[0]:
        st.metric("Total Matches", total)
    with cols[1]:
        st.metric("This Week", this_week_count)
    with cols[2]:
        st.metric("High Priority", high_importance, delta=f"{high_importance} to analyze" if high_importance > 0 else None)
    with cols[3]:
        leagues = matches_df['competition_slug'].nunique() if 'competition_slug' in matches_df.columns else 0
        st.metric("Competitions", leagues)
