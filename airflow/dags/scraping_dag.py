from datetime import datetime, timedelta, timezone

from airflow.decorators import (
    dag,
    task,
)
from notifications import task_failure_alert

default_args = {
    "owner": "data-eng",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
    "on_failure_callback": task_failure_alert,
}

@dag(
    dag_id="scraping_reviews_daily",
    description="Scraping Trustpilot + Google (API places, 5 derniers avis/store), transform et chargement dans ES",
    schedule="0 6 * * *",
    start_date=datetime(2025, 10, 29, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["reviews", "daily"],
)
def pipeline():

    @task()
    def init_ES():
        """Crée l'index Elasticsearch si nécessaire et charge l'historique
        Trustpilot/Google si aucune donnée n'est encore présente pour ces sources."""
        from scraping.load import INDEX_NAME, create_index_if_not_exists, get_es_client, load_to_elasticsearch
        from scraping.transform import transform
        from scraping.extract_trustpilot import is_trustpilot_empty, load_historical_reviews
        from scraping.extract_google import is_google_empty, load_historical_google_reviews

        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)

        if is_trustpilot_empty(client):
            historical_tp = load_historical_reviews()
            final_tp = transform([], historical_tp)
            load_to_elasticsearch(final_tp, client)
            print(f"[INFO] Bootstrap Trustpilot : {len(final_tp)} avis chargés.")
        else:
            print("[INFO] Données Trustpilot déjà présentes, pas de bootstrap.")

        if is_google_empty(client):
            historical_google = load_historical_google_reviews()
            load_to_elasticsearch(historical_google, client)
            print(f"[INFO] Bootstrap Google : {len(historical_google)} avis chargés.")
        else:
            print("[INFO] Données Google déjà présentes, pas de bootstrap.")


    @task()
    def backfill_existing_reviews():
        """Vérifie si des avis anciens ne sont pas enrichis et les met à jour."""
        from ml.enrichment import backfill_unenriched_reviews
        backfill_unenriched_reviews()

    @task()
    def scrape_trustpilot() -> list:
        """Récupère les dernières pages Trustpilot."""
        from scraping.extract_trustpilot import main
        return main()

    @task()
    def scrape_google() -> list:
        """Récupère les avis Google. Retourne la liste des reviews (5 derniers avis/store)."""
        from scraping.extract_google import main
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
        from scraping.load import (
            INDEX_NAME,
            create_index_if_not_exists,
            get_es_client,
            load_to_elasticsearch,
        )
        from scraping.transform import transform
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        final = transform([], tp_reviews)
        load_to_elasticsearch(final, client)

    @task()
    def load_google(google_reviews: list):
        """Charge les avis Google dans ES."""
        from scraping.load import (
            INDEX_NAME,
            create_index_if_not_exists,
            get_es_client,
            load_to_elasticsearch,
        )
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        load_to_elasticsearch(google_reviews, client)


    init = init_ES()

    backfill = backfill_existing_reviews()
    init >> backfill

    tp = scrape_trustpilot()
    tp_enriched = enrich_trustpilot(tp)
    init >> tp

    google = scrape_google()
    google_enriched = enrich_google(google)
    init >> google

    load_trustpilot(tp_enriched)
    load_google(google_enriched)

dag = pipeline()