from datetime import datetime, timedelta

from airflow.decorators import dag, task

default_args = {"owner": "data-eng", "retries": 2, "retry_delay": timedelta(minutes=5)}


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
    def scrape_trustpilot() -> list:
        from scraping.extract_trustpilot import scrape_pages
        return scrape_pages(num_pages=10)

    @task()
    def scrape_google() -> list:
        from scraping.load_google import GOOGLE_CSV, load_google_reviews_from_csv
        from scraping.scrape_google_reviews import main
        main()
        return load_google_reviews_from_csv(GOOGLE_CSV)

    @task()
    def transform_and_load(tp_reviews: list, g_reviews: list):
        from scraping.load import INDEX_NAME, create_index_if_not_exists, get_es_client, load_to_elasticsearch
        from scraping.load_google import load_google_to_elasticsearch, transform_google_reviews
        from scraping.transform import transform
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        final = transform([], tp_reviews)
        load_to_elasticsearch(final, client)
        load_google_to_elasticsearch(transform_google_reviews(g_reviews), client)

    tp = scrape_trustpilot()
    g = scrape_google()
    transform_and_load(tp, g)


dag = pipeline()
