"""
Script de scraping des avis Google Maps pour les magasins LDLC.
Récupère la liste des magasins en temps réel depuis le site LDLC,
puis scrape les avis Google pour chaque magasin.

Pattern identique à Trustpilot :
- JSON historique pour bootstrap si ES est vide
- Retourne les reviews directement (pas de CSV)
- Stockage dans Elasticsearch uniquement
"""

import json
import os
import time
import random
import hashlib
import re
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

def log(msg):
    """Print avec flush immédiat."""
    print(msg, flush=True)

# Configuration
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
HISTORICAL_JSON = os.path.join(DATA_DIR, "google_reviews.json")
INDEX_NAME = "reviews"
MAX_SCROLL_ATTEMPTS = 100  # Limite de sécurité pour éviter boucle infinie


def parse_relative_date(relative_date_str):
    """
    Convertit une date relative Google en date approximative.
    Format adapté à la précision:
    - Années: YYYY
    - Mois: YYYY-MM
    - Semaines/jours/heures: YYYY-MM-DD
    """
    if not relative_date_str:
        return None

    text = relative_date_str.lower().strip()
    today = datetime.now()

    # Patterns pour les différentes unités de temps
    patterns = [
        # Français avec chiffres
        (r"il y a (\d+)\s*an", "years"),
        (r"il y a (\d+)\s*mois", "months"),
        (r"il y a (\d+)\s*semaine", "weeks"),
        (r"il y a (\d+)\s*jour", "days"),
        (r"il y a (\d+)\s*heure", "hours"),
        # Français avec "un/une"
        (r"il y a une?\s*an", "one_year"),
        (r"il y a une?\s*mois", "one_month"),
        (r"il y a une?\s*semaine", "one_week"),
        (r"il y a une?\s*jour", "one_day"),
        (r"il y a une?\s*heure", "one_hour"),
        # Anglais
        (r"(\d+)\s*year", "years"),
        (r"(\d+)\s*month", "months"),
        (r"(\d+)\s*week", "weeks"),
        (r"(\d+)\s*day", "days"),
        (r"(\d+)\s*hour", "hours"),
        (r"a year", "one_year"),
        (r"a month", "one_month"),
        (r"a week", "one_week"),
        (r"a day", "one_day"),
        (r"an hour", "one_hour"),
    ]

    for pattern, unit in patterns:
        match = re.search(pattern, text)
        if match:
            # Déterminer la valeur
            if unit.startswith("one_"):
                value = 1
                unit = unit[4:]
            else:
                value = int(match.group(1))

            # Calculer la date et le format selon la précision
            if unit == "year" or unit == "years":
                result = today - timedelta(days=value * 365)
                return result.strftime("%Y")  # Juste l'année
            elif unit == "month" or unit == "months":
                result = today - timedelta(days=value * 30)
                return result.strftime("%Y-%m")  # Année-mois
            elif unit == "week" or unit == "weeks":
                result = today - timedelta(weeks=value)
                return result.strftime("%Y-%m-%d")
            elif unit == "day" or unit == "days":
                result = today - timedelta(days=value)
                return result.strftime("%Y-%m-%d")
            elif unit == "hour" or unit == "hours":
                result = today - timedelta(hours=value)
                return result.strftime("%Y-%m-%d")

    return None


def generate_review_id(author, text, store):
    """Génère un ID unique pour un avis Google basé sur auteur + texte + magasin."""
    content = f"{author}|{text[:50]}|{store}".lower()
    return f"google_{hashlib.md5(content.encode()).hexdigest()[:12]}"


def load_historical_reviews():
    """Charge les reviews historiques depuis le JSON."""
    if not os.path.exists(HISTORICAL_JSON):
        log("Pas de fichier historique Google trouvé.")
        return []
    with open(HISTORICAL_JSON, "r", encoding="utf-8") as f:
        existing_reviews = json.load(f)
    log(f"{len(existing_reviews)} reviews Google historiques chargées")
    return existing_reviews


def is_google_empty(client):
    """Vérifie si Elasticsearch est vide pour la source Google."""
    try:
        result = client.count(index=INDEX_NAME, body={
            "query": {"term": {"source": "google"}}
        })
        return result["count"] == 0
    except Exception:
        return True


