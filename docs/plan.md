# Plan d'implémentation - Monitoring

## Objectif
Mettre en place une stack de monitoring complète avec Prometheus + Grafana pour surveiller l'API FastAPI, Elasticsearch et Airflow.

---

## Etat actuel du projet

| Service | Status | Port |
|---------|--------|------|
| Elasticsearch | OK | 9200 |
| API FastAPI | OK | 8000 |
| Airflow Webserver | OK | 8080 |
| Airflow Scheduler | OK | - |
| Streamlit | OK | 8501 |
| **Prometheus** | A FAIRE | 9090 |
| **Grafana** | A FAIRE | 3000 |

---

## Etapes d'implémentation

### Etape 1 : Créer la structure monitoring

**Fichiers à créer :**
```
monitoring/
├── prometheus.yml          # Config Prometheus
└── grafana/
    └── provisioning/
        └── datasources/
            └── datasource.yml   # Auto-config Prometheus dans Grafana
```

**Actions :**
- [ ] Créer le dossier `monitoring/`
- [ ] Créer `monitoring/prometheus.yml` avec les jobs de scraping

---

### Etape 2 : Instrumenter l'API FastAPI

**Fichier à modifier :** `api/main.py`

**Dépendance à ajouter :** `api/requirements.txt`
```
prometheus-fastapi-instrumentator
```

**Code à ajouter dans main.py :**
```python
from prometheus_fastapi_instrumentator import Instrumentator

# Après la création de l'app
Instrumentator().instrument(app).expose(app)
```

**Résultat :** Endpoint `/metrics` exposé sur l'API (port 8000)

**Métriques disponibles :**
- `http_requests_total` : nombre de requêtes par endpoint/méthode/status
- `http_request_duration_seconds` : latence des requêtes
- `http_requests_in_progress` : requêtes en cours

---

### Etape 3 : Configurer Prometheus

**Fichier :** `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Métriques API FastAPI
  - job_name: 'fastapi'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics

  # Métriques Elasticsearch (via exporter)
  - job_name: 'elasticsearch'
    static_configs:
      - targets: ['elasticsearch-exporter:9114']

  # Métriques Airflow (via statsd-exporter)
  - job_name: 'airflow'
    static_configs:
      - targets: ['statsd-exporter:9102']
```

---

### Etape 4 : Configurer le provisioning Grafana

**Fichier :** `monitoring/grafana/provisioning/datasources/datasource.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

---

### Etape 5 : Ajouter les services au docker-compose.yml

**Services à ajouter :**

```yaml
# MONITORING - PROMETHEUS
prometheus:
  image: prom/prometheus:latest
  container_name: prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - prometheus_data:/prometheus
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
  depends_on:
    - api
  restart: unless-stopped

# MONITORING - GRAFANA
grafana:
  image: grafana/grafana:latest
  container_name: grafana
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_USER=admin
    - GF_SECURITY_ADMIN_PASSWORD=admin
    - GF_USERS_ALLOW_SIGN_UP=false
  volumes:
    - grafana_data:/var/lib/grafana
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
  depends_on:
    - prometheus
  restart: unless-stopped

# MONITORING - ELASTICSEARCH EXPORTER
elasticsearch-exporter:
  image: quay.io/prometheuscommunity/elasticsearch-exporter:latest
  container_name: elasticsearch-exporter
  command:
    - '--es.uri=http://elasticsearch:9200'
  ports:
    - "9114:9114"
  depends_on:
    - elasticsearch
  restart: unless-stopped

# MONITORING - STATSD EXPORTER (pour Airflow)
statsd-exporter:
  image: prom/statsd-exporter:latest
  container_name: statsd-exporter
  ports:
    - "9125:9125/udp"
    - "9102:9102"
  restart: unless-stopped
```

**Volumes à ajouter :**
```yaml
volumes:
  prometheus_data:
  grafana_data:
```

---

### Etape 6 : Configurer Airflow pour envoyer les métriques

**Modifier les variables d'environnement Airflow** (webserver + scheduler) :

```yaml
environment:
  # ... existant ...
  AIRFLOW__METRICS__STATSD_ON: "True"
  AIRFLOW__METRICS__STATSD_HOST: statsd-exporter
  AIRFLOW__METRICS__STATSD_PORT: 9125
  AIRFLOW__METRICS__STATSD_PREFIX: airflow
```

---

### Etape 7 : Tester le déploiement

**Commandes :**
```bash
# Rebuild l'API avec la nouvelle dépendance
docker compose build api

# Démarrer tous les services
docker compose up -d

# Vérifier les endpoints
curl http://localhost:8000/metrics    # API metrics
curl http://localhost:9114/metrics    # ES exporter metrics
curl http://localhost:9090/targets    # Prometheus targets
```

**Vérifications :**
- [ ] http://localhost:9090 - Prometheus UI accessible
- [ ] http://localhost:9090/targets - Tous les targets UP
- [ ] http://localhost:3000 - Grafana accessible (admin/admin)
- [ ] Prometheus configuré comme datasource dans Grafana

---

### Etape 8 : Créer les dashboards Grafana (optionnel)

**Dashboards recommandés :**

1. **API FastAPI**
   - Requêtes/sec par endpoint
   - Latence moyenne/p95/p99
   - Taux d'erreur (4xx, 5xx)

2. **Elasticsearch**
   - Cluster health
   - Documents indexés
   - Query latency
   - JVM heap usage

3. **Airflow**
   - DAG success/failure rate
   - Task duration
   - Scheduler heartbeat

---

## Récapitulatif des fichiers

| Action | Fichier |
|--------|---------|
| CREER | `monitoring/prometheus.yml` |
| CREER | `monitoring/grafana/provisioning/datasources/datasource.yml` |
| MODIFIER | `api/requirements.txt` (ajouter prometheus-fastapi-instrumentator) |
| MODIFIER | `api/main.py` (ajouter Instrumentator) |
| MODIFIER | `docker-compose.yml` (ajouter 4 services + 2 volumes) |

---

## Ports finaux

| Service | Port | URL |
|---------|------|-----|
| API | 8000 | http://localhost:8000 |
| API Metrics | 8000 | http://localhost:8000/metrics |
| Elasticsearch | 9200 | http://localhost:9200 |
| ES Exporter | 9114 | http://localhost:9114/metrics |
| Airflow | 8080 | http://localhost:8080 |
| StatsD Exporter | 9102 | http://localhost:9102/metrics |
| Streamlit | 8501 | http://localhost:8501 |
| **Prometheus** | 9090 | http://localhost:9090 |
| **Grafana** | 3000 | http://localhost:3000 |

---

## Ordre d'exécution

1. Créer `monitoring/prometheus.yml`
2. Créer `monitoring/grafana/provisioning/datasources/datasource.yml`
3. Modifier `api/requirements.txt`
4. Modifier `api/main.py`
5. Modifier `docker-compose.yml`
6. `docker compose build api`
7. `docker compose up -d`
8. Tester tous les endpoints
