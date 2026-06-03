import logging
import os
from dataclasses import dataclass
from typing import List

import chromadb
import psycopg2
import requests
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHROMA_HOST  = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT  = int(os.getenv("CHROMA_PORT", "8000"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b-instant"
EMBED_MODEL  = "all-MiniLM-L6-v2"

@dataclass
class Source:
    article_id:   str
    source:       str
    title:        str
    url:          str
    published_at: str

@dataclass
class RAGResponse:
    answer:  str
    sources: List[Source]
    query:   str

_embedder   = None
_collection = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder

def _get_collection():
    global _collection
    if _collection is None:
        chroma      = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        _collection = chroma.get_or_create_collection("news_articles")
    return _collection

def _get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5434")),
        dbname=os.getenv("POSTGRES_DB", "intelligence"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )

def _fetch_metadata(article_ids, sources):
    conn = _get_pg_conn()
    cur  = conn.cursor()
    results = []
    for article_id, source in zip(article_ids, sources):
        try:
            if source == "rss":
                cur.execute("SELECT id, 'rss', title, link, published_at FROM raw.rss_items WHERE id=%s", (article_id,))
            elif source == "hn":
                cur.execute("SELECT id, 'hn', title, url, created_at FROM raw.hn_items WHERE id::text=%s", (article_id,))
            elif source == "newsapi":
                cur.execute("SELECT id, 'newsapi', title, url, published_at FROM raw.news_articles WHERE id=%s", (article_id,))
            elif source == "reddit":
                cur.execute("SELECT id, 'reddit', title, url, created_utc FROM raw.reddit_posts WHERE id=%s", (article_id,))
            else:
                continue
            row = cur.fetchone()
            if row:
                results.append(Source(
                    article_id=str(row[0]), source=row[1],
                    title=row[2] or "", url=row[3] or "",
                    published_at=str(row[4]) if row[4] else "",
                ))
        except Exception as e:
            log.warning(f"Metadata error: {e}")
    cur.close()
    conn.close()
    return results

def _ask_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        return "GROQ_API_KEY not set."
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"Groq error: {e}")
        return "Could not generate answer."

def ask(query: str, n_results: int = 5) -> RAGResponse:
    embedder   = _get_embedder()
    collection = _get_collection()

    query_embedding = embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    if not documents:
        return RAGResponse(answer="No relevant articles found.", sources=[], query=query)

    context = "\n\n".join([f"[{i+1}] {doc[:400]}" for i, doc in enumerate(documents)])

    prompt = f"""You are a news intelligence assistant. Answer using ONLY the provided context.
Cite sources using [1], [2], etc. Be concise and factual.

Context:
{context}

Question: {query}

Answer:"""

    answer       = _ask_groq(prompt)
    article_ids  = [m.get("article_id", "") for m in metadatas]
    source_names = [m.get("source", "unknown") for m in metadatas]
    sources      = _fetch_metadata(article_ids, source_names)

    return RAGResponse(answer=answer, sources=sources, query=query)

if __name__ == "__main__":
    result = ask("What are the latest developments in artificial intelligence?")
    print(f"\nAnswer:\n{result.answer}")
    print(f"\nSources ({len(result.sources)}):")
    for s in result.sources:
        print(f"  - [{s.source}] {s.title[:60]}")