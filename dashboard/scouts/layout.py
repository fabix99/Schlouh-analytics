"""Scouts shared layout: shortlist file path and load/save.

Used by the unified app (Discover, Shortlist, Profile, Compare, sidebar)
for shortlist persistence. Navigation is in dashboard.utils.sidebar.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)
_SCOUTS_DIR = pathlib.Path(__file__).parent


def get_shortlist_file_path(query_user: Optional[str] = None) -> pathlib.Path:
    """Path to shortlist JSON: per-user when ?user= or ?user_id= is set, else shortlist_data.json."""
    if not (query_user and str(query_user).strip()):
        return _SCOUTS_DIR / "shortlist_data.json"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(query_user).strip())[:64]
    return _SCOUTS_DIR / f"shortlist_{safe}.json"


def load_shortlist_from_file() -> list:
    """Load shortlist from file (path from query params user/user_id). Use on every page that needs shortlist."""
    path = get_shortlist_file_path(
        st.query_params.get("user") or st.query_params.get("user_id")
    )
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (IOError, OSError, json.JSONDecodeError) as e:
        logger.debug("Load shortlist failed: %s", e)
        return []


def save_shortlist_to_file(data: list) -> None:
    """Save shortlist to file."""
    path = get_shortlist_file_path(
        st.query_params.get("user") or st.query_params.get("user_id")
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except (IOError, OSError) as e:
        logger.warning("Save shortlist failed: %s", e)
        raise
