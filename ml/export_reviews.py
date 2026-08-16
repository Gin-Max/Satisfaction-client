import gzip
import json
import time
from elasticsearch import Elasticsearch

# Configuration
ES_HOST = "http://localhost:9200"
INDEX_NAME = "reviews"
OUTPUT_FILE = "reviews_enriched.json.gz"
BATCH_SIZE = 5000
SCROLL_TIMEOUT = "5m"

client = Elasticsearch([ES_HOST], request_timeout=60)

def export_data():
    """Exporte l'index Elasticsearch vers un fichier JSON compressé."""
    print(f"[INFO] Initialisation de l'exportation depuis l'index '{INDEX_NAME}'...")
    
    try:
        page = client.search(
            index=INDEX_NAME,
            query={"match_all": {}},
            scroll=SCROLL_TIMEOUT,
            size=BATCH_SIZE
        )
        scroll_id = page["_scroll_id"]
        total_docs = page["hits"]["total"]["value"]
        print(f"[INFO] {total_docs} documents à exporter.")
    except Exception as e:
        print(f"[ERREUR] Impossible de lire Elasticsearch : {e}")
        return

    exported_count = 0
    start_time = time.time()

    with gzip.open(OUTPUT_FILE, "wt", encoding="utf-8") as f:
        try:
            while len(page["hits"]["hits"]) > 0:
                for hit in page["hits"]["hits"]:
                    doc_data = {
                        "_id": hit["_id"],
                        "_source": hit["_source"]
                    }
                    f.write(json.dumps(doc_data, ensure_ascii=False) + "\n")
                    exported_count += 1

                print(f"[STATUT] Exportation : {exported_count} / {total_docs} documents...")
                
                page = client.scroll(scroll_id=scroll_id, scroll=SCROLL_TIMEOUT)
                scroll_id = page["_scroll_id"]

        except Exception as e:
            print(f"[ERREUR] Erreur pendant l'export : {e}")
        finally:
            client.clear_scroll(scroll_id=scroll_id)

    elapsed_time = time.time() - start_time
    print(f"[SUCCES] Fichier généré : '{OUTPUT_FILE}' ({exported_count} documents en {elapsed_time:.2f}s).")

if __name__ == "__main__":
    export_data()