"""Single source of truth for compare list (app-wide).

Stores player_ids in dashboard/scouts/compare_list_scouts.json and optionally
season/competition per player. All pages (Scout, Discover, Profile, Shortlist,
Compare) and the sidebar use this module.
"""

import json
import logging
import pathlib
from typing import List, Dict, Any, Optional

import streamlit as st

logger = logging.getLogger(__name__)

_SCOUTS_DIR = pathlib.Path(__file__).parent
_COMPARE_LIST_SCOUTS_FILE = _SCOUTS_DIR / "compare_list_scouts.json"
MAX_PLAYERS = 5  # Maximum number of players allowed in the compare list.


# -----------------------------------------------------------------------------
# Session-state + file API (use from Scout and any page that needs add/remove)
# -----------------------------------------------------------------------------


def init_compare_list() -> None:
    """Initialize compare list in session state from file if not present."""
    if "compare_list" not in st.session_state:
        st.session_state.compare_list = load_scouts_compare_list()


def get_compare_list() -> List[int]:
    """Get current compare list (initializes from file if needed)."""
    init_compare_list()
    return list(st.session_state.compare_list)


def add_to_compare(player_id: int, player_name: str, max_players: int = MAX_PLAYERS) -> bool:
    """Add a player to the compare list. Returns True if added, False if full or already in list."""
    init_compare_list()
    if player_id in st.session_state.compare_list:
        return False
    if len(st.session_state.compare_list) >= max_players:
        return False
    st.session_state.compare_list.append(player_id)
    save_scouts_compare_list(st.session_state.compare_list)
    return True


def remove_from_compare(player_id: int) -> bool:
    """Remove a player from the compare list. Returns True if removed."""
    init_compare_list()
    if player_id not in st.session_state.compare_list:
        return False
    st.session_state.compare_list.remove(player_id)
    save_scouts_compare_list(st.session_state.compare_list)
    return True


def clear_compare() -> None:
    """Clear the compare list and persist."""
    st.session_state.compare_list = []
    save_scouts_compare_list([])


def get_compare_count() -> int:
    """Number of players in the compare list."""
    init_compare_list()
    return len(st.session_state.compare_list)


def is_in_compare(player_id: int) -> bool:
    """Check if a player is in the compare list."""
    init_compare_list()
    return player_id in st.session_state.compare_list


def display_compare_widget(df_all) -> None:
    """Render the compare queue widget (names + link to Compare page)."""
    count = get_compare_count()
    if count == 0:
        return
    names = []
    for pid in st.session_state.compare_list:
        player_rows = df_all[df_all["player_id"] == pid]
        if not player_rows.empty:
            names.append(str(player_rows.iloc[0].get("player_name", pid)))
        else:
            names.append(str(pid))
    st.markdown(
        f"<div style='background:#C9A84011;border:1px solid #C9A84033;border-radius:8px;"
        f"padding:0.6rem 1rem;margin-top:0.5rem;'>"
        f"⚖️ <b>Compare list ({count}/{MAX_PLAYERS}):</b> {' · '.join(names)}</div>",
        unsafe_allow_html=True,
    )
    st.page_link("pages/3_⚖️_Compare.py", label="→ Go to Compare", use_container_width=False)


# -----------------------------------------------------------------------------
# Low-level load/save (used by Compare page, Discover, Profile, Shortlist, sidebar)
# -----------------------------------------------------------------------------


def load_scouts_compare_list() -> List[int]:
    """Load compare list (player IDs) from JSON file. Returns [] on missing or error."""
    if not _COMPARE_LIST_SCOUTS_FILE.exists():
        return []
    try:
        with open(_COMPARE_LIST_SCOUTS_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [int(x) for x in data if isinstance(x, (int, float))][:MAX_PLAYERS]
        ids = data.get("player_ids", data.get("entries", []))
        if not ids:
            return []
        if ids and isinstance(ids[0], dict):
            return [int(e["player_id"]) for e in ids if isinstance(e.get("player_id"), (int, float))][:MAX_PLAYERS]
        return [int(x) for x in ids if isinstance(x, (int, float))][:MAX_PLAYERS]
    except Exception as e:
        logger.debug("Load compare list failed: %s", e)
        return []


def load_scouts_compare_entries() -> List[Dict[str, Any]]:
    """Load compare list as list of {player_id, season, competition_slug}. Fills defaults for missing."""
    if not _COMPARE_LIST_SCOUTS_FILE.exists():
        return []
    try:
        with open(_COMPARE_LIST_SCOUTS_FILE, "r") as f:
            data = json.load(f)
        entries = data.get("entries", [])
        if entries:
            return [
                {
                    "player_id": int(e.get("player_id", e) if isinstance(e, dict) else e),
                    "season": e.get("season", ""),
                    "competition_slug": e.get("competition_slug", ""),
                }
                for e in entries[:MAX_PLAYERS]
            ]
        ids = data.get("player_ids", data if isinstance(data, list) else [])
        return [{"player_id": int(x), "season": "", "competition_slug": ""} for x in ids if isinstance(x, (int, float))][:MAX_PLAYERS]
    except Exception as e:
        logger.debug("Load compare list failed: %s", e)
        return []


def save_scouts_compare_list(ids: List[int], seasons_by_id: Optional[Dict[int, Dict[str, str]]] = None) -> None:
    """Persist compare list. If seasons_by_id is provided, save as entries with season/competition_slug."""
    try:
        _SCOUTS_DIR.mkdir(parents=True, exist_ok=True)
        ids = ids[:MAX_PLAYERS]
        if seasons_by_id:
            entries = [
                {
                    "player_id": pid,
                    "season": seasons_by_id.get(pid, {}).get("season", ""),
                    "competition_slug": seasons_by_id.get(pid, {}).get("competition", ""),
                }
                for pid in ids
            ]
            with open(_COMPARE_LIST_SCOUTS_FILE, "w") as f:
                json.dump({"player_ids": ids, "entries": entries}, f, indent=0)
        else:
            with open(_COMPARE_LIST_SCOUTS_FILE, "w") as f:
                json.dump({"player_ids": ids}, f, indent=0)
    except Exception as e:
        logger.warning("Save compare list failed: %s", e)
