import os

import mlflow
import mlflow.sklearn
import pandas as pd
import requests
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from transformers import pipeline

URL_API = os.getenv("API_URL", "http://localhost:8000/avis")
mlflow.set_experiment("Analyse_Sentiment_LDLC")
response = requests.get(URL_API, timeout=60)
response.raise_for_status()
data = response.json()
df = pd.DataFrame(data["avis"])
df = df[df["rating"] != 3]
df["sentiment_reel"] = df["rating"].apply(lambda x: 1 if x >= 4 else 0)
df_sample = df.sample(n=min(1000, len(df)), random_state=42)
classifier = pipeline(
    task="sentiment-analysis",
    model="cmarkea/distilcamembert-base-sentiment",
    tokenizer="cmarkea/distilcamembert-base-sentiment",
)
predictions_hf = classifier(df_sample["text"].tolist(), truncation=True, batch_size=32)
predictions_binaires = []
for pred in predictions_hf:
    note_predite = int(pred["label"][0])
    predictions_binaires.append(1 if note_predite >= 4 else 0)
y_vrai = df_sample["sentiment_reel"].tolist()
accuracy = accuracy_score(y_vrai, predictions_binaires)
precision = precision_score(y_vrai, predictions_binaires)
recall = recall_score(y_vrai, predictions_binaires)
f1 = f1_score(y_vrai, predictions_binaires)
with mlflow.start_run(run_name="HuggingFace_CamemBERT"):
    mlflow.log_param("pipeline_type", "Transformers - CamemBERT (Distil)")
    mlflow.log_param("source_model", "cmarkea/distilcamembert-base-sentiment")
    mlflow.log_metric("accuracy", accuracy)
    mlflow.log_metric("precision", precision)
    mlflow.log_metric("recall", recall)
    mlflow.log_metric("f1_score", f1)
