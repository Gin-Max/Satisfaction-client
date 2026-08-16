from elasticsearch import Elasticsearch

# 1. Connexion au serveur Elasticsearch local
ES_HOST = "http://localhost:9200"
INDEX_NAME = "reviews"
SAMPLE_SIZE = 5  # Nombre d'exemples à afficher

client = Elasticsearch([ES_HOST], request_timeout=30)

def display_preview():
    """Récupère et affiche un aperçu structuré des avis dans Elasticsearch."""
    try:
        # Requête pour récupérer un échantillon de documents
        response = client.search(
            index=INDEX_NAME,
            query={"match_all": {}},
            size=SAMPLE_SIZE
        )
        
        total_docs = response["hits"]["total"]["value"]
        hits = response["hits"]["hits"]
        
        print("=" * 60)
        print(f"Index : '{INDEX_NAME}' | Total de documents : {total_docs}")
        print(f"Affichage d'un échantillon de {len(hits)} avis :")
        print("=" * 60)
        
        for i, hit in enumerate(hits, start=1):
            source = hit.get("_source", {})
            doc_id = hit.get("_id")
            
            # Extraction des champs pertinents
            text = source.get("text", "N/A")
            sentiment = source.get("sentiment_predit", "Non calculé")
            thematique = source.get("thematique_predite", "Non calculée")
            
            # Tronquer le texte s'il est trop long pour faciliter la lecture
            text_preview = (text[:120] + "...") if len(text) > 120 else text
            
            print(f"[{i}] ID : {doc_id}")
            print(f"    Texte      : {text_preview}")
            print(f"    Sentiment  : {sentiment}")
            print(f"    Thématique : {thematique}")
            print("-" * 60)
            
    except Exception as error:
        print(f"[ERREUR] Impossible d'accéder à Elasticsearch : {error}")

if __name__ == "__main__":
    display_preview()