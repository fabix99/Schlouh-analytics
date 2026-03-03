"""League quality adjustments for cross-league comparison.

Provides tools to normalize player statistics across different leagues,
enabling fair comparison between players from different competitions.
Phase 1 uses static quality scores; Phase 2 uses data-derived league_strength.parquet
when available, with fallback to static scores.
"""

from typing import Dict, List, Optional, Tuple
from pathlib import Path
import pandas as pd
import numpy as np

# Path to processed data (league_strength.parquet)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LEAGUE_STRENGTH_PATH = _PROJECT_ROOT / "data" / "processed" / "league_strength.parquet"
_LEAGUE_STRENGTH_TABLE: Optional[pd.DataFrame] = None


def _load_league_strength_table() -> Optional[pd.DataFrame]:
    """Load league strength table (competition_slug, season, strength_score). Cached."""
    global _LEAGUE_STRENGTH_TABLE
    if _LEAGUE_STRENGTH_TABLE is not None:
        return _LEAGUE_STRENGTH_TABLE
    if not _LEAGUE_STRENGTH_PATH.exists():
        return None
    try:
        _LEAGUE_STRENGTH_TABLE = pd.read_parquet(_LEAGUE_STRENGTH_PATH)
        _LEAGUE_STRENGTH_TABLE["season"] = _LEAGUE_STRENGTH_TABLE["season"].astype(str)
        _LEAGUE_STRENGTH_TABLE["competition_slug"] = _LEAGUE_STRENGTH_TABLE["competition_slug"].astype(str)
        return _LEAGUE_STRENGTH_TABLE
    except Exception:
        return None


# Phase 1: Static quality scores based on UEFA coefficients and historical perception
# Phase 2 will derive these from actual player transfer performance deltas
LEAGUE_QUALITY_SCORES = {
    "Premier League": 1.00,      # Baseline
    "La Liga": 0.95,
    "Bundesliga": 0.93,
    "Serie A": 0.90,
    "Ligue 1": 0.87,
    "Primeira Liga": 0.78,
    "Eredivisie": 0.75,
    "Pro League": 0.72,
    "Süper Lig": 0.70,
    "Saudi Pro League": 0.65,
}

# Alternative names/mappings
LEAGUE_ALIASES = {
    "England": "Premier League",
    "Spain": "La Liga",
    "Germany": "Bundesliga",
    "Italy": "Serie A",
    "France": "Ligue 1",
    "Portugal": "Primeira Liga",
    "Netherlands": "Eredivisie",
    "Belgium": "Pro League",
    "Turkey": "Süper Lig",
    "Saudi Arabia": "Saudi Pro League",
}

# Stat-specific compression factors
# Different stats translate differently across leagues
STAT_COMPRESSION_FACTORS = {
    "attacking": 0.80,    # Attacking stats (goals, xG) compress less
    "creative": 0.75,     # Creative stats (assists, xA) compress similarly
    "defensive": 1.00,    # Defensive stats compress linearly
    "passing": 0.90,      # Passing accuracy adjusts moderately
    "physical": 0.95,     # Physical duels adjust slightly
    "goalkeeping": 1.00,  # GK stats adjust linearly
    "generic": 0.85,      # Default moderate adjustment
}

