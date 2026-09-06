# Image Python officielle et légère
FROM python:3.11-slim

# Installation de MLflow
RUN pip install --no-cache-dir mlflow

# Répertoire de travail dans le conteneur
WORKDIR /ml

# Port d'écoute standard pour l'interface MLflow
EXPOSE 5000

# Commande de lancement pointant sur le dossier mlruns existant
CMD ["mlflow", "ui", "--backend-store-uri", "/ml/mlruns", "--host", "0.0.0.0", "--port", "5000"]