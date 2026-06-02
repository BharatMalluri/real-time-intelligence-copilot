"""
ingest_all_sources.py
Airflow DAG: fetch all sources → publish to Kafka → consume to PostgreSQL
Schedule: every 2 hours
"""
from __future__ import annotations
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=3),
    "email_on_failure": False,
}

def log_run(**context):
    import psycopg2, os
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "intelligence"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO monitoring.pipeline_runs (dag_id, run_id, source, status, started_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (context["dag"].dag_id, context["run_id"], "all", "success", context["data_interval_start"]))
    conn.commit()
    cur.close()
    conn.close()

with DAG(
    dag_id="ingest_all_sources",
    default_args=default_args,
    description="Ingest NewsAPI, Reddit, RSS, HN → Kafka → PostgreSQL",
    schedule_interval="0 */2 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["ingestion", "kafka", "streaming"],
) as dag:

    produce_news = BashOperator(
        task_id="produce_news",
        bash_command="cd /opt/airflow && python kafka/producers/news_producer.py",
    )

    produce_reddit = BashOperator(
        task_id="produce_reddit",
        bash_command="cd /opt/airflow && python kafka/producers/reddit_producer.py",
    )

    produce_rss_hn = BashOperator(
        task_id="produce_rss_hn",
        bash_command="cd /opt/airflow && python kafka/producers/rss_hn_producer.py",
    )

    consume_to_pg = BashOperator(
        task_id="consume_to_postgres",
        bash_command="cd /opt/airflow && python kafka/consumers/postgres_consumer.py",
    )

    log_pipeline = PythonOperator(
        task_id="log_pipeline_run",
        python_callable=log_run,
    )

    [produce_news, produce_reddit, produce_rss_hn] >> consume_to_pg >> log_pipeline
