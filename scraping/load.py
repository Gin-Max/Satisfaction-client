import os
from elasticsearch import Elasticsearch, helpers

INDEX_NAME = "reviews"


def get_es_client():
    es_host = os.getenv("ELASTIC_HOST", "http://elasticsearch:9200")
    client = Elasticsearch(es_host)
    return client


def create_index_if_not_exists(client, index_name):
    if client.indices.exists(index=index_name):
        return

    mapping = {
        "mappings": {
            "properties": {
                "review_id": {"type": "keyword"},
                "likes": {"type": "integer"},
                "source": {"type": "keyword"},
                "rating": {"type": "integer"},
                "title": {"type": "text"},
                "text": {"type": "text"},
                "published_date": {"type": "date"},
                "author_id": {"type": "keyword"},
                "author_name": {"type": "keyword"},
                "author_review_count": {"type": "integer"},
                "consumer_reviews_same_domain": {"type": "integer"},
                "author_is_verified": {"type": "boolean"},
                "verification_is_verified": {"type": "boolean"},
                "review_source_name": {"type": "keyword"},
                "has_reply": {"type": "boolean"},
                "reply_published_date": {"type": "date"},
                "reply_message": {"type": "text"},
            }
        }
    }

    client.indices.create(index=index_name, body=mapping)
    print(f"Index '{index_name}' créé")


def load_to_elasticsearch(reviews, client, index_name=INDEX_NAME):
    if not reviews:
        print("Aucune review à indexer")
        return

    actions = [
        {
            "_index": index_name,
            "_id": review["review_id"],  # _id = review_id pour éviter les doublons
            "_source": review,
            "op_type": "create"          # 'create' échoue si _id existe déjà
        }
        for review in reviews
    ]

    # helpers.bulk avec raise_on_error=False ne lève pas d'exception
    success_count, _ = helpers.bulk(client, actions, raise_on_error=False)

    print(f"{success_count} nouvelles reviews réellement indexées dans Elasticsearch")