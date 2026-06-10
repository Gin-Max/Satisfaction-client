from scraping.transform import clean_text, normalize_google_review, transform


def test_clean_text_handles_none():
    assert clean_text(None) == ""


def test_normalize_google_review_basic_fields():
    row = {
        "Magasin": "Lyon",
        "Auteur": "Alice",
        "Note": "5",
        "Date": "il y a 2 jours",
        "Commentaire": "Super service",
        "Reponse": "oui",
    }
    normalized = normalize_google_review(row)
    assert normalized["source"] == "google"
    assert normalized["rating"] == 5
    assert normalized["store"] == "Lyon"
    assert normalized["has_reply"] is True


def test_transform_deduplicates_reviews():
    existing = [{"review_id": "1", "title": "A", "text": "A", "rating": 5}]
    new = [
        {"review_id": "1", "title": "B", "text": "B", "rating": 1},
        {"review_id": "2", "title": "C", "text": "C", "rating": 4},
    ]
    result = transform(existing, new)
    assert [r["review_id"] for r in result] == ["1", "2"]
