"""Enhanced filter components with debouncing, loading states, and improved UX.

This module provides advanced filter UI components that address the critical
UX issues identified in the audit (Filter UX score: 4/10 → 8+/10).

Key Features:
- Debounced filter inputs (300ms)
- Loading spinners during filter updates
- Active filter count badges
- Clear all / individual reset buttons
- Cascading filter dependencies
- No results explanations
"""

import time
import contextlib
from typing import Optional, Callable, Any, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import streamlit as st


# =============================================================================
# FILTER STATE MANAGEMENT (TASK F1-001: Debouncing)
# =============================================================================

@dataclass
class FilterState:
    """Manages filter state with debouncing to prevent excessive re-renders.

    Usage:
        if 'filter_state' not in st.session_state:
            st.session_state.filter_state = FilterState()

        def on_filter_change():
            filter_state = st.session_state.filter_state
            if filter_state.should_apply('position', st.session_state.position_filter):
                apply_filters_with_loading()
    """

    last_change_time: float = field(default_factory=lambda: time.time() * 1000)
    pending_filters: Dict[str, Any] = field(default_factory=dict)
    debounce_ms: int = 300
    is_loading: bool = False
    last_applied_filters: Dict[str, Any] = field(default_factory=dict)

    def should_apply(self, filter_key: str, new_value: Any) -> bool:
        """Check if filter should be applied based on debounce timing.

        Returns True if enough time has passed since last change.
        """
        current_time = time.time() * 1000

        # Always apply if value hasn't changed
        if self.last_applied_filters.get(filter_key) == new_value:
            return False

        if current_time - self.last_change_time < self.debounce_ms:
            # Queue for later application
            self.pending_filters[filter_key] = new_value
            return False

        self.last_change_time = current_time
        self.pending_filters[filter_key] = new_value
        self.last_applied_filters[filter_key] = new_value
        return True

    def get_pending_filters(self) -> Dict[str, Any]:
        """Get all pending filters that haven't been applied yet."""
        return self.pending_filters.copy()

    def clear_pending(self) -> None:
        """Clear pending filters after they've been applied."""
        self.pending_filters = {}

    def set_loading(self, loading: bool) -> None:
        """Set the loading state."""
        self.is_loading = loading

    def reset_all(self) -> None:
        """Reset all filter tracking state."""
        self.last_change_time = time.time() * 1000
        self.pending_filters = {}
        self.last_applied_filters = {}
        self.is_loading = False


# =============================================================================
# LOADING STATE MANAGEMENT (TASK F1-002: Loading Spinners)
# =============================================================================

@contextlib.contextmanager
def filter_loading_state(message: str = "Updating results..."):
    """Context manager for showing loading state during filter operations.

    Usage:
        def apply_filters():
            with filter_loading_state():
                results = execute_filter_query()
                st.session_state.filtered_results = results
                time.sleep(0.1)  # Ensure spinner is visible briefly
    """
    placeholder = st.empty()
    try:
        with placeholder.container():
            with st.spinner(message):
                yield
    finally:
        placeholder.empty()


def show_filter_loading_indicator(key: str = "filter_loading"):
    """Show a persistent loading indicator in the sidebar or filter area.

    Usage:
        if st.session_state.get('filter_loading', False):
            show_filter_loading_indicator()
    """
    st.markdown("""
        <div style="
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: linear-gradient(135deg, #0068c9 0%, #0055a4 100%);
            border-radius: 6px;
            color: white;
            font-size: 13px;
            margin-bottom: 12px;
        ">
            <div style="
                width: 16px;
                height: 16px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            "></div>
            <span>Updating results...</span>
        </div>
        <style>
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        </style>
    """, unsafe_allow_html=True)


# =============================================================================
# FILTER BADGES AND COUNTERS (TASK F1-003: Active Filter Count Badge)
# =============================================================================

@dataclass
class FilterConfig:
    """Configuration for a single filter with its default value."""

    key: str
    label: str
    default_value: Any
    current_value: Any = None
    check_fn: Optional[Callable[[Any, Any], bool]] = None

    def is_active(self) -> bool:
        """Check if this filter is active (not at default value)."""
        if self.check_fn:
            return self.check_fn(self.current_value, self.default_value)
        return self.current_value != self.default_value


def count_active_filters(filter_configs: List[FilterConfig]) -> int:
    """Count number of non-default filter values.

    Args:
        filter_configs: List of FilterConfig objects representing all filters

    Returns:
        Number of filters that are not at their default values
    """
    return sum(1 for config in filter_configs if config.is_active())


