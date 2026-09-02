"""
Script pour charger les avis Google dans Elasticsearch.
Les reviews sont déjà au format normalisé (venant de scrape_google_reviews.py).
"""

from scraping.load import get_es_client, create_index_if_not_exists, load_to_elasticsearch, INDEX_NAME


def load_google_reviews(reviews, client=None):
    """Charge les avis Google dans Elasticsearch."""
    if client is None:
        client = get_es_client()

    create_index_if_not_exists(client, INDEX_NAME)

    if not reviews:
        print("Aucun avis Google à indexer")
        return

    load_to_elasticsearch(reviews, client)
    print(f"{len(reviews)} avis Google traités")


def main():
    """Point d'entrée standalone (pour tests)."""
    print("=" * 60)
    print("  CHARGEMENT DES AVIS GOOGLE DANS ELASTICSEARCH")
    print("=" * 60)

    # Importer et exécuter le scraping
    from scraping.scrape_google_reviews import main as scrape_main
    reviews = scrape_main()

    # Charger dans ES
    load_google_reviews(reviews)

    # Stats finales
    client = get_es_client()
    try:
        count = client.count(index=INDEX_NAME)["count"]
        print(f"\nTotal d'avis dans l'index '{INDEX_NAME}': {count}")
    except Exception as e:
        print(f"Erreur lors du comptage: {e}")

    print("=" * 60)
    print("  CHARGEMENT TERMINÉ")
    print("=" * 60)
