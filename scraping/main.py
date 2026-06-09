from extract_trustpilot import extract
from transform import transform
from load import get_es_client, create_index_if_not_exists, load_to_elasticsearch, INDEX_NAME

# Import du pipeline Google
from scrape_google_reviews import main as scrape_google
from load_google import (
    load_google_reviews_from_csv,
    transform_google_reviews,
    load_google_to_elasticsearch,
    GOOGLE_CSV
)


def run_trustpilot_pipeline(client):
    """Pipeline ETL pour les avis Trustpilot."""
    print("\n" + "=" * 60)
    print("  PIPELINE TRUSTPILOT")
    print("=" * 60)

    # Extraction : historique si ES vide + nouvelles reviews
    existing_reviews, new_reviews = extract(client)

    # Transformation : fusion, normalisation, suppression des doublons
    final_reviews = transform(existing_reviews, new_reviews)

    # Chargement dans Elasticsearch
    load_to_elasticsearch(final_reviews, client)


def run_google_pipeline(client):
    """Pipeline ETL pour les avis Google."""
    print("\n" + "=" * 60)
    print("  PIPELINE GOOGLE")
    print("=" * 60)

    # Étape 1: Scraping des avis Google (sauvegarde en CSV)
    print("\n[1/2] Scraping des avis Google...")
    scrape_google()

    # Étape 2: Chargement dans Elasticsearch
    print("\n[2/2] Chargement dans Elasticsearch...")
    raw_reviews = load_google_reviews_from_csv(GOOGLE_CSV)
    transformed_reviews = transform_google_reviews(raw_reviews)
    load_google_to_elasticsearch(transformed_reviews, client)


def main():
    print("=" * 60)
    print("  DÉBUT DU SCRAPING ETL")
    print("=" * 60)

    # Création du client ES et de l'index si nécessaire
    client = get_es_client()
    create_index_if_not_exists(client, INDEX_NAME)

    # Pipeline Trustpilot
    run_trustpilot_pipeline(client)

    # Pipeline Google
    run_google_pipeline(client)

    # Stats finales
    try:
        count = client.count(index=INDEX_NAME)["count"]
        print(f"\nTotal d'avis dans l'index '{INDEX_NAME}': {count}")
    except Exception as e:
        print(f"Erreur lors du comptage: {e}")

    print("\n" + "=" * 60)
    print("  FIN DU SCRAPING ETL")
    print("=" * 60)


if __name__ == "__main__":
    main()
