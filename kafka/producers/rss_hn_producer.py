"""
rss_hn_producer.py
Fetches RSS feeds (BBC, Reuters, DW) and Hacker News top stories.
Publishes to Kafka topics: rss-raw, hn-raw
"""
import hashlib
import json
import logging
import os
from datetime import datetime

import feedparser
import requests
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

RSS_FEEDS = [
    {"name": "BBC World",    "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "BBC Tech",     "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"name": "Reuters World","url": "https://feeds.reuters.com/reuters/worldNews"},
    {"name": "DW News",      "url": "https://rss.dw.com/rdf/rss-en-all"},
]

def make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()

def run_rss(producer):
    total = 0
    for feed in RSS_FEEDS:
        log.info(f"Fetching RSS: {feed['name']}")
        try:
            parsed = feedparser.parse(feed["url"])
            for entry in parsed.entries[:20]:
                item_id = make_id(entry.get("link", entry.get("title", "")))
                published = entry.get("published", datetime.now().isoformat())
                payload = {
                    "id":           item_id,
                    "feed_name":    feed["name"],
                    "feed_url":     feed["url"],
                    "title":        entry.get("title"),
                    "summary":      entry.get("summary"),
                    "link":         entry.get("link"),
                    "published_at": published,
                    "loaded_at":    datetime.now().isoformat(),
                }
                producer.send("rss-raw", key=item_id, value=payload)
                total += 1
        except Exception as e:
            log.error(f"RSS error for {feed['name']}: {e}")
    log.info(f"✅ Published {total} RSS items to rss-raw")

def run_hn(producer):
    log.info("Fetching Hacker News top stories...")
    total = 0
    try:
        top_ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json"
        ).json()[:30]

        for item_id in top_ids:
            try:
                item = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
                ).json()
                if not item or item.get("type") not in ("story", "ask"):
                    continue
                payload = {
                    "id":           item_id,
                    "item_type":    item.get("type"),
                    "title":        item.get("title"),
                    "url":          item.get("url"),
                    "score":        item.get("score", 0),
                    "num_comments": item.get("descendants", 0),
                    "author":       item.get("by"),
                    "created_at":   datetime.utcfromtimestamp(
                                        item.get("time", 0)
                                    ).isoformat(),
                    "loaded_at":    datetime.now().isoformat(),
                }
                producer.send("hn-raw", key=str(item_id), value=payload)
                total += 1
            except Exception as e:
                log.error(f"HN item error {item_id}: {e}")
    except Exception as e:
        log.error(f"HN fetch error: {e}")
    log.info(f"✅ Published {total} HN items to hn-raw")

def run():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )
    run_rss(producer)
    run_hn(producer)
    producer.flush()
    producer.close()

if __name__ == "__main__":
    run()