def get_existing_review_keys_from_es(client):
    """
    Récupère les clés uniques des avis Google existants dans ES.
    Retourne un dict: {magasin: set(clés_uniques)}
    """
    existing = {}
    try:
        # Scroll à travers tous les avis Google
        result = client.search(
            index=INDEX_NAME,
            body={
                "query": {"term": {"source": "google"}},
                "size": 10000,
                "_source": ["store", "author_name", "text"]
            },
            scroll="2m"
        )

        scroll_id = result["_scroll_id"]
        hits = result["hits"]["hits"]

        while hits:
            for hit in hits:
                source = hit["_source"]
                store = source.get("store", "")
                author = source.get("author_name", "")
                text = source.get("text", "")[:50]

                if store not in existing:
                    existing[store] = set()

                key = f"{author}|{text}".lower().strip()
                existing[store].add(key)

            result = client.scroll(scroll_id=scroll_id, scroll="2m")
            hits = result["hits"]["hits"]

        client.clear_scroll(scroll_id=scroll_id)

    except Exception as e:
        log(f"Erreur lors de la récupération des avis existants: {e}")

    total = sum(len(keys) for keys in existing.values())
    log(f"{total} avis Google existants dans ES pour {len(existing)} magasins")
    return existing


def get_review_key(author, text):
    """Génère une clé unique pour un avis."""
    return f"{author}|{text[:50]}".lower().strip()


def get_stores_list(page):
    """
    Récupère la liste des magasins depuis la page LDLC.
    Retourne une liste de dicts avec 'name' et 'url'.
    """
    log("Navigation vers la page des magasins LDLC...")
    response = page.goto("https://www.ldlc.com/magasins-ldlc/")
    log(f"Status code: {response.status}")
    page.wait_for_load_state("networkidle")

    log("Extraction de la liste des magasins...")
    js_get_stores = """
    () => {
        const links = Array.from(document.querySelectorAll("a"));
        const stores = [];
        for (const a of links) {
            if (a.href && a.href.includes('/magasins-ldlc/magasin-') && a.innerText.trim() !== '') {
                stores.push({
                    name: a.innerText.trim(),
                    url: a.href
                });
            }
        }
        // Dé-dupliquer par URL
        return Array.from(new Map(stores.map(item => [item.url, item])).values());
    }
    """
    stores = page.evaluate(js_get_stores)
    log(f"{len(stores)} magasins trouvés.")
    return stores


def get_google_reviews_link(page, store_url):
    """
    Va sur la page d'un magasin LDLC et extrait le lien vers les avis Google.
    Retourne l'URL Google Maps ou None si non trouvé.
    """
    page.goto(store_url)
    page.wait_for_load_state("networkidle")

    # Chercher le lien "X avis Google" - priorité aux liens avec "avis" dans le texte
    js_get_google_link = """
    () => {
        const links = Array.from(document.querySelectorAll("a"));

        // Fonction pour vérifier si c'est un lien Google Maps
        const isGoogleMapsLink = (href) => {
            return href.includes('maps.google.com') ||
                   href.includes('google.com/maps') ||
                   href.includes('goo.gl/maps');
        };

        // Priorité 1: lien avec "avis" dans le texte (le vrai lien des avis)
        for (const a of links) {
            if (a.href && isGoogleMapsLink(a.href) && a.innerText.toLowerCase().includes('avis')) {
                return a.href;
            }
        }

        // Priorité 2: lien avec cid= (fiche du lieu)
        for (const a of links) {
            if (a.href && a.href.includes('cid=')) {
                return a.href;
            }
        }

        // Priorité 3: tout autre lien Google Maps (fallback)
        for (const a of links) {
            if (a.href && isGoogleMapsLink(a.href)) {
                return a.href;
            }
        }

        return null;
    }
    """
    return page.evaluate(js_get_google_link)


def handle_google_cookies(page):
    """Gère la bannière de cookies Google si présente."""
    try:
        accept_button = page.locator(
            "button:has-text('Tout accepter'), "
            "button:has-text('Accept all'), "
            "[aria-label='Tout accepter'], "
            "[aria-label='Accept all']"
        )
        accept_button.first.wait_for(state="visible", timeout=5000)
        accept_button.first.click()
        log("  Cookies Google acceptés.")
        page.wait_for_timeout(2000)
    except:
        pass  # Pas de bannière de cookies


