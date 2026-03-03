"""Unified sidebar for the single Schlouh Analytics app.

Calling ``render_sidebar()`` injects the shared CSS and renders navigation
for all sections: Scouting, Teams & Tactics, Data & AI.
"""

import streamlit as st
from dashboard.utils.styles import inject_css
from dashboard.utils.responsive_styles import inject_responsive_css
from dashboard.utils.paths import PROJECT_ROOT
from dashboard.utils.constants import STAT_TOOLTIPS

_LOGO = PROJECT_ROOT / "dashboard" / "assets" / "logo.png"


def _get_compare_count() -> int:
    """Compare queue size (file-based from scouts)."""
    try:
        from dashboard.scouts.compare_state import load_scouts_compare_list
        return len(load_scouts_compare_list())
    except Exception:
        return 0


def _get_shortlist_count() -> int:
    """Shortlist size (file-based)."""
    try:
        from dashboard.scouts.layout import load_shortlist_from_file
        return len(load_shortlist_from_file())
    except Exception:
        return 0


def render_sidebar() -> None:
    """Render the unified sidebar: brand, nav sections, compare/shortlist widgets, footer."""

    inject_css()
    inject_responsive_css()

    with st.sidebar:
        # ----------------------------------------------------------------
        # Brand
        # ----------------------------------------------------------------
        if _LOGO.exists():
            st.image(str(_LOGO), width=90)
            st.markdown(
                "<div class='sb-brand-tagline' style='text-align:center;"
                "margin-top:-4px;margin-bottom:12px;padding-bottom:12px;"
                "border-bottom:1px solid #30363D;'>Football Scouting Intelligence</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="sb-brand">
                    <div class="sb-brand-name">Schlouh Analytics</div>
                    <div class="sb-brand-tagline">Football Scouting Intelligence</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------------------
        # Overview
        # ----------------------------------------------------------------
        st.markdown("<span class='sb-nav-label'>Overview</span>", unsafe_allow_html=True)
        st.page_link("app.py", label="🏠  Home")

        # ----------------------------------------------------------------
        # Scouting
        # ----------------------------------------------------------------
        st.markdown("<span class='sb-nav-label'>Scouting</span>", unsafe_allow_html=True)
        st.page_link("pages/8_🔎_Discover.py", label="🔎  Find Players")
        st.page_link("pages/2_📋_Profile.py", label="📋  Player Profile")
        _compare_n = _get_compare_count()
        st.page_link(
            "pages/3_⚖️_Compare.py",
            label=f"⚖️  Compare ({_compare_n})" if _compare_n else "⚖️  Compare",
        )
        _short_n = _get_shortlist_count()
        st.page_link(
            "pages/4_🎯_Shortlist.py",
            label=f"🎯  Shortlist ({_short_n})" if _short_n else "🎯  Shortlist",
        )

        # ----------------------------------------------------------------
        # Teams & Tactics
        # ----------------------------------------------------------------
        st.markdown("<span class='sb-nav-label'>Teams & Tactics</span>", unsafe_allow_html=True)
        st.page_link("pages/6_🏆_Teams.py", label="🏆  Team Analysis")
        st.page_link("pages/9_🏟️_Team_Directory.py", label="🏟️  Team Directory")
        st.page_link("pages/10_📐_Tactical_Profile.py", label="📐  Tactical Profile")
        st.page_link("pages/11_⚔️_Opponent_Prep.py", label="⚔️  Opponent Prep")
        st.page_link("pages/12_📊_League_Trends.py", label="📊  League Trends")

        # ----------------------------------------------------------------
        # Data
        # ----------------------------------------------------------------
        st.markdown("<span class='sb-nav-label'>Data</span>", unsafe_allow_html=True)
        st.page_link("pages/5_📊_Explore.py", label="📊  Explore Data")

        # ----------------------------------------------------------------
        # Compare queue widget
        # ----------------------------------------------------------------
        st.markdown("<div class='sb-divider'></div>", unsafe_allow_html=True)
        if _compare_n:
            st.markdown(
                f"""
                <div class='sb-compare-widget'>
                    <div class='sb-compare-label'>Comparison Queue</div>
                    <div class='sb-compare-count'>{_compare_n}
                        <span style='font-size:0.78rem;font-weight:400;color:#8B949E;'> / 5 players</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Clear queue", key="_sidebar_clear_compare", use_container_width=True):
                try:
                    from dashboard.scouts.compare_state import save_scouts_compare_list
                    save_scouts_compare_list([])
                except Exception:
                    pass
                st.rerun()
        else:
            st.markdown(
                "<div style='font-size:0.75rem;color:#8B949E;padding:0.3rem 0.2rem;'>"
                "No players in queue — add from Find Players.</div>",
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------------------
        # Metric definitions (on every page)
        # ----------------------------------------------------------------
        with st.expander("ℹ️ Metric Definitions"):
            for abbr, tip in STAT_TOOLTIPS.items():
                st.markdown(f"**{abbr}** — {tip}")

        # ----------------------------------------------------------------
        # Footer — portfolio-ready
        # ----------------------------------------------------------------
        st.markdown(
            """
            <div class="sb-footer">
                Schlouh Analytics · Football Intelligence<br>
                Data from SofaScore
            </div>
            """,
            unsafe_allow_html=True,
        )
