"""
enrich_articles.py
Enriches articles with:
- Local embeddings via sentence-transformers
- Summaries + sentiment + topics via Ollama (local LLM)
- Stores embeddings in ChromaDB
- Stores metadata in PostgreSQL
"""
import json
import logging
import os
from datetime import datetime

import chromadb
import psycopg2
from sentence_transformers import SentenceTransformer
import ollama

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHROMA_HOST  = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT  = int(os.getenv("CHROMA_PORT", "8000"))
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
EMBED_MODEL  = "all-MiniLM-L6-v2"

def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
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
            SELECT id, 'reddit'  as source, title, selftext,    NULL,    created_utc  FROM raw.reddit_posts
            UNION ALL
            SELECT id, 'rss'     as source, title, summary,     NULL,    published_at FROM raw.rss_items
        ) n
        LEFT JOIN raw.article_embeddings e ON n.id = e.article_id
        WHERE e.article_id IS NULL
          AND n.title IS NOT NULL
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    return rows

def summarize_with_llm(title: str, content: str) -> dict:
    prompt = f"""Analyze this news article and respond ONLY with valid JSON, no extra text:

Title: {title}
Content: {content[:500] if content else 'No content'}

Respond with this exact JSON structure:
{{
  "summary": "2-3 sentence summary",
  "sentiment": "positive|negative|neutral",
  "topics": ["topic1", "topic2"],
  "entities": ["entity1", "entity2"]
}}"""

    try:
        client = ollama.Client(host=OLLAMA_HOST)
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response["message"]["content"].strip()
        # Strip markdown fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except Exception as e:
        log.warning(f"LLM error: {e}")
        return {
            "summary": title,
            "sentiment": "neutral",
            "topics": [],
            "entities": []
        }

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

            # 1. Generate embedding
            embedding = embedder.encode(text).tolist()
            chroma_id = f"{source}_{article_id}"

            # 2. Store in ChromaDB
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

            # 3. Store embedding metadata in PG
            cur.execute("""
                INSERT INTO raw.article_embeddings (article_id, source, chroma_id, model_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (str(article_id), source, chroma_id, EMBED_MODEL))

            # 4. LLM summarization
            llm_result = summarize_with_llm(title, content or description or "")

            cur.execute("""
                INSERT INTO raw.article_summaries
                    (article_id, source, summary, sentiment, topics, entities, model_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                str(article_id), source,
                llm_result.get("summary"),
                llm_result.get("sentiment"),
                llm_result.get("topics", []),
                llm_result.get("entities", []),
                OLLAMA_MODEL,
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
