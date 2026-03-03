"""Scouts Dashboard — My Shortlist.

Track and manage target players with status tags, notes, and alerts.
"""

import sys
import pathlib
from datetime import datetime, timezone
from typing import Optional, Tuple

_project_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.utils.data import load_enriched_season_stats
from dashboard.utils.constants import COMP_NAMES, COMP_FLAGS, POSITION_NAMES
from dashboard.utils.scope import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.utils.sidebar import render_sidebar
from dashboard.scouts.layout import load_shortlist_from_file, save_shortlist_to_file
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

render_sidebar()

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

# ---------------------------------------------------------------------------
# Hero — one value proposition + primary CTA
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-v2">
        <div class="hero-v2-title">My Shortlist</div>
        <div class="hero-v2-sub">
            Track and manage your target players. Add notes, set status, and compare candidates.
        </div>
        <div class="hero-v2-tagline">One place to track targets and next steps.</div>
        <div class="hero-v2-accent" aria-hidden="true"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Primary CTA: Find players (only primary on page)
_btn_col, _gap_col, _compare_col, _short_col = st.columns([2, 0.5, 1, 1])
with _btn_col:
    if st.button("Find players", key="hero_find_players", type="primary", use_container_width=True):
        st.switch_page("pages/8_🔎_Discover.py")
with _compare_col:
    if st.button("Compare", key="hero_compare", use_container_width=True):
        st.switch_page("pages/3_⚖️_Compare.py")
with _short_col:
    _short_count = len(st.session_state.get("shortlist", []))
    _short_label = f"Shortlist ({_short_count})" if _short_count else "Shortlist"
    st.button(_short_label, key="hero_shortlist", disabled=True, use_container_width=True)
st.markdown("---")

