# Satisfaction Client LDLC

Plateforme d'analyse des avis clients LDLC (Trustpilot & Google).

## Prérequis
- Docker Desktop installé ou Linux avec Docker

## Démarrage
```bash
git clone https://github.com/Gin-Max/Satisfaction-client
cd Satisfaction-client
docker compose build
docker compose up -d
```

## Services
| Service | URL | Description |
|---|---|---|
| Elasticsearch | http://localhost:9200 | Base de données |
| FastAPI | http://localhost:8000 | API REST |
| FastAPI Docs | http://localhost:8000/docs | Documentation API |
| Airflow | http://localhost:8080 | Orchestrateur |

## Routes API
| Route | Description |
|---|---|
| GET / | Vérifier que l'API tourne |
| GET /avis | Tous les avis |
| GET /avis/{source} | Avis par source |
| GET /avis/note/{note} | Avis par note |

## Commandes utiles
```bash
curl http://localhost:9200/reviews/_count
docker logs api
docker logs elasticsearch
docker compose down
docker compose down -v
```
