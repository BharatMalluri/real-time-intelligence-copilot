"""
setup_topics.py
Creates Kafka topics for the intelligence pipeline.
Run once after Kafka starts: python scripts/setup_topics.py
"""
import os
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

TOPICS = [
    NewTopic(name="news-raw",      num_partitions=3, replication_factor=1),
    NewTopic(name="reddit-raw",    num_partitions=3, replication_factor=1),
    NewTopic(name="rss-raw",       num_partitions=3, replication_factor=1),
    NewTopic(name="hn-raw",        num_partitions=3, replication_factor=1),
    NewTopic(name="news-enriched", num_partitions=3, replication_factor=1),
]

admin = KafkaAdminClient(bootstrap_servers=BOOTSTRAP_SERVERS)

for topic in TOPICS:
    try:
        admin.create_topics([topic])
        print(f"✅ Created topic: {topic.name}")
    except TopicAlreadyExistsError:
        print(f"⚠️  Topic already exists: {topic.name}")

admin.close()
print("Done.")
