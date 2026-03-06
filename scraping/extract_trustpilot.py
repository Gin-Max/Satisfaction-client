import requests
from bs4 import BeautifulSoup
import json
import time
import os

BASE_URL = "https://fr.trustpilot.com/review/www.ldlc.com"
HISTORICAL_JSON = "/data/ldlc_reviews.json"
INDEX_NAME = "reviews"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://fr.trustpilot.com/"
}


def get_page_json(page):
    url = f"{BASE_URL}?page={page}" if page > 1 else BASE_URL
    print(f"Scraping page {page}")
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    script_tag = soup.find("script", id="__NEXT_DATA__")
    if not script_tag:
        return None
    return json.loads(script_tag.string)


def extract_reviews_from_data(data):
    try:
        reviews_raw = data["props"]["pageProps"]["reviews"]
    except KeyError:
        return []

    reviews_clean = []
    for r in reviews_raw:
        consumer = r.get("consumer", {})
        verification = r.get("labels", {}).get("verification", {}) or {}
        dates = r.get("dates", {})
        reply = r.get("reply")

        review = {
            "review_id": r.get("id"),
            "likes": r.get("likes"),
            "source": r.get("source"),
            "rating": r.get("rating"),
            "title": r.get("title"),
            "text": r.get("text"),
            "published_date": dates.get("publishedDate"),
            "author_id": consumer.get("id"),
            "author_name": consumer.get("displayName"),
            "author_review_count": consumer.get("numberOfReviews"),
            "consumer_reviews_same_domain": r.get("consumersReviewCountOnSameDomain"),
            "author_is_verified": consumer.get("isVerified"),
            "verification_is_verified": verification.get("isVerified"),
            "review_source_name": verification.get("reviewSourceName"),
            "has_reply": reply is not None,
            "reply_published_date": reply.get("publishedDate") if reply else None,
            "reply_message": reply.get("message") if reply else None
        }

        reviews_clean.append(review)
    return reviews_clean


def scrape_pages(num_pages=10):
    all_reviews = []
    for page in range(1, num_pages + 1):
        data = get_page_json(page)
        if not data:
            break
        reviews = extract_reviews_from_data(data)
        if not reviews:
            break
        all_reviews.extend(reviews)
        time.sleep(1)
    return all_reviews


def extract(client):
    """
    Retourne :
    - existing_reviews : historique uniquement si ES est vide
    - new_reviews : nouvelles reviews scrapées
    """
    # Vérifie si Elasticsearch est vide ou index inexistant
    try:
        is_empty = client.count(index=INDEX_NAME)["count"] == 0
    except Exception:
        # Si l'index n'existe pas, considérer que c'est vide
        is_empty = True

    existing_reviews = []
    if is_empty and os.path.exists(HISTORICAL_JSON):
        print("Chargement historique depuis JSON...")
        with open(HISTORICAL_JSON, "r", encoding="utf-8") as f:
            existing_reviews = json.load(f)
        print(f"{len(existing_reviews)} reviews historiques chargées")

    # Scrape les nouvelles reviews
    new_reviews = scrape_pages()
    print(f"{len(new_reviews)} nouvelles reviews extraites")

    return existing_reviews, new_reviews