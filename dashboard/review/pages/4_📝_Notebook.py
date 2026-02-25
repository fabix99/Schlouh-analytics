"""Review Dashboard — Match Notebook.

Searchable database of all reviews, notes, and player observations.
"""

import sys
import pathlib
from datetime import datetime, timedelta
from html import escape as _html_escape

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import streamlit as st

from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS
from dashboard.review.layout import render_review_sidebar

# Page config
st.set_page_config(
    page_title="Notebook · Review",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_review_sidebar()

# Initialize session state
if "match_reviews" not in st.session_state:
    st.session_state.match_reviews = {}
if "scout_notes" not in st.session_state:
    st.session_state.scout_notes = []

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">📝 Match Notebook</div>
        <div class="page-hero-sub">
            Searchable database of all reviews and observations.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Statistics Overview
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>📊 Notebook Stats</div>", unsafe_allow_html=True)

review_count = len(st.session_state.match_reviews)
notes_count = len(st.session_state.scout_notes)
observations_count = sum(
    len(review.get("player_observations", {}).get(team, []))
    for review in st.session_state.match_reviews.values()
    for team in review.get("player_observations", {})
)

stat_col1, stat_col2, stat_col3 = st.columns(3)
with stat_col1:
    st.metric("Match Reviews", review_count)
with stat_col2:
    st.metric("Scout Notes", notes_count)
with stat_col3:
    st.metric("Player Observations", observations_count)

# ---------------------------------------------------------------------------
# Search & Filter
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>🔍 Search Notebook</div>", unsafe_allow_html=True)

search_col1, search_col2, search_col3 = st.columns(3)

with search_col1:
    search_query = st.text_input("Search:", placeholder="Team, player, or keyword...")

with search_col2:
    entry_type = st.multiselect(
        "Entry type:",
        ["Match Reviews", "Pre-Match Notes", "Post-Match Reviews", "Player Observations"],
        default=["Match Reviews", "Post-Match Reviews", "Player Observations"]
    )

with search_col3:
    sort_order = st.selectbox(
        "Sort by date:",
        ["Newest first", "Oldest first"],
        key="notebook_sort",
    )
    # Date range filter (optional)
    date_range = st.date_input(
        "Date range:",
        value=(
            (datetime.now() - timedelta(days=365)).date(),
            datetime.now().date(),
        ),
        key="notebook_date_range",
    )

# ---------------------------------------------------------------------------
# Display Results
# ---------------------------------------------------------------------------
st.markdown("---")

all_entries = []

# Match reviews
for review_key, review in st.session_state.match_reviews.items():
    all_entries.append({
        "type": "Match Review",
        "date": review.get("date", "Unknown"),
        "title": f"{review.get('home', 'Unknown')} vs {review.get('away', 'Unknown')}",
        "score": review.get("final_score", "N/A"),
        "content": review.get("overall_summary", "No summary provided"),
        "ratings": review.get("ratings", {}),
        "key": review_key,
    })
    
    # Player observations from reviews
    for team, observations in review.get("player_observations", {}).items():
        for obs in observations:
            all_entries.append({
                "type": "Player Observation",
                "date": review.get("date", "Unknown"),
                "title": f"{obs['player']} ({team})",
                "score": "",
                "content": obs["notes"],
                "match": f"{review.get('home', 'Unknown')} vs {review.get('away', 'Unknown')}",
            })

# Scout notes
for note in st.session_state.scout_notes:
    all_entries.append({
        "type": "Pre-Match Note",
        "date": note.get("timestamp", ""),
        "title": f"{note.get('home', 'Unknown')} vs {note.get('away', 'Unknown')}",
        "score": "",
        "content": note.get("notes", ""),
    })

# Parse dates for filtering and sorting
def _parse_entry_date(entry):
    d = entry.get("date") or "Unknown"
    if d == "Unknown":
        return None
    try:
        if isinstance(d, datetime):
            return d.date()
        s = str(d)
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return None

for e in all_entries:
    e["_parsed_date"] = _parse_entry_date(e)

# Date range filter
start_d, end_d = date_range if isinstance(date_range, tuple) else (date_range, date_range)
filtered_entries = [
    e for e in all_entries
    if e["_parsed_date"] is None or (start_d <= e["_parsed_date"] <= end_d)
]

if search_query:
    filtered_entries = [
        e for e in filtered_entries
        if (search_query.lower() in e["title"].lower() or
            search_query.lower() in e.get("content", "").lower())
    ]

type_filter = []
if "Match Reviews" in entry_type:
    type_filter.append("Match Review")
if "Post-Match Reviews" in entry_type:
    type_filter.append("Match Review")
if "Pre-Match Notes" in entry_type:
    type_filter.append("Pre-Match Note")
if "Player Observations" in entry_type:
    type_filter.append("Player Observation")

if type_filter:
    filtered_entries = [e for e in filtered_entries if e["type"] in type_filter]

# Sort by date (newest first or oldest first)
def _sort_key(e):
    pd = e.get("_parsed_date")
    return (pd or datetime.min.date())

filtered_entries = sorted(
    filtered_entries,
    key=_sort_key,
    reverse=(sort_order == "Newest first"),
)

# Display
st.markdown(f"<div class='section-header'>📋 {len(filtered_entries)} Results</div>", unsafe_allow_html=True)

if not filtered_entries:
    st.info("No entries found. Start reviewing matches to build your notebook!")
else:
    for entry in filtered_entries:
        # Card styling based on type
        border_color = {
            "Match Review": "#C9A840",
            "Pre-Match Note": "#58A6FF",
            "Player Observation": "#3FB950",
        }.get(entry["type"], "#8B949E")
        
        _title_safe = _html_escape(str(entry.get('title', '')))
        _content_raw = str(entry.get('content', ''))
        _content_safe = _html_escape(_content_raw[:300]) + ('...' if len(_content_raw) > 300 else '')
        _score_safe = _html_escape(str(entry.get('score', '')))
        _date_safe = _html_escape(str(entry.get('date', '')))
        st.markdown(
            f"""
            <div style="background:#161B22;padding:15px;border-radius:8px;border-left:4px solid {border_color};margin:10px 0;">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px;">
                    <span style="color:{border_color};font-size:0.75rem;font-weight:600;">{_html_escape(entry['type'])}</span>
                    <span style="color:#8B949E;font-size:0.75rem;">{_date_safe}</span>
                </div>
                <div style="font-weight:600;color:#F0F6FC;margin-bottom:8px;">{_title_safe}</div>
                {f'<div style="color:#C9A840;font-weight:600;margin-bottom:8px;">⚽ {_score_safe}</div>' if entry.get('score') else ''}
                <div style="color:#B0B8C1;font-size:0.9rem;line-height:1.5;">{_content_safe}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Show ratings if available
        if entry.get("ratings"):
            rating_text = " · ".join([f"{k.capitalize()}: {v}/10" for k, v in entry["ratings"].items()])
            st.markdown(f"<span style='font-size:0.8rem;color:#8B949E;'>⭐ {rating_text}</span>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Export Option
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>💾 Export</div>", unsafe_allow_html=True)

if st.button("📄 Export Notebook to CSV", use_container_width=True):
    if filtered_entries:
        df = pd.DataFrame(filtered_entries)
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            data=csv,
            file_name=f"match_notebook_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("No entries to export")

# Clear option
st.markdown("---")
if st.button("🗑️ Clear All Entries", use_container_width=True):
    st.session_state.match_reviews = {}
    st.session_state.scout_notes = []
    st.success("Notebook cleared!")
    st.rerun()

# Navigation
st.markdown("---")
if st.button("← Back to Review Home", use_container_width=True):
    st.switch_page("app.py")
