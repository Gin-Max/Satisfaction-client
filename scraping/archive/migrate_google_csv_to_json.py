"""
Script de migration : convertit le CSV Google existant en JSON historique.
À exécuter une seule fois pour initialiser le fichier google_reviews.json.

Usage:
    python scraping/migrate_google_csv_to_json.py
"""

import csv
import json
import os
import hashlib
import re
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CSV_FILE = os.path.join(DATA_DIR, "google_reviews.csv")
JSON_FILE = os.path.join(DATA_DIR, "google_reviews.json")


def generate_review_id(author, text, store):
    """Génère un ID unique pour un avis Google basé sur auteur + texte + magasin."""
    content = f"{author}|{text[:50]}|{store}".lower()
    return f"google_{hashlib.md5(content.encode()).hexdigest()[:12]}"


def clean_text(text):
    if text is None:
        return ""
    return text.strip().replace("\n", " ")


def parse_relative_date(relative_date_str, reference_date=None):
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
    today = reference_date or datetime.now()

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
                return result.strftime("%Y")
            elif unit == "month" or unit == "months":
                result = today - timedelta(days=value * 30)
                return result.strftime("%Y-%m")
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


def migrate():
    if not os.path.exists(CSV_FILE):
        print(f"Fichier CSV non trouvé: {CSV_FILE}")
        return

    reviews = []

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            author = clean_text(row.get("Auteur", ""))
            text = clean_text(row.get("Commentaire", ""))
            store = clean_text(row.get("Magasin", ""))

            # Ignorer les avis sans texte
            if not text:
                continue

            # Convertir la note en entier
            try:
                rating = int(row.get("Note", 0))
            except (ValueError, TypeError):
                rating = 0

            # Convertir la réponse en booléen
            has_reply = str(row.get("Reponse", "")).lower() in ["oui", "o", "yes", "true", "1"]

            relative_date = clean_text(row.get("Date", ""))
            published_date = parse_relative_date(relative_date)

            review = {
                "review_id": generate_review_id(author, text, store),
                "likes": 0,
                "source": "google",
                "provenance": "Organic",
                "store": store,
                "rating": rating,
                "title": "",
                "text": text,
                "published_date": published_date,
                "relative_date": relative_date,
                "author_id": None,
                "author_name": author,
                "author_review_count": 0,
                "consumer_reviews_same_domain": 0,
                "author_is_verified": False,
                "verification_is_verified": False,
                "review_source_name": "google_maps",
                "has_reply": has_reply,
                "reply_published_date": None,
                "reply_message": None,
            }
            reviews.append(review)

    # Dédupliquer par review_id
    seen_ids = set()
    unique_reviews = []
    for r in reviews:
        if r["review_id"] not in seen_ids:
            seen_ids.add(r["review_id"])
            unique_reviews.append(r)

    # Sauvegarder en JSON
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(unique_reviews, f, ensure_ascii=False, indent=2)

    print(f"Migration terminée!")
    print(f"  - {len(reviews)} avis lus depuis le CSV")
    print(f"  - {len(unique_reviews)} avis uniques sauvegardés dans {JSON_FILE}")


if __name__ == "__main__":
    migrate()
