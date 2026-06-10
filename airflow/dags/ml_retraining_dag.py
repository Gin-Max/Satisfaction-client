from datetime import datetime, timedelta

from airflow.decorators import dag, task

default_args = {"owner": "data-eng", "retries": 2, "retry_delay": timedelta(minutes=5)}


@dag(
    dag_id="ml_retraining_weekly",
    description="Ré-entraînement hebdomadaire du modèle de sentiment",
    schedule="0 8 * * 1",
    start_date=datetime(2025, 10, 29),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["ml", "weekly"],
)
def pipeline():
    @task()
    def check_es_connection() -> bool:
        from scraping.load import get_es_client
        client = get_es_client()
        return client.ping()

    @task()
    def train_model(es_ok: bool):
        if not es_ok:
            raise Exception("Elasticsearch inaccessible, entraînement annulé")
        import runpy
        runpy.run_module("ml.train", run_name="__main__")

    es_ok = check_es_connection()
    train_model(es_ok)


dag = pipeline()
