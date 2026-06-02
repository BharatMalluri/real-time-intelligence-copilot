-- Initialise schemas for P2 real-time intelligence pipeline
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Raw: news articles
CREATE TABLE IF NOT EXISTS raw.news_articles (
    id              VARCHAR(100) PRIMARY KEY,
    source          VARCHAR(50),
    title           TEXT,
    description     TEXT,
    content         TEXT,
    url             TEXT,
    published_at    TIMESTAMP,
    author          VARCHAR(200),
    category        VARCHAR(50),
    loaded_at       TIMESTAMP DEFAULT NOW()
);

-- Raw: reddit posts
CREATE TABLE IF NOT EXISTS raw.reddit_posts (
    id              VARCHAR(50) PRIMARY KEY,
    subreddit       VARCHAR(100),
    title           TEXT,
    selftext        TEXT,
    score           INTEGER,
    num_comments    INTEGER,
    url             TEXT,
    created_utc     TIMESTAMP,
    author          VARCHAR(100),
    loaded_at       TIMESTAMP DEFAULT NOW()
);

-- Raw: RSS feed items
CREATE TABLE IF NOT EXISTS raw.rss_items (
    id              VARCHAR(100) PRIMARY KEY,
    feed_name       VARCHAR(100),
    feed_url        TEXT,
    title           TEXT,
    summary         TEXT,
    link            TEXT,
    published_at    TIMESTAMP,
    loaded_at       TIMESTAMP DEFAULT NOW()
);

-- Raw: Hacker News items
CREATE TABLE IF NOT EXISTS raw.hn_items (
    id              INTEGER PRIMARY KEY,
    item_type       VARCHAR(20),
    title           TEXT,
    url             TEXT,
    score           INTEGER,
    num_comments    INTEGER,
    author          VARCHAR(100),
    created_at      TIMESTAMP,
    loaded_at       TIMESTAMP DEFAULT NOW()
);

-- AI enrichment: embeddings metadata
CREATE TABLE IF NOT EXISTS raw.article_embeddings (
    article_id      VARCHAR(100),
    source          VARCHAR(50),
    chroma_id       VARCHAR(200),
    model_name      VARCHAR(100),
    embedded_at     TIMESTAMP DEFAULT NOW()
);

-- AI enrichment: LLM summaries
CREATE TABLE IF NOT EXISTS raw.article_summaries (
    article_id      VARCHAR(100),
    source          VARCHAR(50),
    summary         TEXT,
    sentiment       VARCHAR(20),
    topics          TEXT[],
    entities        TEXT[],
    model_name      VARCHAR(100),
    summarized_at   TIMESTAMP DEFAULT NOW()
);

-- Monitoring
CREATE TABLE IF NOT EXISTS monitoring.pipeline_runs (
    id              SERIAL PRIMARY KEY,
    dag_id          VARCHAR(100),
    run_id          VARCHAR(100),
    source          VARCHAR(50),
    status          VARCHAR(20),
    rows_loaded     INTEGER,
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS monitoring.anomaly_log (
    id              SERIAL PRIMARY KEY,
    check_name      VARCHAR(100),
    table_name      VARCHAR(100),
    metric_value    NUMERIC,
    threshold       NUMERIC,
    status          VARCHAR(20),
    detected_at     TIMESTAMP DEFAULT NOW()
);
