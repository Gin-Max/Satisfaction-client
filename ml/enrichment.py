# Used by Airflow

import os
import re
import pickle
from typing import List, Dict, Any
from elasticsearch.helpers import bulk
from scraping.load import INDEX_NAME, get_es_client

# -------------------------------------------------------------------------
# 1. Chargement des modèles sérialisés de sentiment
# -------------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

# Chemins possibles pour les fichiers .pkl
SEARCH_PATHS = [
    os.path.join(CURRENT_DIR),
    os.path.join(PROJECT_ROOT, "ml")
]

vectorizer = None
sentiment_model = None

for path in SEARCH_PATHS:
    vec_path = os.path.join(path, "tfidf_vectorizer.pkl")
    mod_path = os.path.join(path, "logistic_regression_model.pkl")
    if os.path.exists(vec_path) and os.path.exists(mod_path):
        try:
            with open(vec_path, "rb") as f:
                vectorizer = pickle.load(f)
            with open(mod_path, "rb") as f:
                sentiment_model = pickle.load(f)
            break
        except Exception:
            pass

# -------------------------------------------------------------------------
# 2. Dictionnaire de règles Regex pour les thématiques
# -------------------------------------------------------------------------
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

COMPILED_PATTERNS = {
    theme: [re.compile(p, re.IGNORECASE) for p in patterns]
    for theme, patterns in THEMES_CONFIG.items()
}

def predict_theme(text: str) -> str:
    """Détecte la thématique dominante à partir du texte."""
    if not text or not isinstance(text, str):
        return "Autre"

    scores = {theme: 0 for theme in COMPILED_PATTERNS}
    for theme, regex_list in COMPILED_PATTERNS.items():
        for regex in regex_list:
            if regex.search(text):
                scores[theme] += 1

    top_score = max(scores.values())
    if top_score == 0:
        return "Autre"

    for theme, score in scores.items():
        if score == top_score:
            return theme
    return "Autre"

def enrich_reviews(reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ajoute sentiment_predit et thematique_predite à chaque dictionnaire d'avis."""
    if not reviews:
        return []

    texts = [str(r.get("text", "") or "") for r in reviews]

    # Inférence du sentiment
    sentiments = []
    if vectorizer and sentiment_model and any(t.strip() for t in texts):
        try:
            features = vectorizer.transform(texts)
            sentiments = sentiment_model.predict(features).tolist()
        except Exception:
            sentiments = ["Inconnu"] * len(reviews)
    else:
        sentiments = ["Inconnu"] * len(reviews)

    # Enrichissement unitaire
    enriched = []
    for i, review in enumerate(reviews):
        item = dict(review)
        item["sentiment_predit"] = sentiments[i]
        item["thematique_predite"] = predict_theme(texts[i])
        enriched.append(item)

    return enriched

def backfill_unenriched_reviews(batch_size: int = 500) -> int:
    """Recherche tous les documents sans 'thematique_predite' dans Elasticsearch

    et les met à jour avec les prédictions ML.
    """
    client = get_es_client()

    # Requête pour filtrer les documents incomplets
    query = {
        "query": {"bool": {"must_not": {"exists": {"field": "thematique_predite"}}}}}

    # Comptage des documents à traiter
    count_res = client.count(index=INDEX_NAME, body=query)
    total_to_update = count_res.get("count", 0)

    if total_to_update == 0:
        print(
            f"[INFO] Tous les documents de l'index '{INDEX_NAME}' sont déjà enrichis."
        )
        return 0

    print(
        f"[INFO] {total_to_update} avis non enrichis trouvés. Lancement du rattrapage..."
    )

    # Récupération des avis non enrichis
    search_res = client.search(index=INDEX_NAME, body=query, size=batch_size)
    hits = search_res["hits"]["hits"]

    reviews_to_enrich = []
    doc_ids = []

    for hit in hits:
        doc_ids.append(hit["_id"])
        reviews_to_enrich.append(hit["_source"])

    # Enrichissement par le modèle ML et les règles Regex
    enriched_data = enrich_reviews(reviews_to_enrich)

    # Préparation de l'opération de mise à jour Bulk pour Elasticsearch
    actions = []
    for doc_id, enriched_doc in zip(doc_ids, enriched_data):
        action = {
            "_op_type": "update",
            "_index": INDEX_NAME,
            "_id": doc_id,
            "doc": {
                "sentiment_predit": enriched_doc.get("sentiment_predit"),
                "thematique_predite": enriched_doc.get("thematique_predite"),
            },
        }
        actions.append(action)

    success_count, _ = bulk(client, actions)
    print(f"[SUCCÈS] {success_count} documents historiques ont été enrichis.")
    return success_count