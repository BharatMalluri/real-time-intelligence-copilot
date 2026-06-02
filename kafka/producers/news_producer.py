"""
news_producer.py
Fetches articles from NewsAPI and publishes to Kafka topic: news-raw
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta

from kafka import KafkaProducer
from newsapi import NewsApiClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
NEWSAPI_KEY       = os.getenv("NEWSAPI_KEY", "")
TOPIC             = "news-raw"

QUERIES = ["technology", "artificial intelligence", "economy", "climate", "geopolitics"]

def make_id(title: str, published_at: str) -> str:
    return hashlib.md5(f"{title}{published_at}".encode()).hexdigest()

def run():
    if not NEWSAPI_KEY:
        raise ValueError("NEWSAPI_KEY environment variable not set")

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )

    client = NewsApiClient(api_key=NEWSAPI_KEY)
    from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    total = 0

    for query in QUERIES:
        log.info(f"Fetching NewsAPI: {query}")
        try:
            response = client.get_everything(
                q=query,
                from_param=from_date,
                language="en",
                sort_by="publishedAt",
                page_size=20,
            )
            for article in response.get("articles", []):
                article_id = make_id(
                    article.get("title", ""),
                    article.get("publishedAt", "")
                )
                payload = {
                    "id":           article_id,
                    "source":       "newsapi",
                    "title":        article.get("title"),
                    "description":  article.get("description"),
                    "content":      article.get("content"),
                    "url":          article.get("url"),
                    "published_at": article.get("publishedAt"),
                    "author":       article.get("author"),
                    "category":     query,
                    "loaded_at":    datetime.now().isoformat(),
                }
                producer.send(TOPIC, key=article_id, value=payload)
                total += 1
        except Exception as e:
            log.error(f"NewsAPI error for query '{query}': {e}")

    producer.flush()
    producer.close()
    log.info(f"✅ Published {total} articles to {TOPIC}")

if __name__ == "__main__":
    run()
