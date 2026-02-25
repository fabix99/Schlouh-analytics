"""Shared constants for the dashboard."""

# ---------------------------------------------------------------------------
# Season and competition scope (default: current season, leagues + UEFA only)
# ---------------------------------------------------------------------------
# Current season used as default across Scouts, Tactics, and Review.
CURRENT_SEASON = "2025-26"

# Domestic leagues (no cups). Default scope includes these + UEFA competitions.
LEAGUE_SLUGS = [
    "england-premier-league",
    "spain-laliga",
    "italy-serie-a",
    "france-ligue-1",
    "germany-bundesliga",
    "portugal-primeira-liga",
    "belgium-pro-league",
    "netherlands-eredivisie",
    "turkey-super-lig",
    "saudi-pro-league",
    "brazil-serie-a",
]

# UEFA European competitions (Champions League, Europa League, Conference League).
UEFA_COMPETITION_SLUGS = [
    "uefa-champions-league",
    "uefa-europa-league",
    "uefa-conference-league",
]

# Cup competitions (excluded from default scope).
CUP_SLUGS = [
    "england-fa-cup",
    "england-league-cup",
    "spain-copa-del-rey",
    "italy-coppa-italia",
    "germany-dfb-pokal",
    "netherlands-knvb-beker",
    "portugal-taca-de-portugal",
    "usa-open-cup",
]

# Default scope: leagues + UEFA only (no cups, no national teams).
# Use this to filter data when "default" or "current season only" is selected.
DEFAULT_COMPETITION_SLUGS = LEAGUE_SLUGS + UEFA_COMPETITION_SLUGS

COMP_NAMES = {
    "spain-laliga": "La Liga",
    "england-premier-league": "Premier League",
    "italy-serie-a": "Serie A",
    "france-ligue-1": "Ligue 1",
    "germany-bundesliga": "Bundesliga",
    "portugal-primeira-liga": "Primeira Liga",
    "belgium-pro-league": "Pro League",
    "netherlands-eredivisie": "Eredivisie",
    "turkey-super-lig": "Süper Lig",
    "saudi-pro-league": "Saudi Pro League",
    "england-fa-cup": "FA Cup",
    "england-league-cup": "League Cup",
    "spain-copa-del-rey": "Copa del Rey",
    "italy-coppa-italia": "Coppa Italia",
    "germany-dfb-pokal": "DFB-Pokal",
    "netherlands-knvb-beker": "KNVB Beker",
    "brazil-serie-a": "Serie A (BR)",
    "copa-libertadores": "Copa Libertadores",
    "uefa-champions-league": "Champions League",
    "uefa-europa-league": "Europa League",
    "uefa-conference-league": "Conference League",
    "uefa-super-cup": "UEFA Super Cup",
    "portugal-taca-de-portugal": "Taça de Portugal",
    "usa-open-cup": "US Open Cup",
}

COMP_FLAGS = {
    "spain-laliga": "🇪🇸",
    "england-premier-league": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "italy-serie-a": "🇮🇹",
    "france-ligue-1": "🇫🇷",
    "germany-bundesliga": "🇩🇪",
    "portugal-primeira-liga": "🇵🇹",
    "belgium-pro-league": "🇧🇪",
    "netherlands-eredivisie": "🇳🇱",
    "turkey-super-lig": "🇹🇷",
    "saudi-pro-league": "🇸🇦",
    "england-fa-cup": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "england-league-cup": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "spain-copa-del-rey": "🇪🇸",
    "italy-coppa-italia": "🇮🇹",
    "germany-dfb-pokal": "🇩🇪",
    "netherlands-knvb-beker": "🇳🇱",
    "brazil-serie-a": "🇧🇷",
    "copa-libertadores": "🌎",
    "uefa-champions-league": "🇪🇺",
    "uefa-europa-league": "🇪🇺",
    "uefa-conference-league": "🇪🇺",
    "uefa-super-cup": "🇪🇺",
    "portugal-taca-de-portugal": "🇵🇹",
    "usa-open-cup": "🇺🇸",
}

POSITION_NAMES = {
    "G": "Goalkeeper",
    "D": "Defender",
    "M": "Midfielder",
    "F": "Forward",
}

POSITION_ORDER = ["F", "M", "D", "G"]

# Core display columns for the scouting table
SCOUT_DISPLAY_COLS = {
    "player_name": "Player",
    "player_position": "Pos",
    "team": "Team",
    "league_name": "League",
    "season": "Season",
    "appearances": "Apps",
    "total_minutes": "Mins",
    "avg_rating": "Rating",
    "goals": "Goals",
    "assists": "Assists",
    "goals_per90": "G/90",
    "expectedGoals_per90": "xG/90",
    "expectedAssists_per90": "xA/90",
    "keyPass_per90": "KP/90",
    "bigChanceCreated_per90": "BCC/90",
    "totalTackle_per90": "Tkl/90",
    "interceptionWon_per90": "Int/90",
    "duelWon_per90": "DW/90",
    "aerialWon_per90": "Air/90",
    "ballRecovery_per90": "Rec/90",
}

# Stats available for "Top N" ranking
RANKING_STATS = {
    "avg_rating": "Avg Rating",
    "goals_per90": "Goals / 90",
    "expectedGoals_per90": "xG / 90",
    "expectedAssists_per90": "xA / 90",
    "goals": "Total Goals",
    "assists": "Total Assists",
    "keyPass_per90": "Key Passes / 90",
    "bigChanceCreated_per90": "Big Chances Created / 90",
    "totalTackle_per90": "Tackles / 90",
    "interceptionWon_per90": "Interceptions / 90",
    "duelWon_per90": "Duels Won / 90",
    "aerialWon_per90": "Aerial Wins / 90",
    "ballRecovery_per90": "Ball Recoveries / 90",
    "progressiveBallCarriesCount_per90": "Progressive Carries / 90",
    "totalPass_per90": "Passes / 90",
    "pass_accuracy_pct": "Pass Accuracy %",
    "saves_per90": "Saves / 90",
    "goalsPrevented_per90": "Goals Prevented / 90",
    "total_minutes": "Total Minutes",
}

