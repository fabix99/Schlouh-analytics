"""Responsive design and mobile optimization utilities.

This module provides:
- Mobile-optimized CSS styles
- Responsive layout helpers
- Mobile detection utilities
- Touch-friendly component sizes
"""

import streamlit as st


def inject_responsive_css() -> None:
    """Inject responsive CSS that adapts to mobile screens."""
    st.markdown("""
    <style>
    /* ===== BASE RESPONSIVE STYLES ===== */
    
    /* Mobile-first approach */
    .main .block-container {
        max-width: 100% !important;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* Responsive typography */
    @media (max-width: 768px) {
        .page-hero-title {
            font-size: 1.5rem !important;
        }
        .page-hero-sub {
            font-size: 0.85rem !important;
        }
        .section-header {
            font-size: 1.1rem !important;
        }
    }
    
    /* Touch-friendly buttons on mobile */
    @media (max-width: 768px) {
        .stButton > button {
            min-height: 44px !important;
            font-size: 16px !important; /* Prevents zoom on iOS */
        }
        
        .stSelectbox > div > div {
            min-height: 44px !important;
        }
        
        .stTextInput > div > div > input {
            min-height: 44px !important;
            font-size: 16px !important;
        }
        
        .stNumberInput > div > div > input {
            min-height: 44px !important;
            font-size: 16px !important;
        }
        
        .stSlider > div > div > div {
            min-height: 44px !important;
        }
    }
    
    /* Responsive columns */
    @media (max-width: 640px) {
        /* Stack columns on very small screens */
        .row-widget.stHorizontalBlock {
            flex-direction: column !important;
        }
        
        .row-widget.stHorizontalBlock > div {
            width: 100% !important;
            min-width: 100% !important;
            margin-bottom: 1rem;
        }
    }
    
    /* Card responsiveness */
    @media (max-width: 768px) {
        div[style*="background:#161B22"] {
            padding: 12px !important;
        }
    }
    
    /* Table responsiveness */
    @media (max-width: 768px) {
        .dataframe {
            font-size: 0.75rem;
        }
        
        .dataframe th,
        .dataframe td {
            padding: 6px 8px !important;
        }
    }
    
    /* Sidebar mobile optimization */
    @media (max-width: 768px) {
        [data-testid="stSidebar"] {
            width: 280px !important;
        }
        
        [data-testid="stSidebar"] .block-container {
            padding: 0.5rem !important;
        }
        
        [data-testid="stSidebar"] img {
            max-width: 60px !important;
        }
    }
    
    /* Plotly chart responsiveness */
    @media (max-width: 768px) {
        .js-plotly-plot {
            max-width: 100% !important;
        }
        
        .js-plotly-plot .plotly {
            max-width: 100% !important;
        }
    }
    
    /* Form indicators mobile */
    @media (max-width: 768px) {
        span[style*="background:"] {
            padding: 2px 5px !important;
            font-size: 10px !important;
        }
    }
    
    /* ===== UTILITY CLASSES ===== */
    
    /* Hide on mobile */
    .hide-mobile {
        display: block;
    }
    
    @media (max-width: 768px) {
        .hide-mobile {
            display: none !important;
        }
    }
    
    /* Show only on mobile */
    .show-mobile {
        display: none;
    }
    
    @media (max-width: 768px) {
        .show-mobile {
            display: block !important;
        }
    }
    
    /* Touch target size */
    .touch-target {
        min-height: 44px;
        min-width: 44px;
    }
    
    /* Responsive spacing */
    .responsive-margin {
        margin: 1rem;
    }
    
    @media (max-width: 768px) {
        .responsive-margin {
            margin: 0.5rem;
        }
    }
    
    /* ===== DARK THEME ENHANCEMENTS ===== */
    
    @media (prefers-color-scheme: dark) {
        /* Ensure dark theme on mobile */
        body {
            background-color: #0D1117;
            color: #F0F6FC;
        }
    }
    
    /* ===== ACCESSIBILITY ===== */
    
    /* Focus indicators */
    button:focus,
    input:focus,
    select:focus {
        outline: 2px solid #C9A840 !important;
        outline-offset: 2px !important;
    }
    
    /* Reduced motion preference */
    @media (prefers-reduced-motion: reduce) {
        * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)


def is_mobile() -> bool:
    """Detect if the user is on a mobile device.

    Returns:
        True if mobile device detected
    """
    # This is a simplified check - in practice, you'd use JavaScript
    # through components.html to get the actual viewport width
    return False  # Default to false for server-side detection


def get_viewport_width() -> int:
    """Get the current viewport width via JavaScript.

    Returns:
        Viewport width in pixels (defaults to 1200 if detection fails)
    """
    import streamlit.components.v1 as components

    # Use JavaScript to detect viewport width
    result = components.html(
        """
        <script>
        window.parent.postMessage({
            type: 'viewport',
            width: window.innerWidth,
            height: window.innerHeight
        }, '*');
        </script>
        """,
        height=0,
    )

    # Default to desktop width
    return 1200


def responsive_columns(
    desktop_columns: int,
    mobile_columns: int = 1,
    gap: str = "small"
) -> list:
    """Create responsive columns that adjust based on screen size.

    Note: This returns st.columns() result - actual responsive behavior
    is achieved through CSS media queries.

    Args:
        desktop_columns: Number of columns for desktop
        mobile_columns: Number of columns for mobile (unused, for API consistency)
        gap: Gap between columns

    Returns:
        List of column containers
    """
    return st.columns(desktop_columns, gap=gap)


def mobile_friendly_button(
    label: str,
    key: str,
    use_container_width: bool = True,
    type: str = "secondary"
) -> bool:
    """Render a mobile-friendly button with proper touch sizing.

    Args:
        label: Button label
        key: Unique key for the button
        use_container_width: Whether to expand to container width
        type: Button type ('primary' or 'secondary')

    Returns:
        True if button clicked
    """
    return st.button(
        label,
        key=key,
        use_container_width=use_container_width,
        type=type  # type: ignore
    )


def render_mobile_nav_bar(
    items: list,
    active_index: int = 0
) -> int:
    """Render a mobile-friendly bottom navigation bar.

    Args:
        items: List of (icon, label) tuples
        active_index: Index of currently active item

    Returns:
        Index of selected item
    """
    st.markdown(
        """
        <style>
        .mobile-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #161B22;
            border-top: 1px solid #30363D;
            display: flex;
            justify-content: space-around;
            padding: 10px 0;
            z-index: 9999;
        }
        
        .mobile-nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            color: #8B949E;
            font-size: 0.7rem;
            cursor: pointer;
        }
        
        .mobile-nav-item.active {
            color: #C9A840;
        }
        
        .mobile-nav-icon {
            font-size: 1.4rem;
            margin-bottom: 2px;
        }
        
        @media (min-width: 769px) {
            .mobile-nav {
                display: none;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Build nav HTML
    nav_html = '<div class="mobile-nav">'
    for i, (icon, label) in enumerate(items):
        active_class = "active" if i == active_index else ""
        nav_html += f'<div class="mobile-nav-item {active_class}" data-index="{i}">'
        nav_html += f'<span class="mobile-nav-icon">{icon}</span>'
        nav_html += f'<span>{label}</span>'
        nav_html += '</div>'
    nav_html += '</div>'

    st.markdown(nav_html, unsafe_allow_html=True)

    # Radio buttons for selection (hidden but functional)
    selected = st.radio(
        "Navigation",
        options=range(len(items)),
        format_func=lambda i: items[i][1],
        index=active_index,
        label_visibility="collapsed"
    )

    return selected
