import json
import logging
import os
import requests
from datetime import datetime

import chromadb
import psycopg2
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL  = "llama-3.1-8b-instant"
EMBED_MODEL = "all-MiniLM-L6-v2"

def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5434")),
        dbname=os.getenv("POSTGRES_DB", "intelligence"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )

def get_chroma_client():
    return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

def get_unenriched_articles(conn, limit=50):
    cur = conn.cursor()
    cur.execute("""
        SELECT n.id, n.source, n.title, n.description, n.content, n.published_at
        FROM (
            SELECT id, 'newsapi' as source, title, description, content, published_at FROM raw.news_articles
            UNION ALL
            SELECT id, 'reddit'  as source, title, selftext, NULL, created_utc FROM raw.reddit_posts
            UNION ALL
            SELECT id, 'rss'     as source, title, summary,  NULL, published_at FROM raw.rss_items
            UNION ALL
            SELECT id::text, 'hn' as source, title, NULL, NULL, created_at FROM raw.hn_items
        ) n
        LEFT JOIN raw.article_embeddings e ON n.id = e.article_id
        WHERE e.article_id IS NULL
          AND n.title IS NOT NULL
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    return rows

def summarize_with_groq(title: str, content: str) -> dict:
    if not GROQ_API_KEY:
        return {"summary": title, "sentiment": "neutral", "topics": [], "entities": []}

    prompt = f"""Analyze this news article and respond ONLY with valid JSON, no extra text, no markdown:

Title: {title}
Content: {content[:500] if content else 'No content'}

Respond with exactly this JSON structure:
{{
  "summary": "2-3 sentence summary",
  "sentiment": "positive or negative or neutral",
  "topics": ["topic1", "topic2"],
  "entities": ["entity1", "entity2"]
}}"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            },
            timeout=30,
        )
        text = response.json()["choices"][0]["message"]["content"].strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        log.warning(f"Groq error: {e}")
        return {"summary": title, "sentiment": "neutral", "topics": [], "entities": []}

def run():
    log.info("Starting enrichment pipeline...")
    pg_conn    = get_pg_conn()
    chroma     = get_chroma_client()
    embedder   = SentenceTransformer(EMBED_MODEL)
    collection = chroma.get_or_create_collection("news_articles")

    articles = get_unenriched_articles(pg_conn, limit=50)
    log.info(f"Found {len(articles)} unenriched articles")

    cur = pg_conn.cursor()
    enriched = 0

    for article_id, source, title, description, content, published_at in articles:
        try:
            text = f"{title}. {description or ''} {content or ''}".strip()[:1000]
            embedding = embedder.encode(text).tolist()
            chroma_id = f"{source}_{article_id}"

            collection.upsert(
                ids=[chroma_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{
                    "article_id":   str(article_id),
                    "source":       source,
                    "published_at": str(published_at),
                }]
            )

            cur.execute("""
                INSERT INTO raw.article_embeddings (article_id, source, chroma_id, model_name)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, (str(article_id), source, chroma_id, EMBED_MODEL))

            llm_result = summarize_with_groq(title, content or description or "")

            cur.execute("""
                INSERT INTO raw.article_summaries
                    (article_id, source, summary, sentiment, topics, entities, model_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, (
                str(article_id), source,
                llm_result.get("summary"),
                llm_result.get("sentiment"),
                llm_result.get("topics", []),
                llm_result.get("entities", []),
                GROQ_MODEL,
            ))

            enriched += 1
            if enriched % 10 == 0:
                pg_conn.commit()
                log.info(f"Enriched {enriched}/{len(articles)}")

        except Exception as e:
            log.error(f"Error enriching {article_id}: {e}")
            continue

    pg_conn.commit()
    cur.close()
    pg_conn.close()
    log.info(f"✅ Enriched {enriched} articles")

if __name__ == "__main__":
    run()