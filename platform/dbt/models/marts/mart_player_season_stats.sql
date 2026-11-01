{{ config(materialized='table') }}
-- Real dbt transform: player × season × competition from appearances (+ incidents when present).
-- Column set is discovered from the loaded appearances table (fixture slice or full lake).
{% set app_rel = source('raw_sofascore', 'player_appearances') %}
{% set app_cols = adapter.get_columns_in_relation(app_rel) | map(attribute='name') | list %}
{% set skip_sum = ['stat_minutesPlayed', 'stat_rating'] %}
{% set stat_cols = [] %}
{% for c in app_cols if c.startswith('stat_') and c not in skip_sum %}
  {% do stat_cols.append(c) %}
{% endfor %}
{% set value_avg_map = {
  'stat_passValueNormalized': 'pass_value_avg',
  'stat_shotValueNormalized': 'shot_value_avg',
  'stat_defensiveValueNormalized': 'defensive_value_avg',
  'stat_dribbleValueNormalized': 'dribble_value_avg',
  'stat_goalkeeperValueNormalized': 'gk_value_avg',
} %}
{% set inc_rel = adapter.get_relation(
    database=app_rel.database,
    schema=app_rel.schema,
    identifier='player_incidents'
) %}
{% set has_incidents = inc_rel is not none %}

with appearances as (
    select *
    from {{ app_rel }}
    where player_id is not null
      and coalesce("stat_minutesPlayed", 0) >= 1
),

cards as (
{% if has_incidents %}
    select
        cast(player_id as bigint) as player_id,
        cast(season as varchar) as season,
        cast(competition_slug as varchar) as competition_slug,
        sum(
            case
                when "incidentType" = 'card'
                 and lower(cast("incidentClass" as varchar)) like '%yellow%'
                then 1 else 0
            end
        ) as yellow_cards,
        sum(
            case
                when "incidentType" = 'card'
                 and lower(cast("incidentClass" as varchar)) like '%red%'
                then 1 else 0
            end
        ) as red_cards
    from {{ source('raw_sofascore', 'player_incidents') }}
    where player_id is not null
    group by 1, 2, 3
{% else %}
    select
        cast(null as bigint) as player_id,
        cast(null as varchar) as season,
        cast(null as varchar) as competition_slug,
        0 as yellow_cards,
        0 as red_cards
    where false
{% endif %}
),

agg as (
    select
        cast(a.player_id as bigint) as player_id,
        a.season,
        a.competition_slug,
        max(a.player_name) as player_name,
        max(a."player_shortName") as "player_shortName",
        max(a.player_position) as player_position,
        {% if 'player_height' in app_cols %}
        max(a.player_height) as player_height,
        {% else %}
        cast(null as double) as player_height,
        {% endif %}
        {% if 'player_dateOfBirthTimestamp' in app_cols %}
        max(a."player_dateOfBirthTimestamp") as "player_dateOfBirthTimestamp",
        {% else %}
        cast(null as double) as "player_dateOfBirthTimestamp",
        {% endif %}
        {% if 'match_date' in app_cols %}
        min(a.match_date) as first_match_date,
        {% else %}
        cast(null as double) as first_match_date,
        {% endif %}
        count(distinct a.match_id) as appearances,
        sum(case when coalesce(a.substitute, false) = false then 1 else 0 end) as starts,
        sum(coalesce(a."stat_minutesPlayed", 0)) as total_minutes,
        avg(
            case
                when a."stat_rating" is not null and a."stat_rating" > 10
                then a."stat_rating" / 2.0
                else a."stat_rating"
            end
        ) as avg_rating,
        sum(coalesce(a."stat_goals", 0)) as goals,
        sum(coalesce(a."stat_goalAssist", 0)) as assists
        {% for c in stat_cols %}
        , sum(coalesce(a."{{ c }}", 0)) as "total_{{ c[5:] }}"
        {% endfor %}
        {% for c, alias in value_avg_map.items() if c in app_cols %}
        , avg(a."{{ c }}") as {{ alias }}
        {% endfor %}
    from appearances a
    group by 1, 2, 3
),

s as (
    select
        a.*,
        a.appearances - a.starts as sub_appearances,
        case when a.appearances > 0 then a.total_minutes / a.appearances end as avg_minutes_per_game,
        a.total_minutes >= 450 as sufficient_minutes,
        a.goals + a.assists as goal_contributions,
        coalesce(c.yellow_cards, 0) as yellow_cards,
        coalesce(c.red_cards, 0) as red_cards,
        case
            when a."player_dateOfBirthTimestamp" is not null and a.first_match_date is not null
            then (cast(a.first_match_date as double) - cast(a."player_dateOfBirthTimestamp" as double))
                 / (365.25 * 24 * 3600)
        end as age_at_season_start
    from agg a
    left join cards c
      on a.player_id = c.player_id
     and a.season = c.season
     and a.competition_slug = c.competition_slug
)

select
    player_id,
    season,
    competition_slug,
    player_name,
    "player_shortName",
    player_position,
    player_height,
    age_at_season_start,
    appearances,
    starts,
    total_minutes,
    sub_appearances,
    avg_minutes_per_game,
    sufficient_minutes,
    avg_rating,
    goals,
    assists,
    goal_contributions,
    yellow_cards,
    red_cards
    {% for c in stat_cols %}
    , case when s.total_minutes > 0 then s."total_{{ c[5:] }}" * 90.0 / s.total_minutes end as "{{ c[5:] }}_per90"
    {% endfor %}
    {% if 'stat_totalPass' in app_cols and 'stat_accuratePass' in app_cols %}
    , case when coalesce("total_totalPass", 0) > 0
           then "total_accuratePass" / "total_totalPass" end as pass_accuracy
    {% endif %}
    {% if 'stat_duelWon' in app_cols and 'stat_duelLost' in app_cols %}
    , case when (coalesce("total_duelWon", 0) + coalesce("total_duelLost", 0)) > 0
           then "total_duelWon" / ("total_duelWon" + "total_duelLost") end as duel_win_rate
    {% endif %}
    {% if 'stat_aerialWon' in app_cols and 'stat_aerialLost' in app_cols %}
    , case when (coalesce("total_aerialWon", 0) + coalesce("total_aerialLost", 0)) > 0
           then "total_aerialWon" / ("total_aerialWon" + "total_aerialLost") end as aerial_win_rate
    {% endif %}
    {% if 'stat_wonTackle' in app_cols and 'stat_totalTackle' in app_cols %}
    , case when coalesce("total_totalTackle", 0) > 0
           then "total_wonTackle" / "total_totalTackle" end as tackle_success_rate
    {% endif %}
    {% if 'stat_wonContest' in app_cols and 'stat_totalContest' in app_cols %}
    , case when coalesce("total_totalContest", 0) > 0
           then "total_wonContest" / "total_totalContest" end as dribble_success_rate
    {% endif %}
    {% if 'stat_accurateCross' in app_cols and 'stat_totalCross' in app_cols %}
    , case when coalesce("total_totalCross", 0) > 0
           then "total_accurateCross" / "total_totalCross" end as cross_accuracy
    {% endif %}
    {% if 'stat_accurateLongBalls' in app_cols and 'stat_totalLongBalls' in app_cols %}
    , case when coalesce("total_totalLongBalls", 0) > 0
           then "total_accurateLongBalls" / "total_totalLongBalls" end as long_ball_accuracy
    {% endif %}
    {% for c, alias in value_avg_map.items() if c in app_cols %}
    , {{ alias }}
    {% endfor %}
    , player_id || '|' || season || '|' || competition_slug as player_season_comp_key
from s
