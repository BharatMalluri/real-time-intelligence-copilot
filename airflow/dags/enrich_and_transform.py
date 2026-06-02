"""
enrich_and_transform.py
Airflow DAG: enrich articles with AI → run dbt models
Schedule: every 4 hours (after ingest)
"""
from __future__ import annotations
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.external_task import ExternalTaskSensor

default_args = {
    "owner": "data-engineering",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

DBT_DIR = "/opt/airflow/dbt"

with DAG(
    dag_id="enrich_and_transform",
    default_args=default_args,
    description="AI enrichment (embeddings + LLM) → dbt build",
    schedule_interval="0 */4 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["enrichment", "dbt", "rag", "ai"],
) as dag:

    wait_for_ingest = ExternalTaskSensor(
        task_id="wait_for_ingest",
        external_dag_id="ingest_all_sources",
        external_task_id="log_pipeline_run",
        timeout=3600,
        mode="reschedule",
    )

    enrich = BashOperator(
        task_id="enrich_articles",
        bash_command="cd /opt/airflow && python rag/enrich_articles.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_DIR} && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_DIR} && dbt test --profiles-dir .",
    )

    wait_for_ingest >> enrich >> dbt_run >> dbt_test
