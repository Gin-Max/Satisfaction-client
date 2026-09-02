import joblib
import time
from elasticsearch import Elasticsearch

# 1. Connexion directe à la base
es = Elasticsearch(["http://localhost:9200"], request_timeout=60)
INDEX_NAME = "reviews"

# 2. Chargement du modèle de sentiment
print("Chargement du modèle de sentiment...")
try:
    vectorizer = joblib.load("ml/tfidf_vectorizer.pkl")
    model_sentiment = joblib.load("ml/logistic_regression_model.pkl")
    print("Modèle chargé.")
except Exception as e:
    print(f"Erreur pkl : {e}")
    exit()

# 3. Initialisation du Scroll (on demande des paquets de 2000 avis pour être tranquille)
print("\nInitialisation de la lecture complète de la base...")
try:
    page = es.search(
        index=INDEX_NAME,
        query={"match_all": {}},
        scroll="2m",  # Garde la recherche en mémoire pendant 2 minutes entre chaque paquet
        size=2000     # Taille de chaque paquet (inférieur à 10 000, donc Elastic accepte !)
    )
    scroll_id = page["_scroll_id"]
    hits = page["hits"]["total"]["value"]
    print(f"Nombre total d'avis détectés dans la base : {hits}")
except Exception as e:
    print(f"Impossible d'initialiser la lecture : {e}")
    exit()

# 4. Boucle de traitement globale
compteur = 0
print("\nAnalyse et injection des sentiments en cours...")

# Tant qu'Elasticsearch nous renvoie des avis
while len(page["hits"]["hits"]) > 0:
    for hit in page["hits"]["hits"]:
        doc_id = hit["_id"]
        source = hit["_source"]
        texte_brut = str(source.get("text", ""))

        # IA : Prédiction du sentiment
        texte_vec = vectorizer.transform([texte_brut])
        pred_sent = model_sentiment.predict(texte_vec)[0]
        sentiment_final = "Positif" if pred_sent == 1 else "Négatif"

        # Écriture directe un par un dans Elasticsearch
        try:
            es.update(
                index=INDEX_NAME,
                id=doc_id,
                body={"doc": {"sentiment_predit": sentiment_final}}
            )
            compteur += 1
            if compteur % 2000 == 0:
                print(f"Progression : {compteur} / {hits} avis enrichis...")
        except Exception as e:
            pass

    # Une fois le paquet fini, on demande le paquet suivant avec le scroll_id
    try:
        page = es.scroll(scroll_id=scroll_id, scroll="2m")
        scroll_id = page["_scroll_id"]
    except Exception as e:
        print(f"\nFin du scroll ou erreur : {e}")
        break

print(f"\nTerminé ! {compteur} avis ont été enrichis avec succès.")