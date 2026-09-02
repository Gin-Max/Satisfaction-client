"""
Script pour mettre à jour les dates dans le JSON historique Google.
Convertit les dates relatives en dates absolues en utilisant
la date du scraping original comme référence.

Usage:
    python scraping/update_historical_dates.py
"""

import json
import os
import re
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
JSON_FILE = os.path.join(DATA_DIR, "google_reviews.json")

# Date du scraping original (commit du CSV)
ORIGINAL_SCRAPE_DATE = datetime(2026, 6, 8)


def parse_relative_date(relative_date_str, reference_date):
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
                result = reference_date - timedelta(days=value * 365)
                return result.strftime("%Y")  # Juste l'année
            elif unit == "month" or unit == "months":
                result = reference_date - timedelta(days=value * 30)
                return result.strftime("%Y-%m")  # Année-mois
            elif unit == "week" or unit == "weeks":
                result = reference_date - timedelta(weeks=value)
                return result.strftime("%Y-%m-%d")
            elif unit == "day" or unit == "days":
                result = reference_date - timedelta(days=value)
                return result.strftime("%Y-%m-%d")
            elif unit == "hour" or unit == "hours":
                result = reference_date - timedelta(hours=value)
                return result.strftime("%Y-%m-%d")

    return None


def update_dates():
    if not os.path.exists(JSON_FILE):
        print(f"Fichier JSON non trouvé: {JSON_FILE}")
        return

    with open(JSON_FILE, "r", encoding="utf-8") as f:
        reviews = json.load(f)

    print(f"Mise à jour de {len(reviews)} avis...")
    print(f"Date de référence: {ORIGINAL_SCRAPE_DATE.strftime('%Y-%m-%d')}")

    updated_count = 0
    for review in reviews:
        relative_date = review.get("relative_date", "")
        if relative_date:
            published_date = parse_relative_date(relative_date, ORIGINAL_SCRAPE_DATE)
            if published_date:
                review["published_date"] = published_date
                updated_count += 1

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(reviews, f, ensure_ascii=False, indent=2)

    print(f"Terminé! {updated_count} dates converties.")


if __name__ == "__main__":
    update_dates()
