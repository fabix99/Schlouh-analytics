-- Curated match mart: cleaned match facts for consumers / scouting prep.
select
    m.match_id,
    m.season,
    m.competition_slug,
    m.match_date_utc,
    m.round,
    m.home_team_name,
    m.away_team_name,
    m.home_score,
    m.away_score,
    m.result,
    m.total_goals,
    m.home_xg,
    m.away_xg,
    m.home_possession,
    m.away_possession,
    m.home_shots,
    m.away_shots,
    m.home_shots_on_target,
    m.away_shots_on_target,
    m.referee_name,
    m.venue_name,
    m.venue_city,
    i.status_type
from {{ ref('stg_match_summary') }} m
left join {{ ref('stg_matches') }} i
    on m.match_id = i.match_id