# Map specific stats to categories
STAT_CATEGORIES = {
    # Attacking
    "goals": "attacking",
    "goals_per90": "attacking",
    "expectedGoals": "attacking",
    "expectedGoals_per90": "attacking",
    "shots": "attacking",
    "shots_on_target": "attacking",
    "big_chances": "attacking",
    
    # Creative
    "assists": "creative",
    "expectedAssists": "creative",
    "expectedAssists_per90": "creative",
    "keyPass": "creative",
    "keyPass_per90": "creative",
    "bigChanceCreated": "creative",
    "bigChanceCreated_per90": "creative",
    
    # Defensive
    "totalTackle": "defensive",
    "totalTackle_per90": "defensive",
    "interceptionWon": "defensive",
    "interceptionWon_per90": "defensive",
    "duelWon": "defensive",
    "duelWon_per90": "defensive",
    "aerialWon": "defensive",
    "aerialWon_per90": "defensive",
    "ballRecovery": "defensive",
    "ballRecovery_per90": "defensive",
    
    # Passing
    "totalPass": "passing",
    "totalPass_per90": "passing",
    "pass_accuracy": "passing",
    "pass_accuracy_pct": "passing",
    "progressivePass": "passing",
    
    # Physical (distinct from defensive — ground duels, no duplicates)
    "groundDuelWon": "physical",
    
    # Goalkeeping
    "saves": "goalkeeping",
    "saves_per90": "goalkeeping",
    "goalsPrevented": "goalkeeping",
    "goalsPrevented_per90": "goalkeeping",
}


def get_league_quality_score(
    league: str,
    competition_slug: Optional[str] = None,
    season: Optional[str] = None,
) -> float:
    """
    Get quality score for a league (0-1 scale, Premier League baseline = 1.0).

    When competition_slug and season are provided, uses data-derived strength
    from league_strength.parquet when available; otherwise falls back to static
    LEAGUE_QUALITY_SCORES.

    Args:
        league: League name (e.g., "Premier League", "Primeira Liga")
        competition_slug: Optional; when provided with season, use data-derived strength
        season: Optional; e.g. "2024-25"

    Returns:
        Quality score (typically 0–1, may exceed 1 for stronger leagues in data)
    """
    if competition_slug and season:
        table = _load_league_strength_table()
        if table is not None and not table.empty:
            season_str = str(season).strip()
            slug_str = str(competition_slug).strip()
            row = table[
                (table["competition_slug"] == slug_str) & (table["season"] == season_str)
            ]
            if not row.empty and "strength_score" in row.columns:
                val = row["strength_score"].iloc[0]
                if pd.notna(val) and np.isfinite(val):
                    return float(val)

    # Fallback: static scores
    if league in LEAGUE_QUALITY_SCORES:
        return LEAGUE_QUALITY_SCORES[league]
    if league in LEAGUE_ALIASES:
        canonical = LEAGUE_ALIASES[league]
        return LEAGUE_QUALITY_SCORES.get(canonical, 0.65)
    for canonical, score in LEAGUE_QUALITY_SCORES.items():
        if canonical.lower() in (league or "").lower() or (league or "").lower() in canonical.lower():
            return score
    return 0.65


def get_stat_category(stat_name: str) -> str:
    """
    Get the category for a specific stat.
    
    Args:
        stat_name: Name of the statistic
        
    Returns:
        Category string (attacking, creative, defensive, etc.)
    """
    # Direct lookup
    if stat_name in STAT_CATEGORIES:
        return STAT_CATEGORIES[stat_name]
    
    # Pattern matching for per90 versions
    base_name = stat_name.replace("_per90", "").replace("_pct", "")
    if base_name in STAT_CATEGORIES:
        return STAT_CATEGORIES[base_name]
    
    # Default
    return "generic"


