# Satisfaction Client LDLC

Plateforme d'analyse des avis clients LDLC (Trustpilot & Google).

## Lancer le projet

### Prérequis
- Docker Desktop installé ou via Linux

### Démarrage
```bash
git clone https://github.com/Gin-Max/Satisfaction-client
cd satisfaction-client
docker compose build
docker compose up -d
```
 

| Service       | URL                        | Description             |
| ------------- | -------------------------- | ----------------------- |
| Elasticsearch | http://localhost:9200      | Base de données         |
| FastAPI       | http://localhost:8000      | API REST                |
| FastAPI Docs  | http://localhost:8000/docs | Documentation API       |

| Route                 | Description                           |
| --------------------- | ------------------------------------- |
| GET /                 | Vérifier que l'API tourne             |
| GET /avis             | Tous les avis                         |
| GET /avis/{source}    | Avis par source (trustpilot / google) |
| GET /avis/note/{note} | Avis par note (1 à 5)                 |

```bash
satisfaction-client/
├── docker-compose.yml
├── scraping/       ← collecte des avis
├── api/            ← API REST FastAPI
├── ml/             ← modèle NLP (à venir)
├── dashboard/      ← ? (à venir)
├── airflow/        ← ? (à venir)
└── monitoring/     ← Prometheus + Grafana (à venir)

# vérifier le nombre d'avis sur elasticsearch
curl http://localhost:9200/reviews/_count

# Voir les logs
docker logs api
docker logs elasticsearch

# Arrêter les services
docker-compose down

# ou Arrêter les services + vider la base de données persistante et relancer
docker compose down -v
docker compose build
docker compose up -d

```
