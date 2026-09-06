import requests
import pandas as pd
import numpy as np
import mlflow
import mlflow.transformers
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from transformers import pipeline

# =====================================================================
# 1. CONFIGURATION DU SERVEUR MLFLOW (DOCKER)
# =====================================================================
# Connexion au serveur de tracking conteneurisé
mlflow.set_tracking_uri("http://localhost:5000")

# Utilisation de la même expérience pour comparer directement avec la régression logistique
mlflow.set_experiment("Analyse_Sentiment_LDLC")

# =====================================================================
# 2. RÉCUPÉRATION DES DONNÉES VIA L'API FASTAPI
# =====================================================================
URL_API = "http://localhost:8000/avis"
print("Récupération des avis depuis l'API...")
response = requests.get(URL_API)
response.raise_for_status()
data = response.json()

# Extraction et création du DataFrame
df = pd.DataFrame(data["avis"])

print("Filtrage des avis neutres...")
df = df[df['rating'] != 3]
df['sentiment_reel'] = df['rating'].apply(lambda x: 1 if x >= 4 else 0)

# Définition de la taille de l'échantillon de test
SAMPLE_SIZE = 1000
BATCH_SIZE = 32
MODEL_NAME = "cmarkea/distilcamembert-base-sentiment"

df_sample = df.sample(n=min(SAMPLE_SIZE, len(df)), random_state=42)

# =====================================================================
# 3. CHARGEMENT DU MODÈLE CAMEMBERT (HUGGING FACE)
# =====================================================================
print("Téléchargement et chargement de CamemBERT...")
classifier = pipeline(
    task="sentiment-analysis", 
    model=MODEL_NAME,
    tokenizer=MODEL_NAME
)

# =====================================================================
# 4. INFERENCE ET PRÉDICTIONS
# =====================================================================
print("Analyse des sentiments par le modèle de Deep Learning...")
textes = df_sample['text'].tolist()

# Prédiction par batch pour accélérer le traitement
predictions_hf = classifier(textes, truncation=True, batch_size=BATCH_SIZE)

# Conversion des labels ('1 star' à '5 stars') en classes binaires (0 ou 1)
predictions_binaires = []
for pred in predictions_hf:
    note_predite = int(pred['label'][0])
    predictions_binaires.append(1 if note_predite >= 4 else 0)

# =====================================================================
# 5. CALCUL DES MÉTRIQUES D'ÉVALUATION
# =====================================================================
y_vrai = df_sample['sentiment_reel'].tolist()

accuracy = accuracy_score(y_vrai, predictions_binaires)
precision = precision_score(y_vrai, predictions_binaires)
recall = recall_score(y_vrai, predictions_binaires)
f1 = f1_score(y_vrai, predictions_binaires)

print("\n--- RÉSULTATS CAMEMBERT ---")
print(f"Accuracy  : {accuracy * 100:.2f}%")
print(f"Précision : {precision * 100:.2f}%")
print(f"Rappel    : {recall * 100:.2f}%")
print(f"F1-Score  : {f1 * 100:.2f}%")

# =====================================================================
# 6. ENREGISTREMENT DU RUN ET DES ARTEFACTS DANS MLFLOW
# =====================================================================
print("\nEnregistrement du run et du modèle dans MLflow...")
with mlflow.start_run(run_name="HuggingFace_CamemBERT"):
    # Enregistrement des hyperparamètres et métadonnées
    mlflow.log_param("pipeline_type", "Transformers - CamemBERT (Distil)")
    mlflow.log_param("source_model", MODEL_NAME)
    mlflow.log_param("batch_size", BATCH_SIZE)
    mlflow.log_param("sample_size", len(df_sample))
    
    # Enregistrement des métriques
    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("precision", precision)
    mlflow.log_metric("recall", recall)
    mlflow.log_metric("f1_score", f1)

    # Sauvegarde du pipeline complet (modèle + tokenizer) dans MLflow
    mlflow.transformers.log_model(
        transformers_model=classifier,
        artifact_path="model",
        pip_requirements=[
            "torch",
            "transformers",
            "mlflow"
        ]
    )

print("Run CamemBERT et artefacts enregistrés avec succès !")