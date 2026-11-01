{{ config(enabled=false) }}
with source as (
    select * from {{ source('raw_sofascore', 'player_appearances') }}
),

normalized as (
    select
        cast(match_id as varchar) as match_id,
        season,
        realm,
        competition_slug,
        match_date as match_date_unix,
        cast(round as integer) as round,
        side,
        team,
        cast(player_id as bigint) as player_id,
        player_name,
        coalesce(player_short_name, "player_shortName") as player_short_name,
        player_slug,
        player_position,
        player_height,
        coalesce(player_date_of_birth_timestamp, "player_dateOfBirthTimestamp") as player_date_of_birth_timestamp,
        coalesce(substitute, false) as substitute,
        coalesce(stat_minutes_played, "stat_minutesPlayed", 0.0) as minutes_played,
        coalesce(stat_rating, "stat_rating") as stat_rating_raw,
        coalesce(stat_goals, "stat_goals", 0.0) as goals,
        coalesce(stat_goal_assist, "stat_goalAssist", 0.0) as assists,
        coalesce(stat_total_pass, "stat_totalPass", 0.0) as total_passes,
        coalesce(stat_accurate_pass, "stat_accuratePass", 0.0) as accurate_passes,
        coalesce(stat_total_shots, "stat_totalShots", 0.0) as total_shots,
        coalesce(stat_on_target_scoring_attempt, "stat_onTargetScoringAttempt", 0.0) as shots_on_target,
        coalesce(stat_key_pass, "stat_keyPass", 0.0) as key_passes,
        coalesce(stat_duel_won, "stat_duelWon", 0.0) as duels_won,
        coalesce(stat_duel_lost, "stat_duelLost", 0.0) as duels_lost,
        coalesce(stat_total_tackle, "stat_totalTackle", 0.0) as tackles,
        coalesce(stat_interception_won, "stat_interceptionWon", 0.0) as interceptions,
        home_team_name,
        away_team_name,
        status_type
    from source
)

select
    match_id,
    season,
    realm,
    competition_slug,
    match_date_unix,
    round,
    side,
    team,
    player_id,
    player_name,
    player_short_name,
    player_slug,
    player_position,
    player_height,
    player_date_of_birth_timestamp,
    substitute,
    minutes_played,
    case
        when stat_rating_raw is not null and stat_rating_raw > 10 then stat_rating_raw / 2.0
        else stat_rating_raw
    end as rating,
    goals,
    assists,
    total_passes,
    accurate_passes,
    total_shots,
    shots_on_target,
    key_passes,
    duels_won,
    duels_lost,
    tackles,
    interceptions,
    home_team_name,
    away_team_name,
    status_type
from normalized
where player_id is not null
  and minutes_played >= 1
