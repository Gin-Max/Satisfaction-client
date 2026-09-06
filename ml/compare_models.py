import requests
import pandas as pd
import numpy as np
import mlflow
import mlflow.sklearn
import mlflow.transformers
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from transformers import pipeline

# =====================================================================
# 1. CONFIGURATION DU SERVEUR MLFLOW
# =====================================================================
# Connexion au conteneur Docker MLflow
mlflow.set_tracking_uri("http://localhost:5000")
mlflow.set_experiment("Analyse_Sentiment_LDLC")

# =====================================================================
# 2. RÉCUPÉRATION ET PRÉPARATION DES DONNÉES DEPUIS L'API
# =====================================================================
URL_API = "http://localhost:8000/avis"
print("Étape 1 : Téléchargement des données depuis l'API...")
response = requests.get(URL_API)
response.raise_for_status()

# Conversion de la réponse JSON en DataFrame Pandas
avis_liste = response.json()["avis"]
df = pd.DataFrame(avis_liste)

# Nettoyage : suppression de la classe neutre (note = 3)
df = df[df["rating"] != 3].copy()

# Cible binaire : 1 pour les avis satisfaits (4 et 5 étoiles), 0 sinon (1 et 2 étoiles)
df["sentiment_binaire"] = df["rating"].apply(lambda note: 1 if note >= 4 else 0)

# =====================================================================
# 3. CRÉATION DU JEU DE TEST STRICTEMENT COMMUN
# =====================================================================
# random_state=42 garantit la reproductibilité exacte du découpage
X_train, X_test, y_train, y_test = train_test_split(
    df["text"],
    df["sentiment_binaire"],
    test_size=0.20,
    random_state=42,
    stratify=df["sentiment_binaire"]
)

print(f"Jeu d'entraînement : {len(X_train)} avis | Jeu d'évaluation commun : {len(X_test)} avis\n")

# =====================================================================
# 4. ÉVALUATION DU MODÈLE 1 : TF-IDF + RÉGRESSION LOGISTIQUE
# =====================================================================
print("--- [1/2] Entraînement et test de la Baseline TF-IDF ---")

# Vectorisation textuelle
vectorizer = TfidfVectorizer(max_features=1000)
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

# Entraînement
modele_logreg = LogisticRegression(C=1.0, max_iter=1000)
modele_logreg.fit(X_train_vec, y_train)

# Prédiction sur le jeu d'évaluation
y_pred_tfidf = modele_logreg.predict(X_test_vec)

# Calcul des scores
acc_tfidf = accuracy_score(y_test, y_pred_tfidf)
prec_tfidf = precision_score(y_test, y_pred_tfidf)
rec_tfidf = recall_score(y_test, y_pred_tfidf)
f1_tfidf = f1_score(y_test, y_pred_tfidf)

print(f"TF-IDF -> Accuracy: {acc_tfidf * 100:.2f}% | Précision: {prec_tfidf * 100:.2f}% | Rappel: {rec_tfidf * 100:.2f}% | F1: {f1_tfidf * 100:.2f}%")

# Enregistrement dans MLflow
with mlflow.start_run(run_name="Bench_TFIDF_LogReg"):
    mlflow.log_param("architecture", "TF-IDF + LogisticRegression")
    mlflow.log_param("max_features", 1000)
    mlflow.log_param("test_samples_count", len(y_test))
    
    mlflow.log_metric("accuracy", acc_tfidf)
    mlflow.log_metric("precision", prec_tfidf)
    mlflow.log_metric("recall", rec_tfidf)
    mlflow.log_metric("f1_score", f1_tfidf)
    
    mlflow.sklearn.log_model(sk_model=modele_logreg, name="model")

# =====================================================================
# 5. ÉVALUATION DU MODÈLE 2 : DEEP LEARNING (DISTILCAMEMBERT)
# =====================================================================
print("\n--- [2/2] Évaluation de DistilCamemBERT sur le même jeu de test ---")

NOM_MODELE_HF = "cmarkea/distilcamembert-base-sentiment"

classifieur_camembert = pipeline(
    task="sentiment-analysis",
    model=NOM_MODELE_HF,
    tokenizer=NOM_MODELE_HF
)

# Inférence par paquets sur les mêmes textes d'évaluation
predictions_brutes = classifieur_camembert(
    X_test.tolist(),
    truncation=True,
    batch_size=32
)

# Conversion du label texte ('1 star' à '5 stars') en valeur binaire
y_pred_camembert = []
for p in predictions_brutes:
    note_extraite = int(p["label"][0])
    y_pred_camembert.append(1 if note_extraite >= 4 else 0)

# Calcul des scores
acc_cam = accuracy_score(y_test, y_pred_camembert)
prec_cam = precision_score(y_test, y_pred_camembert)
rec_cam = recall_score(y_test, y_pred_camembert)
f1_cam = f1_score(y_test, y_pred_camembert)

print(f"CamemBERT -> Accuracy: {acc_cam * 100:.2f}% | Précision: {prec_cam * 100:.2f}% | Rappel: {rec_cam * 100:.2f}% | F1: {f1_cam * 100:.2f}%")

# Enregistrement dans MLflow
with mlflow.start_run(run_name="Bench_DistilCamemBERT"):
    mlflow.log_param("architecture", "DistilCamemBERT")
    mlflow.log_param("source_hf", NOM_MODELE_HF)
    mlflow.log_param("batch_size", 32)
    mlflow.log_param("test_samples_count", len(y_test))
    
    mlflow.log_metric("accuracy", acc_cam)
    mlflow.log_metric("precision", prec_cam)
    mlflow.log_metric("recall", rec_cam)
    mlflow.log_metric("f1_score", f1_cam)
    
    mlflow.transformers.log_model(
        transformers_model=classifieur_camembert,
        artifact_path="model",
        pip_requirements=["torch", "transformers", "mlflow"]
    )

print("\nBenchmark validé avec succès ! Les deux modèles sont enregistrés sur des données de test identiques.")