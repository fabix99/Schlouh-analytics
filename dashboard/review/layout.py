"""Review dashboard shared layout: sidebar with nav, notes widget, and footer."""

from __future__ import annotations

import pathlib
import streamlit as st
from dashboard.utils.styles import inject_css

_REVIEW_DIR = pathlib.Path(__file__).parent
_ASSETS_DIR = _REVIEW_DIR.parent / "assets"
_LOGO = _ASSETS_DIR / "logo.png"


def render_review_sidebar() -> None:
    """Render the review dashboard sidebar (nav, notes widget, other dashboards, footer). Call from app and all review pages."""
    inject_css()
    with st.sidebar:
        if _LOGO.exists():
            st.image(str(_LOGO), width=90)
            st.markdown(
                "<div class='sb-brand-tagline' style='text-align:center;"
                "margin-top:-4px;margin-bottom:12px;padding-bottom:12px;"
                "border-bottom:1px solid #30363D;'>Review Dashboard</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="sb-brand">
                    <div class="sb-brand-name">Schlouh Review</div>
                    <div class="sb-brand-tagline">Match Analysis</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<span class='sb-nav-label'>Schedule</span>", unsafe_allow_html=True)
        st.page_link("app.py", label="🏠  Home")
        st.page_link("pages/1_📅_Schedule.py", label="📅  Find by team")

        st.markdown("<span class='sb-nav-label'>Analysis</span>", unsafe_allow_html=True)
        st.page_link("pages/2_🔍_Pre_Match.py", label="🔍  Pre-Match")
        st.page_link("pages/3_📊_Post_Match.py", label="📊  Post-Match")
        st.page_link("pages/4_📝_Notebook.py", label="📝  Notebook")

        st.markdown("<div class='sb-divider'></div>", unsafe_allow_html=True)

        if "scout_notes" in st.session_state and st.session_state.scout_notes:
            n_notes = len(st.session_state.scout_notes)
            st.markdown(
                f"""
                <div class='sb-compare-widget'>
                    <div class='sb-compare-label'>My Notes</div>
                    <div class='sb-compare-count'>{n_notes}
                        <span style='font-size:0.78rem;font-weight:400;color:#8B949E;'> entries</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Notebook", key="_sidebar_notes", use_container_width=True):
                st.switch_page("pages/4_📝_Notebook.py")
        else:
            st.markdown(
                "<div style='font-size:0.75rem;color:#8B949E;padding:0.3rem 0.2rem;'>"
                "No notes yet — start from Pre-Match or Post-Match.</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div class='sb-divider'></div>", unsafe_allow_html=True)
        st.markdown("<span class='sb-nav-label'>Other Dashboards</span>", unsafe_allow_html=True)
        st.markdown(
            "<a href='../app.py' style='font-size:0.85rem;color:#8B949E;'>← Main Dashboard</a>",
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="sb-footer">
                Schlouh Review · Internal Use<br>
                Data sourced from SofaScore
            </div>
            """,
            unsafe_allow_html=True,
        )
