"""Shared sidebar component used by all dashboard pages.

Calling ``render_sidebar()`` also injects the shared CSS design system, so
pages do not need to call ``inject_css()`` separately.
"""

import os
import pathlib
import streamlit as st
from dashboard.utils.styles import inject_css

# Base URL for Scouts dashboard (separate app); default matches typical dev setup.
SCOUTS_APP_URL = os.environ.get("SCOUTS_APP_URL", "http://localhost:8511")

# Resolve logo path relative to this file — works regardless of cwd
_LOGO = pathlib.Path(__file__).parent.parent / "assets" / "logo.png"


def render_sidebar() -> None:
    """Render the branded navigation sidebar and inject shared CSS."""

    inject_css()

    with st.sidebar:
        # ----------------------------------------------------------------
        # Brand header — real logo + wordmark
        # ----------------------------------------------------------------
        if _LOGO.exists():
            st.image(str(_LOGO), width=90)
            st.markdown(
                "<div class='sb-brand-tagline' style='text-align:center;"
                "margin-top:-4px;margin-bottom:12px;padding-bottom:12px;"
                "border-bottom:1px solid #30363D;'>Scouting Intelligence</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="sb-brand">
                    <div class="sb-brand-name">Schlouh Football</div>
                    <div class="sb-brand-tagline">Scouting Intelligence</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------------------
        # Primary nav
        # ----------------------------------------------------------------
        st.markdown("<span class='sb-nav-label'>Overview</span>", unsafe_allow_html=True)
        st.page_link("app.py", label="🏠  Dashboard Home")

        st.markdown("<span class='sb-nav-label'>Analysis</span>", unsafe_allow_html=True)
        st.page_link("pages/1_🔍_Scout.py",   label="🔍  Scout Players")
        st.page_link("pages/4_🏆_Teams.py",   label="🏆  Team Analysis")
        st.page_link("pages/2_⚖️_Compare.py", label="⚖️  Compare Players")
        st.page_link("pages/3_📊_Explore.py", label="📊  Explore Data")
        st.page_link("pages/5_🤖_AI_Scout.py", label="🤖  AI Scout")

        # ----------------------------------------------------------------
        # Compare queue
        # ----------------------------------------------------------------
        st.markdown("<div class='sb-divider'></div>", unsafe_allow_html=True)

        if "compare_list" in st.session_state and st.session_state.compare_list:
            n = len(st.session_state.compare_list)
            st.markdown(
                f"""
                <div class="sb-compare-widget">
                    <div class="sb-compare-label">Comparison Queue</div>
                    <div class="sb-compare-count">{n}
                        <span style="font-size:0.78rem;font-weight:400;color:#8B949E;"> / 6 players</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Clear queue", key="_sidebar_clear_compare", use_container_width=True):
                st.session_state.compare_list = []
                st.rerun()
        else:
            st.markdown(
                "<div style='font-size:0.75rem;color:#8B949E;padding:0.3rem 0.2rem;'>"
                "No players in queue — add from Scout.</div>",
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------------------
        # Other dashboards (Shortlist lives in Scouts app)
        # ----------------------------------------------------------------
        st.markdown("<div class='sb-divider'></div>", unsafe_allow_html=True)
        st.markdown("<span class='sb-nav-label'>Other</span>", unsafe_allow_html=True)
        st.markdown(
            f"<a href='{SCOUTS_APP_URL}' target='_blank' rel='noopener' "
            "style='font-size:0.85rem;color:#8B949E;'>🎯 My Shortlist (Scouts)</a>",
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------------------
        # Footer
        # ----------------------------------------------------------------
        st.markdown(
            """
            <div class="sb-footer">
                Schlouh Football · Internal Use<br>
                Data sourced from SofaScore
            </div>
            """,
            unsafe_allow_html=True,
        )
