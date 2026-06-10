import csv
import os

from elasticsearch import helpers

from scraping.load import INDEX_NAME, create_index_if_not_exists, get_es_client
from scraping.transform import normalize_google_review

GOOGLE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "google_reviews.csv")


def load_google_reviews_from_csv(filepath):
    reviews = []
    if not os.path.exists(filepath):
        print(f"Fichier non trouvé: {filepath}")
        return reviews
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            reviews.append(row)
    print(f"{len(reviews)} avis Google lus depuis le CSV")
    return reviews


def transform_google_reviews(raw_reviews):
    transformed = []
    for row in raw_reviews:
        normalized = normalize_google_review(row)
        if normalized["text"]:
            transformed.append(normalized)
    print(f"{len(transformed)} avis Google après transformation")
    return transformed


def load_google_to_elasticsearch(reviews, client, index_name=INDEX_NAME):
    if not reviews:
        print("Aucun avis Google à indexer")
        return
    actions = [{"_index": index_name, "_id": review["review_id"], "_source": review} for review in reviews]
    success_count, errors = helpers.bulk(client, actions, raise_on_error=False, raise_on_exception=False)
    if errors:
        print(f"Erreurs lors de l'indexation: {len(errors)}")
    print(f"{success_count} avis Google indexés dans Elasticsearch")


def main():
    client = get_es_client()
    create_index_if_not_exists(client, INDEX_NAME)
    raw_reviews = load_google_reviews_from_csv(GOOGLE_CSV)
    transformed_reviews = transform_google_reviews(raw_reviews)
    load_google_to_elasticsearch(transformed_reviews, client)


if __name__ == "__main__":
    main()