def render_filter_badge(active_count: int, show_pulse: bool = True) -> None:
    """Render active filter count badge with attractive styling.

    Args:
        active_count: Number of active filters
        show_pulse: Whether to show pulse animation when filters are active
    """
    if active_count == 0:
        return

    pulse_animation = """
        <style>
        @keyframes pulse {
            0%, 100% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.05); opacity: 0.9; }
        }
        .filter-badge-pulse {
            animation: pulse 2s ease-in-out infinite;
        }
        </style>
    """ if show_pulse else ""

    badge_html = f"""
    {pulse_animation}
    <div class="{'filter-badge-pulse' if show_pulse else ''}" style="
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: linear-gradient(135deg, #0068c9 0%, #00D4AA 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,104,201,0.3);
    ">
        <span>🔍</span>
        <span>{active_count} filter{'s' if active_count > 1 else ''} active</span>
    </div>
    """
    st.markdown(badge_html, unsafe_allow_html=True)


def get_filter_summary_text(filter_configs: List[FilterConfig]) -> str:
    """Generate human-readable text describing active filters.

    Returns:
        Comma-separated string of active filter names
    """
    active = [cfg.label for cfg in filter_configs if cfg.is_active()]
    if not active:
        return "No active filters"
    return f"Active: {', '.join(active)}"


# =============================================================================
# CLEAR ALL BUTTON (TASK F1-004: Clear All Filters)
# =============================================================================

@dataclass
class FilterDefaults:
    """Container for default filter values."""

    values: Dict[str, Any]

    def reset_session_state(self) -> None:
        """Reset all filter values in session state to defaults."""
        for key, default_value in self.values.items():
            if key in st.session_state:
                st.session_state[key] = default_value

    def get_keys(self) -> List[str]:
        """Get all filter keys."""
        return list(self.values.keys())


def render_clear_all_button(
    filter_defaults: FilterDefaults,
    on_clear: Optional[Callable] = None,
    key_prefix: str = "clear_all"
) -> bool:
    """Render "Clear All" button that resets all filters to defaults.

    Args:
        filter_defaults: FilterDefaults object containing default values
        on_clear: Optional callback to run after clearing filters
        key_prefix: Prefix for the button key

    Returns:
        True if button was clicked and filters were cleared
    """
    clicked = st.button(
        "🗑️ Clear All Filters",
        key=f"{key_prefix}_filters",
        help="Reset all filters to default values",
        use_container_width=True,
        type="secondary"
    )

    if clicked:
        # Reset all filter session state values
        filter_defaults.reset_session_state()

        # Clear filtered results
        if 'filtered_results' in st.session_state:
            st.session_state.filtered_results = None
        if 'filter_loading' in st.session_state:
            st.session_state.filter_loading = False

        # Reset filter state if present
        if 'filter_state' in st.session_state:
            st.session_state.filter_state.reset_all()

        # Call optional callback
        if on_clear:
            on_clear()

        return True

    return False


def render_clear_filters_section(
    filter_configs: List[FilterConfig],
    filter_defaults: FilterDefaults,
    on_clear: Optional[Callable] = None
) -> None:
    """Render the complete clear filters section with badge and button.

    Args:
        filter_configs: List of all filter configurations
        filter_defaults: Default values for filters
        on_clear: Optional callback when filters are cleared
    """
    active_count = count_active_filters(filter_configs)

    # Show badge
    render_filter_badge(active_count)

    # Show clear button only if filters are active
    if active_count > 0:
        if render_clear_all_button(filter_defaults, on_clear):
            st.rerun()
        st.divider()


# =============================================================================
# INDIVIDUAL FILTER RESET (TASK F1-005: X Icons for Individual Filters)
# =============================================================================

def filter_with_clear(
    label: str,
    options: List[str],
    default: str,
    key: str,
    help_text: Optional[str] = None,
    on_change: Optional[Callable] = None
) -> str:
    """Filter dropdown with inline clear button.

    Args:
        label: Label for the selectbox
        options: List of options including default
        default: Default value (should be in options)
        key: Session state key for this filter
        help_text: Optional help text
        on_change: Optional callback when value changes

    Returns:
        Selected value
    """
    # Get current value from session state or use default
    current_value = st.session_state.get(key, default)

    # Ensure current value is valid option
    if current_value not in options:
        current_value = default
        st.session_state[key] = current_value

    col1, col2 = st.columns([4.5, 0.5])

    with col1:
        try:
            selected_index = options.index(current_value)
        except ValueError:
            selected_index = 0

        selected = st.selectbox(
            label,
            options,
            index=selected_index,
            key=key,
            help=help_text,
            on_change=on_change
        )

    with col2:
        st.write("")  # Vertical spacing
        st.write("")

        # Show X button only if not default
        is_default = selected == default

        if not is_default:
            if st.button(
                "✕",
                key=f"{key}_clear",
                help=f"Clear {label}",
                type="tertiary"
            ):
                st.session_state[key] = default
                if on_change:
                    on_change()
                st.rerun()

    return selected


