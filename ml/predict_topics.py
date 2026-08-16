import re
import time
from elasticsearch import Elasticsearch, helpers

# =========================================================================
# 1. Configuration et Connexion Elasticsearch
# =========================================================================
ES_HOST = "http://localhost:9200"
INDEX_NAME = "reviews"

# Taille des lots (2000 documents) pour concilier vitesse et usage mémoire
BATCH_SIZE = 2000
SCROLL_TIMEOUT = "5m"

# Connexion directe au conteneur Elasticsearch local
client = Elasticsearch([ES_HOST], request_timeout=60)

# =========================================================================
# 2. Dictionnaire enrichi des règles thématiques (Regex)
# =========================================================================
# Chaque catégorie est enrichie avec les termes découverts lors de l'inspection.
THEMES_CONFIG = {
    "Livraison": [
        r"\bcolis\b", r"\blivraison\b", r"\blivr[eé]\b", r"\bfacteur\b",
        r"\bretard\b", r"\bre[cç]u\b", r"\btransporteur\b", r"\bchronopost\b",
        r"\bdhl\b", r"\brelais\b", r"\bd[eé]lai[s]?\b", r"\benvoi\b",
        r"\bexp[eé]diti?on\b", r"\bexp[eé]di[eé]\b", r"\brapidit[eé]\b",
        r"\brapide\b", r"\brapidement\b", r"\breception\b", r"\br[eé]ception\b"
    ],
    "Qualite du produit": [
        r"\bqualit[eé]\b", r"\bcass[eé]\b", r"\bsolide\b", r"\bfragile\b",
        r"\bpanne\b", r"\bmati[eè]re\b", r"\bdurable\b", r"\btissu\b",
        r"\bconforme\b", r"\bdefectueux\b", r"\bd[eé]fectueux\b",
        r"\bproduit\b", r"\barticle\b", r"\bmat[eé]riel\b", r"\bcomposant\b"
    ],
    "Service Apres-Vente (SAV)": [
        r"\bs\.?a\.?v\.?\b", r"\bservice client\b", r"\bremboursement\b", r"\bretour\b",
        r"\bt[eé]l[eé]phon[eé]?\b", r"\br[eé]ponse\b", r"\bconseiller\b",
        r"\br[eé]clamation\b", r"\bmail\b", r"\bcontact\b", r"\br[eé]paration\b",
        r"\bgarantie\b", r"\bechange\b", r"\b[eé]change\b"
    ],
    "Prix et Tarifs": [
        r"\bprix\b", r"\bcher\b", r"\babordable\b", r"\barnaque\b",
        r"\bco[uû]t\b", r"\beuro[s]?\b", r"\bpromotion\b", r"\br[eé]duction\b",
        r"\bremise\b", r"\btarif[s]?\b", r"\bfactur[eé]\b"
    ],
    "Accueil": [
        r"\baccueil\b", r"\baccueillant\b", r"\bagence\b", r"\bboutique\b",
        r"\bmagasin\b", r"\bguichet\b", r"\bamabilit[eé]\b", r"\bsourire\b",
        r"\bpersonnel\b", r"\bvendeur\b", r"\bvendeuse\b", r"\bconseill[eè]re?\b",
        r"\bprofessionnalisme\b", r"\br[eé]activit[eé]\b", r"\bcomp[eé]tence\b",
        r"\bconseil\b", r"\b[eé]quipe\b"
    ]
}

# Compilation des expressions régulières pour un traitement haute performance
COMPILED_PATTERNS = {
    theme: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for theme, patterns in THEMES_CONFIG.items()
}

def classify_text(text: str) -> str:
    """
    Parcourt le texte d'un avis client et renvoie la catégorie thématique dominante.
    Renvoie 'Autre' si aucun motif n'est trouvé.
    """
    if not text:
        return "Autre"

    scores = {theme: 0 for theme in COMPILED_PATTERNS}

    # Calcul du nombre de correspondances pour chaque thématique
    for theme, regex_list in COMPILED_PATTERNS.items():
        for regex in regex_list:
            if regex.search(text):
                scores[theme] += 1

    highest_score = max(scores.values())

    # Aucun mot-clé détecté
    if highest_score == 0:
        return "Autre"

    # Attribution de la catégorie ayant le score le plus élevé
    for theme, score in scores.items():
        if score == highest_score:
            return theme

    return "Autre"

# =========================================================================
# 3. Initialisation du curseur de recherche (Scroll)
# =========================================================================
print("[INFO] Connexion a Elasticsearch et initialisation du scroll...")

try:
    page = client.search(
        index=INDEX_NAME,
        query={"match_all": {}},
        scroll=SCROLL_TIMEOUT,
        size=BATCH_SIZE,
        _source=["text"]
    )
    scroll_id = page["_scroll_id"]
    total_docs = page["hits"]["total"]["value"]
    print(f"[INFO] {total_docs} documents detectes dans l'index '{INDEX_NAME}'.")
except Exception as e:
    print(f"[ERREUR] Impossible d'initialiser la lecture Elasticsearch : {e}")
    exit(1)

# =========================================================================
# 4. Traitement et mise à jour par lots (Bulk API)
# =========================================================================
processed_count = 0
start_time = time.time()

print("[INFO] Lancement de la re-categorisation thematique...")

try:
    while len(page["hits"]["hits"]) > 0:
        bulk_actions = []

        for hit in page["hits"]["hits"]:
            doc_id = hit["_id"]
            raw_text = hit.get("_source", {}).get("text", "")

            predicted_topic = classify_text(raw_text)

            # Préparation de l'action de mise à jour unitaire
            action = {
                "_op_type": "update",
                "_index": INDEX_NAME,
                "_id": doc_id,
                "doc": {
                    "thematique_predite": predicted_topic
                }
            }
            bulk_actions.append(action)

        # Envoi en masse des mises à jour
        if bulk_actions:
            success, _ = helpers.bulk(client, bulk_actions, request_timeout=60)
            processed_count += success

        print(f"[STATUT] Progression : {processed_count} / {total_docs} documents traites.")

        # Récupération du lot suivant
        page = client.scroll(scroll_id=scroll_id, scroll=SCROLL_TIMEOUT)
        scroll_id = page["_scroll_id"]

except Exception as e:
    print(f"[ERREUR] Erreur rencontree pendant le traitement : {e}")
finally:
    # Fermeture de la session de scroll
    try:
        client.clear_scroll(scroll_id=scroll_id)
    except Exception:
        pass

elapsed_time = time.time() - start_time
print(f"[TERMINE] {processed_count} documents traites et mis a jour en {elapsed_time:.2f} secondes.")