def project_stat_to_baseline(
    value: float,
    source_league: str,
    target_league: str = "Premier League",
    stat_name: str = "generic",
    source_competition_slug: Optional[str] = None,
    source_season: Optional[str] = None,
    target_competition_slug: Optional[str] = None,
    target_season: Optional[str] = None,
) -> Dict:
    """
    Project a stat from source league to target league equivalent.

    Args:
        value: Raw stat value
        source_league: League the player currently plays in
        target_league: Target league for projection (default: Premier League)
        stat_name: Name of the statistic for category-specific adjustment
        source_competition_slug: Optional; for data-derived source strength
        source_season: Optional; e.g. "2024-25"
        target_competition_slug: Optional; for data-derived target strength
        target_season: Optional; if not set, uses source_season for target lookup

    Returns:
        Dictionary with projected_value, adjustment_factor, confidence, note, etc.
    """
    stat_category = get_stat_category(stat_name)
    adjustment_ratio = 1.0
    confidence = 0.60
    use_transfer_factor = False

    # Optional: use transfer-based factor when available (from_comp|to_comp|all|stat)
    if source_competition_slug and target_competition_slug:
        factors = load_adjustment_factors(filepath=str(_PROJECT_ROOT / "data" / "processed" / "league_adjustment_factors.json"))
        if factors:
            key_all = f"{source_competition_slug}|{target_competition_slug}|all|{stat_name}"
            if key_all in factors:
                adjustment_ratio = float(factors[key_all])
                use_transfer_factor = True
                confidence = 0.75

    if not use_transfer_factor:
        source_quality = get_league_quality_score(
            source_league, competition_slug=source_competition_slug, season=source_season
        )
        target_quality = get_league_quality_score(
            target_league,
            competition_slug=target_competition_slug,
            season=target_season or source_season,
        )
        compression = STAT_COMPRESSION_FACTORS.get(stat_category, 0.85)
        if source_quality > 0 and target_quality > 0:
            adjustment_ratio = (source_quality / target_quality) ** compression
        if source_league in LEAGUE_QUALITY_SCORES and target_league in LEAGUE_QUALITY_SCORES:
            confidence = 0.85
        else:
            confidence = 0.60

    projected_value = value * adjustment_ratio

    if adjustment_ratio > 1.0:
        direction = "increase"
        pct = (adjustment_ratio - 1) * 100
    else:
        direction = "decrease"
        pct = (1 - adjustment_ratio) * 100
    note = f"Stat adjusted from {source_league} to {target_league}: {direction}s by {pct:.1f}%"
    if use_transfer_factor:
        note += " (transfer-based factor)"

    return {
        "projected_value": projected_value,
        "original_value": value,
        "adjustment_factor": adjustment_ratio,
        "source_league": source_league,
        "target_league": target_league,
        "stat_category": stat_category,
        "confidence": confidence,
        "note": note
    }


def project_player_to_baseline(
    player_data: pd.Series,
    target_league: str = "Premier League",
    stats_to_project: Optional[List[str]] = None
) -> pd.Series:
    """
    Project all relevant stats for a player to target league baseline.
    
    Args:
        player_data: Series with player statistics
        target_league: Target league for projection
        stats_to_project: List of stat names to project (None = all per90 stats)
        
    Returns:
        Series with projected values added as new columns
    """
    source_league = player_data.get("league_name", player_data.get("competition_slug", "Unknown"))
    
    result = player_data.copy()
    
    # Determine which stats to project
    if stats_to_project is None:
        # Auto-detect per90 stats
        stats_to_project = [col for col in player_data.index if "per90" in col or col in STAT_CATEGORIES]
    
    for stat_name in stats_to_project:
        if stat_name in player_data.index:
            value = player_data[stat_name]
            if pd.notna(value) and isinstance(value, (int, float)):
                projection = project_stat_to_baseline(
                    value, source_league, target_league, stat_name
                )
                # Add projected value as new column
                result[f"{stat_name}_projected"] = projection["projected_value"]
                result[f"{stat_name}_confidence"] = projection["confidence"]
    
    return result


