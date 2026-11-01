{{ config(enabled=var('use_processed_sources', true)) }}
-- Serving mart: DLT-loaded processed table published via dbt (tested contract).
-- Upstream transforms: scripts/build/* → parquet → DLT → this mart.
select * from {{ source('raw_sofascore', 'player_progression') }}
