from elasticsearch import Elasticsearch
import json
from datetime import datetime

# Connexion Elasticsearch
es = Elasticsearch("http://elasticsearch:9200")

# Crée l'index si il n'existe pas
if not es.indices.exists(index="avis_bruts"):
    es.indices.create(index="avis_bruts", body={
        "mappings": {
            "properties": {
                "review_id":        {"type": "keyword"},
                "rating":           {"type": "integer"},
                "title":            {"type": "text"},
                "text":             {"type": "text"},
                "language":         {"type": "keyword"},
                "source":           {"type": "keyword"},
                "published_date":   {"type": "date"},
                "author_country":   {"type": "keyword"},
                "has_reply":        {"type": "boolean"},
                "scraped_at":       {"type": "date"}
            }
        }
    })
    print("Index avis_bruts créé ✅")

# Données de test (à remplacer par le vrai scraping)
avis_test = [
    {
        "review_id": "1",
        "rating": 1,
        "title": "Livraison catastrophique",
        "text": "Mon colis est arrivé avec 15 jours de retard et complètement abîmé.",
        "language": "fr",
        "source": "trustpilot",
        "published_date": "2026-03-01",
        "author_country": "FR",
        "has_reply": False,
        "scraped_at": datetime.now().isoformat()
    },
    {
        "review_id": "2",
        "rating": 5,
        "title": "Excellent service",
        "text": "Commande reçue en 24h, produit parfait, je recommande vivement.",
        "language": "fr",
        "source": "trustpilot",
        "published_date": "2026-03-02",
        "author_country": "FR",
        "has_reply": True,
        "scraped_at": datetime.now().isoformat()
    },
    {
        "review_id": "3",
        "rating": 2,
        "title": "Prix trop élevé",
        "text": "Produit correct mais beaucoup trop cher par rapport à la concurrence.",
        "language": "fr",
        "source": "google",
        "published_date": "2026-03-03",
        "author_country": "FR",
        "has_reply": False,
        "scraped_at": datetime.now().isoformat()
    }
]

# Insertion dans Elasticsearch
for avis in avis_test:
    es.index(index="avis_bruts", id=avis["review_id"], document=avis)
    print(f"Avis {avis['review_id']} inséré ✅")

print("Scraping terminé ✅")