# ---------------------------------------------------------------------------
# Empty state: one message + one primary CTA
# ---------------------------------------------------------------------------
if not st.session_state.get("shortlist", []):
    st.info("Your shortlist is empty. Use **Find players** to add candidates.")
    if st.button("Find players", key="empty_find_players", type="primary", use_container_width=True):
        st.switch_page("pages/8_🔎_Discover.py")
    st.markdown("---")
    st.markdown("<div class='section-header'>Coverage</div>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-accent' aria-hidden='true'></div>", unsafe_allow_html=True)
    st.markdown(
        '<p class="data-attribution">Data sourced from SofaScore. Shortlist is stored locally. Use <strong>Find players</strong> to add candidates.</p>',
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Visual anchor: Shortlist at a glance (spotlight first priority player)
# ---------------------------------------------------------------------------
def _shortlist_spotlight_player(
    shortlist: list,
    df_all: pd.DataFrame,
) -> Tuple[Optional[dict], Optional[pd.Series]]:
    """First Recommended, else first Watching, else first in list; returns (player_dict, latest_row) or (None, None)."""
    order = ["Recommended", "Watching", "Offer Made", "Signed", "Rejected"]
    for status in order:
        for p in shortlist:
            if p.get("status") == status:
                pid = p.get("id")
                if pid is None:
                    continue
                rows = df_all[df_all["player_id"] == pid] if not df_all.empty else pd.DataFrame()
                if not rows.empty:
                    default = rows[(rows["season"] == CURRENT_SEASON) & (rows["competition_slug"].isin(DEFAULT_COMPETITION_SLUGS))]
                    latest = default.iloc[0] if not default.empty else rows.sort_values("season", ascending=False).iloc[0]
                else:
                    latest = None
                return p, latest
    if shortlist:
        p = shortlist[0]
        pid = p.get("id")
        rows = df_all[df_all["player_id"] == pid] if not df_all.empty and pid is not None else pd.DataFrame()
        latest = rows.iloc[0] if not rows.empty else None
        return p, latest
    return None, None

_spot_player, _spot_row = _shortlist_spotlight_player(st.session_state.get("shortlist", []), df_all)
if _spot_player and (_spot_row is not None or _spot_player.get("name")):
    st.markdown("<div class='section-header'>Shortlist at a glance</div>", unsafe_allow_html=True)
    pos_label = POSITION_NAMES.get(_spot_row.get("player_position", "?"), "?") if _spot_row is not None else POSITION_NAMES.get(_spot_player.get("position", "?"), "?")
    team = _spot_row.get("team", "—") if _spot_row is not None else "—"
    if pd.isna(team) or team == "" or (isinstance(team, float) and np.isnan(team)):
        team = "—"
    rating_val = _spot_row.get("avg_rating") if _spot_row is not None else None
    rating_str = f"{rating_val:.2f}" if rating_val is not None and not (isinstance(rating_val, float) and np.isnan(rating_val)) else "—"
    status_info = STATUS_OPTIONS.get(_spot_player.get("status", "Watching"), STATUS_OPTIONS["Watching"])
    st.markdown(
        f"""
        <div class="spotlight-card">
            <div class="spotlight-badge">Spotlight · {status_info['icon']} {_spot_player.get('status', 'Watching')}</div>
            <div class="spotlight-name">{_spot_player.get('name', 'Unknown')}</div>
            <div class="spotlight-meta">{pos_label} · {team}</div>
            <div class="spotlight-stats">
                <span class="spotlight-stat"><strong>{rating_str}</strong> rating</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("View profile", key="shortlist_spotlight_profile", type="primary", use_container_width=True):
        st.session_state["profile_player_id"] = _spot_player.get("id")
        st.switch_page("pages/2_📋_Profile.py")
    st.markdown("---")

# ---------------------------------------------------------------------------
# Overview (status counts) + Not in data
# ---------------------------------------------------------------------------
if st.session_state.get("shortlist", []):
    status_counts = {}
    for player in st.session_state.shortlist:
        status = player.get("status", "Watching")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    st.markdown("<div class='section-header'>📊 Overview</div>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-accent' aria-hidden='true'></div>", unsafe_allow_html=True)
    cols = st.columns(len(STATUS_OPTIONS))
    for i, (status, info) in enumerate(STATUS_OPTIONS.items()):
        count = status_counts.get(status, 0)
        with cols[i]:
            st.markdown(
                f"""
                <div class="shortlist-status-card" style="border-color:{info['color']};">
                    <div class="shortlist-status-icon">{info['icon']}</div>
                    <div class="shortlist-status-label">{status}</div>
                    <div class="shortlist-status-count" style="color:{info['color']};">{count}</div>
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
# Filter and display shortlist
# ---------------------------------------------------------------------------
st.markdown("<div class='section-header'>🔍 Filter shortlist</div>", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    filter_status = st.multiselect(
        "Filter by status:",
        options=list(STATUS_OPTIONS.keys()),
        default=[],
        placeholder="All statuses",
    )
with col2:
    filter_search = st.text_input("Search by name:", placeholder="Player name…")
with col3:
    filter_position = st.multiselect(
        "Filter by position:",
        options=["F", "M", "D", "G"],
        format_func=lambda x: POSITION_NAMES.get(x, x),
        default=[],
    )
st.markdown("<div class='section-header'>👥 Tracked players</div>", unsafe_allow_html=True)

filtered_shortlist = st.session_state.get("shortlist", []).copy()
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
    filtered_shortlist = [p for p in filtered_shortlist if _player_position(p.get("id")) in filter_position]

if not filtered_shortlist:
    st.info("No players match your filters. Clear filters above or use **Find players** to add more.")
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
            
            # Player card (design system)
            meta_line = f"{POSITION_NAMES.get(position, position)} · {team} · {league} {season}"
            with st.container():
                st.markdown(
                    f"""
                    <div class="shortlist-player-card">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                            <div>
                                <div class="shortlist-player-name">{player_name}</div>
                                <div class="shortlist-player-meta">{meta_line}</div>
                            </div>
                            <span class="shortlist-status-badge" style="background:{status_info['color']}20;color:{status_info['color']};">
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
                        st.button("✅ In Compare", disabled=True, use_container_width=True, key=f"in_compare_{player_id}")
                
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
                                try:
                                    save_shortlist_to_file(st.session_state.shortlist)
                                    st.toast("Notes saved!")
                                    st.rerun()
                                except (IOError, OSError):
                                    st.error("Could not save notes. Check file permissions or disk space.")
                
                st.markdown("---")

# ---------------------------------------------------------------------------
# Bulk Actions
# ---------------------------------------------------------------------------
if st.session_state.get("shortlist", []):
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
if st.session_state.get("shortlist", []):
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
            "⬇️ Export shortlist (CSV)",
            data=csv,
            file_name=f"schlouh_shortlist_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# Coverage and attribution
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("<div class='section-header'>Coverage</div>", unsafe_allow_html=True)
st.markdown("<div class='kpi-accent' aria-hidden='true'></div>", unsafe_allow_html=True)
st.markdown(
    '<p class="data-attribution">Data sourced from SofaScore. Shortlist is stored locally. Use <strong>Find players</strong> to add candidates.</p>',
    unsafe_allow_html=True,
)

# Footer navigation
st.markdown("---")
if st.button("← Back to Find Players", use_container_width=True):
    st.switch_page("pages/8_🔎_Discover.py")