def scrape_reviews_from_maps(page, store_name, google_url, existing_keys):
    """
    Scrape les avis depuis une page Google Maps.
    S'arrête dès qu'on trouve un avis déjà en base.
    Retourne une liste de nouveaux reviews uniquement.
    """
    log(f"  Navigation vers Google Maps...")
    page.goto(google_url)
    page.wait_for_timeout(3000)

    # Gérer les cookies Google (uniquement au premier accès)
    handle_google_cookies(page)

    # Cliquer sur l'onglet "Avis" si présent
    try:
        avis_tab = page.locator("button[role='tab']:has-text('Avis'), button[role='tab']:has-text('Reviews')")
        if avis_tab.count() > 0:
            avis_tab.first.click()
            page.wait_for_timeout(2000)
            log("  Onglet 'Avis' ouvert.")
    except:
        log("  Pas d'onglet 'Avis' trouvé, tentative de scroll direct...")

    # Scroll pour charger les avis jusqu'à trouver un avis existant
    log("  Chargement des avis (mode incrémental)...")
    scroll_container = page.locator('.m6QErb.DxyBCb.kA9KIf.dS8AEf')

    previous_count = 0
    no_change_count = 0
    found_existing = False

    for i in range(MAX_SCROLL_ATTEMPTS):
        if scroll_container.count() == 0:
            break

        # Scroll vers le bas
        scroll_container.first.evaluate("el => el.scrollTop = el.scrollHeight")
        page.wait_for_timeout(random.uniform(1500, 2500))

        # Compter les avis actuels
        current_count = page.locator('div.jftiEf').count()

        # Afficher progression tous les 10 scrolls
        if (i + 1) % 10 == 0:
            log(f"  ... {current_count} avis chargés (scroll #{i+1})")

        # Vérifier si on a trouvé un avis existant (vérification périodique)
        if (i + 1) % 5 == 0 and existing_keys:
            # Extraire les derniers avis chargés pour vérifier
            check_result = page.evaluate("""
            () => {
                const reviews = Array.from(document.querySelectorAll('div.jftiEf'));
                // Vérifier les 10 derniers avis
                return reviews.slice(-10).map(node => {
                    const author = node.querySelector('.d4r55')?.innerText ||
                                  node.querySelector('.WNxzHc')?.innerText || '';
                    const text = node.querySelector('.wiI7pd')?.innerText || '';
                    return {
                        author: author.trim(),
                        text: text.substring(0, 50).trim()
                    };
                });
            }
            """)

            for item in check_result:
                key = get_review_key(item['author'], item['text'])
                if key in existing_keys:
                    log(f"  Avis existant trouvé, arrêt du scroll.")
                    found_existing = True
                    break

            if found_existing:
                break

        # Si pas de changement après 5 scrolls consécutifs, on a tout chargé
        if current_count == previous_count:
            no_change_count += 1
            if no_change_count >= 5:
                log(f"  Fin du scroll: {current_count} avis chargés.")
                break
        else:
            no_change_count = 0
            previous_count = current_count

    # Extraction des avis
    log("  Extraction des avis...")
    js_extract = """
    () => {
        const reviews_nodes = Array.from(document.querySelectorAll('div.jftiEf'));
        return reviews_nodes.map(node => {
            const author = node.querySelector('.d4r55')?.innerText ||
                          node.querySelector('.WNxzHc')?.innerText || '';

            // Note dans l'aria-label (ex: '5 étoiles')
            const ratingEl = node.querySelector('.kvMYJc');
            const ratingLabel = ratingEl ? ratingEl.getAttribute('aria-label') : '';
            // Extraire le chiffre de la note
            const noteMatch = ratingLabel.match(/([0-9])/);
            const note = noteMatch ? parseInt(noteMatch[1]) : 0;

            const date = node.querySelector('.rsqaWe')?.innerText || '';
            let text = node.querySelector('.wiI7pd')?.innerText || '';
            // Nettoyer les retours à la ligne
            text = text.replace(/[\\r\\n]+/g, ' ').replace(/\\s+/g, ' ');
            const hasResponse = node.querySelector('.CDe7pd') ? true : false;

            return {
                author: author.trim().replace(/[\\r\\n]+/g, ' '),
                rating: note,
                relative_date: date.trim(),
                text: text.trim(),
                has_reply: hasResponse
            };
        });
    }
    """
    raw_reviews = page.evaluate(js_extract)

    # Filtrer pour ne garder que les nouveaux avis et les normaliser
    new_reviews = []
    for review in raw_reviews:
        key = get_review_key(review['author'], review['text'])
        if key not in existing_keys:
            # Convertir la date relative en date absolue
            published_date = parse_relative_date(review['relative_date'])

            # Normaliser au format Elasticsearch
            normalized = {
                "review_id": generate_review_id(review['author'], review['text'], store_name),
                "likes": 0,
                "source": "google",
                "provenance": "Organic",
                "store": store_name,
                "rating": review['rating'],
                "title": "",
                "text": review['text'],
                "published_date": published_date,
                "relative_date": review['relative_date'],  # Gardé pour référence
                "author_id": None,
                "author_name": review['author'],
                "author_review_count": 0,
                "consumer_reviews_same_domain": 0,
                "author_is_verified": False,
                "verification_is_verified": False,
                "review_source_name": "google_maps",
                "has_reply": review['has_reply'],
                "reply_published_date": None,
                "reply_message": None,
            }
            new_reviews.append(normalized)
        else:
            # On a atteint les avis existants, on peut s'arrêter
            break

    return new_reviews


