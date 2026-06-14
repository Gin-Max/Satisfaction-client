"""Pour charger manuellement les JSON historiques dans ES :
docker exec -it airflow-webserver bash
python /opt/airflow/project/scraping/manual_load_hist.py
exit

Note: Si vous avez un ancien CSV Google, lancez d'abord:
python /opt/airflow/project/scraping/migrate_google_csv_to_json.py
"""

from extract_trustpilot import load_historical_reviews as load_tp_historical
from scrape_google_reviews import load_historical_reviews as load_google_historical
from transform import transform
from load import get_es_client, create_index_if_not_exists, load_to_elasticsearch, INDEX_NAME

client = get_es_client()
create_index_if_not_exists(client, INDEX_NAME)

# Trustpilot
print("=== CHARGEMENT TRUSTPILOT ===")
tp_reviews = load_tp_historical()
final_tp = transform([], tp_reviews)
load_to_elasticsearch(final_tp, client)

# Google
print("=== CHARGEMENT GOOGLE ===")
google_reviews = load_google_historical()
load_to_elasticsearch(google_reviews, client)

print(f"\n=== TOTAL ===")
count = client.count(index=INDEX_NAME)["count"]
print(f"Total d'avis dans l'index '{INDEX_NAME}': {count}")