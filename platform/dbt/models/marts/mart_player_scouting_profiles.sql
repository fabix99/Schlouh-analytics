-- Lightweight scouting profile mart (platform slice of legacy step 08).
with season_stats as (
    select * from {{ ref('mart_player_season_stats') }}
),

players as (
    select * from {{ ref('stg_players') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by player_id
            order by season desc, total_minutes desc
        ) as season_rank
    from season_stats
),

career as (
    select
        player_id,
        max(player_name) as player_name,
        max(player_short_name) as player_short_name,
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
        sufficient_minutes as sufficient_minutes_latest_season
    from ranked
    where season_rank = 1
)

select
    c.player_id,
    coalesce(p.player_name, c.player_name) as player_name,
    p.player_slug,
    coalesce(p.player_short_name, c.player_short_name) as player_short_name,
    c.player_position,
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
    true as active
from career c
left join players p on c.player_id = p.player_id
left join latest l on c.player_id = l.player_id
