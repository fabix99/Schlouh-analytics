{{ config(enabled=false) }}
with source as (
    select * from {{ source('raw_sofascore', 'players') }}
)

select
    cast(player_id as bigint) as player_id,
    player_name,
    player_slug,
    coalesce(player_short_name, "player_shortName") as player_short_name,
    n_matches,
    competitions,
    seasons
from source
where player_id is not null
