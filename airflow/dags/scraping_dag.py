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
    def scrape_google() -> str:
        """Scrape les avis Google et sauvegarde en CSV. Retourne le chemin du CSV."""
        from scraping.scrape_google_reviews import main
        main()
        from scraping.load_google import GOOGLE_CSV
        return GOOGLE_CSV

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
    def load_google(csv_path: str):
        """Charge les avis Google depuis le CSV dans ES."""
        from scraping.load_google import (
            load_google_reviews_from_csv,
            transform_google_reviews,
            load_google_to_elasticsearch,
        )
        from scraping.load import get_es_client, create_index_if_not_exists, INDEX_NAME
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        raw_reviews = load_google_reviews_from_csv(csv_path)
        transformed_reviews = transform_google_reviews(raw_reviews)
        load_google_to_elasticsearch(transformed_reviews, client)

    tp = scrape_trustpilot()
    csv_path = scrape_google()
    load_trustpilot(tp)
    load_google(csv_path)

dag = pipeline()