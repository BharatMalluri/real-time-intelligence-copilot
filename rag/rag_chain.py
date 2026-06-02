"""
rag_chain.py
RAG retrieval chain:
  query → ChromaDB semantic search → context assembly → Ollama LLM → cited answer
"""
import logging
import os
from dataclasses import dataclass
from typing import List

import chromadb
import ollama
import psycopg2
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHROMA_HOST  = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT  = int(os.getenv("CHROMA_PORT", "8000"))
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
EMBED_MODEL  = "all-MiniLM-L6-v2"

@dataclass
class Source:
    article_id: str
    source:     str
    title:      str
    url:        str
    published_at: str

@dataclass
class RAGResponse:
    answer:   str
    sources:  List[Source]
    query:    str

_embedder   = None
_chroma     = None
_collection = None

def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder

def _get_collection():
    global _chroma, _collection
    if _collection is None:
        _chroma     = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        _collection = _chroma.get_or_create_collection("news_articles")
    return _collection

def _get_pg_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "intelligence"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )

def _fetch_article_metadata(article_ids: List[str], sources: List[str]) -> List[Source]:
    conn = _get_pg_conn()
    cur  = conn.cursor()
    results = []
    for article_id, source in zip(article_ids, sources):
        try:
            if source == "newsapi":
                cur.execute(
                    "SELECT id, 'newsapi', title, url, published_at FROM raw.news_articles WHERE id=%s",
                    (article_id,)
                )
            elif source == "reddit":
                cur.execute(
                    "SELECT id, 'reddit', title, url, created_utc FROM raw.reddit_posts WHERE id=%s",
                    (article_id,)
                )
            elif source == "rss":
                cur.execute(
                    "SELECT id, 'rss', title, link, published_at FROM raw.rss_items WHERE id=%s",
                    (article_id,)
                )
            else:
                cur.execute(
                    "SELECT id, 'hn', title, url, created_at FROM raw.hn_items WHERE id=%s::integer",
                    (article_id,)
                )
            row = cur.fetchone()
            if row:
                results.append(Source(
                    article_id=str(row[0]),
                    source=row[1],
                    title=row[2] or "",
                    url=row[3] or "",
                    published_at=str(row[4]) if row[4] else "",
                ))
        except Exception as e:
            log.warning(f"Metadata fetch error for {article_id}: {e}")
    cur.close()
    conn.close()
    return results

def ask(query: str, n_results: int = 5) -> RAGResponse:
    """Main RAG function: query → search → answer with citations."""

    # 1. Embed the query
    embedder   = _get_embedder()
    collection = _get_collection()
    query_embedding = embedder.encode(query).tolist()

    # 2. Semantic search in ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    if not documents:
        return RAGResponse(
            answer="No relevant articles found for your query.",
            sources=[],
            query=query,
        )

    # 3. Build context
    context = "\n\n".join([
        f"[{i+1}] {doc[:400]}" for i, doc in enumerate(documents)
    ])

    # 4. LLM answer with citations
    prompt = f"""You are a news intelligence assistant. Answer the question using ONLY the provided context.
Cite sources using [1], [2], etc. Be concise and factual.

Context:
{context}

Question: {query}

Answer:"""

    try:
        ollama_client = ollama.Client(host=OLLAMA_HOST)
        response = ollama_client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response["message"]["content"].strip()
    except Exception as e:
        log.error(f"LLM error: {e}")
        answer = f"LLM unavailable. Top result: {documents[0][:200]}"

    # 5. Fetch source metadata
    article_ids = [m.get("article_id", "") for m in metadatas]
    sources_list = [m.get("source", "unknown") for m in metadatas]
    sources = _fetch_article_metadata(article_ids, sources_list)

    return RAGResponse(answer=answer, sources=sources, query=query)

if __name__ == "__main__":
    result = ask("What are the latest developments in artificial intelligence?")
    print(f"\nAnswer:\n{result.answer}")
    print(f"\nSources ({len(result.sources)}):")
    for s in result.sources:
        print(f"  - [{s.source}] {s.title[:60]}")
