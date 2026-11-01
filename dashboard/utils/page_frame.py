"""Shared page frame: config, sidebar, and styles.

Use render_page_frame() at the top of each page so set_page_config,
sidebar, and CSS are applied consistently. Must be the first Streamlit
command on the page (Streamlit requires set_page_config first).
"""

from __future__ import annotations

import streamlit as st

from dashboard.utils.sidebar import render_sidebar


def render_page_frame(
    page_title: str,
    page_icon: str = "⚽",
    layout: str = "wide",
    initial_sidebar_state: str = "expanded",
) -> None:
    """Set page config and render the shared sidebar (which injects CSS and responsive styles).

    Call this at the very start of each page, before any other st.* calls.

    Example:
        # In pages/8_🔎_Discover.py
        from dashboard.utils.page_frame import render_page_frame
        render_page_frame("Find Players", "🔎")
    """
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar_state,
    )
    render_sidebar()
