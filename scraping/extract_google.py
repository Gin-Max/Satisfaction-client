import os
import time
import requests
from bs4 import BeautifulSoup
from scraping.load import get_es_client, create_index_if_not_exists, load_to_elasticsearch, INDEX_NAME

def log(message):
    print(message)

def get_stores_list():
    """
    Récupère la liste des magasins depuis la page LDLC via requests + BeautifulSoup.
    Retourne une liste de noms de magasins.
    """
    log("Navigation vers la page des magasins LDLC...")
    url = "https://www.ldlc.com/magasins-ldlc/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    log(f"Status code: {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    stores = []
    
    # Trouver tous les liens
    for a in soup.find_all('a', href=True):
        if '/magasins-ldlc/magasin-' in a['href'] and a.text.strip():
            store_name = a.text.strip()
            if store_name not in stores:
                stores.append(store_name)
                
    log(f"{len(stores)} magasins trouvés.")
    return stores

def get_google_reviews_via_api(store_name, api_key):
    """
    Utilise l'API Google Places (New) pour récupérer les 5 derniers avis d'un magasin.
    """
    # 1. Text Search pour trouver le place_id
    search_url = 'https://places.googleapis.com/v1/places:searchText'
    search_headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.id,places.displayName'
    }
    search_data = {
        'textQuery': f'LDLC {store_name}'
    }
    
    try:
        search_resp = requests.post(search_url, headers=search_headers, json=search_data)
        search_json = search_resp.json()
        
        if 'places' not in search_json or not search_json['places']:
            log(f"  Aucun lieu trouvé sur Google Maps pour LDLC {store_name}.")
            return []
            
        place_id = search_json['places'][0]['id']
        
        # 2. Place Details pour récupérer les avis
        details_url = f'https://places.googleapis.com/v1/places/{place_id}'
        details_headers = {
            'X-Goog-Api-Key': api_key,
            'X-Goog-FieldMask': 'id,displayName,reviews',
            'Accept-Language': 'fr'
        }
        
        details_resp = requests.get(details_url, headers=details_headers)
        details_json = details_resp.json()
        
        if 'reviews' not in details_json:
            log("  Aucun avis trouvé.")
            return []
            
        reviews = []
        for r in details_json['reviews']:
            # L'API renvoie un timestamp strict, ex: 2024-05-12T08:50:15.237897993Z
            published_date = r.get('publishTime', '')
            
            author_name = ''
            if 'authorAttribution' in r and 'displayName' in r['authorAttribution']:
                author_name = r['authorAttribution']['displayName']
                
            text = ''
            if 'text' in r and 'text' in r['text']:
                text = r['text']['text']
                
            rating = r.get('rating', 0)
            
            # Construire un review_id basé sur l'auteur et la date pour Elasticsearch (clé d'unicité)
            review_id = f"{author_name}|{text[:50]}".lower().strip()
            
            reviews.append({
                "source": "google",
                "store": store_name,
                "review_id": review_id,
                "author_name": author_name,
                "rating": float(rating),
                "text": text,
                "published_date": published_date
            })
            
        return reviews
        
    except Exception as e:
        log(f"  Erreur lors de l'appel API: {e}")
        return []

def main():
    log("\n" + "="*60)
    log("  SCRAPING DES AVIS GOOGLE VIA API PLACES - MAGASINS LDLC")
    log("="*60)
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "AJOUTEZ_VOTRE_CLE_ICI":
        log("ERREUR CRITIQUE: La variable d'environnement GOOGLE_API_KEY est manquante ou invalide.")
        log("Veuillez renseigner votre clé API (ex: dans docker-compose.yml ou en local).")
        return []

    stores = get_stores_list()
    
    all_new_reviews = []
    
    for i, store_name in enumerate(stores):
        log(f"\n[{i+1}/{len(stores)}] {store_name}")
        log("-" * 40)
        
        reviews = get_google_reviews_via_api(store_name, api_key)
        
        if reviews:
            all_new_reviews.extend(reviews)
            log(f"  {len(reviews)} avis récents extraits via l'API.")
        
        # Respecter les quotas API Google (pause symbolique)
        time.sleep(0.5)

    log("\n" + "=" * 60)
    log("  EXTRACTION API TERMINÉE")
    log(f"  Total des avis extraits : {len(all_new_reviews)}")
    log("=" * 60)

    return all_new_reviews

if __name__ == "__main__":
    all_reviews = main()
    
    if all_reviews:
        log("Sauvegarde locale dans Elasticsearch...")
        client = get_es_client()
        create_index_if_not_exists(client, INDEX_NAME)
        load_to_elasticsearch(all_reviews, client)
        log("Sauvegarde terminée !")
