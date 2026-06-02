"""
reddit_producer.py
Fetches hot posts from Reddit and publishes to Kafka topic: reddit-raw
"""
import json
import logging
import os
from datetime import datetime

import praw
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC             = "reddit-raw"

SUBREDDITS = ["worldnews", "technology", "artificial", "economics", "science", "europe"]

def run():
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID", ""),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
        user_agent=os.getenv("REDDIT_USER_AGENT", "p2-intelligence/1.0"),
    )

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )

    total = 0
    for subreddit_name in SUBREDDITS:
        log.info(f"Fetching Reddit: r/{subreddit_name}")
        try:
            subreddit = reddit.subreddit(subreddit_name)
            for post in subreddit.hot(limit=25):
                payload = {
                    "id":           post.id,
                    "subreddit":    subreddit_name,
                    "title":        post.title,
                    "selftext":     post.selftext[:1000] if post.selftext else None,
                    "score":        post.score,
                    "num_comments": post.num_comments,
                    "url":          post.url,
                    "created_utc":  datetime.utcfromtimestamp(post.created_utc).isoformat(),
                    "author":       str(post.author) if post.author else None,
                    "loaded_at":    datetime.now().isoformat(),
                }
                producer.send(TOPIC, key=post.id, value=payload)
                total += 1
        except Exception as e:
            log.error(f"Reddit error for r/{subreddit_name}: {e}")

    producer.flush()
    producer.close()
    log.info(f"✅ Published {total} posts to {TOPIC}")

if __name__ == "__main__":
    run()
