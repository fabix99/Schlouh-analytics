"""Dashboard utilities package.

This package provides shared utilities for all dashboard applications including:
- Data loading and processing
- Chart generation
- Reusable UI components
- Filter management
- Styling and theming
"""

# Data utilities
from dashboard.utils.data import (
    load_enriched_season_stats,
    load_rolling_form,
    load_player_consistency,
    load_scouting_profiles,
    get_similar_players,
    get_player_match_log,
    load_career_stats,
    get_league_avg_stats,
    get_filtered_teams_tactics,
    get_team_wdl,
    get_team_form,
)

# Chart utilities
from dashboard.utils.charts import (
    rating_trend,
    xg_trend,
)

# Type definitions
from dashboard.utils.types import (
    FilterConfig,
)

# Filter utilities (base)
from dashboard.utils.filters import (
    create_league_selector,
    create_season_selector,
    create_position_selector,
    create_age_band_selector,
    create_min_minutes_input,
    create_team_selector,
    apply_filters,
    display_filter_summary,
    FilterPanel,
)

# Enhanced filter components (Phase 1 UX improvements)
from dashboard.utils.filter_components import (
    # Filter State & Debouncing
    FilterState,

    # Loading States
    filter_loading_state,
    show_filter_loading_indicator,

    # Filter Badges
    FilterConfig as EnhancedFilterConfig,
    count_active_filters,
    render_filter_badge,
    get_filter_summary_text,

    # Clear All Functionality
    FilterDefaults,
    render_clear_all_button,
    render_clear_filters_section,

    # Individual Reset Buttons
    filter_with_clear,
    multiselect_with_clear,
    slider_with_clear,
    number_input_with_clear,

    # Cascading Filters
    CascadingFilterConfig,
    handle_cascading_filter,
    render_cascading_indicator,
    create_league_dependent_selector,
    get_available_positions_for_league,
    get_available_teams_for_league,

    # Precision Sliders
    precision_slider,
    rating_slider_with_context,

    # No Results State
    FilterConflict,
    analyze_filter_conflicts,
    find_relaxed_matches,
    render_no_results_state,

    # Composite Panel
    EnhancedFilterPanel,
)

# UI Components
from dashboard.utils.components import (
    player_header_card,
    metrics_row,
    season_kpis,
    league_benchmark_badge,
    strength_pills,
    consistency_badge,
    form_metrics_row,
    big_game_metrics,
    progression_deltas,
    stat_columns,
    goalkeeper_card,
    career_overview_card,
    similar_players_cards,
    player_match_log,
    export_player_brief,
)

# Constants
from dashboard.utils.constants import (
    COMP_NAMES,
    COMP_FLAGS,
    POSITION_NAMES,
    POSITION_ORDER,
    PLAYER_COLORS,
    TOP_5_LEAGUES,
    AGE_BANDS,
    MIN_MINUTES_DEFAULT,
)

# Badges
from dashboard.utils.badges import (
    calculate_badges,
    get_badge_summary,
    format_badge_for_display,
)

# Monitoring and Error Tracking (Sprint 1.3)
from dashboard.utils.monitoring import (
    init_sentry,
    set_sentry_user,
    set_sentry_tag,
    capture_exception,
    capture_message,
    timing_decorator,
    monitor_performance,
    PerformanceMonitor,
    get_performance_monitor,
    log_slow_operations,
    DashboardErrorHandler,
    get_error_handler,
    safe_execute,
    run_health_checks,
    render_health_status,
)

# Search components (Sprint 1.2)
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

# Responsive Design (Sprint 3.1)
from dashboard.utils.responsive_styles import (
    inject_responsive_css,
    is_mobile,
    get_viewport_width,
    responsive_columns,
    mobile_friendly_button,
    render_mobile_nav_bar,
)

# Accessibility (Sprint 3.2)
from dashboard.utils.accessibility import (
    announce_to_screen_reader,
    add_aria_label,
    check_contrast_ratio,
    get_accessible_colors,
    inject_accessibility_css,
    render_accessibility_toolbar,
    validate_accessibility,
)

# Advanced Analytics (Sprint 4.1-4.2)
from dashboard.utils.advanced_analytics import (
    CorrelationAnalyzer,
    SimilarityEngine,
    PatternRecognizer,
    CorrelationResult,
    render_correlation_insights,
    calculate_predictive_metrics,
)

__all__ = [
    # Data
    "load_enriched_season_stats",
    "load_rolling_form",
    "load_player_consistency",
    "load_scouting_profiles",
    "get_similar_players",
    "get_player_match_log",
    "load_career_stats",
    "get_league_avg_stats",
    "get_filtered_teams_tactics",
    "get_team_wdl",
    "get_team_form",

    # Charts
    "rating_trend",
    "xg_trend",

    # Types
    "FilterConfig",

    # Base Filters
    "create_league_selector",
    "create_season_selector",
    "create_position_selector",
    "create_age_band_selector",
    "create_min_minutes_input",
    "create_team_selector",
    "apply_filters",
    "display_filter_summary",
    "FilterPanel",

    # Enhanced Filter Components
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

    # UI Components
    "player_header_card",
    "metrics_row",
    "season_kpis",
    "league_benchmark_badge",
    "strength_pills",
    "consistency_badge",
    "form_metrics_row",
    "big_game_metrics",
    "progression_deltas",
    "stat_columns",
    "goalkeeper_card",
    "career_overview_card",
    "similar_players_cards",
    "player_match_log",
    "export_player_brief",

    # Constants
    "COMP_NAMES",
    "COMP_FLAGS",
    "POSITION_NAMES",
    "POSITION_ORDER",
    "PLAYER_COLORS",
    "TOP_5_LEAGUES",
    "AGE_BANDS",
    "MIN_MINUTES_DEFAULT",

    # Badges
    "calculate_badges",
    "get_badge_summary",
    "format_badge_for_display",

    # Monitoring and Error Tracking
    "init_sentry",
    "set_sentry_user",
    "set_sentry_tag",
    "capture_exception",
    "capture_message",
    "timing_decorator",
    "monitor_performance",
    "PerformanceMonitor",
    "get_performance_monitor",
    "log_slow_operations",
    "DashboardErrorHandler",
    "get_error_handler",
    "safe_execute",
    "run_health_checks",
    "render_health_status",

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

    # Responsive Design
    "inject_responsive_css",
    "is_mobile",
    "get_viewport_width",
    "responsive_columns",
    "mobile_friendly_button",
    "render_mobile_nav_bar",

    # Accessibility
    "announce_to_screen_reader",
    "add_aria_label",
    "check_contrast_ratio",
    "get_accessible_colors",
    "inject_accessibility_css",
    "render_accessibility_toolbar",
    "validate_accessibility",

    # Advanced Analytics
    "CorrelationAnalyzer",
    "SimilarityEngine",
    "PatternRecognizer",
    "CorrelationResult",
    "render_correlation_insights",
    "calculate_predictive_metrics",
]
