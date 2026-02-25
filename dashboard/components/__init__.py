"""Dashboard Components Library.

A centralized collection of reusable UI components for all dashboards.
This library provides consistent, accessible, and well-tested components.

Usage:
    from dashboard.components import FilterPanel, SearchInput, PlayerCard

Structure:
    filters.py      - Filter components (FilterState, debouncing, badges)
    search.py       - Search components (debounced search, recent searches)
    player_cards.py - Player display components
    charts.py       - Chart/visualization components
    forms.py        - Form input components
    feedback.py     - Loading states, empty states, error states
    layout.py       - Layout helpers and containers
"""

# Filter Components (from Phase 1 Sprint 1.1)
from dashboard.utils.filter_components import (
    FilterState,
    filter_loading_state,
    show_filter_loading_indicator,
    EnhancedFilterConfig,
    count_active_filters,
    render_filter_badge,
    get_filter_summary_text,
    FilterDefaults,
    render_clear_all_button,
    render_clear_filters_section,
    filter_with_clear,
    multiselect_with_clear,
    slider_with_clear,
    number_input_with_clear,
    CascadingFilterConfig,
    handle_cascading_filter,
    render_cascading_indicator,
    create_league_dependent_selector,
    get_available_positions_for_league,
    get_available_teams_for_league,
    precision_slider,
    rating_slider_with_context,
    FilterConflict,
    analyze_filter_conflicts,
    find_relaxed_matches,
    render_no_results_state,
    EnhancedFilterPanel,
)

# Search Components (from Phase 1 Sprint 1.2)
from dashboard.utils.search_components import (
    SearchDebouncer,
    SearchState,
    get_recent_searches,
    add_to_search_history,
    render_recent_searches_pills,
    render_recent_searches_dropdown,
    clear_search_history,
    render_search_loading_skeleton,
    render_search_results_header,
    search_with_disambiguation,
    DisambiguatedPlayer,
    render_disambiguated_result,
    handle_common_name_search,
    COMMON_NAMES,
    get_trending_searches,
    get_search_suggestions,
    render_empty_search_state,
    EnhancedSearch,
)

# Re-export base filter panel for backward compatibility
from dashboard.utils.filters import FilterPanel

__all__ = [
    # Filter Components
    "FilterState",
    "filter_loading_state",
    "show_filter_loading_indicator",
    "EnhancedFilterConfig",
    "count_active_filters",
    "render_filter_badge",
    "get_filter_summary_text",
    "FilterDefaults",
    "render_clear_all_button",
    "render_clear_filters_section",
    "filter_with_clear",
    "multiselect_with_clear",
    "slider_with_clear",
    "number_input_with_clear",
    "CascadingFilterConfig",
    "handle_cascading_filter",
    "render_cascading_indicator",
    "create_league_dependent_selector",
    "get_available_positions_for_league",
    "get_available_teams_for_league",
    "precision_slider",
    "rating_slider_with_context",
    "FilterConflict",
    "analyze_filter_conflicts",
    "find_relaxed_matches",
    "render_no_results_state",
    "EnhancedFilterPanel",
    "FilterPanel",

    # Search Components
    "SearchDebouncer",
    "SearchState",
    "get_recent_searches",
    "add_to_search_history",
    "render_recent_searches_pills",
    "render_recent_searches_dropdown",
    "clear_search_history",
    "render_search_loading_skeleton",
    "render_search_results_header",
    "search_with_disambiguation",
    "DisambiguatedPlayer",
    "render_disambiguated_result",
    "handle_common_name_search",
    "COMMON_NAMES",
    "get_trending_searches",
    "get_search_suggestions",
    "render_empty_search_state",
    "EnhancedSearch",
]
