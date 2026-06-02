-- marts/agg_hourly_trends.sql: hourly trend aggregates per source + sentiment
{{
  config(materialized='table')
}}

with base as (
    select * from {{ ref('fct_articles') }}
),

hourly as (
    select
        article_hour                                as hour,
        source,
        sentiment,
        count(*)                                    as article_count,
        count(case when is_enriched then 1 end)     as enriched_count,
        count(distinct category)                    as unique_categories
    from base
    group by article_hour, source, sentiment
)

select
    *,
    sum(article_count) over (
        partition by source
        order by hour
        rows between 5 preceding and current row
    )                                               as rolling_6h_count
from hourly
order by hour desc, source
