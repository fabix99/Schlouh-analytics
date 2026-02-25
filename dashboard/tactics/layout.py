"""Tactics dashboard shared layout: sidebar with nav and footer."""

from __future__ import annotations

import pathlib
import streamlit as st
from dashboard.utils.styles import inject_css

_TACTICS_DIR = pathlib.Path(__file__).parent
_ASSETS_DIR = _TACTICS_DIR.parent / "assets"
_LOGO = _ASSETS_DIR / "logo.png"


def render_tactics_sidebar() -> None:
    """Render the tactics dashboard sidebar (nav, other dashboards, footer). Call from app and all tactics pages."""
    inject_css()
    with st.sidebar:
        if _LOGO.exists():
            st.image(str(_LOGO), width=90)
            st.markdown(
                "<div class='sb-brand-tagline' style='text-align:center;"
                "margin-top:-4px;margin-bottom:12px;padding-bottom:12px;"
                "border-bottom:1px solid #30363D;'>Tactics Dashboard</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="sb-brand">
                    <div class="sb-brand-name">Schlouh Tactics</div>
                    <div class="sb-brand-tagline">Team Analysis</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<span class='sb-nav-label'>Teams</span>", unsafe_allow_html=True)
        st.page_link("app.py", label="🏠  Home")
        st.page_link("pages/1_🏟️_Team_Directory.py", label="🏟️  Team Directory")
        st.page_link("pages/2_📐_Tactical_Profile.py", label="📐  Tactical Profile")

        st.markdown("<span class='sb-nav-label'>Analysis</span>", unsafe_allow_html=True)
        st.page_link("pages/3_⚔️_Opponent_Prep.py", label="⚔️  Opponent Prep")
        st.page_link("pages/4_📊_League_Trends.py", label="📊  League Trends")

        st.markdown("<div class='sb-divider'></div>", unsafe_allow_html=True)
        st.markdown("<span class='sb-nav-label'>Other Dashboards</span>", unsafe_allow_html=True)
        st.markdown(
            "<a href='../scouts/app.py' style='font-size:0.85rem;color:#8B949E;'>🔎 Scouts Dashboard</a>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<a href='../app.py' style='font-size:0.85rem;color:#8B949E;'>← Main Dashboard</a>",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="sb-footer">
                Schlouh Tactics · Internal Use<br>
                Data sourced from SofaScore
            </div>
            """,
            unsafe_allow_html=True,
        )
