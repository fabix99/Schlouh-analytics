with source as (
    select * from {{ source('raw_sofascore', 'player_appearances') }}
)

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
    player_short_name,
    player_slug,
    player_position,
    player_height,
    player_date_of_birth_timestamp,
    coalesce(substitute, false) as substitute,
    coalesce(stat_minutes_played, 0.0) as minutes_played,
    case
        when stat_rating is not null and stat_rating > 10 then stat_rating / 2.0
        else stat_rating
    end as rating,
    coalesce(stat_goals, 0.0) as goals,
    coalesce(stat_goal_assist, 0.0) as assists,
    coalesce(stat_total_pass, 0.0) as total_passes,
    coalesce(stat_accurate_pass, 0.0) as accurate_passes,
    coalesce(stat_total_shots, 0.0) as total_shots,
    coalesce(stat_on_target_scoring_attempt, 0.0) as shots_on_target,
    coalesce(stat_key_pass, 0.0) as key_passes,
    coalesce(stat_duel_won, 0.0) as duels_won,
    coalesce(stat_duel_lost, 0.0) as duels_lost,
    coalesce(stat_total_tackle, 0.0) as tackles,
    coalesce(stat_interception_won, 0.0) as interceptions,
    home_team_name,
    away_team_name,
    status_type
from source
where player_id is not null
  and coalesce(stat_minutes_played, 0.0) >= 1
