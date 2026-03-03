"""Session state helpers for the unified dashboard.

- Profile view: which player is shown inline on Scout (profile_player_id/name).
  Compare list is handled by dashboard.scouts.compare_state (single source of truth).
"""

from typing import Optional
import streamlit as st


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
