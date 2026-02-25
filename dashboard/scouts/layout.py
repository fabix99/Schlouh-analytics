"""Scouts dashboard shared layout: sidebar and shortlist file path."""

from __future__ import annotations

import pathlib
from typing import Optional
import streamlit as st
from dashboard.utils.styles import inject_css

_SCOUTS_DIR = pathlib.Path(__file__).parent


def render_scouts_sidebar() -> None:
    """Render the scouts dashboard sidebar (nav + footer). Call from all 5 scouts pages."""
    inject_css()
    with st.sidebar:
        st.page_link("app.py", label="🏠  Home")
        st.page_link("pages/1_🔎_Discover.py", label="🔎  Find Players")
        st.page_link("pages/2_📋_Profile.py", label="📋  Profile")
        st.page_link("pages/3_⚖️_Compare.py", label="⚖️  Compare")
        st.page_link("pages/4_🎯_Shortlist.py", label="🎯  Shortlist")
        st.markdown(
            """
            <div class="sb-footer">
                Schlouh Scouts · Internal Use<br>
                Data sourced from SofaScore
            </div>
            """,
            unsafe_allow_html=True,
        )


def get_shortlist_file_path(query_user: Optional[str] = None) -> pathlib.Path:
    """Path to shortlist JSON: per-user when ?user= or ?user_id= is set, else shortlist_data.json."""
    if not (query_user and str(query_user).strip()):
        return _SCOUTS_DIR / "shortlist_data.json"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(query_user).strip())[:64]
    return _SCOUTS_DIR / f"shortlist_{safe}.json"


def load_shortlist_from_file() -> list:
    """Load shortlist from file (path from query params user/user_id). Use on every page that needs shortlist."""
    import json
    path = get_shortlist_file_path(
        st.query_params.get("user") or st.query_params.get("user_id")
    )
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_shortlist_to_file(data: list) -> None:
    """Save shortlist to file."""
    import json
    path = get_shortlist_file_path(
        st.query_params.get("user") or st.query_params.get("user_id")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
