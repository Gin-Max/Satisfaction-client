# Tâches Monitoring - Projet LDLC

## Liste des tâches

1. Installer Prometheus pour collecter les métriques
2. Installer Grafana pour visualiser les dashboards
3. Ajouter les métriques à l'API FastAPI
4. Monitorer Elasticsearch
5. Monitorer Airflow
6. Configurer les alertes
7. Ajouter les services au docker-compose.yml

---

## Détails des tâches

### 1. Installer Prometheus pour collecter les métriques

Prometheus scrape (récupère) les métriques de tous les services à intervalles réguliers (toutes les 15s par défaut). Il stocke ces données en time-series pour analyse.

Fichier à créer : `monitoring/prometheus.yml`
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'fastapi'
    static_configs:
      - targets: ['api:8000']

  - job_name: 'elasticsearch'
    static_configs:
      - targets: ['elasticsearch:9200']

  - job_name: 'airflow'
    static_configs:
      - targets: ['airflow-webserver:8080']
```

---

### 2. Installer Grafana pour visualiser les dashboards

Grafana se connecte à Prometheus et affiche les métriques sous forme de graphiques, tableaux et alertes visuelles.

- Port : 3000
- Login par défaut : admin/admin
- Ajouter Prometheus comme datasource

---

### 3. Ajouter les métriques à l'API FastAPI

Installer la librairie `prometheus-fastapi-instrumentator` pour exposer automatiquement les métriques de l'API.

```bash
pip install prometheus-fastapi-instrumentator
```

Modifier `api/main.py` :
```python
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

Métriques exposées sur `/metrics` :
- Nombre de requêtes par endpoint
- Temps de réponse (latence)
- Erreurs HTTP (4xx, 5xx)

---

### 4. Monitorer Elasticsearch

Utiliser `elasticsearch-exporter` pour exposer les métriques ES à Prometheus.

Métriques importantes :
- Santé du cluster (green/yellow/red)
- Nombre de documents indexés
- Utilisation mémoire/CPU
- Temps de réponse des requêtes

---

### 5. Monitorer Airflow

Airflow expose des métriques nativement via StatsD ou Prometheus.

Métriques importantes :
- DAGs en succès/échec
- Durée des tâches
- Files d'attente des tâches
- Scheduler health

Activer dans `airflow.cfg` :
```ini
[metrics]
statsd_on = True
statsd_host = statsd-exporter
statsd_port = 9125
```

---

### 6. Configurer les alertes

Créer des alertes Grafana ou utiliser Alertmanager avec Prometheus.

Alertes recommandées :
- API : temps de réponse > 2s
- API : taux d'erreur > 5%
- Elasticsearch : cluster status != green
- Elasticsearch : disk usage > 80%
- Airflow : DAG failed
- Serveur : CPU > 90%, RAM > 85%

---

### 7. Ajouter les services au docker-compose.yml

```yaml
# Ajouter à docker-compose.yml

prometheus:
  image: prom/prometheus:latest
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  depends_on:
    - api

grafana:
  image: grafana/grafana:latest
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
  volumes:
    - grafana_data:/var/lib/grafana
  depends_on:
    - prometheus

elasticsearch-exporter:
  image: quay.io/prometheuscommunity/elasticsearch-exporter:latest
  command:
    - '--es.uri=http://elasticsearch:9200'
  ports:
    - "9114:9114"
  depends_on:
    - elasticsearch

volumes:
  grafana_data:
```

---

## Ports récapitulatifs

| Service | Port | URL |
|---------|------|-----|
| Prometheus | 9090 | http://localhost:9090 |
| Grafana | 3000 | http://localhost:3000 |
| ES Exporter | 9114 | http://localhost:9114/metrics |
| API Metrics | 8000 | http://localhost:8000/metrics |