def compare_players_cross_league(
    player_a: pd.Series,
    player_b: pd.Series,
    target_league: str = "Premier League",
    stats: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Create a comparison DataFrame between two players from different leagues.
    
    Args:
        player_a: First player data
        player_b: Second player data
        target_league: League to normalize both players to
        stats: List of stats to compare
        
    Returns:
        DataFrame with comparison columns
    """
    if stats is None:
        stats = ["goals_per90", "expectedGoals_per90", "assists_per90", "expectedAssists_per90"]
    
    comparison_data = []
    
    for stat in stats:
        row = {"stat": stat}
        
        # Player A
        if stat in player_a.index:
            proj_a = project_stat_to_baseline(
                player_a[stat], 
                player_a.get("league_name", "Unknown"), 
                target_league, 
                stat
            )
            row["player_a_raw"] = proj_a["original_value"]
            row["player_a_projected"] = proj_a["projected_value"]
            row["player_a_league"] = proj_a["source_league"]
        else:
            row["player_a_raw"] = None
            row["player_a_projected"] = None
            row["player_a_league"] = player_a.get("league_name", "Unknown")
        
        # Player B
        if stat in player_b.index:
            proj_b = project_stat_to_baseline(
                player_b[stat], 
                player_b.get("league_name", "Unknown"), 
                target_league, 
                stat
            )
            row["player_b_raw"] = proj_b["original_value"]
            row["player_b_projected"] = proj_b["projected_value"]
            row["player_b_league"] = proj_b["source_league"]
        else:
            row["player_b_raw"] = None
            row["player_b_projected"] = None
            row["player_b_league"] = player_b.get("league_name", "Unknown")
        
        # Difference
        if row["player_a_projected"] is not None and row["player_b_projected"] is not None:
            row["difference"] = row["player_a_projected"] - row["player_b_projected"]
            row["advantage"] = "A" if row["difference"] > 0 else "B" if row["difference"] < 0 else "Tie"
        else:
            row["difference"] = None
            row["advantage"] = "N/A"
        
        comparison_data.append(row)
    
    return pd.DataFrame(comparison_data)


# Phase 2: Historical Transfer Analysis

def analyze_transfer_effects(
    team_lookup: pd.DataFrame,
    season_stats: pd.DataFrame,
    min_minutes_before: float = 450,
    min_minutes_after: float = 450,
) -> pd.DataFrame:
    """
    Infer transfers from team changes and compute performance deltas.

    Uses team_lookup (player_id, season, competition_slug -> team) to detect
    when a player's team changed between consecutive seasons. Merges with
    season_stats to get before/after stats and computes deltas.

    Args:
        team_lookup: DataFrame with columns player_id, season, competition_slug, team
        season_stats: DataFrame with player_id, season, competition_slug and stat columns
        min_minutes_before: Minimum total_minutes in from_season to include
        min_minutes_after: Minimum total_minutes in to_season to include

    Returns:
        DataFrame of transfer records with from_*/to_* and stat deltas
    """
    if team_lookup.empty or season_stats.empty:
        return pd.DataFrame()

    required = ["player_id", "season", "competition_slug", "team"]
    if not all(c in team_lookup.columns for c in required):
        return pd.DataFrame()

    lookup = team_lookup.sort_values(["player_id", "season", "competition_slug"]).drop_duplicates(
        subset=["player_id", "season", "competition_slug"], keep="first"
    )
    lookup["season_ord"] = pd.to_numeric(lookup["season"].astype(str).str.replace("-", "").str[:4], errors="coerce")

    # Build prev_team: same player, same comp, previous season
    lookup = lookup.sort_values(["player_id", "competition_slug", "season_ord"])
    lookup["prev_season"] = lookup.groupby(["player_id", "competition_slug"])["season"].shift(1)
    lookup["prev_team"] = lookup.groupby(["player_id", "competition_slug"])["team"].shift(1)

    transfers = lookup[
        lookup["prev_team"].notna()
        & (lookup["team"] != lookup["prev_team"])
        & (lookup["team"].astype(str).str.strip() != "")
        & (lookup["prev_team"].astype(str).str.strip() != "")
    ].copy()
    transfers = transfers.rename(columns={
        "season": "to_season",
        "competition_slug": "to_comp",
        "team": "to_team",
    })
    transfers["from_season"] = transfers["prev_season"]
    transfers["from_comp"] = transfers["to_comp"]
    transfers["from_team"] = transfers["prev_team"]
    transfers = transfers[["player_id", "from_season", "to_season", "from_comp", "to_comp", "from_team", "to_team"]].drop_duplicates()

    # Merge with season stats for before/after
    id_cols = ["player_id", "season", "competition_slug"]
    stats_cols = [c for c in season_stats.columns if c not in id_cols]
    before = season_stats.rename(columns={
        "season": "from_season", "competition_slug": "from_comp",
        **{c: f"before_{c}" for c in stats_cols},
    })
    after = season_stats.rename(columns={
        "season": "to_season", "competition_slug": "to_comp",
        **{c: f"after_{c}" for c in stats_cols},
    })

    t = transfers.merge(
        before,
        on=["player_id", "from_season", "from_comp"],
        how="inner",
    )
    t = t.merge(
        after,
        on=["player_id", "to_season", "to_comp"],
        how="inner",
    )

    # Filter by minutes
    if "before_total_minutes" in t.columns and "after_total_minutes" in t.columns:
        t = t[
            (t["before_total_minutes"].fillna(0) >= min_minutes_before)
            & (t["after_total_minutes"].fillna(0) >= min_minutes_after)
        ]
    if "before_avg_rating" in t.columns and "after_avg_rating" in t.columns:
        t["delta_rating"] = t["after_avg_rating"] - t["before_avg_rating"]
    for col in stats_cols:
        b, a = f"before_{col}", f"after_{col}"
        if b in t.columns and a in t.columns and t[b].dtype in (np.floating, np.int_, np.int64):
            t[f"delta_{col}"] = t[a] - t[b]

    return t


def calculate_league_adjustment_factors_from_transfers(
    transfer_data: pd.DataFrame,
    stat_columns: Optional[List[str]] = None,
    position_column: str = "before_player_position",
) -> Dict[str, float]:
    """
    Compute league adjustment factors from transfer deltas.

    For each (from_comp, to_comp) and optionally position, computes median
    ratio (after/before) or delta for key stats. Returns a flat dict keyed
    by "from_comp|to_comp|position|stat" for lookup.

    Args:
        transfer_data: Output from analyze_transfer_effects()
        stat_columns: Stats to compute factors for (e.g. goals_per90, avg_rating)
        position_column: Column name for position (if present)

    Returns:
        Dict mapping "from_comp|to_comp|pos|stat" -> adjustment factor (ratio or scale)
    """
    if transfer_data.empty:
        return {}

    stat_columns = stat_columns or ["avg_rating", "goals_per90", "assists_per90"]
    factors = {}
    for stat in stat_columns:
        before_col = f"before_{stat}"
        after_col = f"after_{stat}"
        delta_col = f"delta_{stat}"
        if before_col not in transfer_data.columns or after_col not in transfer_data.columns:
            continue
        df = transfer_data.copy()
        df["ratio"] = np.where(
            df[before_col].fillna(0) != 0,
            df[after_col] / df[before_col].replace(0, np.nan),
            np.nan,
        )
        df = df.dropna(subset=["ratio"])
        if position_column in df.columns:
            for (from_comp, to_comp, pos), g in df.groupby(["from_comp", "to_comp", position_column]):
                med = g["ratio"].median()
                if np.isfinite(med):
                    factors[f"{from_comp}|{to_comp}|{pos}|{stat}"] = float(med)
        else:
            for (from_comp, to_comp), g in df.groupby(["from_comp", "to_comp"]):
                med = g["ratio"].median()
                if np.isfinite(med):
                    factors[f"{from_comp}|{to_comp}|all|{stat}"] = float(med)
    return factors


def save_adjustment_factors(
    factors: Dict,
    filepath: str = "data/processed/league_adjustment_factors.json"
) -> None:
    """Save calculated adjustment factors to disk."""
    import json
    import pathlib
    
    path = pathlib.Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump(factors, f, indent=2)


def load_adjustment_factors(
    filepath: str = "data/processed/league_adjustment_factors.json"
) -> Optional[Dict]:
    """Load calculated adjustment factors from disk."""
    import json
    import pathlib
    
    path = pathlib.Path(filepath)
    if path.exists():
        with open(path, 'r') as f:
            return json.load(f)
    return None
