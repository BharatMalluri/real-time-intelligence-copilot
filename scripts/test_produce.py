import os
import json
import requests
from datetime import datetime
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers="10.102.48.29:9093",
    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8"),
    request_timeout_ms=60000,
    max_block_ms=60000,
    retries=5,
)

print("Fetching HN...")
top_ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:10]
for item_id in top_ids:
    item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json").json()
    if not item:
        continue
    future = producer.send("hn-raw", key=str(item_id), value={
        "id": item_id,
        "title": item.get("title"),
        "url": item.get("url"),
        "score": item.get("score", 0),
        "item_type": item.get("type"),
        "author": item.get("by"),
        "num_comments": item.get("descendants", 0),
        "created_at": datetime.utcfromtimestamp(item.get("time", 0)).isoformat(),
        "loaded_at": datetime.now().isoformat(),
    })
    result = future.get(timeout=30)
    print(f"Sent: offset {result.offset} partition {result.partition}")

producer.flush()
producer.close()
print("Done!")