import requests
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from transformers import pipeline

# 1. Configuration de l'expérience MLflow
mlflow.set_experiment("Analyse_Sentiment_LDLC")

# 2. Récupération des données via l'API
URL_API = "http://localhost:8000/avis"
print("Récupération des 10 000 avis depuis l'API...")
response = requests.get(URL_API)
response.raise_for_status()
data = response.json()

# Extraction et création du DataFrame
df = pd.DataFrame(data["avis"])

print("Filtrage des avis neutres...")
df = df[df['rating'] != 3]
df['sentiment_reel'] = df['rating'].apply(lambda x: 1 if x >= 4 else 0)

# échantillon de test de 1 000 avis parmi les 10 000.
df_sample = df.sample(n=1000, random_state=42)

# 4. Chargement du modèle CamemBERT spécialisé en sentiments depuis Hugging Face
print("Téléchargement et chargement de CamemBERT (Hugging Face)...")
# un CamemBERT distillé, optimisé pour être léger et rapide sur PC (recherche sur un forum)
classifier = pipeline(
    task="sentiment-analysis", 
    model="cmarkea/distilcamembert-base-sentiment",
    tokenizer="cmarkea/distilcamembert-base-sentiment"
)

# 5. Prédiction avec CamemBERT
print("Analyse des sentiments par le modèle de Deep Learning...")
textes = df_sample['text'].tolist()

# Analyse les textes par paquets (batchs) pour aller plus vite
predictions_hf = classifier(textes, truncation=True, batch_size=32)

# Traduction des labels du modèle (1 à 5 étoiles) en notre cible binaire (0 ou 1)
# Le modèle 'cmarkea' renvoie des labels comme '1 star', '5 stars', etc.
predictions_binaires = []
for pred in predictions_hf:
    # On extrait le premier caractère qui correspond à la note prédite (ex: '5' depuis '5 stars')
    note_predite = int(pred['label'][0])
    # Si la note prédite est >= 4, on considère ça positif (1), sinon négatif (0)
    predictions_binaires.append(1 if note_predite >= 4 else 0)

# 6. Calcul des métriques avancées
y_vrai = df_sample['sentiment_reel'].tolist()

accuracy = accuracy_score(y_vrai, predictions_binaires)
precision = precision_score(y_vrai, predictions_binaires)
recall = recall_score(y_vrai, predictions_binaires)
f1 = f1_score(y_vrai, predictions_binaires)

print("\n --- RÉSULTATS CAMEMBERT ---")
print(f"Accuracy  : {accuracy * 100:.2f}%")
print(f"Précision : {precision * 100:.2f}%")
print(f"Rappel    : {recall * 100:.2f}%")
print(f"F1-Score  : {f1 * 100:.2f}%")

# 7. Enregistrement des résultats dans MLflow
print("Enregistrement du run dans MLflow...")
with mlflow.start_run(run_name="HuggingFace_CamemBERT"):
    mlflow.log_param("pipeline_type", "Transformers - CamemBERT (Distil)")
    mlflow.log_param("source_model", "cmarkea/distilcamembert-base-sentiment")
    
    # On enregistre TOUTES les métriques pour une comparaison rigoureuse
    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("precision", precision)
    mlflow.log_metric("recall", recall)
    mlflow.log_metric("f1_score", f1)

print("Run CamemBERT enregistré avec succès !")