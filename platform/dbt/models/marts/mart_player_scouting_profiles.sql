{{ config(materialized='table') }}
-- Real dbt transform: one row per player from season stats + players index
-- (platform replacement for pandas scripts/build/08_build_player_scouting_profiles.py grain).
with season_stats as (
    select * from {{ ref('mart_player_season_stats') }}
),

players as (
    select * from {{ source('raw_sofascore', 'players') }}
),

dob as (
    select
        cast(player_id as bigint) as player_id,
        max("player_dateOfBirthTimestamp") as dob_ts
    from {{ source('raw_sofascore', 'player_appearances') }}
    where "player_dateOfBirthTimestamp" is not null
    group by 1
),

ranked as (
    select
        *,
        row_number() over (
            partition by player_id
            order by
                case when sufficient_minutes then 0 else 1 end,
                season desc,
                total_minutes desc
        ) as season_rank
    from season_stats
),

career as (
    select
        player_id,
        max(player_name) as player_name,
        max("player_shortName") as "player_shortName",
        max(player_position) as player_position,
        sum(appearances) as n_matches,
        sum(total_minutes) as total_minutes,
        sum(goals) as goals,
        sum(assists) as assists,
        min(season) as first_season,
        max(season) as last_season,
        count(distinct season) as n_seasons,
        count(distinct competition_slug) as n_competitions
    from season_stats
    group by 1
),

latest as (
    select
        player_id,
        season as latest_season,
        competition_slug as latest_competition,
        avg_rating as latest_rating,
        total_minutes as latest_minutes,
        appearances as latest_appearances,
        coalesce(total_minutes, 0) >= 450 as sufficient_minutes_latest_season
    from ranked
    where season_rank = 1
)

select
    c.player_id,
    coalesce(p.player_name, c.player_name) as player_name,
    p.player_slug,
    coalesce(p."player_shortName", c."player_shortName") as "player_shortName",
    c.player_position,
    case
        when d.dob_ts is not null
        then (epoch(current_timestamp) - cast(d.dob_ts as double)) / (365.25 * 24 * 3600)
    end as age_today,
    c.n_matches,
    c.total_minutes,
    c.goals,
    c.assists,
    c.first_season,
    c.last_season,
    c.n_seasons,
    c.n_competitions,
    l.latest_season,
    l.latest_competition,
    l.latest_rating,
    l.latest_minutes,
    l.latest_appearances,
    l.sufficient_minutes_latest_season,
    c.last_season is not null as active
from career c
left join players p on c.player_id = cast(p.player_id as bigint)
left join latest l on c.player_id = l.player_id
left join dob d on c.player_id = d.player_id
