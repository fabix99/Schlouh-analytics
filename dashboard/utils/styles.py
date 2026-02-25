"""Shared design system for Schlouh Analytics dashboard.

Single source of truth for all CSS.  Import and call ``inject_css()`` at the
top of every page (or rely on ``render_sidebar()`` which calls it for you).

Design tokens
-------------
Background:  #0D1117 (main)  |  #161B22 (surface/card)  |  #1C2128 (elevated)
Border:      #30363D (default)  |  rgba(201,168,64,0.35) (accent hover)
Brand gold:  #C9A840  (primary accent — Schlouh Football brand colour)
Text:        #F0F6FC (primary)  |  #8B949E (muted)  |  #C9D1D9 (secondary)
Status:      #6BCB77 (success)  |  #FFD93D (warning)  |  #FF6B6B (danger)  |  #4D96FF (info)
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Python-side token dict (use in chart builders / inline styles)
# ---------------------------------------------------------------------------
TOKENS = {
    "bg_main":        "#0D1117",
    "bg_surface":     "#161B22",
    "bg_elevated":    "#1C2128",
    "border":         "#30363D",
    "accent":         "#C9A840",          # Schlouh Football brand gold
    "accent_dim":     "rgba(201,168,64,0.1)",
    "accent_border":  "rgba(201,168,64,0.35)",
    "text_primary":   "#F0F6FC",
    "text_secondary": "#C9D1D9",
    "text_muted":     "#8B949E",
    "success":        "#6BCB77",
    "warning":        "#FFD93D",
    "danger":         "#FF6B6B",
    "info":           "#4D96FF",
    # Plotly chart helpers
    "chart_bg":       "#0D1117",
    "chart_grid":     "#30363D",
    "chart_text":     "#E6EDF3",
}

# Shared Plotly layout for tactics dark theme (improvement #90)
PLOTLY_LAYOUT_TACTICS = {
    "paper_bgcolor": "#0D1117",
    "plot_bgcolor": "#0D1117",
    "font": {"color": "#E6EDF3", "size": 11},
    "xaxis": {"gridcolor": "#30363D", "zerolinecolor": "#30363D"},
    "yaxis": {"gridcolor": "#30363D", "zerolinecolor": "#30363D"},
    "margin": {"l": 44, "r": 44, "t": 40, "b": 40},
    "legend": {"font": {"color": "#E6EDF3"}, "orientation": "h", "yanchor": "bottom", "y": -0.2, "xanchor": "center", "x": 0.5},
}

# ---------------------------------------------------------------------------
# Master CSS block
# ---------------------------------------------------------------------------
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=DM+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&display=swap');

/* ============================================================
   SCHLOUH FOOTBALL — SHARED DESIGN SYSTEM
   Brand: Black (#0D1117) + Gold (#C9A840)
   ============================================================ */

/* ----- GLOBAL / TYPOGRAPHY ----- */
html, body, [class*="css"] {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI',
                 system-ui, sans-serif !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

/* ----- LAYOUT ----- */
.block-container {
    padding-top: 1.6rem !important;
    padding-bottom: 2rem !important;
    max-width: 1440px;
}

/* KPI row accent (gold line under first metric row) */
.kpi-accent {
    height: 3px;
    background: linear-gradient(90deg, transparent 0%, rgba(201,168,64,0.15) 15%, #C9A840 50%, rgba(201,168,64,0.15) 85%, transparent 100%);
    margin: 0.25rem 0 1.25rem 0;
    border-radius: 2px;
    max-width: 100%;
}

/* ============================================================
   SIDEBAR
   ============================================================ */
[data-testid="stSidebar"] {
    background: #0D1117 !important;
    border-right: 1px solid #30363D !important;
}
[data-testid="stSidebarContent"] {
    background: #0D1117 !important;
    padding-top: 0.4rem !important;
}

/* Sidebar branding block */
.sb-brand {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.6rem 0.4rem 0.9rem;
    border-bottom: 1px solid #30363D;
    margin-bottom: 0.4rem;
    text-align: center;
}
[data-testid="stSidebar"] [data-testid="stImage"] {
    display: flex !important;
    justify-content: center !important;
    border-radius: 8px;
    box-shadow: 0 0 0 1px rgba(201,168,64,0.2);
}
.sb-brand-name {
    font-size: 0.88rem;
    font-weight: 700;
    color: #C9A840;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 4px;
    line-height: 1.2;
}
.sb-brand-tagline {
    font-size: 0.63rem;
    color: #8B949E;
    letter-spacing: 0.04em;
    margin-top: 2px;
}

/* Sidebar nav group labels */
.sb-nav-label {
    font-size: 0.63rem;
    font-weight: 600;
    color: #8B949E;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    padding: 0.7rem 0.3rem 0.2rem;
    display: block;
}

/* Sidebar divider */
.sb-divider {
    height: 1px;
    background: #30363D;
    margin: 0.6rem 0;
}

/* Sidebar compare widget */
.sb-compare-widget {
    background: rgba(201,168,64,0.07);
    border: 1px solid rgba(201,168,64,0.22);
    border-radius: 8px;
    padding: 0.6rem 0.8rem;
    margin: 0.4rem 0;
}
.sb-compare-label {
    font-size: 0.65rem;
    color: #8B949E;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.sb-compare-count {
    font-size: 1.15rem;
    font-weight: 700;
    color: #C9A840;
    margin-top: 2px;
}

/* Sidebar page links */
[data-testid="stSidebar"] [data-testid="stPageLink"] {
    border-radius: 6px !important;
    margin: 1px 0 !important;
    transition: background 0.2s ease, color 0.2s ease !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"]:hover {
    background: rgba(201,168,64,0.06) !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"] p,
[data-testid="stSidebar"] [data-testid="stPageLink"] span {
    font-size: 0.87rem !important;
    color: #C9D1D9 !important;
    font-weight: 400 !important;
}
[data-testid="stSidebar"] [data-testid="stPageLink"]:hover p,
[data-testid="stSidebar"] [data-testid="stPageLink"]:hover span {
    color: #C9A840 !important;
}

/* Sidebar footer */
.sb-footer {
    margin-top: 2rem;
    padding-top: 0.8rem;
    border-top: 1px solid #30363D;
    font-size: 0.67rem;
    color: #8B949E;
    line-height: 1.5;
    text-align: center;
}

/* ============================================================
   METRIC CONTAINERS
   ============================================================ */
[data-testid="metric-container"] {
    background: #161B22 !important;
    border: 1px solid #30363D !important;
    border-radius: 10px !important;
    padding: 0.9rem 1.1rem !important;
    transition: border-color 0.22s ease, box-shadow 0.22s ease;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
[data-testid="metric-container"]:hover {
    border-color: rgba(201,168,64,0.4) !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.35), 0 0 0 1px rgba(201,168,64,0.08);
}
[data-testid="stMetricValue"] {
    font-size: 1.7rem !important;
    font-weight: 700 !important;
    color: #F0F6FC !important;
    letter-spacing: -0.02em !important;
    font-variant-numeric: tabular-nums;
}
[data-testid="stMetricLabel"] {
    font-size: 0.73rem !important;
    font-weight: 600 !important;
    color: #8B949E !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
}

/* ============================================================
   PAGE HERO
   ============================================================ */
.page-hero {
    margin-bottom: 1.6rem;
    padding: 1.25rem 1rem 1.35rem;
    border-bottom: 1px solid #30363D;
    background: linear-gradient(180deg, rgba(201,168,64,0.03) 0%, transparent 60%);
    border-radius: 0 0 12px 12px;
}
.page-hero-title {
    font-family: 'Oswald', sans-serif !important;
    font-size: 1.95rem;
    font-weight: 700;
    color: #F0F6FC;
    margin: 0 0 0.35rem;
    letter-spacing: 0.02em;
    line-height: 1.2;
    text-transform: uppercase;
}
.page-hero-sub {
    color: #8B949E;
    margin: 0;
    font-size: 0.93rem;
    line-height: 1.55;
}

/* ============================================================
   SECTION HEADERS
   ============================================================ */
.section-header {
    font-family: 'Oswald', sans-serif !important;
    font-size: 0.8rem;
    font-weight: 600;
    color: #C9A840;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 1.5rem 0 0.65rem;
    padding-bottom: 0.45rem;
    border-bottom: 1px solid #30363D;
}

/* ============================================================
   CARDS & INFO BLOCKS
   ============================================================ */
.info-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.45rem;
    transition: border-color 0.22s ease, box-shadow 0.22s ease;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
.info-card:hover {
    border-color: rgba(201,168,64,0.35);
    box-shadow: 0 4px 12px rgba(0,0,0,0.28);
}

.narrative-box {
    background: #161B22;
    border: 1px solid #30363D;
    border-left: 3px solid #C9A840;
    border-radius: 0 8px 8px 0;
    padding: 0.95rem 1.15rem;
    color: #C9D1D9;
    font-size: 0.9rem;
    line-height: 1.75;
    margin-bottom: 0.8rem;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}

/* ============================================================
   FILTER BLOCK
   ============================================================ */
.filter-block-label {
    font-size: 0.68rem;
    font-weight: 600;
    color: #8B949E;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.6rem;
    padding: 0.1rem 0;
}

/* ============================================================
   PILLS / CHIPS / BADGES
   ============================================================ */
.pill {
    display: inline-block;
    background: rgba(201,168,64,0.1);
    border: 1px solid rgba(201,168,64,0.35);
    border-radius: 20px;
    padding: 3px 11px;
    font-size: 0.78rem;
    margin: 3px;
    color: #C9A840;
    font-weight: 500;
}
.strength-pill {
    display: inline-block;
    background: rgba(201,168,64,0.1);
    border: 1px solid rgba(201,168,64,0.35);
    border-radius: 20px;
    padding: 3px 11px;
    font-size: 0.8rem;
    margin: 3px;
    color: #C9A840;
    font-weight: 500;
}
.strength-chip {
    display: inline-block;
    background: rgba(201,168,64,0.1);
    border: 1px solid rgba(201,168,64,0.35);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.82rem;
    margin: 3px;
    color: #C9A840;
    font-weight: 500;
}
.weakness-chip {
    display: inline-block;
    background: rgba(255,107,107,0.1);
    border: 1px solid rgba(255,107,107,0.3);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.82rem;
    margin: 3px;
    color: #FF6B6B;
    font-weight: 500;
}
.tag-pill {
    display: inline-block;
    background: rgba(77,150,255,0.1);
    border: 1px solid rgba(77,150,255,0.3);
    border-radius: 20px;
    padding: 3px 10px;
    font-size: 0.8rem;
    margin: 3px;
    color: #4D96FF;
    font-weight: 500;
}
.consistency-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-left: 8px;
}

/* Result badges */
.result-w {
    display: inline-block;
    background: rgba(201,168,64,0.15);
    border: 1px solid rgba(201,168,64,0.4);
    border-radius: 6px;
    padding: 3px 9px;
    color: #C9A840;
    font-weight: 700;
    margin: 2px;
    font-size: 0.85rem;
}
.result-d {
    display: inline-block;
    background: rgba(255,217,61,0.15);
    border: 1px solid rgba(255,217,61,0.4);
    border-radius: 6px;
    padding: 3px 9px;
    color: #FFD93D;
    font-weight: 700;
    margin: 2px;
    font-size: 0.85rem;
}
.result-l {
    display: inline-block;
    background: rgba(255,107,107,0.15);
    border: 1px solid rgba(255,107,107,0.4);
    border-radius: 6px;
    padding: 3px 9px;
    color: #FF6B6B;
    font-weight: 700;
    margin: 2px;
    font-size: 0.85rem;
}

/* ============================================================
   PLAYER / TEAM CARDS
   ============================================================ */
.sim-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 8px;
    padding: 0.7rem;
    text-align: center;
    margin-bottom: 0.4rem;
    transition: border-color 0.22s ease, box-shadow 0.22s ease;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
.sim-card:hover {
    border-color: rgba(201,168,64,0.35);
    box-shadow: 0 4px 10px rgba(0,0,0,0.28);
}

.xi-card {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 8px;
    padding: 0.65rem;
    text-align: center;
    margin-bottom: 0.4rem;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}

.player-header {
    text-align: center;
    padding: 0.8rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
}

/* ============================================================
   TABS
   ============================================================ */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 1px solid #30363D;
    gap: 2px;
}
[data-testid="stTabs"] [role="tab"] {
    color: #8B949E !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
    padding: 0.45rem 0.85rem !important;
    border-radius: 6px 6px 0 0 !important;
    border: 1px solid transparent !important;
    border-bottom: none !important;
    transition: color 0.15s, background 0.15s;
    background: transparent !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
    color: #F0F6FC !important;
    background: rgba(255,255,255,0.04) !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #C9A840 !important;
    background: #161B22 !important;
    border-color: #30363D !important;
    border-bottom-color: #161B22 !important;
}

/* ============================================================
   EXPANDERS
   ============================================================ */
[data-testid="stExpander"] {
    border: 1px solid #30363D !important;
    border-radius: 8px !important;
    background: #161B22 !important;
    margin-bottom: 0.5rem !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.2) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 500 !important;
    color: #C9D1D9 !important;
    font-size: 0.88rem !important;
}
[data-testid="stExpander"] summary:hover {
    color: #F0F6FC !important;
}

/* ============================================================
   BUTTONS
   ============================================================ */
[data-testid="stButton"] > button {
    border: 1px solid #30363D !important;
    background: #161B22 !important;
    color: #C9D1D9 !important;
    border-radius: 6px !important;
    font-size: 0.84rem !important;
    font-weight: 500 !important;
    transition: border-color 0.22s ease, color 0.22s ease, background 0.22s ease !important;
    padding: 0.35rem 0.75rem !important;
}
[data-testid="stButton"] > button:hover {
    border-color: #C9A840 !important;
    color: #C9A840 !important;
    background: rgba(201,168,64,0.07) !important;
}
[data-testid="stButton"] > button[kind="primary"] {
    background: #C9A840 !important;
    border-color: #C9A840 !important;
    color: #0D1117 !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #b89530 !important;
    border-color: #b89530 !important;
    color: #0D1117 !important;
}

/* ============================================================
   PAGE LINKS (nav shortcuts)
   ============================================================ */
[data-testid="stPageLink"] {
    border: 1px solid #30363D !important;
    border-radius: 8px !important;
    background: #161B22 !important;
    transition: all 0.15s !important;
    padding: 0.05rem !important;
}
[data-testid="stPageLink"]:hover {
    border-color: rgba(201,168,64,0.4) !important;
    background: rgba(201,168,64,0.05) !important;
}
[data-testid="stPageLink"] p,
[data-testid="stPageLink"] span {
    color: #C9D1D9 !important;
    font-size: 0.84rem !important;
}

/* ============================================================
   FORM WIDGETS
   ============================================================ */
[data-testid="stSelectbox"] > div > div,
[data-testid="stMultiSelect"] > div > div > div {
    border-color: #30363D !important;
    background: #161B22 !important;
    border-radius: 6px !important;
}
[data-baseweb="input"] input,
[data-testid="stNumberInput"] input {
    border-color: #30363D !important;
    background: #161B22 !important;
    border-radius: 6px !important;
    color: #F0F6FC !important;
}
[data-baseweb="select"] > div {
    border-color: #30363D !important;
    background: #161B22 !important;
}

/* ============================================================
   DATA TABLES
   ============================================================ */
[data-testid="stDataFrame"] {
    border: 1px solid #30363D;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.22);
}
[data-testid="stDataFrame"] > div {
    border: none !important;
}
[data-testid="stDataFrame"] table thead th {
    background: #161B22 !important;
    color: #C9A840 !important;
    font-weight: 600 !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    border-bottom: 2px solid #30363D !important;
    padding: 0.6rem 0.75rem !important;
}
[data-testid="stDataFrame"] table tbody tr:nth-child(even) {
    background: #1C2128 !important;
}
[data-testid="stDataFrame"] table tbody tr:nth-child(odd) {
    background: #161B22 !important;
}
[data-testid="stDataFrame"] table tbody tr:hover {
    background: rgba(201,168,64,0.06) !important;
}
[data-testid="stDataFrame"] table td {
    padding: 0.5rem 0.75rem !important;
    border-bottom: 1px solid #30363D !important;
    color: #F0F6FC !important;
}

/* ============================================================
   ALERTS / CALLOUTS
   ============================================================ */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border-width: 1px !important;
}
[data-testid="stInfo"] {
    background: rgba(77,150,255,0.08) !important;
    border-color: rgba(77,150,255,0.3) !important;
    color: #C9D1D9 !important;
}
[data-testid="stWarning"] {
    background: rgba(255,217,61,0.08) !important;
    border-color: rgba(255,217,61,0.3) !important;
    color: #C9D1D9 !important;
}
[data-testid="stSuccess"] {
    background: rgba(107,203,119,0.08) !important;
    border-color: rgba(107,203,119,0.3) !important;
    color: #C9D1D9 !important;
}

/* ============================================================
   CHART CONTAINERS (Plotly)
   ============================================================ */
.stPlotlyChart,
[data-testid="stPlotlyChart"] {
    border-radius: 10px !important;
    overflow: hidden !important;
    border: 1px solid #30363D !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.25) !important;
}
.stPlotlyChart iframe,
[data-testid="stPlotlyChart"] iframe {
    border-radius: 10px !important;
}

/* ============================================================
   FOCUS STATES (accessibility)
   ============================================================ */
[data-testid="stButton"] > button:focus-visible,
[data-testid="stPageLink"]:focus-visible,
[data-baseweb="input"] input:focus-visible,
[data-testid="stSelectbox"]:focus-within {
    outline: 2px solid #C9A840 !important;
    outline-offset: 2px !important;
}

/* ============================================================
   HORIZONTAL RULE
   ============================================================ */
hr {
    border-color: #30363D !important;
    margin: 1.2rem 0 !important;
}

/* ============================================================
   STREAMLIT CHROME — HIDE DEFAULT ELEMENTS
   ============================================================ */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }

/* ============================================================
   SCROLLBAR
   ============================================================ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0D1117; }
::-webkit-scrollbar-thumb { background: #30363D; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(201,168,64,0.4); }

/* ============================================================
   TOAST
   ============================================================ */
[data-testid="stToast"] {
    background: #1C2128 !important;
    border: 1px solid #30363D !important;
    border-radius: 8px !important;
    color: #F0F6FC !important;
}
</style>
"""


def inject_css() -> None:
    """Inject the shared Schlouh Analytics design system CSS and accessibility enhancements."""
    st.markdown(_CSS, unsafe_allow_html=True)
    try:
        from dashboard.utils.accessibility import inject_accessibility_css
        inject_accessibility_css()
    except Exception:
        pass
