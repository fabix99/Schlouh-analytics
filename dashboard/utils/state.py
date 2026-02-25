"""Centralized session state management utilities."""

from typing import List, Optional
import json
import pathlib
import streamlit as st

# Persist Main dashboard compare queue (SM.1, SM.4)
_COMPARE_LIST_MAIN_FILE = pathlib.Path(__file__).parent.parent / "compare_list_main.json"


def _load_compare_list_from_file() -> List[int]:
    """Load compare list from JSON file. Returns [] on missing or error."""
    if not _COMPARE_LIST_MAIN_FILE.exists():
        return []
    try:
        with open(_COMPARE_LIST_MAIN_FILE, "r") as f:
            data = json.load(f)
        ids = data if isinstance(data, list) else data.get("player_ids", [])
        return [int(x) for x in ids if isinstance(x, (int, float))]
    except Exception:
        return []


def _save_compare_list_to_file(ids: List[int]) -> None:
    """Persist compare list to JSON file."""
    try:
        _COMPARE_LIST_MAIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_COMPARE_LIST_MAIN_FILE, "w") as f:
            json.dump({"player_ids": ids}, f, indent=0)
    except Exception:
        pass


def init_compare_list() -> None:
    """Initialize the compare list in session state if not present (load from file)."""
    if "compare_list" not in st.session_state:
        st.session_state.compare_list = _load_compare_list_from_file()


def get_compare_list() -> List[int]:
    """Get the current compare list, ensuring it's initialized."""
    init_compare_list()
    return st.session_state.compare_list


def add_to_compare(player_id: int, player_name: str, max_players: int = 6) -> bool:
    """
    Add a player to the compare list.

    Returns:
        True if added successfully, False if already in list or list is full.
    """
    init_compare_list()

    if player_id in st.session_state.compare_list:
        return False

    if len(st.session_state.compare_list) >= max_players:
        return False

    st.session_state.compare_list.append(player_id)
    _save_compare_list_to_file(st.session_state.compare_list)
    return True


def remove_from_compare(player_id: int) -> bool:
    """
    Remove a player from the compare list.

    Returns:
        True if removed, False if not in list.
    """
    init_compare_list()

    if player_id not in st.session_state.compare_list:
        return False

    st.session_state.compare_list.remove(player_id)
    _save_compare_list_to_file(st.session_state.compare_list)
    return True


def clear_compare() -> None:
    """Clear all players from the compare list."""
    st.session_state.compare_list = []
    _save_compare_list_to_file(st.session_state.compare_list)


def get_compare_count() -> int:
    """Get the number of players in the compare list."""
    init_compare_list()
    return len(st.session_state.compare_list)


def is_in_compare(player_id: int) -> bool:
    """Check if a player is already in the compare list."""
    init_compare_list()
    return player_id in st.session_state.compare_list


def display_compare_widget(df_all) -> None:
    """Display the compare queue widget in the main content area."""
    count = get_compare_count()

    if count == 0:
        return

    # Get player names
    names = []
    for pid in st.session_state.compare_list:
        player_rows = df_all[df_all["player_id"] == pid]
        if not player_rows.empty:
            names.append(player_rows.iloc[0]["player_name"])
        else:
            names.append(str(pid))

    st.markdown(
        f"<div style='background:#C9A84011;border:1px solid #C9A84033;border-radius:8px;"
        f"padding:0.6rem 1rem;margin-top:0.5rem;'>"
        f"⚖️ <b>Compare list ({count}/6):</b> {' · '.join(names)} "
        f"→ <a href='/Compare_Players' target='_self' style='color:#C9A840;'>Go to Compare</a></div>",
        unsafe_allow_html=True,
    )


def init_profile_view() -> None:
    """Initialize profile view state if not present."""
    if "profile_player_id" not in st.session_state:
        st.session_state.profile_player_id = None
    if "profile_player_name" not in st.session_state:
        st.session_state.profile_player_name = None


def set_profile_player(player_id: int, player_name: str) -> None:
    """Set the current player for profile view."""
    st.session_state.profile_player_id = player_id
    st.session_state.profile_player_name = player_name


def clear_profile_player() -> None:
    """Clear the current profile player."""
    st.session_state.profile_player_id = None
    st.session_state.profile_player_name = None


def get_profile_player() -> tuple[Optional[int], Optional[str]]:
    """Get the current profile player ID and name."""
    init_profile_view()
    return (
        st.session_state.profile_player_id,
        st.session_state.profile_player_name,
    )


def is_profile_view_active() -> bool:
    """Check if profile view is currently active."""
    init_profile_view()
    return st.session_state.profile_player_id is not None
