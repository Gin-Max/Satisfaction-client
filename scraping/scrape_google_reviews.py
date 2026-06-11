"""
Script de scraping des avis Google Maps pour les magasins LDLC.
Récupère la liste des magasins en temps réel depuis le site LDLC,
puis scrape les avis Google pour chaque magasin.

Mode incrémental : ne récupère que les nouveaux avis (compare avec la BDD existante).
"""

import json
import os
import time
import random
import csv
import sys
from playwright.sync_api import sync_playwright

def log(msg):
    """Print avec flush immédiat."""
    print(msg, flush=True)

# Configuration
DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "google_reviews.csv")
STATUS_FILE = "scraping_status.json"
MAX_SCROLL_ATTEMPTS = 100  # Limite de sécurité pour éviter boucle infinie


def load_existing_reviews():
    """
    Charge les avis existants depuis le CSV.
    Retourne un dict: {magasin: set(clés_uniques)}
    La clé unique = auteur + 50 premiers caractères du commentaire
    """
    existing = {}

    if not os.path.exists(CSV_FILE):
        return existing

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            store = row.get("Magasin", "")
            author = row.get("Auteur", "")
            comment = row.get("Commentaire", "")[:50]  # 50 premiers caractères

            if store not in existing:
                existing[store] = set()

            # Clé unique pour identifier un avis
            key = f"{author}|{comment}".lower().strip()
            existing[store].add(key)

    return existing


def get_review_key(author, text):
    """Génère une clé unique pour un avis."""
    return f"{author}|{text[:50]}".lower().strip()


def setup_csv():
    """Initialise le fichier CSV s'il n'existe pas."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Magasin", "Auteur", "Note", "Date", "Commentaire", "Reponse"])


def get_stores_list(page):
    """
    Récupère la liste des magasins depuis la page LDLC.
    Retourne une liste de dicts avec 'name' et 'url'.
    """
    log("Navigation vers la page des magasins LDLC...")
    page.goto("https://www.ldlc.com/magasins-ldlc/")
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
            const note = noteMatch ? noteMatch[1] : '';

            const date = node.querySelector('.rsqaWe')?.innerText || '';
            let text = node.querySelector('.wiI7pd')?.innerText || '';
            // Nettoyer les retours à la ligne pour éviter de casser le CSV
            text = text.replace(/[\\r\\n]+/g, ' ').replace(/\\s+/g, ' ');
            const hasResponse = node.querySelector('.CDe7pd') ? 'oui' : 'non';

            return {
                author: author.trim().replace(/[\\r\\n]+/g, ' '),
                note: note,
                date: date.trim(),
                text: text.trim(),
                response: hasResponse
            };
        });
    }
    """
    all_reviews = page.evaluate(js_extract)

    # Filtrer pour ne garder que les nouveaux avis
    new_reviews = []
    for review in all_reviews:
        key = get_review_key(review['author'], review['text'])
        if key not in existing_keys:
            new_reviews.append(review)
        else:
            # On a atteint les avis existants, on peut s'arrêter
            break

    return new_reviews


def save_reviews_to_csv(store_name, reviews):
    """Sauvegarde les avis dans le fichier CSV."""
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for review in reviews:
            writer.writerow([
                store_name,
                review['author'],
                review['note'],
                review['date'],
                review['text'],
                review['response']
            ])


def main():
    log("=" * 60)
    log("  SCRAPING DES AVIS GOOGLE - MAGASINS LDLC")
    log("  Mode: INCRÉMENTAL (nouveaux avis uniquement)")
    log("=" * 60)

    setup_csv()

    # Charger les avis existants
    log("\nChargement des avis existants...")
    existing_reviews = load_existing_reviews()
    total_existing = sum(len(keys) for keys in existing_reviews.values())
    log(f"{total_existing} avis existants en base pour {len(existing_reviews)} magasins.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="fr-FR")
        page = context.new_page()

        # Étape 1: Récupérer la liste des magasins
        stores = get_stores_list(page)

        total_new_reviews = 0

        # Étape 2: Pour chaque magasin, scraper les nouveaux avis
        for i, store in enumerate(stores):
            store_name = store['name']
            store_url = store['url']

            log(f"\n[{i+1}/{len(stores)}] {store_name}")
            log("-" * 40)

            # Récupérer les clés existantes pour ce magasin
            existing_keys = existing_reviews.get(store_name, set())
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
                    save_reviews_to_csv(store_name, new_reviews)
                    total_new_reviews += len(new_reviews)
                    log(f"  {len(new_reviews)} NOUVEAUX avis extraits et sauvegardés.")
                else:
                    log(f"  Aucun nouvel avis.")

                # Pause aléatoire entre les magasins
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                log(f"  ERREUR: {e}")
                log("  Passage au magasin suivant...")
                continue

        browser.close()

    log("\n" + "=" * 60)
    log("  SCRAPING TERMINÉ")
    log(f"  Nouveaux avis ajoutés: {total_new_reviews}")
    log(f"  Données sauvegardées dans: {CSV_FILE}")
    log("=" * 60)


if __name__ == "__main__":
    main()
