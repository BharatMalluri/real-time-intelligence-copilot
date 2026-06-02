-- marts/fct_articles.sql: fact table for all enriched articles
{{
  config(materialized='table')
}}

select
    id,
    source,
    title,
    url,
    article_date,
    date_trunc('hour', article_date)    as article_hour,
    article_date::date                  as article_day,
    category,
    summary,
    coalesce(sentiment, 'neutral')      as sentiment,
    topics,
    entities,
    is_enriched,
    summarized_at
from {{ ref('stg_enriched_articles') }}
where article_date is not null
