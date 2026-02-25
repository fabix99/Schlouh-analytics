"""Scouts Dashboard — My Shortlist.

Track and manage target players with status tags, notes, and alerts.
"""

import os
import sys
import pathlib
from datetime import datetime, timezone

# Review dashboard base URL (separate app) for Schedule / Notebook links
REVIEW_APP_URL = os.environ.get("REVIEW_APP_URL", "http://localhost:8513")

_project_root = pathlib.Path(__file__).parent.parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.utils.data import (
    load_enriched_season_stats,
    load_rolling_form,
)
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, POSITION_NAMES
from dashboard.utils.scope import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.scouts.layout import (
    render_scouts_sidebar,
    load_shortlist_from_file,
    save_shortlist_to_file,
)
from dashboard.scouts.compare_state import load_scouts_compare_list, save_scouts_compare_list

STATUS_OPTIONS = {
    "Watching": {"color": "#8B949E", "icon": "👀"},
    "Recommended": {"color": "#C9A840", "icon": "⭐"},
    "Offer Made": {"color": "#58A6FF", "icon": "💰"},
    "Signed": {"color": "#3FB950", "icon": "✅"},
    "Rejected": {"color": "#F85149", "icon": "❌"},
}

# Page config
st.set_page_config(
    page_title="My Shortlist · Scouts",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_scouts_sidebar()

# Sync shortlist from file (source of truth)
st.session_state["shortlist"] = load_shortlist_from_file()

# Initialize session state
if "compare_list" not in st.session_state:
    st.session_state.compare_list = load_scouts_compare_list()
if "confirm_remove_player_id" not in st.session_state:
    st.session_state.confirm_remove_player_id = None

# Load data
with st.spinner("Loading data…"):
    df_all = load_enriched_season_stats()
    form_df = load_rolling_form()

# Page header
st.markdown(
    """
    <div class="page-hero">
        <div class="page-hero-title">🎯 My Shortlist</div>
        <div class="page-hero-sub">
            Track and manage your target players. Add notes, set status, and compare candidates.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Link to Review dashboard: Schedule and Notebook (opens in same or new tab)
st.markdown("<div class='section-header'>📅 Next steps</div>", unsafe_allow_html=True)
_schedule_col, _notebook_col = st.columns(2)
with _schedule_col:
    st.link_button(
        "📅 Schedule observation",
        url=f"{REVIEW_APP_URL}/pages/1_📅_Schedule",
        type="secondary",
        use_container_width=True,
    )
with _notebook_col:
    st.link_button(
        "📝 Add to Notebook",
        url=f"{REVIEW_APP_URL}/pages/4_📝_Notebook",
        type="secondary",
        use_container_width=True,
    )
st.markdown("---")

# ---------------------------------------------------------------------------
# Summary Stats
# ---------------------------------------------------------------------------
if st.session_state.shortlist:
    status_counts = {}
    for player in st.session_state.shortlist:
        status = player.get("status", "Watching")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    st.markdown("<div class='section-header'>📊 Overview</div>", unsafe_allow_html=True)
    
    cols = st.columns(len(STATUS_OPTIONS))
    for i, (status, info) in enumerate(STATUS_OPTIONS.items()):
        count = status_counts.get(status, 0)
        with cols[i]:
            st.markdown(
                f"""
                <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid {info['color']};text-align:center;">
                    <div style="font-size:1.5rem;margin-bottom:5px;">{info['icon']}</div>
                    <div style="font-size:0.85rem;color:#8B949E;">{status}</div>
                    <div style="font-size:1.3rem;font-weight:700;color:{info['color']};">{count}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    
    st.markdown("---")

    # Players not in current data (e.g. transferred out)
    ids_in_data = set(df_all["player_id"].unique()) if not df_all.empty else set()
    shortlist_ids = [p.get("id") for p in st.session_state.shortlist if p.get("id") is not None]
    not_in_data = [pid for pid in shortlist_ids if pid not in ids_in_data]
    if not_in_data:
        st.markdown("<div class='section-header'>⚠️ Not in current data</div>", unsafe_allow_html=True)
        names_not = [next((p.get("name", str(pid)) for p in st.session_state.shortlist if p.get("id") == pid), str(pid)) for pid in not_in_data]
        st.caption(f"{len(not_in_data)} player(s) on your shortlist are not in the current dataset (e.g. transferred out): {', '.join(names_not[:5])}{'…' if len(names_not) > 5 else ''}.")
        if st.button("Remove these from shortlist", key="remove_not_in_data"):
            st.session_state.shortlist = [p for p in st.session_state.shortlist if p.get("id") not in not_in_data]
            save_shortlist_to_file(st.session_state.shortlist)
            st.toast(f"Removed {len(not_in_data)} player(s)")
            st.rerun()
        st.markdown("---")

# ---------------------------------------------------------------------------
# Filter/Search Controls
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🔍 Filter Shortlist</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
with col1:
    filter_status = st.multiselect(
        "Filter by status:",
        options=list(STATUS_OPTIONS.keys()),
        default=[],
        placeholder="All statuses"
    )
with col2:
    filter_search = st.text_input("Search by name:", placeholder="Player name...")
with col3:
    filter_position = st.multiselect(
        "Filter by position:",
        options=["F", "M", "D", "G"],
        format_func=lambda x: POSITION_NAMES.get(x, x),
        default=[]
    )

# ---------------------------------------------------------------------------
# Display Shortlist
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>👥 Tracked Players</div>", unsafe_allow_html=True)

if not st.session_state.shortlist:
    st.info("🎯 Your shortlist is empty. Go to 'Find Players' to add candidates.")
    
    if st.button("🔎 Go to Discover", type="primary", use_container_width=True):
        st.switch_page("pages/1_🔎_Discover.py")
else:
    # Apply filters
    filtered_shortlist = st.session_state.shortlist.copy()
    
    if filter_status:
        filtered_shortlist = [p for p in filtered_shortlist if p.get("status") in filter_status]
    
    if filter_search:
        filtered_shortlist = [p for p in filtered_shortlist if filter_search.lower() in p.get("name", "").lower()]
    
    if filter_position:
        def _player_position(pid):
            rows = df_all[df_all["player_id"] == pid]
            if not rows.empty:
                return rows.iloc[0].get("player_position", None)
            return None
        filtered_shortlist = [
            p for p in filtered_shortlist
            if _player_position(p.get("id")) in filter_position
        ]
    
    if not filtered_shortlist:
        st.info("No players match your filters")
    else:
        # Display each player
        for player in filtered_shortlist:
            player_id = player.get("id")
            player_name = player.get("name", "Unknown")
            status = player.get("status", "Watching")
            status_info = STATUS_OPTIONS.get(status, STATUS_OPTIONS["Watching"])
            
            # Get latest player data (prefer current season + leagues/UEFA)
            player_data = df_all[df_all["player_id"] == player_id]
            if not player_data.empty:
                default_scope = player_data[
                    (player_data["season"] == CURRENT_SEASON) &
                    (player_data["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))
                ]
                if not default_scope.empty:
                    latest = default_scope.iloc[0]
                else:
                    latest = player_data.sort_values("season", ascending=False).iloc[0]
                position = latest.get("player_position", "?")
                team = latest.get("team", "Unknown")
                league = latest.get("league_name", "Unknown")
                rating = latest.get("avg_rating", 0)
                season = latest.get("season", "")
            else:
                position = player.get("position", "?")
                team = "Unknown"
                league = "Unknown"
                rating = 0
                season = ""
            
            # Player card
            with st.container():
                st.markdown(
                    f"""
                    <div style="background:#161B22;padding:15px;border-radius:8px;border:1px solid #30363D;margin-bottom:10px;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                            <div>
                                <div style="font-size:1.2rem;font-weight:600;color:#F0F6FC;">{player_name}</div>
                                <div style="font-size:0.85rem;color:#8B949E;margin-top:3px;">
                                    {POSITION_NAMES.get(position, position)} · {team} · {league} {season}
                                </div>
                            </div>
                            <span style="background:{status_info['color']}20;color:{status_info['color']};padding:4px 12px;border-radius:12px;font-size:0.8rem;font-weight:500;">
                                {status_info['icon']} {status}
                            </span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
                # Actions row
                action_cols = st.columns([2, 2, 1, 1, 1])
                
                with action_cols[0]:
                    # Status selector
                    new_status = st.selectbox(
                        "Status:",
                        options=list(STATUS_OPTIONS.keys()),
                        index=list(STATUS_OPTIONS.keys()).index(status),
                        key=f"status_{player_id}",
                        label_visibility="collapsed"
                    )
                    if new_status != status:
                        player["status"] = new_status
                        save_shortlist_to_file(st.session_state.shortlist)
                        st.rerun()
                
                with action_cols[1]:
                    # Note preview (~50 chars) and last updated
                    raw_notes = (player.get("notes") or "").strip()
                    has_notes = bool(raw_notes)
                    notes_updated_at = player.get("notes_updated_at")
                    if has_notes:
                        preview = (raw_notes[:50] + "…") if len(raw_notes) > 50 else raw_notes
                        preview_safe = preview.replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")
                        if notes_updated_at:
                            try:
                                dt = datetime.fromisoformat(notes_updated_at.replace("Z", "+00:00"))
                                notes_label = f"📝 {preview_safe} <span style='color:#6E7681;'>({dt.strftime('%d %b')})</span>"
                            except Exception:
                                notes_label = f"📝 {preview_safe}"
                        else:
                            notes_label = f"📝 {preview_safe}"
                    else:
                        notes_label = "📝 Add notes..."
                    _title = (raw_notes[:200].replace("'", "&#39;").replace('"', "&quot;") if raw_notes else "")
                    st.markdown(f"<span style='font-size:0.8rem;color:#8B949E;' title='{_title}'>{notes_label}</span>", unsafe_allow_html=True)
                
                with action_cols[2]:
                    if st.button("📋 Profile", key=f"profile_{player_id}", use_container_width=True):
                        st.session_state["profile_player_id"] = player_id
                        st.switch_page("pages/2_📋_Profile.py")
                
                with action_cols[3]:
                    if player_id not in st.session_state.compare_list:
                        if st.button("⚖️ Compare", key=f"compare_{player_id}", use_container_width=True):
                            st.session_state.compare_list.append(player_id)
                            save_scouts_compare_list(st.session_state.compare_list)
                            st.toast("Added!")
                            st.rerun()
                    else:
                        st.button("✅ In Compare", disabled=True, use_container_width=True)
                
                with action_cols[4]:
                    if st.session_state.get("confirm_remove_player_id") == player_id:
                        if st.button("✅ Yes, remove", key=f"confirm_remove_yes_{player_id}"):
                            st.session_state.shortlist = [p for p in st.session_state.shortlist if p["id"] != player_id]
                            save_shortlist_to_file(st.session_state.shortlist)
                            st.session_state.confirm_remove_player_id = None
                            st.toast(f"Removed {player.get('name', 'Player')} from shortlist")
                            st.rerun()
                        if st.button("Cancel", key=f"confirm_remove_cancel_{player_id}"):
                            st.session_state.confirm_remove_player_id = None
                            st.rerun()
                    elif st.button("🗑️ Remove", key=f"remove_{player_id}", use_container_width=True):
                        st.session_state.confirm_remove_player_id = player_id
                        st.rerun()
                
                # Notes expander (max length + character count + friendly error)
                MAX_NOTE_LENGTH = 2000
                with st.expander("📝 Notes", expanded=False):
                    notes_key = f"notes_{player_id}"
                    current_notes = player.get("notes", "")
                    
                    new_notes = st.text_area(
                        "Scouting notes:",
                        value=current_notes,
                        placeholder="Add your observations here...",
                        key=notes_key,
                        label_visibility="collapsed",
                        max_chars=MAX_NOTE_LENGTH,
                    )
                    st.caption(f"Characters: {len(new_notes)} / {MAX_NOTE_LENGTH}")
                    
                    # Show last updated timestamp when available
                    notes_updated = player.get("notes_updated_at")
                    if notes_updated:
                        try:
                            dt = datetime.fromisoformat(notes_updated.replace("Z", "+00:00"))
                            st.caption(f"Last updated: {dt.strftime('%d %b %Y, %H:%M')}")
                        except Exception:
                            st.caption(f"Last updated: {notes_updated}")
                    col_save, col_cancel = st.columns([1, 4])
                    with col_save:
                        if st.button("💾 Save Notes", key=f"save_notes_{player_id}"):
                            if len(new_notes) > MAX_NOTE_LENGTH:
                                st.error(f"Notes are too long. Please keep them under {MAX_NOTE_LENGTH} characters (current: {len(new_notes)}).")
                            else:
                                now = datetime.now(timezone.utc).isoformat()
                                player["notes"] = new_notes
                                player["notes_updated_at"] = now
                                if not player.get("notes_created_at"):
                                    player["notes_created_at"] = now
                                save_shortlist_to_file(st.session_state.shortlist)
                            st.toast("Notes saved!")
                
                st.markdown("---")

# ---------------------------------------------------------------------------
# Bulk Actions
# ---------------------------------------------------------------------------
if st.session_state.shortlist:
    st.markdown("<div class='section-header'>🔧 Bulk Actions</div>", unsafe_allow_html=True)

    # Confirmation step for bulk remove
    if st.session_state.get("confirm_bulk_remove_ids"):
        ids_to_remove = st.session_state.confirm_bulk_remove_ids
        st.warning(f"Remove {len(ids_to_remove)} player(s) from shortlist?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Yes, remove"):
                st.session_state.shortlist = [p for p in st.session_state.shortlist if p["id"] not in ids_to_remove]
                save_shortlist_to_file(st.session_state.shortlist)
                st.session_state.confirm_bulk_remove_ids = None
                st.toast(f"Removed {len(ids_to_remove)} player(s)")
                st.rerun()
        with c2:
            if st.button("Cancel"):
                st.session_state.confirm_bulk_remove_ids = None
                st.rerun()
    else:
        with st.form("bulk_actions_form"):
            bulk_cols = st.columns([2, 1, 1])
            with bulk_cols[0]:
                selected_for_bulk = st.multiselect(
                    "Select players:",
                    options=[p["id"] for p in st.session_state.shortlist],
                    format_func=lambda x: next((p["name"] for p in st.session_state.shortlist if p["id"] == x), str(x)),
                    key="bulk_select",
                )
            with bulk_cols[1]:
                bulk_action = st.selectbox(
                    "Action:",
                    options=["Compare Selected", "Change Status", "Remove Selected"],
                    key="bulk_action",
                )
            new_bulk_status = None
            if bulk_action == "Change Status":
                new_bulk_status = st.selectbox("New status:", options=list(STATUS_OPTIONS.keys()), key="bulk_status")
            with bulk_cols[2]:
                submitted = st.form_submit_button("Execute")
            if submitted:
                if not selected_for_bulk:
                    st.warning("Select players first")
                elif bulk_action == "Compare Selected":
                    st.session_state.compare_list = selected_for_bulk[:5]
                    save_scouts_compare_list(st.session_state.compare_list, {})
                    st.toast(f"Added {min(5, len(selected_for_bulk))} to compare")
                    st.switch_page("pages/3_⚖️_Compare.py")
                elif bulk_action == "Change Status" and new_bulk_status:
                    for p in st.session_state.shortlist:
                        if p["id"] in selected_for_bulk:
                            p["status"] = new_bulk_status
                    save_shortlist_to_file(st.session_state.shortlist)
                    st.toast(f"Updated {len(selected_for_bulk)} players")
                    st.rerun()
                elif bulk_action == "Remove Selected":
                    st.session_state.confirm_bulk_remove_ids = selected_for_bulk
                    st.rerun()

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
if st.session_state.shortlist:
    st.markdown("---")
    st.markdown("<div class='section-header'>📤 Export</div>", unsafe_allow_html=True)
    
    # Prepare export data
    export_data = []
    for player in st.session_state.shortlist:
        player_data = df_all[df_all["player_id"] == player.get("id")]
        if not player_data.empty:
            latest = player_data.sort_values("season", ascending=False).iloc[0]
            export_data.append({
                "Player": player.get("name", "Unknown"),
                "Status": player.get("status", "Watching"),
                "Position": latest.get("player_position", "?"),
                "Team": latest.get("team", "Unknown"),
                "League": latest.get("league_name", "Unknown"),
                "Season": latest.get("season", ""),
                "Age": latest.get("age_at_season_start", 0),
                "Rating": latest.get("avg_rating", 0),
                "Notes": player.get("notes", ""),
            })
    
    if export_data:
        export_df = pd.DataFrame(export_data)
        csv = export_df.to_csv(index=False)
        st.download_button(
            "⬇️ Export Shortlist (CSV)",
            data=csv,
            file_name=f"schlouh_shortlist_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# Footer navigation
st.markdown("---")
if st.button("← Back to Discover", use_container_width=True):
    st.switch_page("pages/1_🔎_Discover.py")
