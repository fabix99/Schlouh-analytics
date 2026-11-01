{{ config(materialized='table') }}
-- Real dbt transform: team × season × competition rollup from player appearances.
{% set app_rel = source('raw_sofascore', 'player_appearances') %}
{% set app_cols = adapter.get_columns_in_relation(app_rel) | map(attribute='name') | list %}

with appearances as (
    select *
    from {{ app_rel }}
    where player_id is not null
      and coalesce("stat_minutesPlayed", 0) >= 1
      and team is not null
),

agg as (
    select
        team as team_name,
        season,
        competition_slug,
        count(distinct match_id) as matches_total,
        sum(coalesce("stat_goals", 0)) as goals_for,
        sum(coalesce("stat_goalAssist", 0)) as assists_total
        {% if 'stat_expectedGoals' in app_cols %}
        , sum(coalesce("stat_expectedGoals", 0)) as xg_for_total
        {% endif %}
        {% if 'stat_expectedAssists' in app_cols %}
        , sum(coalesce("stat_expectedAssists", 0)) as xa_for_total
        {% endif %}
        {% if 'stat_totalShots' in app_cols %}
        , sum(coalesce("stat_totalShots", 0)) as shots_total
        {% endif %}
        {% if 'stat_onTargetScoringAttempt' in app_cols %}
        , sum(coalesce("stat_onTargetScoringAttempt", 0)) as shots_on_target
        {% endif %}
        {% if 'stat_bigChanceCreated' in app_cols %}
        , sum(coalesce("stat_bigChanceCreated", 0)) as big_chances_total
        {% endif %}
        {% if 'stat_keyPass' in app_cols %}
        , sum(coalesce("stat_keyPass", 0)) as key_passes_total
        {% endif %}
        {% if 'stat_totalPass' in app_cols %}
        , sum(coalesce("stat_totalPass", 0)) as passes_total
        {% endif %}
        {% if 'stat_accuratePass' in app_cols %}
        , sum(coalesce("stat_accuratePass", 0)) as accurate_passes_total
        {% endif %}
        {% if 'stat_totalTackle' in app_cols %}
        , sum(coalesce("stat_totalTackle", 0)) as tackles_total
        {% endif %}
        {% if 'stat_wonTackle' in app_cols %}
        , sum(coalesce("stat_wonTackle", 0)) as tackles_won
        {% endif %}
        {% if 'stat_interceptionWon' in app_cols %}
        , sum(coalesce("stat_interceptionWon", 0)) as interceptions_total
        {% endif %}
        {% if 'stat_ballRecovery' in app_cols %}
        , sum(coalesce("stat_ballRecovery", 0)) as recoveries_total
        {% endif %}
        {% if 'stat_totalClearance' in app_cols %}
        , sum(coalesce("stat_totalClearance", 0)) as clearances_total
        {% endif %}
        {% if 'stat_fouls' in app_cols %}
        , sum(coalesce("stat_fouls", 0)) as fouls_total
        {% endif %}
        {% if 'stat_saves' in app_cols %}
        , sum(coalesce("stat_saves", 0)) as goalkeeper_saves_total
        {% endif %}
        , sum(coalesce("stat_minutesPlayed", 0)) as minutes_total
        , avg(
            case
                when "stat_rating" is not null and "stat_rating" > 10
                then "stat_rating" / 2.0
                else "stat_rating"
            end
        ) as avg_player_rating
    from appearances
    group by 1, 2, 3
)

select
    *
    {% if 'stat_totalPass' in app_cols and 'stat_accuratePass' in app_cols %}
    , case when passes_total > 0 then accurate_passes_total / passes_total end as pass_accuracy
    {% endif %}
    {% if 'stat_totalTackle' in app_cols and 'stat_wonTackle' in app_cols %}
    , case when tackles_total > 0 then tackles_won / tackles_total end as tackle_success_rate
    {% endif %}
    , team_name || '|' || season || '|' || competition_slug as team_season_comp_key
from agg
