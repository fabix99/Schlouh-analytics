"""Reusable filter utilities to reduce code duplication across pages."""

from typing import Optional, Tuple
import pandas as pd
import streamlit as st
from dashboard.utils.constants import (
    COMP_NAMES, COMP_FLAGS, POSITION_NAMES, POSITION_ORDER,
    MIN_MINUTES_DEFAULT, AGE_BANDS, TOP_5_LEAGUES,
)
from dashboard.utils.scope import CURRENT_SEASON, DEFAULT_COMPETITION_SLUGS
from dashboard.utils.types import FilterConfig


def create_league_selector(
    df: pd.DataFrame,
    key: str,
    label: str = "League",
    default_all: bool = False,
    top5_only_checkbox: bool = False,
    default_scope_slugs: Optional[list[str]] = None,
) -> list[str]:
    """
    Create a league multi-select with consistent formatting.

    Args:
        default_scope_slugs: If set (e.g. DEFAULT_COMPETITION_SLUGS), default
            selection to these slugs (leagues + UEFA only), so user can add cups etc. via "Include more".
    Returns:
        List of selected competition slugs.
    """
    col1, col2 = st.columns([3, 1])

    with col1:
        if top5_only_checkbox:
            top5_only = st.checkbox(
                "🌟 Top 5 leagues only",
                key=f"{key}_top5",
                help="Filter to Premier League, La Liga, Serie A, Bundesliga, Ligue 1",
            )
        else:
            top5_only = False

        avail = sorted(df["competition_slug"].unique())
        avail_leagues = (
            [s for s in TOP_5_LEAGUES if s in avail]
            if top5_only
            else avail
        )

        league_labels = {s: f"{COMP_FLAGS.get(s, '🏆')} {COMP_NAMES.get(s, s)}" for s in avail_leagues}

        if default_all or top5_only:
            defaults = avail_leagues
        elif default_scope_slugs:
            defaults = [s for s in default_scope_slugs if s in avail_leagues]
        else:
            defaults = []

        sel_leagues = st.multiselect(
            label,
            options=avail_leagues,
            default=defaults,
            format_func=lambda x: league_labels[x],
            placeholder="All leagues",
            key=key,
            help="Default: leagues + UEFA only. Add cups or other competitions to include more.",
        )

    return sel_leagues


def create_season_selector(
    df: pd.DataFrame,
    key: str,
    leagues: Optional[list[str]] = None,
    label: str = "Season",
    allow_all: bool = False,
    default_seasons: Optional[list[str]] = None,
) -> list[str]:
    """
    Create a season multi-select with optional league filtering.

    Args:
        df: Player/team DataFrame
        key: Streamlit widget key
        leagues: If provided, only show seasons for these leagues
        label: Widget label
        allow_all: If True, include "All" option (returns list with "All")
        default_seasons: If set (e.g. [CURRENT_SEASON]), default selection to these seasons.

    Returns:
        List of selected seasons
    """
    if leagues:
        avail_seasons = sorted(
            df[df["competition_slug"].isin(leagues)]["season"].unique(),
            reverse=True,
        )
    else:
        avail_seasons = sorted(df["season"].unique(), reverse=True)

    if allow_all:
        avail_seasons = ["All"] + avail_seasons

    if default_seasons:
        defaults = [s for s in default_seasons if s in avail_seasons]
    else:
        defaults = []

    return st.multiselect(
        label,
        options=avail_seasons,
        default=defaults,
        placeholder="All seasons" if not allow_all else None,
        key=key,
        help="Default: current season only. Add more seasons to include past years.",
    )


def create_position_selector(
    df: pd.DataFrame,
    key: str,
    label: str = "Position",
    multiselect: bool = True,
) -> list[str]:
    """Create a position selector with human-readable labels."""
    pos_options = [p for p in POSITION_ORDER if p in df["player_position"].dropna().unique()]

    if multiselect:
        return st.multiselect(
            label,
            options=pos_options,
            default=[],
            format_func=lambda x: POSITION_NAMES.get(x, x),
            placeholder="All positions",
            key=key,
        )
    else:
        selected = st.selectbox(
            label,
            options=["All"] + pos_options,
            format_func=lambda x: "All" if x == "All" else POSITION_NAMES.get(x, x),
            key=key,
        )
        return [] if selected == "All" else [selected]


