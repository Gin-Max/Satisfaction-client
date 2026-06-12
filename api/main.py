from fastapi import FastAPI
from elasticsearch import Elasticsearch
from prometheus_fastapi_instrumentator import Instrumentator
from typing import Optional

app = FastAPI()

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
Instrumentator().instrument(app).expose(app)
es = Elasticsearch("http://elasticsearch:9200")

# Route de test
@app.get("/")
def home():
    return {"status": "API OK ✅"}

# Récupérer tous les avis (j'ai un peu modifié pour le ML)
@app.get("/avis")
def get_avis():
    result = es.search(index="reviews", body={"query": {"match_all": {}}}, size=10000)
    avis = [hit["_source"] for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}

# Récupérer les avis par note
@app.get("/avis/note/{note}")
def get_avis_by_note(note: int):
    result = es.search(index="reviews", body={
        "query": {"match": {"rating": note}}
    }, size=10000)
    avis = [hit["_source"] for hit in result["hits"]["hits"]]
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
    avis = [hit["_source"] for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}

# Récupérer les avis par source
@app.get("/avis/{source}")
def get_avis_by_source(source: str):
    result = es.search(index="reviews", body={
        "query": {"match": {"source": source}}
    }, size=10000)
    avis = [hit["_source"] for hit in result["hits"]["hits"]]
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
def get_evolution_mensuelle(source: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None):
    filters = build_filters(source, date_from, date_to)
    query = {"bool": {"filter": [{"exists": {"field": "published_date"}}] + filters}} if filters else {"exists": {"field": "published_date"}}
    result = es.search(index="reviews", body={
        "size": 0,
        "query": query,
        "aggs": {
            "par_mois": {
                "date_histogram": {
                    "field": "published_date",
                    "calendar_interval": "month",
                    "format": "yyyy-MM"
                }
            }
        }
    })
    buckets = result["aggregations"]["par_mois"]["buckets"]
    return {
        "evolution": [
            {"mois": b["key_as_string"], "count": b["doc_count"]}
            for b in buckets
        ]
    }

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