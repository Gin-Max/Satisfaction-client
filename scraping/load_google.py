"""
Script pour charger les avis Google dans Elasticsearch.
Lit le fichier google_reviews.csv et l'intègre au même index que Trustpilot.
"""

import csv
import os
from transform import normalize_google_review
from load import get_es_client, create_index_if_not_exists, INDEX_NAME
from elasticsearch import helpers

# Chemin vers le CSV Google
GOOGLE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "google_reviews.csv")


def load_google_reviews_from_csv(filepath):
    """Lit le CSV Google et retourne une liste de dictionnaires."""
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
    """Transforme les avis Google au format Elasticsearch."""
    transformed = []
    for row in raw_reviews:
        normalized = normalize_google_review(row)
        # Ignorer les avis sans texte
        if normalized["text"]:
            transformed.append(normalized)

    print(f"{len(transformed)} avis Google après transformation")
    return transformed


def load_google_to_elasticsearch(reviews, client, index_name=INDEX_NAME):
    """Charge les avis Google dans Elasticsearch."""
    if not reviews:
        print("Aucun avis Google à indexer")
        return

    actions = [
        {
            "_index": index_name,
            "_id": review["review_id"],
            "_source": review,
        }
        for review in reviews
    ]

    # Utiliser upsert pour mettre à jour ou créer
    success_count, errors = helpers.bulk(
        client,
        actions,
        raise_on_error=False,
        raise_on_exception=False
    )

    if errors:
        print(f"Erreurs lors de l'indexation: {len(errors)}")

    print(f"{success_count} avis Google indexés dans Elasticsearch")


def main():
    print("=" * 60)
    print("  CHARGEMENT DES AVIS GOOGLE DANS ELASTICSEARCH")
    print("=" * 60)

    # Connexion à Elasticsearch
    client = get_es_client()

    # Vérifier la connexion
    try:
        info = client.info()
        print(f"Connecté à Elasticsearch {info['version']['number']}")
    except Exception as e:
        print(f"Erreur de connexion à Elasticsearch: {e}")
        print("Assurez-vous qu'Elasticsearch est lancé (docker-compose up elasticsearch)")
        return

    # Créer l'index si nécessaire
    create_index_if_not_exists(client, INDEX_NAME)

    # Charger et transformer les avis Google
    raw_reviews = load_google_reviews_from_csv(GOOGLE_CSV)
    transformed_reviews = transform_google_reviews(raw_reviews)

    # Charger dans Elasticsearch
    load_google_to_elasticsearch(transformed_reviews, client)

    # Stats finales
    try:
        count = client.count(index=INDEX_NAME)["count"]
        print(f"\nTotal d'avis dans l'index '{INDEX_NAME}': {count}")
    except Exception as e:
        print(f"Erreur lors du comptage: {e}")

    print("=" * 60)
    print("  CHARGEMENT TERMINÉ")
    print("=" * 60)


if __name__ == "__main__":
    main()
