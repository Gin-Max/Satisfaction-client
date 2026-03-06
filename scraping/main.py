from extract_trustpilot import extract
from transform import transform
from load import get_es_client, create_index_if_not_exists, load_to_elasticsearch, INDEX_NAME

def main():
    
    print("=== Début du scraping ETL ===")
    # Création du client ES et de l'index si nécessaire
    client = get_es_client()
    create_index_if_not_exists(client, INDEX_NAME)

    # Extraction : historique si ES vide + nouvelles reviews
    existing_reviews, new_reviews = extract(client)

    # Transformation : fusion, normalisation, suppression des doublons
    final_reviews = transform(existing_reviews, new_reviews)

    # Chargement dans Elasticsearch
    load_to_elasticsearch(final_reviews, client)

    print("=== Fin du scraping ETL ===")


if __name__ == "__main__":
    main()