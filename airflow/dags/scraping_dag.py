from datetime import datetime, timedelta
from airflow.decorators import dag, task

default_args = {
    "owner": "data-eng",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

@dag(
    dag_id="scraping_reviews_weekly",
    description="Scraping Trustpilot + Google, transform et chargement dans ES",
    schedule_interval="0 6 * * 1",  # lundi 6h
    start_date=datetime(2025, 10, 29),
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["reviews", "weekly"],
)
def pipeline():

    @task()
    def scrape_trustpilot() -> list:
        from scraping.extract_trustpilot import scrape_pages
        return scrape_pages(num_pages=10)

    @task()
    def scrape_google() -> list:
        from scraping.scrape_google_reviews import scrape_google_reviews
        return scrape_google_reviews()

    @task()
    def transform_and_load(tp_reviews: list, g_reviews: list):
        from scraping.transform import transform
        from scraping.load import (
            get_es_client,
            create_index_if_not_exists,
            load_to_elasticsearch,
            INDEX_NAME,
        )
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        final = transform([], tp_reviews + g_reviews)
        load_to_elasticsearch(final, client)

    tp = scrape_trustpilot()
    g = scrape_google()
    transform_and_load(tp, g)

dag = pipeline()