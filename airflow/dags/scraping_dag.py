from datetime import datetime, timedelta
from airflow.decorators import dag, task # type: ignore (car le Docker tourne sur le conteneur)
from notifications import task_failure_alert

default_args = {
    "owner": "data-eng",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": task_failure_alert,
}

@dag(
    dag_id="scraping_reviews_weekly",
    description="Scraping Trustpilot + Google, transform et chargement dans ES",
    schedule="0 6 * * 1",
    start_date=datetime(2025, 10, 29),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["reviews", "weekly"],
)
def pipeline():

    @task()
    def backfill_existing_reviews():
        """Vérifie si des avis anciens ne sont pas enrichis et les met à jour."""
        from ml.enrichment import backfill_unenriched_reviews
        backfill_unenriched_reviews()

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
    def enrich_trustpilot(tp_reviews: list) -> list:
        """Enrichit les avis Trustpilot avec le sentiment et la thématique prédits."""
        from ml.enrichment import enrich_reviews
        return enrich_reviews(tp_reviews)

    @task()
    def enrich_google(google_reviews: list) -> list:
        """Enrichit les avis Google avec le sentiment et la thématique prédits."""
        from ml.enrichment import enrich_reviews
        return enrich_reviews(google_reviews)
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

    backfill_task = backfill_existing_reviews()
    tp = scrape_trustpilot()
    tp_enriched = enrich_trustpilot(tp)
    google = scrape_google()
    google_enriched = enrich_google(google)
    load_trustpilot(tp_enriched)
    load_google(google_enriched)

dag = pipeline()