import requests
import pandas as pd
import re
import mlflow
import mlflow.sklearn
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.metrics import classification_report, precision_score, recall_score, f1_score

# =====================================================================
# 1. ENREGISTREMENT DE L'EXPÉRIENCE DANS MLFLOW
# =====================================================================
mlflow.set_experiment("Analyse_Sentiment_LDLC")

# =====================================================================
# 2. COLLECTE DES DONNÉES VIA L'API
# =====================================================================
URL_API = "http://localhost:8000/avis"

print("Étape 1 : Récupération des avis depuis l'API...")
response = requests.get(URL_API)
response.raise_for_status()
data = response.json()
avis = data["avis"]
df = pd.DataFrame(avis)

print(f"Nombre d'avis récupérés : {len(df)}")

# =====================================================================
# 3. PRÉTRAITEMENT DES DONNÉES (NLP)
# =====================================================================
print("Nettoyage du texte et création de la cible...")

# Filtrage : On exclut les notes neutres (3 étoiles) car difficile à discerner
df = df[df['rating'] != 3]

# Création de la cible (Label) : 1 pour Positif (>=4), 0 pour Négatif (<=2)
df['sentiment'] = df['rating'].apply(lambda x: 1 if x >= 4 else 0)

# Fonction de nettoyage textuel basique
def nettoyer_texte(texte):
    if not isinstance(texte, str):
        return ""
    texte = texte.lower() # Minuscules
    texte = re.sub(r'[^\w\s]', ' ', texte) # Retrait de la ponctuation
    texte = re.sub(r'\d+', '', texte) # Retrait des chiffres
    return texte.strip()

df['texte_propre'] = df['text'].apply(nettoyer_texte)

# Séparation des données : 80% entraînement / 20% test
X_train, X_test, y_train, y_test = train_test_split(
    df['texte_propre'], 
    df['sentiment'], 
    test_size=0.2, 
    random_state=42
)

# =====================================================================
# 4. ENTRAÎNEMENT ET SUIVI MLFLOW
# =====================================================================
print(" Entraînement du modèle et log MLflow...")

# Démarrage du run MLflow pour enregistrer cette tentative
with mlflow.start_run(run_name="Baseline_TFIDF_LogReg"):
    
    # Choix des hyperparamètres
    MAX_FEATURES = 1000
    C_REGULARIZATION = 1.0
    
    # Vectorisation TF-IDF avec la liste des mots vides en français
    vectorizer = TfidfVectorizer(max_features=MAX_FEATURES, stop_words=None)
    
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    
    # Création et entraînement de la Régression Logistique
    model = LogisticRegression(C=C_REGULARIZATION)
    model.fit(X_train_vec, y_train)
    
    # Évaluation
    predictions = model.predict(X_test_vec)
    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions)
    recall = recall_score(y_test, predictions)
    f1 = f1_score(y_test, predictions)
    print(f"Précision finale (Accuracy) : {accuracy * 100:.1f}%")
    
    # --- ENREGISTREMENT DANS MLFLOW ---
    # Log des paramètres de configuration
    mlflow.log_param("pipeline_type", "TFIDF + LogisticRegression")
    mlflow.log_param("max_features", MAX_FEATURES)
    mlflow.log_param("C_value", C_REGULARIZATION)
    
    # Log de la performance
    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("precision", precision)
    mlflow.log_metric("recall", recall)
    mlflow.log_metric("f1_score", f1)
    
    # Sauvegarde physique du modèle dans MLflow pour pouvoir le réutiliser plus tard
    mlflow.sklearn.log_model(model, "model")