with source as (
    select * from {{ source('raw_sofascore', 'match_summary') }}
)

select
    cast(match_id as varchar) as match_id,
    season,
    competition_slug,
    match_date_utc,
    cast(round as integer) as round,
    home_team_name,
    away_team_name,
    home_score,
    away_score,
    result,
    total_goals,
    home_xg,
    away_xg,
    home_possession,
    away_possession,
    home_shots,
    away_shots,
    home_shots_on_target,
    away_shots_on_target,
    referee_name,
    venue_name,
    venue_city
from source
