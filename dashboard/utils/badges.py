"""ML-powered and rule-based player badges.

Badges provide quick visual indicators of player characteristics
for scouting reports. Phase 1 uses rule-based logic; Phase 2
will incorporate ML models trained on inferred transfer success.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import pandas as pd
import numpy as np


@dataclass
class Badge:
    """Represents a player badge/scouting indicator."""
    id: str
    name: str
    icon: str
    description: str
    is_positive: bool
    confidence: float  # 0-1, for ML-based badges
    category: str  # 'performance', 'personality', 'potential', 'risk'


# Badge definitions with rules for Phase 1
# Phase 2 will add ML confidence scores based on transfer success patterns
BADGE_DEFINITIONS = {
    # Positive performance badges (use enriched season stats + optional consistency/opponent)
    "elite_rating": {
        "name": "Elite Rating",
        "icon": "⭐",
        "description": "Season rating among the best in the pool",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (p.get("avg_rating") or 0) >= 7.5
    },
    "big_game_player": {
        "name": "Big Game Player",
        "icon": "🔥",
        "description": "Elevates performance against top opposition",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: p.get("big_game_ratio", 1.0) > 1.2
    },
    "consistent": {
        "name": "Consistent",
        "icon": "📊",
        "description": "Highly consistent week-to-week performance",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (p.get("cv_rating") or p.get("rating_cv") or 1.0) < 0.10
    },
    # Potential badges
    "rising_talent": {
        "name": "Rising Talent",
        "icon": "🚀",
        "description": "Young player with elite output for age",
        "is_positive": True,
        "category": "potential",
        "rule": lambda p, ctx: (p.get("age_at_season_start") or p.get("age") or 30) <= 22 and (p.get("avg_rating") or 0) >= 7.2
    },
    "breakout_season": {
        "name": "Breakout Season",
        "icon": "⭐",
        "description": "Significant improvement vs previous seasons",
        "is_positive": True,
        "category": "potential",
        "rule": lambda p, ctx: (p.get("progression_delta") or p.get("rating_delta") or 0) > 0.3
    },
    "late_bloomer": {
        "name": "Late Bloomer",
        "icon": "🌱",
        "description": "Improving with age, peak may be ahead",
        "is_positive": True,
        "category": "potential",
        "rule": lambda p, ctx: (p.get("age_at_season_start") or p.get("age") or 20) >= 25 and (p.get("trend_direction") or "flat") == "up"
    },
    
    # Personality/Style badges
    "technical": {
        "name": "Technical",
        "icon": "🎨",
        "description": "Excellent technique, skillful on the ball",
        "is_positive": True,
        "category": "personality",
        "rule": lambda p, ctx: (p.get("dribble_success_rate") or 0) > 0.60 and ((p.get("pass_accuracy_pct") or 0) > 85 or (float(p.get("pass_accuracy", 0) or 0) * 100) > 85)
    },
    "physical_dominant": {
        "name": "Physical Specimen",
        "icon": "💪",
        "description": "Wins duels through athletic advantage",
        "is_positive": True,
        "category": "personality",
        "rule": lambda p, ctx: (p.get("duel_win_rate") or p.get("duel_won_rate") or 0) > 0.60 and (p.get("aerial_win_rate") or p.get("aerial_won_rate") or 0) > 0.55
    },
    
    # Risk/negative badges
    "inconsistent": {
        "name": "Inconsistent",
        "icon": "⚠️",
        "description": "Performance varies significantly game-to-game",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("cv_rating") or p.get("rating_cv") or 0) > 0.25
    },
    "flat_track_bully": {
        "name": "Flat Track Bully",
        "icon": "📉",
        "description": "Stats come from weak opponents; struggles vs top teams",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: p.get("big_game_ratio", 1.0) < 0.8
    },
    "age_concern": {
        "name": "Age Concern",
        "icon": "⏰",
        "description": "May be past peak or approaching decline",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("age_at_season_start") or p.get("age") or 25) >= 30 and (p.get("minutes_decline") is True)
    },
    "experienced": {
        "name": "Experienced",
        "icon": "🧠",
        "description": "Many seasons at high level, proven durability",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (p.get("seasons_at_level") or 0) >= 5 and (p.get("appearances_career") or 0) > 100
    },
    # --- Stats-based badges (available for any player when they meet the bar) ---
    "high_scorer": {
        "name": "High Scorer",
        "icon": "⚽",
        "description": "Strong goal output per 90",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("goals_per90") or 0)) > 0.35
    },
    "goal_threat": {
        "name": "Goal Threat",
        "icon": "🎯",
        "description": "High expected goals per 90",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("expectedGoals_per90") or 0)) > 0.25
    },
    "creative": {
        "name": "Creative",
        "icon": "✨",
        "description": "Creates chances (key passes and xA)",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("keyPass_per90") or 0)) > 2.0 or (float(p.get("expectedAssists_per90") or 0)) > 0.15
    },
    "playmaker": {
        "name": "Playmaker",
        "icon": "🎭",
        "description": "Consistent chance creation and assist threat",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("keyPass_per90") or 0)) > 1.5 and (float(p.get("expectedAssists_per90") or 0)) > 0.10
    },
    "ball_winner": {
        "name": "Ball Winner",
        "icon": "🛡️",
        "description": "High tackle and interception output",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("totalTackle_per90") or 0)) + (float(p.get("interceptionWon_per90") or 0)) > 3.0
    },
    "ball_carrier": {
        "name": "Ball Carrier",
        "icon": "🏃",
        "description": "High ball recoveries and duels won per 90",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("ballRecovery_per90") or 0)) > 5.0 or (float(p.get("duelWon_per90") or 0)) > 6.0
    },
    "reliable_passer": {
        "name": "Reliable Passer",
        "icon": "📋",
        "description": "Very high pass completion",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("pass_accuracy_pct") or 0) > 88) or (float(p.get("pass_accuracy") or 0) * 100 > 88)
    },
    "aerial_presence": {
        "name": "Aerial Presence",
        "icon": "🦅",
        "description": "Wins a high share of aerial duels",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (p.get("aerial_win_rate") or 0) > 0.55 and (float(p.get("aerialWon_per90") or 0)) > 1.0
    },
    "veteran_quality": {
        "name": "Veteran Quality",
        "icon": "🌟",
        "description": "Older player still performing at a high level",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (p.get("age_at_season_start") or 0) >= 28 and (p.get("avg_rating") or 0) >= 7.0
    },
    "high_volume_season": {
        "name": "High Volume",
        "icon": "📊",
        "description": "Substantial minutes this season (reliable sample)",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (p.get("total_minutes") or 0) >= 2000
    },
    # --- More positive (scout-relevant) ---
    "shot_volume": {
        "name": "Shot Volume",
        "icon": "🎯",
        "description": "High shot output per 90",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("totalShots_per90") or 0)) > 2.5
    },
    "chance_creator": {
        "name": "Chance Creator",
        "icon": "🔑",
        "description": "Creates big chances for others",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("bigChanceCreated_per90") or 0)) > 0.15
    },
    "progressive_carrier": {
        "name": "Progressive Carrier",
        "icon": "➡️",
        "description": "Meaningful progressive carries per 90",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("progressiveBallCarriesCount_per90") or 0)) > 0.8 or (float(p.get("totalProgressiveBallCarriesDistance_per90") or 0)) > 15
    },
    "on_target_shooter": {
        "name": "Accurate Shooter",
        "icon": "🎪",
        "description": "High share of shots on target",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (float(p.get("totalShots_per90") or 0)) > 1.0 and (float(p.get("onTargetScoringAttempt_per90") or 0)) / max(0.01, float(p.get("totalShots_per90") or 0)) > 0.4
    },
    "clean_rating": {
        "name": "Strong Season",
        "icon": "✅",
        "description": "Rating 7.0+ with meaningful minutes",
        "is_positive": True,
        "category": "performance",
        "rule": lambda p, ctx: (p.get("avg_rating") or 0) >= 7.0 and (p.get("total_minutes") or 0) >= 900
    },

    # --- Negative / concern badges (scout risk view) ---
    "discipline_risk": {
        "name": "Discipline Risk",
        "icon": "🟨",
        "description": "High card count this season",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("yellow_cards") or 0) >= 8 or (p.get("red_cards") or 0) >= 1
    },
    "limited_sample": {
        "name": "Limited Sample",
        "icon": "📉",
        "description": "Few minutes this season; stats less reliable",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("total_minutes") or 0) > 0 and (p.get("total_minutes") or 0) < 450
    },
    "low_goal_threat": {
        "name": "Low Goal Threat",
        "icon": "⚠️",
        "description": "Very low goal and xG output (attacking roles)",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("player_position") or "F") in ("F", "M") and (float(p.get("goals_per90") or 0)) < 0.1 and (float(p.get("expectedGoals_per90") or 0)) < 0.12 and (p.get("total_minutes") or 0) >= 450
    },
    "loose_passer": {
        "name": "Loose Passer",
        "icon": "❌",
        "description": "Below-average pass completion",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (float(p.get("pass_accuracy_pct") or 0) < 75) or (float(p.get("pass_accuracy") or 0) * 100 < 75)
    },
    "big_chance_waster": {
        "name": "Big Chance Waster",
        "icon": "😬",
        "description": "High big chances missed vs conversion",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (float(p.get("bigChanceMissed_per90") or 0)) > 0.2 and (float(p.get("goals_per90") or 0)) < 0.4
    },
    "frequent_fouler": {
        "name": "Frequent Fouler",
        "icon": "🤚",
        "description": "High foul rate per 90",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (float(p.get("fouls_per90") or 0)) > 2.0
    },
    "loose_in_possession": {
        "name": "Loose in Possession",
        "icon": "🔄",
        "description": "Often dispossessed or loses ball in control",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (float(p.get("dispossessed_per90") or 0)) > 2.0 or (float(p.get("possessionLostCtrl_per90") or 0)) > 17
    },
    "declining_trend": {
        "name": "Declining Trend",
        "icon": "📉",
        "description": "Rating trend down vs previous season",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("trend_direction") or "") == "down"
    },
    "weak_aerially": {
        "name": "Weak in the Air",
        "icon": "🦅",
        "description": "Low aerial duel win rate",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("aerial_win_rate") or 1) < 0.40 and (float(p.get("aerialWon_per90") or 0)) + (float(p.get("aerialLost_per90") or 0)) > 0.5
    },
    "low_creative_output": {
        "name": "Low Creative Output",
        "icon": "🔇",
        "description": "Minimal key passes and xA (creative roles)",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("player_position") or "F") in ("F", "M") and (float(p.get("keyPass_per90") or 0)) < 0.5 and (float(p.get("expectedAssists_per90") or 0)) < 0.05 and (p.get("total_minutes") or 0) >= 450
    },
    "below_par_rating": {
        "name": "Below-Par Rating",
        "icon": "📊",
        "description": "Season rating below 6.5 with meaningful minutes",
        "is_positive": False,
        "category": "risk",
        "rule": lambda p, ctx: (p.get("avg_rating") or 7) < 6.5 and (p.get("total_minutes") or 0) >= 900
    },
}


def calculate_badges(
    player_data: pd.Series,
    context_data: Optional[pd.DataFrame] = None
) -> List[Badge]:
    """
    Calculate all applicable badges for a player.
    
    Args:
        player_data: Series with player statistics
        context_data: Optional DataFrame for league/position context averages
        
    Returns:
        List of Badge objects applicable to this player
    """
    badges = []
    
    # Build context dictionary with league/position averages
    context = {}
    if context_data is not None and not context_data.empty:
        # Calculate context averages for comparison
        context["avg_decisive"] = context_data.get("decisive_actions_per90", pd.Series([0.3])).mean()
        context["avg_distance"] = context_data.get("distance_covered_per90", pd.Series([10])).mean()
    
    # Apply each badge rule
    for badge_id, definition in BADGE_DEFINITIONS.items():
        try:
            rule_func = definition["rule"]
            if rule_func(player_data, context):
                badges.append(Badge(
                    id=badge_id,
                    name=definition["name"],
                    icon=definition["icon"],
                    description=definition["description"],
                    is_positive=definition["is_positive"],
                    confidence=0.75,  # Phase 1: fixed confidence
                    category=definition["category"]
                ))
        except Exception as e:
            # Skip badges that can't be calculated (missing data)
            continue
    
    return badges


def get_badge_summary(badges: List[Badge]) -> Dict[str, Any]:
    """
    Summarize a player's badges by category.
    
    Returns dict with counts and key badges by category.
    """
    summary = {
        "total": len(badges),
        "positive": len([b for b in badges if b.is_positive]),
        "negative": len([b for b in badges if not b.is_positive]),
        "by_category": {}
    }
    
    for badge in badges:
        cat = badge.category
        if cat not in summary["by_category"]:
            summary["by_category"][cat] = []
        summary["by_category"][cat].append(badge)
    
    return summary


def format_badge_for_display(badge: Badge) -> str:
    """Format a badge as HTML for display. Single-line to avoid markdown treating it as a code block."""
    color = "#3FB950" if badge.is_positive else "#F85149"
    rgba = "59,185,80" if badge.is_positive else "248,81,73"
    desc = (badge.description or "").replace('"', "&quot;")
    return f'<span style="display:inline-flex;align-items:center;background:rgba({rgba},0.15);color:{color};padding:4px 10px;border-radius:12px;font-size:0.85rem;margin:2px;border:1px solid {color}40;" title="{desc}">{badge.icon} {badge.name}</span>'


# Phase 2: ML and transfer-inferred features

def infer_transfer_success_features(
    team_lookup: Optional[pd.DataFrame] = None,
    season_stats: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Infer transfers from team changes and attach before/after stats + success label.

    Uses team_lookup (player_id, season, competition_slug -> team) and season_stats
    to build transfer records. Success is heuristically: rating delta >= -0.3 and
    after_minutes >= 0.4 * before_minutes (maintained meaningful game time).

    Args:
        team_lookup: Optional; if None, loaded via dashboard.utils.data.load_team_lookup()
        season_stats: Optional; if None, loaded via dashboard.utils.data.load_player_season_stats()

    Returns:
        DataFrame of inferred transfers with before_*/after_*, delta_*, and success (0/1)
    """
    from dashboard.utils.projections import analyze_transfer_effects

    if team_lookup is None or season_stats is None:
        try:
            from dashboard.utils.data import load_team_lookup, load_player_season_stats
            team_lookup = team_lookup if team_lookup is not None else load_team_lookup()
            season_stats = season_stats if season_stats is not None else load_player_season_stats()
        except Exception:
            return pd.DataFrame()

    transfers = analyze_transfer_effects(
        team_lookup=team_lookup,
        season_stats=season_stats,
        min_minutes_before=450,
        min_minutes_after=270,
    )
    if transfers.empty:
        return transfers

    # Heuristic success: maintained or improved rating and kept material minutes
    rating_ok = transfers.get("delta_rating", pd.Series(0)).fillna(0) >= -0.3
    before_mins = transfers.get("before_total_minutes", pd.Series(0)).fillna(0)
    after_mins = transfers.get("after_total_minutes", pd.Series(0)).fillna(0)
    minutes_ok = (before_mins <= 0) | (after_mins >= 0.4 * before_mins)
    transfers["success"] = (rating_ok & minutes_ok).astype(int)
    return transfers


