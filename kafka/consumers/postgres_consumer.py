"""
postgres_consumer.py
Consumes messages from all raw Kafka topics and writes to PostgreSQL raw schema.
Run as a long-lived process or via Airflow.
"""
import json
import logging
import os
import threading
from datetime import datetime

import psycopg2
from kafka import KafkaConsumer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

def get_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "intelligence"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )

def consume_news(conn):
    consumer = KafkaConsumer(
        "news-raw",
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="news-pg-consumer",
        auto_offset_reset="earliest",
        consumer_timeout_ms=10000,
    )
    cur = conn.cursor()
    count = 0
    for msg in consumer:
        d = msg.value
        cur.execute("""
            INSERT INTO raw.news_articles
                (id, source, title, description, content, url, published_at, author, category, loaded_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, (
            d.get("id"), d.get("source"), d.get("title"), d.get("description"),
            d.get("content"), d.get("url"), d.get("published_at"),
            d.get("author"), d.get("category"), d.get("loaded_at"),
        ))
        count += 1
    conn.commit()
    cur.close()
    consumer.close()
    log.info(f"✅ news-raw: wrote {count} rows")

def consume_reddit(conn):
    consumer = KafkaConsumer(
        "reddit-raw",
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="reddit-pg-consumer",
        auto_offset_reset="earliest",
        consumer_timeout_ms=10000,
    )
    cur = conn.cursor()
    count = 0
    for msg in consumer:
        d = msg.value
        cur.execute("""
            INSERT INTO raw.reddit_posts
                (id, subreddit, title, selftext, score, num_comments, url, created_utc, author, loaded_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, (
            d.get("id"), d.get("subreddit"), d.get("title"), d.get("selftext"),
            d.get("score"), d.get("num_comments"), d.get("url"),
            d.get("created_utc"), d.get("author"), d.get("loaded_at"),
        ))
        count += 1
    conn.commit()
    cur.close()
    consumer.close()
    log.info(f"✅ reddit-raw: wrote {count} rows")

def consume_rss(conn):
    consumer = KafkaConsumer(
        "rss-raw",
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="rss-pg-consumer",
        auto_offset_reset="earliest",
        consumer_timeout_ms=10000,
    )
    cur = conn.cursor()
    count = 0
    for msg in consumer:
        d = msg.value
        cur.execute("""
            INSERT INTO raw.rss_items
                (id, feed_name, feed_url, title, summary, link, published_at, loaded_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, (
            d.get("id"), d.get("feed_name"), d.get("feed_url"), d.get("title"),
            d.get("summary"), d.get("link"), d.get("published_at"), d.get("loaded_at"),
        ))
        count += 1
    conn.commit()
    cur.close()
    consumer.close()
    log.info(f"✅ rss-raw: wrote {count} rows")

def consume_hn(conn):
    consumer = KafkaConsumer(
        "hn-raw",
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="hn-pg-consumer",
        auto_offset_reset="earliest",
        consumer_timeout_ms=10000,
    )
    cur = conn.cursor()
    count = 0
    for msg in consumer:
        d = msg.value
        cur.execute("""
            INSERT INTO raw.hn_items
                (id, item_type, title, url, score, num_comments, author, created_at, loaded_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO NOTHING
        """, (
            d.get("id"), d.get("item_type"), d.get("title"), d.get("url"),
            d.get("score"), d.get("num_comments"), d.get("author"),
            d.get("created_at"), d.get("loaded_at"),
        ))
        count += 1
    conn.commit()
    cur.close()
    consumer.close()
    log.info(f"✅ hn-raw: wrote {count} rows")

def run():
    conn = get_conn()
    threads = [
        threading.Thread(target=consume_news,   args=(conn,)),
        threading.Thread(target=consume_reddit, args=(conn,)),
        threading.Thread(target=consume_rss,    args=(conn,)),
        threading.Thread(target=consume_hn,     args=(conn,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    conn.close()
    log.info("All consumers finished.")

if __name__ == "__main__":
    run()
