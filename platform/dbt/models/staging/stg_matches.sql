with source as (
    select * from {{ source('raw_sofascore', 'matches') }}
)

select
    cast(match_id as varchar) as match_id,
    season,
    realm,
    competition_slug,
    cast(home_team_id as bigint) as home_team_id,
    home_team_name,
    cast(away_team_id as bigint) as away_team_id,
    away_team_name,
    match_date as match_date_unix,
    cast(round as integer) as round,
    status_code,
    status_type
from source