def scrape_all_stores(existing_review_keys):
    """
    Scrape les avis Google pour tous les magasins LDLC.
    Retourne la liste des nouveaux avis (format normalisé).
    """
    all_new_reviews = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = browser.new_context(locale="fr-FR")
        page = context.new_page()

        # Étape 1: Récupérer la liste des magasins
        stores = get_stores_list(page)

        # Étape 2: Pour chaque magasin, scraper les nouveaux avis
        for i, store in enumerate(stores):
            store_name = store['name']
            store_url = store['url']

            log(f"\n[{i+1}/{len(stores)}] {store_name}")
            log("-" * 40)

            # Récupérer les clés existantes pour ce magasin
            existing_keys = existing_review_keys.get(store_name, set())
            log(f"  {len(existing_keys)} avis existants en base.")

            try:
                # Récupérer le lien Google Maps depuis la page LDLC
                google_url = get_google_reviews_link(page, store_url)

                if not google_url:
                    log(f"  Aucun lien Google Maps trouvé pour {store_name}. Skip.")
                    continue

                log(f"  Lien Google trouvé: {google_url[:60]}...")

                # Scraper les nouveaux avis Google
                new_reviews = scrape_reviews_from_maps(page, store_name, google_url, existing_keys)

                if new_reviews:
                    all_new_reviews.extend(new_reviews)
                    log(f"  {len(new_reviews)} NOUVEAUX avis extraits.")
                else:
                    log(f"  Aucun nouvel avis.")

                # Pause aléatoire entre les magasins
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                log(f"  ERREUR: {e}")
                log("  Passage au magasin suivant...")
                continue

        browser.close()

    return all_new_reviews


def main():
    """
    Point d'entrée principal - suit le pattern Trustpilot.
    Retourne existing_reviews + new_reviews pour chargement dans ES.
    """
    from scraping.load import get_es_client

    log("=" * 60)
    log("  SCRAPING DES AVIS GOOGLE - MAGASINS LDLC")
    log("  Mode: INCRÉMENTAL (nouveaux avis uniquement)")
    log("=" * 60)

    client = get_es_client()

    # Si ES est vide pour Google, charger l'historique JSON
    existing_reviews = load_historical_reviews() if is_google_empty(client) else []

    # Récupérer les clés des avis existants dans ES pour le mode incrémental
    existing_review_keys = get_existing_review_keys_from_es(client)

    # Scraper les nouveaux avis
    new_reviews = scrape_all_stores(existing_review_keys)

    log("\n" + "=" * 60)
    log("  SCRAPING TERMINÉ")
    log(f"  Reviews historiques: {len(existing_reviews)}")
    log(f"  Nouveaux avis: {len(new_reviews)}")
    log("=" * 60)

    return existing_reviews + new_reviews