def train_badge_ml_model(
    transfer_data: pd.DataFrame,
    success_labels: Optional[pd.Series] = None,
    feature_columns: Optional[List[str]] = None,
) -> Any:
    """
    Train a simple classifier to predict transfer success from pre-transfer stats.

    Uses inferred transfer data with before_* stats as features. If success_labels
    is not provided, uses the "success" column from transfer_data when present.

    Args:
        transfer_data: DataFrame with before_* stat columns and optionally "success"
        success_labels: Optional 0/1 labels; default uses transfer_data["success"]
        feature_columns: Optional list of before_* column names to use as features

    Returns:
        Trained sklearn classifier (or None if insufficient data)
    """
    try:
        from sklearn.ensemble import RandomForestClassifier
    except ImportError:
        return None

    if transfer_data.empty or len(transfer_data) < 20:
        return None

    labels = success_labels
    if labels is None and "success" in transfer_data.columns:
        labels = transfer_data["success"]
    if labels is None or labels.empty:
        return None

    before_cols = [c for c in transfer_data.columns if c.startswith("before_") and c not in ("before_season", "before_comp", "before_team")]
    numeric_before = [c for c in before_cols if transfer_data[c].dtype in (np.floating, np.int_, np.int64)]
    feature_columns = feature_columns or numeric_before[:15]
    feature_columns = [c for c in feature_columns if c in transfer_data.columns]
    if len(feature_columns) < 2:
        return None

    X = transfer_data[feature_columns].fillna(0)
    y = labels.astype(int).values
    if len(np.unique(y)) < 2:
        return None

    clf = RandomForestClassifier(n_estimators=50, max_depth=6, random_state=42)
    clf.fit(X, y)
    return clf
