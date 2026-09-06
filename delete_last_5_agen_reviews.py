import os
from elasticsearch import Elasticsearch

def delete_last_5_agen_reviews():
    # Connexion à Elasticsearch (utilise la variable d'environnement ou localhost par défaut)
    es_host = os.environ.get("ELASTIC_HOST", "http://localhost:9200")
    es = Elasticsearch(es_host)

    try:
        # Vérifier si l'index existe
        if not es.indices.exists(index="reviews"):
            print("L'index 'reviews' n'existe pas encore.")
            return

        # Recherche des 5 avis les plus récents pour "Agen"
        result = es.search(
            index="reviews",
            query={
                "match": {
                    "store": "Agen"
                }
            },
            sort=[
                {"published_date": {"order": "desc"}}
            ],
            size=5
        )

        hits = result["hits"]["hits"]

        if not hits:
            print("Aucun avis trouvé pour le magasin contenant 'agen'.")
            return

        print(f"Trouvé {len(hits)} avis pour 'agen'. Suppression en cours...")

        # Suppression des documents
        for hit in hits:
            doc_id = hit["_id"]
            source = hit["_source"]
            date = source.get("published_date", "Date inconnue")
            store = source.get("store", "Magasin inconnu")
            author = source.get("author_name", "Anonyme")
            
            # Suppression du document via son _id
            es.delete(index="reviews", id=doc_id)
            print(f"✅ Avis supprimé : ID={doc_id} | Magasin='{store}' | Date={date[:10]} | Auteur={author}")

        print("\nSuppression terminée avec succès ! Vous pouvez maintenant relancer le scrapping pour les récupérer.")

    except Exception as e:
        print(f"Erreur lors de la connexion ou de la suppression : {e}")

if __name__ == "__main__":
    delete_last_5_agen_reviews()