def multiselect_with_clear(
    label: str,
    options: List[str],
    default: List[str],
    key: str,
    help_text: Optional[str] = None,
    on_change: Optional[Callable] = None
) -> List[str]:
    """Multi-select filter with clear button.

    Args:
        label: Label for the multiselect
        options: List of available options
        default: Default selected values (usually empty list)
        key: Session state key
        help_text: Optional help text
        on_change: Optional callback when value changes

    Returns:
        List of selected values
    """
    current_value = st.session_state.get(key, default)

    col1, col2 = st.columns([4.5, 0.5])

    with col1:
        selected = st.multiselect(
            label,
            options,
            default=current_value,
            key=key,
            help=help_text,
            on_change=on_change
        )

    with col2:
        st.write("")
        st.write("")

        # Show X button if something is selected
        if len(selected) > 0:
            if st.button(
                "✕",
                key=f"{key}_clear",
                help=f"Clear {label}",
                type="tertiary"
            ):
                st.session_state[key] = default
                if on_change:
                    on_change()
                st.rerun()

    return selected


def slider_with_clear(
    label: str,
    min_val: int,
    max_val: int,
    default: Tuple[int, int],
    key: str,
    help_text: Optional[str] = None,
    on_change: Optional[Callable] = None
) -> Tuple[int, int]:
    """Range slider with reset button and value display.

    Args:
        label: Slider label
        min_val: Minimum value
        max_val: Maximum value
        default: Default range tuple (min, max)
        key: Session state key
        help_text: Optional help text
        on_change: Optional callback when value changes

    Returns:
        Selected range tuple (min, max)
    """
    current_range = st.session_state.get(key, default)

    col1, col2 = st.columns([4.5, 0.5])

    with col1:
        selected = st.slider(
            label,
            min_val,
            max_val,
            value=current_range,
            key=key,
            help=help_text,
            on_change=on_change
        )

        # Show selected values inline
        if selected != (min_val, max_val):
            st.caption(f"📊 Selected: {selected[0]} - {selected[1]}")

    with col2:
        st.write("")
        st.write("")

        # Show reset button if not at default
        if selected != default:
            if st.button(
                "↺",
                key=f"{key}_reset",
                help=f"Reset {label} to default ({default[0]}-{default[1]})",
                type="tertiary"
            ):
                st.session_state[key] = default
                if on_change:
                    on_change()
                st.rerun()

    return selected


def number_input_with_clear(
    label: str,
    min_val: int,
    max_val: int,
    default: int,
    key: str,
    step: int = 1,
    help_text: Optional[str] = None,
    on_change: Optional[Callable] = None
) -> int:
    """Number input with clear button.

    Args:
        label: Input label
        min_val: Minimum value
        max_val: Maximum value
        default: Default value
        key: Session state key
        step: Step increment
        help_text: Optional help text
        on_change: Optional callback when value changes

    Returns:
        Input value
    """
    current_value = st.session_state.get(key, default)

    col1, col2 = st.columns([4.5, 0.5])

    with col1:
        value = st.number_input(
            label,
            min_value=min_val,
            max_value=max_val,
            value=current_value,
            step=step,
            key=key,
            help=help_text,
            on_change=on_change
        )

    with col2:
        st.write("")
        st.write("")

        # Show reset button if not at default
        if value != default:
            if st.button(
                "✕",
                key=f"{key}_clear",
                help=f"Reset {label} to default ({default})",
                type="tertiary"
            ):
                st.session_state[key] = default
                if on_change:
                    on_change()
                st.rerun()

    return value


# =============================================================================
# CASCADING FILTER DEPENDENCIES (TASK F1-006: Cascading Filters)
# =============================================================================

@dataclass
class CascadingFilterConfig:
    """Configuration for cascading filter dependencies.

    Example:
        config = CascadingFilterConfig(
            parent_key="league_filter",
            child_key="position_filter",
            get_child_options_fn=get_available_positions_for_league,
            reset_child_on_parent_change=True
        )
    """

    parent_key: str
    child_key: str
    get_child_options_fn: Callable[[Any], List[str]]
    reset_child_on_parent_change: bool = True
    dependency_indicator: str = "📍"


