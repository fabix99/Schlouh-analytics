"""Calculate tactical fit between player and team.

Provides scoring system to evaluate how well a player fits a team's
tactical system, based on statistical similarity, squad gap analysis,
and style alignment.
"""

from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np


def calculate_statistical_similarity(
    player_data: pd.Series,
    team_data: pd.Series,
    position: str,
    stats: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Calculate how similar a player's stats are to a team's average for that position.
    
    Args:
        player_data: Player statistics
        team_data: Team statistics (including position averages)
        position: Player position (F, M, D, G)
        stats: List of stats to compare (None = auto-select by position)
        
    Returns:
        Dictionary with similarity score and breakdown
    """
    if stats is None:
        # Position-specific stats
        position_stats = {
            "F": ["goals_per90", "expectedGoals_per90", "shots_per90", "assists_per90", "keyPass_per90"],
            "M": ["pass_accuracy", "keyPass_per90", "duelWon_per90", "interceptionWon_per90", "expectedAssists_per90"],
            "D": ["duelWon_per90", "interceptionWon_per90", "totalTackle_per90", "pass_accuracy", "aerialWon_per90"],
            "G": ["saves_per90", "goalsPrevented_per90"]
        }
        stats = position_stats.get(position, ["goals_per90", "assists_per90", "pass_accuracy"])
    
    similarities = []
    breakdown = {}
    
    for stat in stats:
        player_val = player_data.get(stat, np.nan)
        team_key = f"{position}_{stat}_avg" if f"{position}_{stat}_avg" in team_data else stat
        team_val = team_data.get(team_key, np.nan)
        
        if pd.notna(player_val) and pd.notna(team_val) and team_val > 0:
            # Calculate relative difference
            diff = abs(player_val - team_val) / team_val
            sim = max(0, 1 - diff)  # 1 = identical, 0 = very different
            similarities.append(sim)
            breakdown[stat] = {
                "player_value": player_val,
                "team_average": team_val,
                "similarity": sim
            }
    
    if similarities:
        overall = np.mean(similarities)
    else:
        overall = 0.5  # Neutral if no data
    
    return {
        "score": overall * 100,
        "stat_count": len(similarities),
        "breakdown": breakdown
    }


def calculate_squad_gap_fill(
    player_data: pd.Series,
    team_data: pd.Series,
    position: str,
    team_players: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Calculate how much this player would improve the squad at their position.
    
    Args:
        player_data: Player statistics
        team_data: Team statistics
        position: Player position
        team_players: DataFrame of current team players at this position
        
    Returns:
        Dictionary with gap fill score and explanation
    """
    # Key stats for gap analysis by position
    key_stats = {
        "F": ["goals_per90", "expectedGoals_per90"],
        "M": ["keyPass_per90", "expectedAssists_per90", "duelWon_per90"],
        "D": ["duelWon_per90", "interceptionWon_per90", "totalTackle_per90"],
        "G": ["saves_per90", "goalsPrevented_per90"]
    }
    
    position_key_stats = key_stats.get(position, ["goals_per90"])
    
    # Get team current average for position
    team_averages = {}
    for stat in position_key_stats:
        team_key = f"{position}_{stat}_avg"
        if team_key in team_data:
            team_averages[stat] = team_data[team_key]
        elif stat in team_data:
            team_averages[stat] = team_data[stat]
    
    if not team_averages:
        return {
            "score": 50,
            "explanation": "No team baseline available for comparison",
            "improvements": {}
        }
    
    # Calculate improvements
    improvements = {}
    for stat, team_avg in team_averages.items():
        player_val = player_data.get(stat, 0)
        if team_avg > 0:
            improvement = (player_val - team_avg) / team_avg
            improvements[stat] = {
                "player_value": player_val,
                "team_average": team_avg,
                "improvement_pct": improvement * 100
            }
    
    # Overall gap fill score
    if improvements:
        avg_improvement = np.mean([v["improvement_pct"] for v in improvements.values()])
        # Score: 50 = no change, 100 = 50% improvement, 0 = 50% worse
        score = 50 + avg_improvement
        score = max(0, min(100, score))
    else:
        score = 50
        avg_improvement = 0
    
    # Generate explanation
    if avg_improvement > 20:
        explanation = f"Significant upgrade: {avg_improvement:.0f}% better than current squad"
    elif avg_improvement > 5:
        explanation = f"Solid upgrade: {avg_improvement:.0f}% better than current squad"
    elif avg_improvement > -5:
        explanation = "Similar level to current squad"
    else:
        explanation = f"Below current squad level: {abs(avg_improvement):.0f}% worse"
    
    return {
        "score": score,
        "explanation": explanation,
        "improvements": improvements,
        "avg_improvement_pct": avg_improvement
    }


def calculate_style_alignment(
    player_data: pd.Series,
    team_tactical_profile: pd.Series,
    position: str
) -> Dict[str, Any]:
    """
    Calculate how well a player's strengths align with team tactics.
    
    Args:
        player_data: Player statistics
        team_tactical_profile: Team tactical indices (possession, pressing, etc.)
        position: Player position
        
    Returns:
        Dictionary with alignment score and explanation
    """
    # Define what player stats matter for each tactical style
    style_requirements = {
        "possession_index": {
            "important_stats": ["pass_accuracy", "keyPass_per90", "dribbleSuccess"],
            "thresholds": {"pass_accuracy": 80, "keyPass_per90": 1.5}
        },
        "pressing_index": {
            "important_stats": ["ballRecovery_per90", "totalTackle_per90", "interceptionWon_per90"],
            "thresholds": {"ballRecovery_per90": 5, "totalTackle_per90": 2}
        },
        "directness_index": {
            "important_stats": ["expectedGoals_per90", "shots_per90", "duelWon_per90"],
            "thresholds": {"expectedGoals_per90": 0.25, "duelWon_per90": 8}
        },
        "aerial_index": {
            "important_stats": ["aerialWon_per90", "aerialWonRate"],
            "thresholds": {"aerialWon_per90": 2, "aerialWonRate": 50}
        }
    }
    
    team_style_scores = {}
    alignments = []
    
    for style, requirements in style_requirements.items():
        team_score = team_tactical_profile.get(style, 50)  # 0-100 scale
        
        # Calculate player score for this style
        player_style_score = 0
        stat_count = 0
        
        for stat in requirements["important_stats"]:
            if stat in player_data:
                val = player_data[stat]
                threshold = requirements["thresholds"].get(stat, 0)
                if threshold > 0:
                    # Score based on how much they exceed threshold
                    stat_score = min(100, (val / threshold) * 50)
                    player_style_score += stat_score
                    stat_count += 1
        
        if stat_count > 0:
            player_style_score /= stat_count
            
            # Alignment = how well player score matches team emphasis
            # If team values possession highly (80+), player needs high passing stats
            # If team doesn't value possession (low), any passing level is fine
            if team_score > 70:  # Team emphasizes this style
                alignment = player_style_score / 100  # 0-1 based on player capability
            elif team_score > 40:  # Moderate emphasis
                alignment = 0.7 + (player_style_score / 100) * 0.3  # Prefer capability but flexible
            else:  # Low emphasis
                alignment = 0.9  # Don't penalize for low capability if team doesn't value it
            
            team_style_scores[style] = {
                "team_emphasis": team_score,
                "player_capability": player_style_score,
                "alignment": alignment
            }
            alignments.append(alignment)
    
    # Overall alignment score
    if alignments:
        overall = np.mean(alignments) * 100
    else:
        overall = 70  # Neutral default
    
    # Generate explanation
    top_emphasis = max(team_style_scores.items(), key=lambda x: x[1]["team_emphasis"])
    style_name = top_emphasis[0].replace("_index", "").title()
    
    if overall > 85:
        explanation = f"Excellent fit: Player excels at {style_name}, which team prioritizes"
    elif overall > 70:
        explanation = f"Good fit: Player matches {style_name} style team values"
    elif overall > 50:
        explanation = f"Moderate fit: Player acceptable but not ideal for {style_name} system"
    else:
        explanation = f"Poor fit: Player lacks key attributes for {style_name} system"
    
    return {
        "score": overall,
        "explanation": explanation,
        "style_breakdown": team_style_scores
    }


def calculate_fit_score(
    player_data: pd.Series,
    team_data: pd.Series,
    team_tactical_profile: pd.Series,
    position: str,
    team_players: Optional[pd.DataFrame] = None,
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive tactical fit score between player and team.
    
    Combines statistical similarity, squad gap fill, and style alignment
    into an overall fit score with detailed breakdown.
    
    Args:
        player_data: Player statistics
        team_data: Team statistics
        team_tactical_profile: Team tactical indices
        position: Player position (F, M, D, G)
        team_players: Current team players at position (for gap analysis)
        weights: Custom weights for components (default: equal weighting)
        
    Returns:
        Dictionary with:
            - overall_score: 0-100 overall fit
            - components: Individual component scores
            - explanation: Human-readable summary
            - recommendation: Specific recommendation
            - confidence: Confidence in assessment (0-1)
    """
    # Default weights
    if weights is None:
        weights = {
            "statistical_similarity": 0.35,
            "squad_gap_fill": 0.40,
            "style_alignment": 0.25
        }
    
    # Calculate components
    sim_result = calculate_statistical_similarity(player_data, team_data, position)
    gap_result = calculate_squad_gap_fill(player_data, team_data, position, team_players)
    style_result = calculate_style_alignment(player_data, team_tactical_profile, position)
    
    # Weighted overall score
    overall = (
        sim_result["score"] * weights["statistical_similarity"] +
        gap_result["score"] * weights["squad_gap_fill"] +
        style_result["score"] * weights["style_alignment"]
    )
    
    # Confidence based on data completeness
    data_points = (
        sim_result.get("stat_count", 0) +
        len(gap_result.get("improvements", {})) +
        len(style_result.get("style_breakdown", {}))
    )
    confidence = min(0.95, 0.5 + data_points * 0.05)
    
    # Generate recommendation
    if overall >= 85:
        recommendation = "Strong recommendation: Ideal fit for tactical system"
    elif overall >= 70:
        recommendation = "Recommended: Good fit with room to integrate"
    elif overall >= 55:
        recommendation = "Conditional: Requires tactical adaptation or specific role"
    else:
        recommendation = "Not recommended: Significant style or capability mismatch"
    
    # Summary explanation
    explanations = [
        f"Statistical match: {sim_result['score']:.0f}/100",
        f"Squad upgrade: {gap_result['explanation']}",
        f"Style fit: {style_result['explanation']}"
    ]
    
    return {
        "overall_score": overall,
        "confidence": confidence,
        "grade": _score_to_grade(overall),
        "components": {
            "statistical_similarity": sim_result,
            "squad_gap_fill": gap_result,
            "style_alignment": style_result
        },
        "weights_used": weights,
        "explanation": " | ".join(explanations),
        "recommendation": recommendation,
        "position": position
    }


def _score_to_grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A+"
    elif score >= 85:
        return "A"
    elif score >= 80:
        return "A-"
    elif score >= 75:
        return "B+"
    elif score >= 70:
        return "B"
    elif score >= 65:
        return "B-"
    elif score >= 60:
        return "C+"
    elif score >= 55:
        return "C"
    elif score >= 50:
        return "C-"
    else:
        return "D"


def compare_fit_scores(
    players: List[pd.Series],
    team_data: pd.Series,
    team_tactical_profile: pd.Series,
    position: str
) -> pd.DataFrame:
    """
    Compare fit scores for multiple player candidates.
    
    Args:
        players: List of player data Series
        team_data: Team statistics
        team_tactical_profile: Team tactical indices
        position: Position to evaluate for
        
    Returns:
        DataFrame comparing all players
    """
    results = []
    
    for player in players:
        fit = calculate_fit_score(player, team_data, team_tactical_profile, position)
        
        results.append({
            "player_name": player.get("player_name", "Unknown"),
            "player_id": player.get("player_id", 0),
            "overall_score": fit["overall_score"],
            "grade": fit["grade"],
            "statistical_similarity": fit["components"]["statistical_similarity"]["score"],
            "squad_gap_fill": fit["components"]["squad_gap_fill"]["score"],
            "style_alignment": fit["components"]["style_alignment"]["score"],
            "recommendation": fit["recommendation"],
            "confidence": fit["confidence"]
        })
    
    return pd.DataFrame(results).sort_values("overall_score", ascending=False)


def format_fit_score_for_display(fit_result: Dict[str, Any]) -> str:
    """Format fit score as HTML for display."""
    score = fit_result["overall_score"]
    grade = fit_result["grade"]
    
    # Color based on score
    if score >= 80:
        color = "#3FB950"  # Green
    elif score >= 60:
        color = "#C9A840"  # Gold
    else:
        color = "#F85149"  # Red
    
    return f"""
    <div style="
        background:rgba({"59,185,80" if score >= 70 else "248,81,73"},0.1);
        border:1px solid {color}40;
        border-radius:8px;
        padding:12px;
        margin:8px 0;
    ">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
            <span style="font-weight:600;color:#F0F6FC;">Tactical Fit</span>
            <span style="font-size:1.5rem;font-weight:700;color:{color};">{grade}</span>
        </div>
        <div style="background:#21262D;border-radius:4px;height:6px;margin-bottom:8px;">
            <div style="background:{color};border-radius:4px;height:6px;width:{score}%"></div>
        </div>
        <div style="font-size:0.85rem;color:#8B949E;margin-bottom:4px;">
            {fit_result["explanation"]}
        </div>
        <div style="font-size:0.8rem;color:{color};font-weight:500;">
            {fit_result["recommendation"]}
        </div>
    </div>
    """
