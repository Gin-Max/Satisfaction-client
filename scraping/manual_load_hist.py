"""Pour charger manuellement le json et csv historiques dans ES :
docker exec -it airflow-webserver bash
python /opt/airflow/project/scraping/manual_load_all.py
exit
"""

from load_google import (
    load_google_reviews_from_csv,
    transform_google_reviews,
    load_google_to_elasticsearch,
    GOOGLE_CSV,
)
from extract_trustpilot import load_historical_reviews
from transform import transform
from load import get_es_client, create_index_if_not_exists, load_to_elasticsearch, INDEX_NAME

client = get_es_client()
create_index_if_not_exists(client, INDEX_NAME)

# Trustpilot
print("=== CHARGEMENT TRUSTPILOT ===")
tp_reviews = load_historical_reviews()
final_tp = transform([], tp_reviews)
load_to_elasticsearch(final_tp, client)

# Google
print("=== CHARGEMENT GOOGLE ===")
raw_reviews = load_google_reviews_from_csv(GOOGLE_CSV)
transformed_google = transform_google_reviews(raw_reviews)
load_google_to_elasticsearch(transformed_google, client)