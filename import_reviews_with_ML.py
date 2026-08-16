import gzip
import json
import time
from elasticsearch import Elasticsearch, helpers

# Configuration
ES_HOST = "http://localhost:9200"
INDEX_NAME = "reviews"
INPUT_FILE = "reviews_enriched.json.gz"
BATCH_SIZE = 5000

client = Elasticsearch([ES_HOST], request_timeout=60)

def import_data():
    """Importe les documents depuis le fichier compressé vers Elasticsearch."""
    print(f"[INFO] Début de l'importation dans l'index '{INDEX_NAME}'...")
    
    start_time = time.time()
    bulk_actions = []
    imported_count = 0

    try:
        with gzip.open(INPUT_FILE, "rt", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                
                action = {
                    "_op_type": "index",
                    "_index": INDEX_NAME,
                    "_id": item["_id"],
                    "_source": item["_source"]
                }
                bulk_actions.append(action)

                if len(bulk_actions) >= BATCH_SIZE:
                    success, _ = helpers.bulk(client, bulk_actions, request_timeout=60)
                    imported_count += success
                    print(f"[STATUT] {imported_count} documents importés...")
                    bulk_actions = []

            # Importation du reliquat
            if bulk_actions:
                success, _ = helpers.bulk(client, bulk_actions, request_timeout=60)
                imported_count += success

    except FileNotFoundError:
        print(f"[ERREUR] Fichier introuvable : '{INPUT_FILE}'.")
        return
    except Exception as e:
        print(f"[ERREUR] Erreur pendant l'importation : {e}")
        return

    elapsed_time = time.time() - start_time
    print(f"[SUCCES] {imported_count} documents importés avec succès en {elapsed_time:.2f}s.")

if __name__ == "__main__":
    import_data()