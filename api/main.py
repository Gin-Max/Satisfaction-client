from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from elasticsearch import Elasticsearch
from prometheus_fastapi_instrumentator import Instrumentator
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# for Prometheus
Instrumentator().instrument(app).expose(app)

def pseudonymize_name(name: str) -> str:
    """pseudonymise un nom d'auteur."""
    if not name or not isinstance(name, str):
        return name
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[-1][0].upper()}."
    return name


def pseudonymize_doc(doc: dict) -> dict:
    """applique pseudonymisation sur un document avis avant restitution."""
    if "author_name" in doc:
        doc["author_name"] = pseudonymize_name(doc["author_name"])
    doc.pop("author_id", None)
    return doc

def build_filters(source: Optional[str], date_from: Optional[str], date_to: Optional[str]) -> list:
    filters = []
    if source:
        filters.append({"term": {"source": source}})
    if date_from or date_to:
        date_range = {}
        if date_from:
            date_range["gte"] = date_from
        if date_to:
            date_range["lte"] = date_to
        filters.append({"range": {"published_date": date_range}})
    return filters

# Prometheus metrics
#Instrumentator().instrument(app).expose(app)
es = Elasticsearch("http://elasticsearch:9200")

# Route de test
@app.get("/")
def home():
    return {"status": "API OK"}

# Récupérer tous les avis pour le ML
@app.get("/avis")
def get_avis(from_: int = 0, size: int = 1000):
    result = es.search(
        index="reviews", 
        query={"match_all": {}},
        from_=from_,
        size=size
    )
    
    # Sécurité : Si aucun hit (la base est vide à cet index ou on a dépassé la fin)
    hits = result["hits"]["hits"]
    if not hits:
        return {
            "total_dans_la_base": result["hits"]["total"]["value"],
            "taille_paquet": 0,
            "avis": []
        }
        
    avis = []
    for hit in hits:
        doc = hit["_source"]
        doc["id"] = hit["_id"]
        avis.append(pseudonymize_doc(doc))
        
    return {
        "total_dans_la_base": result["hits"]["total"]["value"],
        "taille_paquet": len(avis),
        "avis": avis
    }

# Récupérer les avis par note
@app.get("/avis/note/{note}")
def get_avis_by_note(note: int):
    result = es.search(index="reviews", body={
        "query": {"match": {"rating": note}}
    }, size=10000)
    avis = [pseudonymize_doc(hit["_source"]) for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}

# Récupérer les derniers avis
@app.get("/avis/recents")
def get_avis_recents(limit: int = 10):
    """Retourne les N avis les plus récents."""
    result = es.search(index="reviews", body={
        "query": {"exists": {"field": "published_date"}},
        "sort": [{"published_date": {"order": "desc"}}],
        "size": limit
    })
    avis = [pseudonymize_doc(hit["_source"]) for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}

# Récupérer les avis par source
@app.get("/avis/{source}")
def get_avis_by_source(source: str):
    result = es.search(index="reviews", body={
        "query": {"match": {"source": source}}
    }, size=10000)
    avis = [pseudonymize_doc(hit["_source"]) for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}


@app.get("/stats/distribution-notes")
def get_distribution_notes(source: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None):
    filters = build_filters(source, date_from, date_to)
    query = {"bool": {"filter": filters}} if filters else {"match_all": {}}
    result = es.search(index="reviews", body={
        "size": 0,
        "query": query,
        "aggs": {
            "par_note": {
                "terms": {"field": "rating", "size": 5, "order": {"_key": "asc"}}
            }
        }
    })
    buckets = result["aggregations"]["par_note"]["buckets"]
    return {
        "distribution": [
            {"note": b["key"], "count": b["doc_count"]}
            for b in buckets
        ]
    }

