-- stg_all_articles: unified view across all sources
with news as (
    select
        id,
        'newsapi'       as source,
        title,
        description     as body,
        url,
        published_at    as article_date,
        category,
        loaded_at
    from {{ source('raw', 'news_articles') }}
    where title is not null
),

reddit as (
    select
        id,
        'reddit'        as source,
        title,
        selftext        as body,
        url,
        created_utc     as article_date,
        subreddit       as category,
        loaded_at
    from {{ source('raw', 'reddit_posts') }}
    where title is not null
),

rss as (
    select
        id,
        'rss'           as source,
        title,
        summary         as body,
        link            as url,
        published_at    as article_date,
        feed_name       as category,
        loaded_at
    from {{ source('raw', 'rss_items') }}
    where title is not null
),

hn as (
    select
        id::varchar,
        'hackernews'    as source,
        title,
        null            as body,
        url,
        created_at      as article_date,
        'technology'    as category,
        loaded_at
    from {{ source('raw', 'hn_items') }}
    where title is not null
),

unioned as (
    select * from news
    union all
    select * from reddit
    union all
    select * from rss
    union all
    select * from hn
)

select * from unioned
