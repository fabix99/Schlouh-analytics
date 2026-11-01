{{ config(materialized='table') }}
-- Real dbt transform: match grain from index matches, enriched with processed match_summary
-- (scores, xG, possession, managers, venue). Works for fixture slice and full lake.
{% set match_rel = source('raw_sofascore', 'matches') %}
{% set scores_rel = adapter.get_relation(
    database=match_rel.database,
    schema=match_rel.schema,
    identifier='match_scores_full'
) %}
{% set has_scores = scores_rel is not none %}

with matches as (
    select * from {{ match_rel }}
),

enrichment as (
    select * from {{ source('raw_sofascore', 'match_summary') }}
)
{% if has_scores %}
,
scores as (
    select * from {{ source('raw_sofascore', 'match_scores_full') }}
)
{% endif %}

select
    cast(m.match_id as varchar) as match_id,
    m.season,
    m.competition_slug,
    coalesce(cast(e.match_date_utc as varchar), cast(m.match_date as varchar)) as match_date_utc,
    coalesce(e.round, m.round) as round,
    coalesce(e.home_team_name, m.home_team_name) as home_team_name,
    coalesce(e.away_team_name, m.away_team_name) as away_team_name,
    {% if has_scores %}
    coalesce(s.home_score, e.home_score) as home_score,
    coalesce(s.away_score, e.away_score) as away_score,
    coalesce(s.result, e.result) as result,
    coalesce(s.total_goals, e.total_goals) as total_goals,
    {% else %}
    e.home_score,
    e.away_score,
    e.result,
    e.total_goals,
    {% endif %}
    e.home_xg,
    e.away_xg,
    e.home_possession,
    e.away_possession,
    e.home_shots,
    e.away_shots,
    e.home_shots_on_target,
    e.away_shots_on_target,
    e.referee_name,
    e.venue_name,
    e.venue_city,
    m.status_type
from matches m
left join enrichment e on cast(m.match_id as varchar) = cast(e.match_id as varchar)
{% if has_scores %}
left join scores s on cast(m.match_id as varchar) = cast(s.match_id as varchar)
{% endif %}