def create_age_band_selector(key: str, label: str = "Age band") -> list[str]:
    """Create an age band multi-select (legacy). Prefer create_age_min_max_inputs."""
    return st.multiselect(
        label,
        options=AGE_BANDS,
        default=[],
        placeholder="All ages",
        key=key,
    )


def create_age_min_max_inputs(
    key_prefix: str,
    min_default: int = 16,
    max_default: int = 45,
) -> Tuple[Optional[int], Optional[int]]:
    """Create min and max age number inputs. Returns (age_min, age_max); None means no bound."""
    c1, c2 = st.columns(2)
    with c1:
        age_min = st.number_input(
            "Age min",
            min_value=15,
            max_value=50,
            value=min_default,
            step=1,
            key=f"{key_prefix}_age_min",
            help="Minimum age (at season start)",
        )
    with c2:
        age_max = st.number_input(
            "Age max",
            min_value=15,
            max_value=50,
            value=max_default,
            step=1,
            key=f"{key_prefix}_age_max",
            help="Maximum age (at season start)",
        )
    return (age_min, age_max)


def create_min_minutes_input(
    key: str,
    default: int = MIN_MINUTES_DEFAULT,
    label: str = "Min. minutes",
) -> int:
    """Create a standardized minutes input."""
    return st.number_input(
        label,
        min_value=0,
        max_value=4000,
        value=default,
        step=90,
        key=key,
    )


def create_team_selector(
    df: pd.DataFrame,
    key: str,
    label: str = "Team",
) -> list[str]:
    """Create a team multi-select."""
    return st.multiselect(
        label,
        options=sorted(df["team"].dropna().unique()),
        default=[],
        placeholder="All teams",
        key=key,
    )


def apply_filters(
    df: pd.DataFrame,
    config: FilterConfig,
) -> pd.DataFrame:
    """
    Apply standard filters to a DataFrame based on config.

    This is the central filter function that replaces all the duplicated
    filter logic across pages.
    """
    mask = pd.Series(True, index=df.index)

    if config.get("leagues"):
        mask &= df["competition_slug"].isin(config["leagues"])

    # Season: default to current season only when none selected or "All"
    seasons = config.get("seasons") or []
    seasons = [s for s in seasons if s != "All"]
    if not seasons:
        seasons = [CURRENT_SEASON]
    mask &= df["season"].isin(seasons)

    if config.get("positions"):
        mask &= df["player_position"].isin(config["positions"])

    if config.get("min_minutes", 0) > 0 and "total_minutes" in df.columns:
        mask &= df["total_minutes"] >= config["min_minutes"]

    if config.get("age_min") is not None and "age_at_season_start" in df.columns:
        mask &= df["age_at_season_start"] >= config["age_min"]
    if config.get("age_max") is not None and "age_at_season_start" in df.columns:
        mask &= df["age_at_season_start"] <= config["age_max"]

    if config.get("teams"):
        mask &= df["team"].isin(config["teams"])

    if config.get("min_rating", 0) > 0 and "avg_rating" in df.columns:
        mask &= df["avg_rating"] >= config["min_rating"]

    return df[mask].copy()


def display_filter_summary(df_filtered: pd.DataFrame, df_original: pd.DataFrame) -> None:
    """Display consistent filter result summary."""
    n_rows = len(df_filtered)
    n_players = df_filtered["player_id"].nunique() if "player_id" in df_filtered.columns else n_rows

    st.markdown(
        f"<p style='color:#8B949E;margin:0 0 0.5rem;'>"
        f"<b style='color:#C9A840;'>{n_rows:,}</b> rows · "
        f"<b style='color:#C9A840;'>{n_players:,}</b> unique players</p>",
        unsafe_allow_html=True,
    )