def handle_cascading_filter(
    config: CascadingFilterConfig,
    df: pd.DataFrame
) -> Tuple[List[str], bool]:
    """Handle cascading filter logic where child options depend on parent.

    Args:
        config: CascadingFilterConfig defining the relationship
        df: DataFrame to query for available options

    Returns:
        Tuple of (available child options, whether child was reset)
    """
    parent_value = st.session_state.get(config.parent_key)

    # Get new child options based on parent selection
    child_options = config.get_child_options_fn(parent_value, df)

    # Check if current child selection is still valid
    current_child = st.session_state.get(config.child_key)
    child_reset = False

    if current_child is not None:
        # Handle single select vs multi-select
        if isinstance(current_child, list):
            # Multi-select: filter to valid options
            valid_selections = [c for c in current_child if c in child_options]
            if len(valid_selections) != len(current_child):
                st.session_state[config.child_key] = valid_selections
                child_reset = True
        else:
            # Single select: reset to default if not valid
            if current_child not in child_options and config.reset_child_on_parent_change:
                st.session_state[config.child_key] = child_options[0] if child_options else None
                child_reset = True

    return child_options, child_reset


def render_cascading_indicator(
    parent_value: Any,
    parent_label: str,
    child_label: str,
    indicator: str = "📍"
) -> None:
    """Render a visual indicator showing filter dependency.

    Args:
        parent_value: Current value of parent filter
        parent_label: Label for parent filter
        child_label: Label for child filter
        indicator: Emoji or icon to show
    """
    if parent_value and parent_value not in [None, "All", []]:
        st.caption(
            f"{indicator} {child_label} filtered to those in {parent_label}: **{parent_value}**"
        )


def create_league_dependent_selector(
    df: pd.DataFrame,
    league_key: str,
    child_key: str,
    get_options_fn: Callable[[Any, pd.DataFrame], List[str]],
    child_label: str,
    default_value: Any = None
) -> Any:
    """Create a selector whose options depend on league selection.

    Args:
        df: DataFrame to query
        league_key: Session state key for league filter
        child_key: Session state key for this selector
        get_options_fn: Function(league_value, df) -> List[options]
        child_label: Label for this selector
        default_value: Default value to use if selection is reset

    Returns:
        Selected value
    """
    league_value = st.session_state.get(league_key)
    options = get_options_fn(league_value, df)

    # Add default option if specified
    if default_value is not None and default_value not in options:
        options = [default_value] + options

    # Ensure current value is valid
    current = st.session_state.get(child_key)
    if current not in options:
        current = options[0] if options else default_value
        st.session_state[child_key] = current

    # Render dependency indicator
    if league_value:
        render_cascading_indicator(league_value, "League", child_label)

    return st.selectbox(
        child_label,
        options,
        index=options.index(current) if current in options else 0,
        key=child_key
    )


def get_available_positions_for_league(league: Optional[str], df: pd.DataFrame) -> List[str]:
    """Get positions available in selected league.

    Args:
        league: Selected league slug or None
        df: Player DataFrame

    Returns:
        List of positions in the league
    """
    if league is None or league == "All" or league == []:
        return ["All"] + list(df["player_position"].dropna().unique())

    league_players = df[df["competition_slug"] == league]
    positions = ["All"] + sorted(league_players["player_position"].dropna().unique().tolist())
    return positions


def get_available_teams_for_league(league: Optional[str], df: pd.DataFrame) -> List[str]:
    """Get teams available in selected league.

    Args:
        league: Selected league slug or None
        df: Player DataFrame

    Returns:
        List of teams in the league
    """
    if league is None or league == "All" or league == []:
        return sorted(df["team"].dropna().unique().tolist())

    league_players = df[df["competition_slug"] == league]
    teams = sorted(league_players["team"].dropna().unique().tolist())
    return teams


# =============================================================================
# PRECISION SLIDERS (TASK F1-007: Filter Slider Precision Tooltips)
# =============================================================================

