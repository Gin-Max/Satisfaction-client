from fastapi import FastAPI
from elasticsearch import Elasticsearch

app = FastAPI()
es = Elasticsearch("http://elasticsearch:9200")

# Route de test
@app.get("/")
def home():
    return {"status": "API OK ✅"}

# Récupérer tous les avis
@app.get("/avis")
def get_avis():
    result = es.search(index="avis_bruts", body={"query": {"match_all": {}}})
    avis = [hit["_source"] for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}

# Récupérer les avis par source
@app.get("/avis/{source}")
def get_avis_by_source(source: str):
    result = es.search(index="avis_bruts", body={
        "query": {"match": {"source": source}}
    })
    avis = [hit["_source"] for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}

# Récupérer les avis par note
@app.get("/avis/note/{note}")
def get_avis_by_note(note: int):
    result = es.search(index="avis_bruts", body={
        "query": {"match": {"rating": note}}
    })
    avis = [hit["_source"] for hit in result["hits"]["hits"]]
    return {"total": len(avis), "avis": avis}
