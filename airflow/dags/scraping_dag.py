from datetime import datetime, timedelta
from airflow.decorators import dag, task

default_args = {
    "owner": "data-eng",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

@dag(
    dag_id="scraping_reviews_weekly",
    description="Scraping Trustpilot + Google, transform et chargement dans ES",
    schedule_interval="0 6 * * 1",
    start_date=datetime(2025, 10, 29),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["reviews", "weekly"],
)
def pipeline():


    @task()
    def scrape_trustpilot() -> list:
        from scraping.extract_trustpilot import main
        return main()

    @task()
    def scrape_google() -> list:
        """Scrape les avis Google. Retourne la liste des reviews (historique + nouveaux)."""
        from scraping.scrape_google_reviews import main
        return main()

    @task()
    def load_trustpilot(tp_reviews: list):
        """Transform et charge les avis Trustpilot dans ES."""
        from scraping.transform import transform
        from scraping.load import (
            get_es_client,
            create_index_if_not_exists,
            load_to_elasticsearch,
            INDEX_NAME,
        )
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        final = transform([], tp_reviews)
        load_to_elasticsearch(final, client)

    @task()
    def load_google(google_reviews: list):
        """Charge les avis Google dans ES."""
        from scraping.load import (
            get_es_client,
            create_index_if_not_exists,
            load_to_elasticsearch,
            INDEX_NAME,
        )
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        load_to_elasticsearch(google_reviews, client)

    tp = scrape_trustpilot()
    google = scrape_google()
    load_trustpilot(tp)
    load_google(google)

dag = pipeline()