def precision_slider(
    label: str,
    min_val: float,
    max_val: float,
    default: Tuple[float, float],
    key: str,
    step: float = 0.1,
    format_str: str = "{:.1f}",
    help_text: Optional[str] = None,
    context_data: Optional[Dict] = None
) -> Tuple[float, float]:
    """Slider with precision display and optional context data.

    Args:
        label: Slider label
        min_val: Minimum value
        max_val: Maximum value
        default: Default range tuple
        key: Session state key
        step: Step increment
        format_str: Format string for value display
        help_text: Help text (auto-generated if not provided)
        context_data: Optional dict with 'average' and other context

    Returns:
        Selected range tuple
    """
    # Auto-generate help text with precision info
    if help_text is None:
        help_text = (
            f"Select range with {step} precision. "
            f"Current: {format_str.format(default[0])} - {format_str.format(default[1])}"
        )

    col1, col2 = st.columns([4, 1])

    with col1:
        values = st.slider(
            label,
            min_val,
            max_val,
            st.session_state.get(key, default),
            step=step,
            key=key,
            help=help_text
        )

    with col2:
        # Show exact values as formatted badges
        st.write("")
        st.write("")

        is_default = values == default
        badge_style = (
            "background: #00D4AA33; border: 1px solid #00D4AA; color: #00D4AA;"
            if not is_default
            else "background: #30363D; color: #8B949E;"
        )

        st.markdown(f"""
            <div style="text-align: right;">
                <div style="{badge_style} padding: 4px 8px; border-radius: 4px;
                            font-size: 12px; font-family: monospace;">
                    {format_str.format(values[0])}
                </div>
                <div style="color: #666; font-size: 10px; margin: 2px 0;">to</div>
                <div style="{badge_style} padding: 4px 8px; border-radius: 4px;
                            font-size: 12px; font-family: monospace;">
                    {format_str.format(values[1])}
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Show context data if provided
    if context_data:
        avg_val = context_data.get('average', (min_val + max_val) / 2)
        coverage = context_data.get('coverage_percent')

        context_html = f"""
            <div style="font-size: 11px; color: #8B949E; margin-top: 4px;">
                📊 League average: {format_str.format(avg_val)}
        """
        if coverage:
            context_html += f" | Your range covers {coverage:.0f}% of players"
        context_html += "</div>"

        st.markdown(context_html, unsafe_allow_html=True)

    return values


def rating_slider_with_context(
    df: pd.DataFrame,
    key: str,
    label: str = "⭐ Rating Range"
) -> Tuple[float, float]:
    """Specialized rating slider with league context.

    Args:
        df: Player DataFrame for context
        key: Session state key
        label: Slider label

    Returns:
        Selected rating range
    """
    default = (0.0, 10.0)

    # Calculate league average for context
    if "avg_rating" in df.columns and len(df) > 0:
        avg_rating = df["avg_rating"].mean()
        context_data = {"average": avg_rating}
    else:
        context_data = None

    return precision_slider(
        label,
        0.0,
        10.0,
        default,
        key,
        step=0.1,
        format_str="{:.1f}",
        context_data=context_data
    )


# =============================================================================
# NO RESULTS EXPLANATION (TASK F1-008: No Results State)
# =============================================================================

@dataclass
class FilterConflict:
    """Represents a conflict between filters that causes no results."""

    filter_keys: List[str]
    explanation: str
    suggestion: str


def analyze_filter_conflicts(
    filters: Dict[str, Any],
    df: pd.DataFrame,
    min_players_threshold: int = 5
) -> List[FilterConflict]:
    """Analyze filters to find conflicts causing no results.

    Args:
        filters: Current filter values
        df: Full dataset
        min_players_threshold: Minimum players to consider a combination valid

    Returns:
        List of FilterConflict objects explaining issues
    """
    conflicts = []

    # Check position + age conflicts
    if filters.get('position') and filters.get('age_range'):
        position = filters['position']
        age_min, age_max = filters['age_range']

        position_players = df[df['player_position'] == position]
        if len(position_players) > 0 and 'age_at_season_start' in position_players.columns:
            ages = position_players['age_at_season_start'].dropna()
            if len(ages) > 0:
                min_age, max_age = ages.min(), ages.max()

                if min_age > age_max or max_age < age_min:
                    conflicts.append(FilterConflict(
                        filter_keys=['position', 'age_range'],
                        explanation=(
                            f"⚠️ No {position}s found in age range {age_min:.0f}-{age_max:.0f}. "
                            f"Available {position}s are aged {min_age:.0f}-{max_age:.0f}"
                        ),
                        suggestion=(
                            f"💡 Try age range {max(min_age, age_min):.0f}-{min(max_age, age_max):.0f} "
                            f"for {position}s"
                        )
                    ))

    # Check rating + minutes conflict (rare combination)
    rating_threshold = filters.get('rating_threshold', 0)
    minutes_threshold = filters.get('min_minutes', 0)

    if rating_threshold > 8.0 and minutes_threshold > 2000:
        elite_regular = df[
            (df.get('avg_rating', 0) > 8.0) &
            (df.get('total_minutes', 0) > 2000)
        ]
        if len(elite_regular) < min_players_threshold:
            conflicts.append(FilterConflict(
                filter_keys=['rating_threshold', 'min_minutes'],
                explanation=(
                    f"⚠️ Rating >{rating_threshold:.1f} with >{minutes_threshold} minutes is rare - "
                    f"you're looking for elite regular starters"
                ),
                suggestion="💡 Try Rating >7.5 or Minutes >1500 for broader results"
            ))

    # Check league + position scarcity
    if filters.get('league') and filters.get('position'):
        league_pos_count = len(df[
            (df['competition_slug'] == filters['league']) &
            (df['player_position'] == filters['position'])
        ])
        if league_pos_count < min_players_threshold:
            conflicts.append(FilterConflict(
                filter_keys=['league', 'position'],
                explanation=(
                    f"⚠️ Only {league_pos_count} {filters['position']}s in {filters['league']}"
                ),
                suggestion="💡 Try selecting multiple leagues or a different position"
            ))

    return conflicts


def find_relaxed_matches(
    filters: Dict[str, Any],
    df: pd.DataFrame,
    limit: int = 5
) -> Optional[pd.DataFrame]:
    """Find closest matches by relaxing one filter at a time.

    Args:
        filters: Current filter values
        df: Full dataset
        limit: Maximum number of suggestions

    Returns:
        DataFrame with relaxed matches or None
    """
    relaxed_results = []

    # Try relaxing each filter individually
    for key in filters.keys():
        if key in ['position', 'league', 'age_range', 'rating_threshold']:
            relaxed_filters = filters.copy()
            del relaxed_filters[key]

            # Apply remaining filters
            mask = pd.Series(True, index=df.index)
            for k, v in relaxed_filters.items():
                if k == 'min_minutes' and v > 0:
                    mask &= df.get('total_minutes', 0) >= v
                elif k == 'position' and v:
                    mask &= df.get('player_position') == v
                elif k == 'league' and v:
                    mask &= df.get('competition_slug') == v
                elif k == 'age_range':
                    pass  # Would need age column

            results = df[mask]
            if len(results) > 0:
                relaxed_results.append(results.head(limit))

    if relaxed_results:
        # Combine all relaxed results
        combined = pd.concat(relaxed_results).drop_duplicates()
        return combined.head(limit)

    return None


def render_no_results_state(
    filters: Dict[str, Any],
    df: pd.DataFrame,
    on_clear_all: Optional[Callable] = None,
    on_undo: Optional[Callable] = None,
    on_show_similar: Optional[Callable] = None
) -> None:
    """Render enhanced empty state with explanations and suggestions.

    Args:
        filters: Current filter values
        df: Full dataset
        on_clear_all: Callback for clear all button
        on_undo: Callback for undo button
        on_show_similar: Callback for show similar button
    """
    st.info("🔍 **No players match your current filters**")

    # Analyze conflicts
    conflicts = analyze_filter_conflicts(filters, df)

    if conflicts:
        st.write("**Why no results?**")
        for conflict in conflicts:
            st.markdown(conflict.explanation)

        st.write("**Try these suggestions:**")
        for conflict in conflicts:
            st.markdown(conflict.suggestion)

    # Quick action buttons
    st.divider()
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🗑️ Clear All Filters", use_container_width=True, type="primary"):
            if on_clear_all:
                on_clear_all()

    with col2:
        if on_undo and st.button("↩️ Undo Last Filter", use_container_width=True):
            on_undo()

    with col3:
        if on_show_similar and st.button("📊 Show Similar Players", use_container_width=True):
            on_show_similar()

    # Show what WOULD match if filters relaxed
    st.divider()
    st.write("**Players that ALMOST match:**")

    relaxed_results = find_relaxed_matches(filters, df)
    if relaxed_results is not None and len(relaxed_results) > 0:
        display_cols = ['player_name', 'team', 'player_position', 'avg_rating', 'total_minutes']
        available_cols = [c for c in display_cols if c in relaxed_results.columns]
        st.dataframe(relaxed_results[available_cols], use_container_width=True, hide_index=True)
    else:
        st.caption("No close matches found - try clearing more filters")


# =============================================================================
# COMPOSITE ENHANCED FILTER PANEL
# =============================================================================

class EnhancedFilterPanel:
    """Enhanced filter panel with all UX improvements.

    This combines all the filter improvements into a single reusable component.

    Usage:
        panel = EnhancedFilterPanel(df_all, "scout")
        config = panel.render()
        df_filtered = panel.apply_filters(df_all, config)
    """

    def __init__(
        self,
        df: pd.DataFrame,
        key_prefix: str,
        show_top5_toggle: bool = False,
        show_age: bool = True,
        show_teams: bool = True,
        show_rating: bool = False,
        show_cascading: bool = True,
        default_min_minutes: int = 450,
        on_filter_change: Optional[Callable] = None
    ):
        self.df = df
        self.key_prefix = key_prefix
        self.show_top5_toggle = show_top5_toggle
        self.show_age = show_age
        self.show_teams = show_teams
        self.show_rating = show_rating
        self.show_cascading = show_cascading
        self.default_min_minutes = default_min_minutes
        self.on_filter_change = on_filter_change

        # Initialize filter state
        if f"{key_prefix}_filter_state" not in st.session_state:
            st.session_state[f"{key_prefix}_filter_state"] = FilterState()

    def _on_change(self, key: str) -> None:
        """Handle filter change with debouncing."""
        filter_state = st.session_state[f"{self.key_prefix}_filter_state"]

        current_value = st.session_state.get(key)

        if filter_state.should_apply(key, current_value):
            filter_state.set_loading(True)
            if self.on_filter_change:
                self.on_filter_change()

    def render(self) -> Dict[str, Any]:
        """Render the enhanced filter panel."""
        filter_configs = []

        with st.expander("⚙️ Filters", expanded=True):
            # Build filter configs for badge counting
            st.markdown("<div class='filter-block-label'>Player Filters</div>", unsafe_allow_html=True)

            # Row 1: League, Season, Position
            c1, c2, c3 = st.columns(3)

            with c1:
                from dashboard.utils.filters import create_league_selector
                leagues = create_league_selector(
                    self.df,
                    key=f"{self.key_prefix}_leagues",
                    top5_only_checkbox=self.show_top5_toggle,
                )
                filter_configs.append(FilterConfig(
                    key=f"{self.key_prefix}_leagues",
                    label="Leagues",
                    default_value=[],
                    current_value=leagues,
                    check_fn=lambda c, d: len(c) > 0
                ))

            with c2:
                from dashboard.utils.filters import create_season_selector
                seasons = create_season_selector(
                    self.df,
                    key=f"{self.key_prefix}_seasons",
                    leagues=leagues if leagues else None,
                )
                filter_configs.append(FilterConfig(
                    key=f"{self.key_prefix}_seasons",
                    label="Seasons",
                    default_value=[],
                    current_value=seasons,
                    check_fn=lambda c, d: len(c) > 0
                ))

            with c3:
                # Use cascading position selector if enabled
                if self.show_cascading and leagues:
                    position_options = get_available_positions_for_league(
                        leagues[0] if leagues else None, self.df
                    )
                    positions = st.multiselect(
                        "Position",
                        options=position_options,
                        default=st.session_state.get(f"{self.key_prefix}_positions", []),
                        key=f"{self.key_prefix}_positions",
                        format_func=lambda x: x,
                        placeholder="All positions"
                    )
                    if leagues:
                        render_cascading_indicator(leagues[0], "League", "Position")
                else:
                    from dashboard.utils.filters import create_position_selector
                    positions = create_position_selector(
                        self.df,
                        key=f"{self.key_prefix}_positions",
                    )

                filter_configs.append(FilterConfig(
                    key=f"{self.key_prefix}_positions",
                    label="Positions",
                    default_value=[],
                    current_value=positions,
                    check_fn=lambda c, d: len(c) > 0
                ))

            # Row 2: Minutes, Age, Teams
            col_layout = [c for c in [self.show_age, self.show_teams] if c]
            if len(col_layout) == 2:
                c4, c5, c6 = st.columns(3)
            elif len(col_layout) == 1:
                c4, c5 = st.columns(2)
            else:
                c4 = st.container()

            with c4:
                min_minutes = number_input_with_clear(
                    "Min. minutes",
                    min_val=0,
                    max_val=4000,
                    default=self.default_min_minutes,
                    key=f"{self.key_prefix}_mins",
                    step=90,
                    help_text="Minimum minutes played in the season"
                )
                filter_configs.append(FilterConfig(
                    key=f"{self.key_prefix}_mins",
                    label="Min Minutes",
                    default_value=self.default_min_minutes,
                    current_value=min_minutes,
                    check_fn=lambda c, d: c != d
                ))

            idx = 1
            if self.show_age:
                col = [c5, c6][idx - 1]
                with col:
                    from dashboard.utils.filters import create_age_band_selector
                    age_bands = create_age_band_selector(key=f"{self.key_prefix}_age")
                idx += 1
                filter_configs.append(FilterConfig(
                    key=f"{self.key_prefix}_age",
                    label="Age Bands",
                    default_value=[],
                    current_value=age_bands,
                    check_fn=lambda c, d: len(c) > 0
                ))
            else:
                age_bands = []

            if self.show_teams:
                col = [c5, c6][idx - 1] if self.show_age else c5
                with col:
                    if self.show_cascading and leagues:
                        team_options = get_available_teams_for_league(
                            leagues[0] if leagues else None, self.df
                        )
                        teams = st.multiselect(
                            "Team",
                            options=team_options,
                            default=st.session_state.get(f"{self.key_prefix}_teams", []),
                            key=f"{self.key_prefix}_teams",
                            placeholder="All teams"
                        )
                        if leagues:
                            render_cascading_indicator(leagues[0], "League", "Team")
                    else:
                        from dashboard.utils.filters import create_team_selector
                        teams = create_team_selector(
                            self.df,
                            key=f"{self.key_prefix}_teams",
                        )
                idx += 1
                filter_configs.append(FilterConfig(
                    key=f"{self.key_prefix}_teams",
                    label="Teams",
                    default_value=[],
                    current_value=teams,
                    check_fn=lambda c, d: len(c) > 0
                ))
            else:
                teams = []

            min_rating = 0.0
            if self.show_rating:
                min_rating = st.number_input(
                    "Min. avg rating",
                    min_value=0.0,
                    max_value=10.0,
                    value=0.0,
                    step=0.1,
                    key=f"{self.key_prefix}_rating",
                )
                filter_configs.append(FilterConfig(
                    key=f"{self.key_prefix}_rating",
                    label="Min Rating",
                    default_value=0.0,
                    current_value=min_rating,
                    check_fn=lambda c, d: c > d
                ))

            # Show filter badge and clear button
            st.divider()
            active_count = count_active_filters(filter_configs)
            render_filter_badge(active_count)

            if active_count > 0:
                defaults = FilterDefaults(values={
                    f"{self.key_prefix}_leagues": [],
                    f"{self.key_prefix}_seasons": [],
                    f"{self.key_prefix}_positions": [],
                    f"{self.key_prefix}_mins": self.default_min_minutes,
                    f"{self.key_prefix}_age": [],
                    f"{self.key_prefix}_teams": [],
                    f"{self.key_prefix}_rating": 0.0,
                })
                if render_clear_all_button(defaults, self.on_filter_change, self.key_prefix):
                    st.rerun()

        return {
            "leagues": leagues,
            "seasons": seasons,
            "positions": positions,
            "min_minutes": min_minutes,
            "age_bands": age_bands,
            "teams": teams,
            "min_rating": min_rating,
        }

    def apply_filters(self, df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
        """Apply filter config to DataFrame."""
        from dashboard.utils.filters import apply_filters as base_apply
        from dashboard.utils.types import FilterConfig as FC

        fc = FC(
            leagues=config.get("leagues"),
            seasons=config.get("seasons"),
            positions=config.get("positions"),
            min_minutes=config.get("min_minutes"),
            age_bands=config.get("age_bands"),
            teams=config.get("teams"),
            min_rating=config.get("min_rating"),
        )
        return base_apply(df, fc)

    def render_no_results_if_empty(
        self,
        df_filtered: pd.DataFrame,
        df_original: pd.DataFrame,
        config: Dict[str, Any]
    ) -> bool:
        """Render no results state if filtered DataFrame is empty.

        Returns True if results were shown (not empty), False if empty state rendered.
        """
        if len(df_filtered) == 0:
            filters_dict = {
                "position": config.get("positions", [None])[0] if config.get("positions") else None,
                "league": config.get("leagues", [None])[0] if config.get("leagues") else None,
                "age_range": None,  # Would need to be added to config
                "rating_threshold": config.get("min_rating", 0),
                "min_minutes": config.get("min_minutes", 0),
            }

            def on_clear():
                for key in ["leagues", "seasons", "positions", "age", "teams"]:
                    full_key = f"{self.key_prefix}_{key}"
                    if full_key in st.session_state:
                        st.session_state[full_key] = []
                st.session_state[f"{self.key_prefix}_mins"] = self.default_min_minutes
                st.session_state[f"{self.key_prefix}_rating"] = 0.0
                st.rerun()

            render_no_results_state(filters_dict, df_original, on_clear_all=on_clear)
            return False

        return True
