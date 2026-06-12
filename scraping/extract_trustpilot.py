import json
import time
import random
import os
from playwright.sync_api import sync_playwright

BASE_URL = "https://fr.trustpilot.com/review/www.ldlc.com"
HISTORICAL_JSON = os.path.join(os.path.dirname(__file__), "..", "data", "ldlc_reviews.json")
INDEX_NAME = "reviews"

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
            "source": "trustpilot",
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
            "reply_message": reply.get("message") if reply else None,
        }

        reviews_clean.append(review)

    return reviews_clean


def scrape_pages(num_pages=10):
    all_reviews = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        context = browser.new_context(
            locale="fr-FR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        page = context.new_page()

        for num in range(1, num_pages + 1):
            url = f"{BASE_URL}?page={num}" if num > 1 else BASE_URL
            print(f"\nScraping page {num} -> {url}")

            try:
                response = page.goto(
                    url,
                    wait_until="load",
                    timeout=90000
                )

                print("HTTP status:", response.status if response else None)

                page.wait_for_timeout(4000)

                html = page.content()

                if "verifying" in html.lower() or "captcha" in html.lower():
                    print("⚠️ Blocage anti-bot détecté (verifying/captcha)")
                    break

                content = page.evaluate(
                    "() => document.getElementById('__NEXT_DATA__')?.textContent"
                )

                if not content:
                    print("❌ __NEXT_DATA__ introuvable")
                    break

                data = json.loads(content)
                reviews = extract_reviews_from_data(data)

                if not reviews:
                    print("❌ Aucun review extrait")
                    break

                all_reviews.extend(reviews)

                print(f"✔ Page {num}: {len(reviews)} reviews (total {len(all_reviews)})")

                # pause “humaine”
                time.sleep(random.uniform(2.0, 4.0))

            except Exception as e:
                print(f"❌ Erreur page {num}: {repr(e)}")
                break

        browser.close()

    return all_reviews



def load_historical_reviews():
    """Charge les reviews historiques depuis le JSON."""
    if not os.path.exists(HISTORICAL_JSON):
        print("Pas de fichier historique trouvé.")
        return []
    with open(HISTORICAL_JSON, "r", encoding="utf-8") as f:
        existing_reviews = json.load(f)
    print(f"{len(existing_reviews)} reviews historiques chargées")
    return existing_reviews

def is_trustpilot_empty(client):
    try:
        result = client.count(index=INDEX_NAME, body={
            "query": {"term": {"source": "trustpilot"}}
        })
        return result["count"] == 0
    except Exception:
        return True

def main():
    from scraping.load import get_es_client
    client = get_es_client()
    existing_reviews = load_historical_reviews() if is_trustpilot_empty(client) else []
    new_reviews = scrape_pages(num_pages=10)
    print(f"\n=== FIN SCRAPING ===")
    print(f"New reviews: {len(new_reviews)}")
    return existing_reviews + new_reviews
