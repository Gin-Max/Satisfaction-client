from scraping.extract_trustpilot import extract
from scraping.load import INDEX_NAME, create_index_if_not_exists, get_es_client, load_to_elasticsearch
from scraping.load_google import GOOGLE_CSV, load_google_reviews_from_csv, load_google_to_elasticsearch, transform_google_reviews
from scraping.scrape_google_reviews import main as scrape_google
from scraping.transform import transform


def run_trustpilot_pipeline(client):
    existing_reviews, new_reviews = extract(client)
    final_reviews = transform(existing_reviews, new_reviews)
    load_to_elasticsearch(final_reviews, client)


def run_google_pipeline(client):
    scrape_google()
    raw_reviews = load_google_reviews_from_csv(GOOGLE_CSV)
    transformed_reviews = transform_google_reviews(raw_reviews)
    load_google_to_elasticsearch(transformed_reviews, client)


def main():
    client = get_es_client()
    create_index_if_not_exists(client, INDEX_NAME)
    run_trustpilot_pipeline(client)
    run_google_pipeline(client)


if __name__ == "__main__":
    main()
