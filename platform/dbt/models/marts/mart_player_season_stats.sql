-- Core player × season × competition mart (platform slice of legacy step 03).
with appearances as (
    select * from {{ ref('stg_player_appearances') }}
),

agg as (
    select
        player_id,
        season,
        competition_slug,
        max(player_name) as player_name,
        max(player_short_name) as player_short_name,
        max(player_position) as player_position,
        max(player_height) as player_height,
        count(distinct match_id) as appearances,
        sum(case when not substitute then 1 else 0 end) as starts,
        sum(minutes_played) as total_minutes,
        avg(rating) as avg_rating,
        sum(goals) as goals,
        sum(assists) as assists,
        sum(goals) + sum(assists) as goal_contributions,
        sum(total_passes) as total_passes,
        sum(accurate_passes) as accurate_passes,
        sum(total_shots) as total_shots,
        sum(shots_on_target) as shots_on_target,
        sum(key_passes) as key_passes,
        sum(duels_won) as duels_won,
        sum(duels_lost) as duels_lost,
        sum(tackles) as tackles,
        sum(interceptions) as interceptions
    from appearances
    group by 1, 2, 3
)

select
    player_id || '|' || season || '|' || competition_slug as player_season_comp_key,
    player_id,
    season,
    competition_slug,
    player_name,
    player_short_name,
    player_position,
    player_height,
    appearances,
    starts,
    appearances - starts as sub_appearances,
    total_minutes,
    total_minutes / nullif(appearances, 0) as avg_minutes_per_game,
    total_minutes >= 450 as sufficient_minutes,
    avg_rating,
    goals,
    assists,
    goal_contributions,
    case when total_minutes > 0 then total_passes * 90.0 / total_minutes end as total_pass_per90,
    case when total_minutes > 0 then accurate_passes * 90.0 / total_minutes end as accurate_pass_per90,
    case when total_minutes > 0 then total_shots * 90.0 / total_minutes end as total_shots_per90,
    case when total_minutes > 0 then key_passes * 90.0 / total_minutes end as key_pass_per90,
    case when total_minutes > 0 then goals * 90.0 / total_minutes end as goals_per90,
    case when total_minutes > 0 then assists * 90.0 / total_minutes end as assists_per90,
    case
        when (duels_won + duels_lost) > 0
        then duels_won / (duels_won + duels_lost)
    end as duel_win_rate,
    case
        when total_passes > 0
        then accurate_passes / total_passes
    end as pass_accuracy
from agg
