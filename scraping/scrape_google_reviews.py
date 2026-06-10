import csv
import os
import random
import time

from playwright.sync_api import sync_playwright


def log(msg):
    print(msg, flush=True)


DATA_DIR = "data"
CSV_FILE = os.path.join(DATA_DIR, "google_reviews.csv")
MAX_SCROLL_ATTEMPTS = 100


def load_existing_reviews():
    existing = {}
    if not os.path.exists(CSV_FILE):
        return existing
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            store = row.get("Magasin", "")
            author = row.get("Auteur", "")
            comment = row.get("Commentaire", "")[:50]
            existing.setdefault(store, set()).add(f"{author}|{comment}".lower().strip())
    return existing


def get_review_key(author, text):
    return f"{author}|{text[:50]}".lower().strip()


def setup_csv():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Magasin", "Auteur", "Note", "Date", "Commentaire", "Reponse"])


def get_stores_list(page):
    page.goto("https://www.ldlc.com/magasins-ldlc/")
    page.wait_for_load_state("networkidle")
    stores = page.evaluate(
        """
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            const stores = [];
            for (const a of links) {
                if (a.href && a.href.includes('/magasins-ldlc/magasin-') && a.innerText.trim() !== '') {
                    stores.push({ name: a.innerText.trim(), url: a.href });
                }
            }
            return Array.from(new Map(stores.map(item => [item.url, item])).values());
        }
        """
    )
    return stores


def get_google_reviews_link(page, store_url):
    page.goto(store_url)
    page.wait_for_load_state("networkidle")
    return page.evaluate(
        """
        () => {
            const links = Array.from(document.querySelectorAll('a'));
            const isGoogleMapsLink = (href) => href.includes('maps.google.com') || href.includes('google.com/maps') || href.includes('goo.gl/maps');
            for (const a of links) {
                if (a.href && isGoogleMapsLink(a.href) && a.innerText.toLowerCase().includes('avis')) return a.href;
            }
            for (const a of links) {
                if (a.href && a.href.includes('cid=')) return a.href;
            }
            for (const a of links) {
                if (a.href && isGoogleMapsLink(a.href)) return a.href;
            }
            return null;
        }
        """
    )


def handle_google_cookies(page):
    try:
        accept_button = page.locator("button:has-text('Tout accepter'), button:has-text('Accept all')")
        accept_button.first.wait_for(state="visible", timeout=5000)
        accept_button.first.click()
        page.wait_for_timeout(2000)
    except Exception:
        pass


def scrape_reviews_from_maps(page, store_name, google_url, existing_keys):
    page.goto(google_url)
    page.wait_for_timeout(3000)
    handle_google_cookies(page)
    try:
        avis_tab = page.locator("button[role='tab']:has-text('Avis'), button[role='tab']:has-text('Reviews')")
        if avis_tab.count() > 0:
            avis_tab.first.click()
            page.wait_for_timeout(2000)
    except Exception:
        pass
    scroll_container = page.locator('.m6QErb.DxyBCb.kA9KIf.dS8AEf')
    previous_count = 0
    no_change_count = 0
    for _ in range(MAX_SCROLL_ATTEMPTS):
        if scroll_container.count() == 0:
            break
        scroll_container.first.evaluate("el => el.scrollTop = el.scrollHeight")
        page.wait_for_timeout(random.uniform(1500, 2500))
        current_count = page.locator('div.jftiEf').count()
        if current_count == previous_count:
            no_change_count += 1
            if no_change_count >= 5:
                break
        else:
            no_change_count = 0
            previous_count = current_count
    all_reviews = page.evaluate(
        """
        () => Array.from(document.querySelectorAll('div.jftiEf')).map(node => {
            const author = node.querySelector('.d4r55')?.innerText || node.querySelector('.WNxzHc')?.innerText || '';
            const ratingEl = node.querySelector('.kvMYJc');
            const ratingLabel = ratingEl ? ratingEl.getAttribute('aria-label') : '';
            const noteMatch = ratingLabel.match(/([0-9])/);
            const note = noteMatch ? noteMatch[1] : '';
            const date = node.querySelector('.rsqaWe')?.innerText || '';
            let text = node.querySelector('.wiI7pd')?.innerText || '';
            text = text.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ');
            const hasResponse = node.querySelector('.CDe7pd') ? 'oui' : 'non';
            return {author: author.trim().replace(/[\r\n]+/g, ' '), note, date: date.trim(), text: text.trim(), response: hasResponse};
        })
        """
    )
    new_reviews = []
    for review in all_reviews:
        key = get_review_key(review["author"], review["text"])
        if key not in existing_keys:
            new_reviews.append(review)
        else:
            break
    return new_reviews


def save_reviews_to_csv(store_name, reviews):
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for review in reviews:
            writer.writerow([store_name, review['author'], review['note'], review['date'], review['text'], review['response']])


def main():
    setup_csv()
    existing_reviews = load_existing_reviews()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="fr-FR")
        page = context.new_page()
        stores = get_stores_list(page)
        for store in stores:
            store_name = store['name']
            existing_keys = existing_reviews.get(store_name, set())
            try:
                google_url = get_google_reviews_link(page, store['url'])
                if not google_url:
                    continue
                new_reviews = scrape_reviews_from_maps(page, store_name, google_url, existing_keys)
                if new_reviews:
                    save_reviews_to_csv(store_name, new_reviews)
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                log(f"Erreur {store_name}: {e}")
                continue
        browser.close()


if __name__ == "__main__":
    main()
