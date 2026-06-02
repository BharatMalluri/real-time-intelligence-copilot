-- stg_enriched_articles: join articles with AI summaries
with articles as (
    select * from {{ ref('stg_all_articles') }}
),

summaries as (
    select
        article_id,
        source,
        summary,
        sentiment,
        topics,
        entities,
        model_name,
        summarized_at
    from {{ source('raw', 'article_summaries') }}
)

select
    a.id,
    a.source,
    a.title,
    a.body,
    a.url,
    a.article_date,
    a.category,
    s.summary,
    s.sentiment,
    s.topics,
    s.entities,
    s.model_name,
    s.summarized_at,
    case
        when s.article_id is not null then true
        else false
    end                 as is_enriched
from articles a
left join summaries s
    on a.id = s.article_id
    and a.source = s.source