@app.get("/stats/evolution-mensuelle")
def get_evolution_mensuelle(
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    split_provenance: bool = False,
):
    filters = build_filters(source, date_from, date_to)
    query = {"bool": {"filter": [{"exists": {"field": "published_date"}}] + filters}} if filters else {"exists": {"field": "published_date"}}

    date_histogram_agg = {
        "field": "published_date",
        "calendar_interval": "month",
        "format": "yyyy-MM",
    }

    if split_provenance:
        aggs = {
            "par_mois": {
                "date_histogram": date_histogram_agg,
                "aggs": {
                    "par_provenance": {
                        "terms": {"field": "provenance", "size": 20}
                    }
                },
            }
        }
    else:
        aggs = {"par_mois": {"date_histogram": date_histogram_agg}}

    result = es.search(index="reviews", body={
        "size": 0,
        "query": query,
        "aggs": aggs
    })
    buckets = result["aggregations"]["par_mois"]["buckets"]

    if not split_provenance:
        return {
            "evolution": [
                {"mois": b["key_as_string"], "count": b["doc_count"]}
                for b in buckets
            ]
        }

    evolution = []
    for b in buckets:
        row = {"mois": b["key_as_string"], "Organique": 0, "Invitation": 0}
        for pb in b.get("par_provenance", {}).get("buckets", []):
            if pb["key"] == "Organic":
                row["Organique"] += pb["doc_count"]
            else:
                row["Invitation"] += pb["doc_count"]
        evolution.append(row)

    return {"evolution": evolution}

@app.get("/stats/taux-reponse")
def get_taux_reponse():
    """Taux de réponse de l'entreprise aux avis."""
    result = es.search(index="reviews", body={
        "size": 0,
        "aggs": {
            "par_reponse": {
                "terms": {"field": "has_reply"}
            }
        }
    })
    buckets = result["aggregations"]["par_reponse"]["buckets"]
    total = sum(b["doc_count"] for b in buckets)
    avec_reponse = next((b["doc_count"] for b in buckets if b["key"] == 1), 0)
    return {
        "total": total,
        "avec_reponse": avec_reponse,
        "sans_reponse": total - avec_reponse,
        "taux": round(avec_reponse / total * 100, 1) if total > 0 else 0
    }

@app.get("/stats/note-moyenne")
def get_note_moyenne(source: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None):
    filters = build_filters(source, date_from, date_to)
    query = {"bool": {"filter": filters}} if filters else {"match_all": {}}
    result = es.search(index="reviews", body={
        "size": 0,
        "query": query,
        "aggs": {
            "note_moyenne": {"avg": {"field": "rating"}},
            "total": {"value_count": {"field": "rating"}}
        }
    })
    return {
        "moyenne": round(result["aggregations"]["note_moyenne"]["value"] or 0, 2),
        "total_avis": result["aggregations"]["total"]["value"]
    }

@app.get("/stats/verified")
def get_verified():
    """Répartition avis vérifiés vs non vérifiés."""
    result = es.search(index="reviews", body={
        "size": 0,
        "aggs": {
            "par_verification": {
                "terms": {"field": "verification_is_verified"}
            }
        }
    })
    buckets = result["aggregations"]["par_verification"]["buckets"]
    return {
        "verification": [
            {"verifie": bool(b["key"]), "count": b["doc_count"]}
            for b in buckets
        ]
    }

@app.get("/stats/date-min")
def get_date_min(source: Optional[str] = None):
    filters = build_filters(source, None, None)
    query = {"bool": {"filter": filters}} if filters else {"match_all": {}}
    result = es.search(index="reviews", body={
        "size": 0,
        "query": query,
        "aggs": {
            "date_min": {"min": {"field": "published_date"}}
        }
    })
    date_min = result["aggregations"]["date_min"]["value_as_string"] if result["aggregations"]["date_min"]["value"] else None
    return {"date_min": date_min}

@app.get("/stats/google/stores")
def get_google_stores():
    """Liste des agences Google avec note moyenne et nb avis."""
    result = es.search(index="reviews", body={
        "size": 0,
        "query": {"term": {"source": "google"}},
        "aggs": {
            "par_store": {
                "terms": {"field": "store", "size": 100},
                "aggs": {
                    "note_moyenne": {"avg": {"field": "rating"}},
                }
            }
        }
    })
    buckets = result["aggregations"]["par_store"]["buckets"]
    return [
        {
            "store": b["key"],
            "note_moyenne": round(b["note_moyenne"]["value"] or 0, 2),
            "nb_avis": b["doc_count"]
        }
        for b in buckets
    ]


