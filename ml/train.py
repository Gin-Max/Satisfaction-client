import os
import re

import mlflow
import mlflow.sklearn
import pandas as pd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split

URL_API = os.getenv("API_URL", "http://localhost:8000/avis")
mlflow.set_experiment("Analyse_Sentiment_LDLC")
response = requests.get(URL_API, timeout=60)
response.raise_for_status()
data = response.json()
df = pd.DataFrame(data["avis"])
df = df[df["rating"] != 3]
df["sentiment"] = df["rating"].apply(lambda x: 1 if x >= 4 else 0)


def nettoyer_texte(texte):
    if not isinstance(texte, str):
        return ""
    texte = texte.lower()
    texte = re.sub(r"[^\w\s]", " ", texte)
    texte = re.sub(r"\d+", "", texte)
    return texte.strip()


df["texte_propre"] = df["text"].apply(nettoyer_texte)
X_train, X_test, y_train, y_test = train_test_split(
    df["texte_propre"], df["sentiment"], test_size=0.2, random_state=42
)

with mlflow.start_run(run_name="Baseline_TFIDF_LogReg"):
    vectorizer = TfidfVectorizer(max_features=1000, stop_words=None)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    model = LogisticRegression(C=1.0)
    model.fit(X_train_vec, y_train)
    predictions = model.predict(X_test_vec)
    accuracy = accuracy_score(y_test, predictions)
    precision = precision_score(y_test, predictions)
    recall = recall_score(y_test, predictions)
    f1 = f1_score(y_test, predictions)
    mlflow.log_param("pipeline_type", "TFIDF + LogisticRegression")
    mlflow.log_param("max_features", 1000)
    mlflow.log_param("C_value", 1.0)
    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("precision", precision)
    mlflow.log_metric("recall", recall)
    mlflow.log_metric("f1_score", f1)
    mlflow.sklearn.log_model(model, "model")
