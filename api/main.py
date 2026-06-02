"""
main.py — FastAPI backend for the intelligence copilot
Endpoints: /ask, /trends, /summary, /entities, /health
"""
import os
import sys
from datetime import datetime, timedelta
from typing import List, Optional

import psycopg2
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.append("/app")

app = FastAPI(
    title="Real-Time Intelligence Copilot API",
    description="RAG-powered news intelligence API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB ────────────────────────────────────────────────────────────────────────
def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "intelligence"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )

# ── Schemas ───────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str
    n_results: Optional[int] = 5

class AskResponse(BaseModel):
    answer:   str
    sources:  List[dict]
    query:    str

class TrendItem(BaseModel):
    topic:      str
    count:      int
    sentiment:  str
    sources:    List[str]

class EntityItem(BaseModel):
    entity:  str
    count:   int
    sources: List[str]

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/ask", response_model=AskResponse)
def ask_question(req: AskRequest):
    """RAG endpoint: ask a question, get a cited answer from news articles."""
    try:
        from rag.rag_chain import ask
        result = ask(req.question, n_results=req.n_results)
        return AskResponse(
            answer=result.answer,
            sources=[{
                "article_id":   s.article_id,
                "source":       s.source,
                "title":        s.title,
                "url":          s.url,
                "published_at": s.published_at,
            } for s in result.sources],
            query=result.query,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trends", response_model=List[TrendItem])
def get_trends(hours: int = Query(default=24, ge=1, le=168)):
    """Get trending topics from the last N hours."""
    conn = get_conn()
    cur  = conn.cursor()
    try:
        since = datetime.now() - timedelta(hours=hours)
        cur.execute("""
            SELECT
                unnest(topics)              as topic,
                count(*)                    as cnt,
                mode() WITHIN GROUP (ORDER BY sentiment) as sentiment,
                array_agg(DISTINCT source)  as sources
            FROM raw.article_summaries
            WHERE summarized_at >= %s
              AND topics IS NOT NULL
              AND array_length(topics, 1) > 0
            GROUP BY topic
            ORDER BY cnt DESC
            LIMIT 20
        """, (since,))
        rows = cur.fetchall()
        return [
            TrendItem(topic=r[0], count=r[1], sentiment=r[2] or "neutral", sources=r[3] or [])
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()

@app.get("/summary")
def get_summary(source: Optional[str] = None, hours: int = Query(default=24, ge=1, le=168)):
    """Get article summaries from the last N hours."""
    conn = get_conn()
    cur  = conn.cursor()
    try:
        since = datetime.now() - timedelta(hours=hours)
        query = """
            SELECT s.article_id, s.source, s.summary, s.sentiment, s.topics, s.summarized_at
            FROM raw.article_summaries s
            WHERE s.summarized_at >= %s
        """
        params = [since]
        if source:
            query += " AND s.source = %s"
            params.append(source)
        query += " ORDER BY s.summarized_at DESC LIMIT 50"

        cur.execute(query, params)
        rows = cur.fetchall()
        return [{
            "article_id":   r[0],
            "source":       r[1],
            "summary":      r[2],
            "sentiment":    r[3],
            "topics":       r[4],
            "summarized_at": str(r[5]),
        } for r in rows]
    finally:
        cur.close()
        conn.close()

@app.get("/entities", response_model=List[EntityItem])
def get_entities(hours: int = Query(default=24, ge=1, le=168)):
    """Get top entities mentioned in articles."""
    conn = get_conn()
    cur  = conn.cursor()
    try:
        since = datetime.now() - timedelta(hours=hours)
        cur.execute("""
            SELECT
                unnest(entities)            as entity,
                count(*)                    as cnt,
                array_agg(DISTINCT source)  as sources
            FROM raw.article_summaries
            WHERE summarized_at >= %s
              AND entities IS NOT NULL
              AND array_length(entities, 1) > 0
            GROUP BY entity
            ORDER BY cnt DESC
            LIMIT 30
        """, (since,))
        rows = cur.fetchall()
        return [
            EntityItem(entity=r[0], count=r[1], sources=r[2] or [])
            for r in rows
        ]
    finally:
        cur.close()
        conn.close()

@app.get("/stats")
def get_stats():
    """Pipeline statistics."""
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT
                (SELECT count(*) FROM raw.news_articles)    as news_count,
                (SELECT count(*) FROM raw.reddit_posts)     as reddit_count,
                (SELECT count(*) FROM raw.rss_items)        as rss_count,
                (SELECT count(*) FROM raw.hn_items)         as hn_count,
                (SELECT count(*) FROM raw.article_embeddings) as embedded_count,
                (SELECT count(*) FROM raw.article_summaries)  as summarized_count
        """)
        row = cur.fetchone()
        return {
            "news_articles":    row[0],
            "reddit_posts":     row[1],
            "rss_items":        row[2],
            "hn_items":         row[3],
            "embedded":         row[4],
            "summarized":       row[5],
            "timestamp":        datetime.now().isoformat(),
        }
    finally:
        cur.close()
        conn.close()