@app.get("/stats/google/store-distribution")
def get_google_store_distribution(store: str):
    """Distribution des notes pour une agence Google."""
    result = es.search(index="reviews", body={
        "size": 0,
        "query": {"bool": {"filter": [
            {"term": {"source": "google"}},
            {"term": {"store": store}}
        ]}},
        "aggs": {
            "par_note": {
                "terms": {"field": "rating", "size": 5, "order": {"_key": "asc"}}
            }
        }
    })
    buckets = result["aggregations"]["par_note"]["buckets"]
    return {
        "distribution": [
            {"note": b["key"], "count": b["doc_count"]}
            for b in buckets
        ]
    }


@app.get("/stats/google/store-reviews")
def get_google_store_reviews(store: str, limit: int = 10):
    """Derniers avis pour une agence Google."""
    result = es.search(index="reviews", body={
        "size": limit,
        "query": {"bool": {"filter": [
            {"term": {"source": "google"}},
            {"term": {"store": store}}
        ]}},
        "sort": [{"published_date": {"order": "desc"}}]
    })
    return [pseudonymize_doc(hit["_source"]) for hit in result["hits"]["hits"]]

# Dictionnaire de normalisation pour gérer toutes les variantes de casse
LABEL_MAP = {
    "positif": "Positif",
    "Positif": "Positif",
    "négatif": "Négatif",
    "Négatif": "Négatif",
    "negatif": "Négatif",
    "Negatif": "Négatif",
    "1": "Positif",
    1: "Positif",
    "0": "Négatif",
    0: "Négatif",
}