class FilterPanel:
    """
    Composite filter panel that creates all standard filters in a grid layout.
    When default_scope=True, league and season default to current season + leagues & UEFA only.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        key_prefix: str,
        show_top5_toggle: bool = False,
        show_age: bool = True,
        show_teams: bool = True,
        show_min_rating: bool = False,
        default_min_minutes: int = MIN_MINUTES_DEFAULT,
        default_scope: bool = True,
    ):
        self.df = df
        self.key_prefix = key_prefix
        self.show_top5_toggle = show_top5_toggle
        self.show_age = show_age
        self.show_teams = show_teams
        self.show_min_rating = show_min_rating
        self.default_min_minutes = default_min_minutes
        self.default_scope = default_scope

    def load_config(self, config: dict) -> None:
        """Pre-populate filter widgets from a saved config by setting session state keys before render()."""
        key = self.key_prefix
        if config.get("leagues"):
            st.session_state[f"{key}_leagues"] = config["leagues"]
        if config.get("seasons"):
            st.session_state[f"{key}_seasons"] = config["seasons"]
        if config.get("positions"):
            st.session_state[f"{key}_positions"] = config["positions"]
        if "min_minutes" in config:
            st.session_state[f"{key}_mins"] = int(config["min_minutes"])
        if config.get("age_min") is not None:
            st.session_state[f"{key}_age_min"] = int(config["age_min"])
        if config.get("age_max") is not None:
            st.session_state[f"{key}_age_max"] = int(config["age_max"])
        if config.get("teams"):
            st.session_state[f"{key}_teams"] = config["teams"]

    def render(self) -> FilterConfig:
        """Render the filter panel and return the config."""
        with st.expander("⚙️ Filters", expanded=True):
            st.markdown("<div class='filter-block-label'>Player Filters</div>", unsafe_allow_html=True)

            # Row 1: League, Season, Position
            c1, c2, c3 = st.columns(3)

            with c1:
                leagues = create_league_selector(
                    self.df,
                    key=f"{self.key_prefix}_leagues",
                    top5_only_checkbox=self.show_top5_toggle,
                    default_scope_slugs=DEFAULT_COMPETITION_SLUGS if self.default_scope else None,
                )

            with c2:
                seasons = create_season_selector(
                    self.df,
                    leagues=leagues if leagues else None,
                    key=f"{self.key_prefix}_seasons",
                    default_seasons=[CURRENT_SEASON] if self.default_scope else None,
                )

            with c3:
                positions = create_position_selector(
                    self.df,
                    key=f"{self.key_prefix}_positions",
                )

            # Row 2: Minutes, Age, Teams (and optionally Rating)
            if self.show_age and self.show_teams:
                c4, c5, c6 = st.columns(3)
            elif self.show_age or self.show_teams:
                c4, c5 = st.columns(2)
            else:
                c4 = st.container()

            with c4:
                min_minutes = create_min_minutes_input(
                    key=f"{self.key_prefix}_mins",
                    default=self.default_min_minutes,
                )

            idx = 1
            age_min, age_max = None, None
            if self.show_age:
                col = [c5, c6][idx - 1] if self.show_teams else c5
                with col:
                    age_min, age_max = create_age_min_max_inputs(self.key_prefix)
                idx += 1

            if self.show_teams:
                col = [c5, c6][idx - 1] if self.show_age else c5
                with col:
                    teams = create_team_selector(
                        self.df,
                        key=f"{self.key_prefix}_teams",
                    )
                idx += 1
            else:
                teams = []

            min_rating = 0.0
            if self.show_min_rating:
                min_rating = st.number_input(
                    "Min. avg rating",
                    min_value=0.0,
                    max_value=10.0,
                    value=0.0,
                    step=0.1,
                    key=f"{self.key_prefix}_rating",
                )

        return FilterConfig(
            leagues=leagues,
            seasons=seasons,
            positions=positions,
            min_minutes=min_minutes,
            age_min=age_min,
            age_max=age_max,
            teams=teams,
            min_rating=min_rating,
        )