# Radar chart stat groups by position
RADAR_STATS_BY_POSITION = {
    "F": [
        ("goals_per90", "Goals/90"),
        ("expectedGoals_per90", "xG/90"),
        ("expectedAssists_per90", "xA/90"),
        ("keyPass_per90", "Key Passes/90"),
        ("bigChanceCreated_per90", "Big Chances/90"),
        ("totalShots_per90", "Shots/90"),
        ("duelWon_per90", "Duels Won/90"),
        ("ballRecovery_per90", "Ball Recovery/90"),
    ],
    "M": [
        ("keyPass_per90", "Key Passes/90"),
        ("expectedAssists_per90", "xA/90"),
        ("bigChanceCreated_per90", "Big Chances/90"),
        ("totalPass_per90", "Passes/90"),
        ("ballRecovery_per90", "Ball Recovery/90"),
        ("totalTackle_per90", "Tackles/90"),
        ("interceptionWon_per90", "Interceptions/90"),
        ("duelWon_per90", "Duels Won/90"),
    ],
    "D": [
        ("totalTackle_per90", "Tackles/90"),
        ("interceptionWon_per90", "Interceptions/90"),
        ("totalClearance_per90", "Clearances/90"),
        ("aerialWon_per90", "Aerials Won/90"),
        ("duelWon_per90", "Duels Won/90"),
        ("ballRecovery_per90", "Ball Recovery/90"),
        ("pass_accuracy_pct", "Pass Accuracy %"),
        ("totalPass_per90", "Passes/90"),
    ],
    "G": [
        ("saves_per90", "Saves/90"),
        ("goalsPrevented_per90", "Goals Prevented/90"),
        ("savedShotsFromInsideTheBox_per90", "Saves In-Box/90"),
        ("goodHighClaim_per90", "High Claims/90"),
        ("totalKeeperSweeper_per90", "Sweeper/90"),
        ("pass_accuracy_pct", "Pass Accuracy %"),
        ("totalPass_per90", "Passes/90"),
        ("ballRecovery_per90", "Ball Recovery/90"),
    ],
}

# Universal radar stats (used when comparing mixed positions)
RADAR_STATS_UNIVERSAL = [
    ("avg_rating", "Rating"),
    ("goals_per90", "Goals/90"),
    ("expectedGoals_per90", "xG/90"),
    ("expectedAssists_per90", "xA/90"),
    ("keyPass_per90", "Key Passes/90"),
    ("totalTackle_per90", "Tackles/90"),
    ("interceptionWon_per90", "Interceptions/90"),
    ("duelWon_per90", "Duels Won/90"),
]

# Stat tooltips
STAT_TOOLTIPS = {
    "xG": "Expected Goals — the probability of a shot becoming a goal based on shot quality.",
    "xA": "Expected Assists — the probability that a pass leads to a goal.",
    "KP/90": "Key Passes per 90 minutes — passes that directly create a shot.",
    "BCC/90": "Big Chances Created per 90 — passes creating clear goal-scoring opportunities.",
    "Tkl/90": "Tackles per 90 minutes.",
    "Int/90": "Interceptions per 90 minutes.",
    "DW/90": "Duels Won per 90 minutes (ground duels).",
    "Air/90": "Aerial Duels Won per 90 minutes.",
    "Rec/90": "Ball Recoveries per 90 minutes.",
    "Rating": "SofaScore player performance rating (1-10).",
}

# Colour palette for charts (up to 6 players)
# Index 0 = Schlouh brand gold; remaining are high-contrast data colours
PLAYER_COLORS = [
    "#C9A840",  # Schlouh gold  (brand primary)
    "#FF6B6B",  # red
    "#4D96FF",  # blue
    "#6BCB77",  # green
    "#FFD93D",  # yellow
    "#FF6AC1",  # pink
]

MIN_MINUTES_DEFAULT = 450

# Reliability tier by minutes (for uncertainty indicator)
# < 450 = Low, 450–900 = Medium, > 900 = High
RELIABILITY_MINUTES_LOW = 450
RELIABILITY_MINUTES_MEDIUM = 900

# Top 5 European leagues slugs
TOP_5_LEAGUES = [
    "england-premier-league",
    "spain-laliga",
    "italy-serie-a",
    "germany-bundesliga",
    "france-ligue-1",
]

# Age bands including Unknown (C4 fix)
AGE_BANDS = ["≤21", "22–24", "25–27", "28–30", "31+", "Unknown"]

# Tactical index display labels (for Teams page)
TACTICAL_INDEX_LABELS = {
    "possession_index": "Possession",
    "directness_index": "Directness",
    "pressing_index": "Pressing",
    "aerial_index": "Aerial",
    "crossing_index": "Crossing",
    "chance_creation_index": "Chance Creation",
    "defensive_solidity": "Defensive Solidity",
    "home_away_consistency": "Home/Away Consistency",
    "second_half_intensity": "2nd Half Intensity",
}

# Tactical tag thresholds
TACTICAL_TAGS = {
    "possession_index": (65, "Possession-dominant"),
    "directness_index": (60, "Direct"),
    "pressing_index": (65, "High Press"),
    "aerial_index": (65, "Aerial threat"),
    "crossing_index": (65, "Cross-heavy"),
    "chance_creation_index": (65, "Chance creation"),
    "defensive_solidity": (65, "Defensively solid"),
    "second_half_intensity": (65, "Second-half team"),
}