@app.get("/stats/sentiments")
def get_stats_sentiments(
    source: Optional[str] = None,
    store: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Calcule la repartition globale ou par agence des avis positifs et negatifs."""
    filters = build_filters(source, date_from, date_to)
    if store:
        filters.append({"match_phrase": {"store": store}})

    query = {"bool": {"filter": filters}} if filters else {"match_all": {}}

    # Ciblage obligatoire de .keyword pour agreger sur un champ texte
    result = es.search(
        index="reviews",
        body={
            "size": 0,
            "query": query,
            "aggs": {
                "par_sentiment": {
                    "terms": {"field": "sentiment_predit.keyword", "size": 10}
                }
            },
        },
    )

    buckets = result.get("aggregations", {}).get("par_sentiment", {}).get("buckets", [])
    total = sum(b["doc_count"] for b in buckets)

    comptes = {"Positif": 0, "Négatif": 0}
    for b in buckets:
        raw_val = str(b["key"]).strip()
        label = LABEL_MAP.get(raw_val, raw_val.capitalize())
        if label in comptes:
            comptes[label] += b["doc_count"]
        else:
            comptes[label] = b["doc_count"]

    return {
        "total": total,
        "sentiments": [
            {
                "sentiment": label,
                "count": count,
                "pourcentage": round(count / total * 100, 1) if total > 0 else 0.0,
            }
            for label, count in comptes.items()
        ],
    }

@app.get("/stats/thematiques")
def get_stats_thematiques(
    source: Optional[str] = None,
    store: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Calcule la répartition par thématique avec support du filtre par agence/store."""
    filters = build_filters(source, date_from, date_to)

    # Ajout du filtre par magasin si spécifié
    if store:
        filters.append({"match_phrase": {"store": store}})

    query = {"bool": {"filter": filters}} if filters else {"match_all": {}}

    result = es.search(
        index="reviews",
        body={
            "size": 0,
            "query": query,
            "aggs": {
                "par_thematique": {
                    "terms": {
                        "script": {
                            "source": "params._source.thematique_predite"
                        },
                        "size": 15,
                    }
                }
            },
        },
    )

    buckets = (
        result.get("aggregations", {})
        .get("par_thematique", {})
        .get("buckets", [])
    )
    return {
        "thematiques": [
            {
                "thematique": str(b["key"]).strip().capitalize(),
                "count": b["doc_count"],
            }
            for b in buckets
            if b["key"]
        ]
    }

@app.get("/stats/thematiques-sentiments")
def get_stats_thematiques_sentiments(
    source: Optional[str] = None,
    store: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Calcule la repartition des sentiments par thematique pour le tableau de bord."""
    filters = build_filters(source, date_from, date_to)
    if store:
        filters.append({"match_phrase": {"store": store}})

    query = {"bool": {"filter": filters}} if filters else {"match_all": {}}

    result = es.search(
        index="reviews",
        body={
            "size": 0,
            "query": query,
            "aggs": {
                "par_thematique": {
                    "terms": {
                        "script": {"source": "params._source.thematique_predite"},
                        "size": 15,
                    },
                    "aggs": {
                        "par_sentiment": {
                            # Sous-agregation sur .keyword
                            "terms": {"field": "sentiment_predit.keyword", "size": 5}
                        }
                    },
                }
            },
        },
    )

    data = []
    buckets_theme = (
        result.get("aggregations", {})
        .get("par_thematique", {})
        .get("buckets", [])
    )

    for b_theme in buckets_theme:
        theme_nom = str(b_theme["key"]).strip().capitalize()
        if not theme_nom or theme_nom.lower() in ["none", "null"]:
            continue

        total_theme = b_theme["doc_count"]
        sent_buckets = b_theme.get("par_sentiment", {}).get("buckets", [])

        sent_comptes = {}
        for b_sent in sent_buckets:
            raw_key = str(b_sent["key"]).strip()
            label = LABEL_MAP.get(raw_key, raw_key.capitalize())
            sent_comptes[label] = sent_comptes.get(label, 0) + b_sent["doc_count"]

        for sent_label, count in sent_comptes.items():
            data.append({
                "thematique": theme_nom,
                "sentiment": sent_label,
                "count": count,
                "pourcentage": round(count / total_theme * 100, 1) if total_theme > 0 else 0.0,
            })

    return {"matrice": data}

@app.get("/export/avis")
def export_avis(
    source: Optional[str] = None,
    store: Optional[str] = None,
    rating: Optional[int] = None,
    sentiment: Optional[str] = None,
    thematique: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10000,
):
    """Exporte les avis bruts selon les filtres actifs pour le téléchargement CSV."""
    must_conditions = []

    # 1. Filtre sur la source (recherche tolérante sur les libellés réels)
    if source:
        src = source.strip().lower()
        if "trustpilot" in src:
            must_conditions.append(
                {
                    "bool": {
                        "should": [
                            {"match": {"source": "trustpilot"}},
                            {"match": {"source": "BasicLink"}},
                            {"match": {"review_source_name": "BasicLink"}},
                            {"match": {"source": "Organic"}},
                        ],
                        "minimum_should_match": 1,
                    }
                }
            )
        elif "google" in src:
            must_conditions.append({"match": {"source": "google"}})

    # 2. Filtres optionnels
    if rating is not None:
        must_conditions.append({"term": {"rating": rating}})

    if sentiment:
        must_conditions.append({"term": {"sentiment_predit.keyword": sentiment}})

    if store:
        must_conditions.append({"match_phrase": {"store": store}})

    if thematique:
        must_conditions.append(
            {"match_phrase": {"thematique_predite": thematique}}
        )

    # 3. Filtre chronologique sur published_date
    if date_from or date_to:
        date_range = {}
        if date_from:
            date_range["gte"] = date_from
        if date_to:
            date_range["lte"] = date_to
        must_conditions.append({"range": {"published_date": date_range}})

    query_body = (
        {"bool": {"must": must_conditions}}
        if must_conditions
        else {"match_all": {}}
    )

    res = es.search(
        index="reviews",
        size=limit,
        query=query_body,
        _source=[
            "published_date",
            "rating",
            "author_name",
            "store",
            "text",
            "reply_message",
        ],
    )

    hits = res.get("hits", {}).get("hits", [])
    data = []
    for h in hits:
        src = h.get("_source", {})
        data.append(
            {
                "Date de publication": str(src.get("published_date", ""))[:10],
                "Note": src.get("rating", ""),
                "Auteur": pseudonymize_name(src.get("author_name", "Anonyme")),
                "Agence": src.get("store", "LDLC Web"),
                "Commentaire": src.get("text", ""),
                "Réponse service client": src.get("reply_message", ""),
            }
        )

    return {"total": len(data), "avis": data}