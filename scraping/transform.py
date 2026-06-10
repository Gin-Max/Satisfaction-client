import hashlib


def clean_text(text):
    if text is None:
        return ""
    return text.strip().replace("\n", " ")


def generate_review_id(author, text, store):
    content = f"{author}|{text[:50]}|{store}".lower()
    return f"google_{hashlib.md5(content.encode()).hexdigest()[:12]}"


def normalize_google_review(row):
    author = clean_text(row.get("Auteur", ""))
    text = clean_text(row.get("Commentaire", ""))
    store = clean_text(row.get("Magasin", ""))
    try:
        rating = int(row.get("Note", 0))
    except (ValueError, TypeError):
        rating = 0
    has_reply = str(row.get("Reponse", "")).lower() in ["oui", "o", "yes", "true", "1"]
    return {
        "review_id": generate_review_id(author, text, store),
        "likes": 0,
        "source": "google",
        "store": store,
        "rating": rating,
        "title": "",
        "text": text,
        "published_date": None,
        "relative_date": clean_text(row.get("Date", "")),
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


def normalize_review(review):
    return {
        "review_id": str(review.get("review_id")),
        "likes": int(review.get("likes", 0)),
        "source": review.get("source", ""),
        "rating": int(review.get("rating", 0)),
        "title": clean_text(review.get("title")),
        "text": clean_text(review.get("text")),
        "published_date": review.get("published_date"),
        "author_id": review.get("author_id"),
        "author_name": clean_text(review.get("author_name")),
        "author_review_count": int(review.get("author_review_count", 0)),
        "consumer_reviews_same_domain": int(
            review.get("consumer_reviews_same_domain", 0)
        ),
        "author_is_verified": bool(review.get("author_is_verified", False)),
        "verification_is_verified": bool(review.get("verification_is_verified", False)),
        "review_source_name": review.get("review_source_name"),
        "has_reply": bool(review.get("has_reply")),
        "reply_published_date": review.get("reply_published_date"),
        "reply_message": clean_text(review.get("reply_message")),
    }


def transform(existing_reviews, new_reviews):
    all_reviews = existing_reviews + new_reviews
    seen_ids = set()
    final_reviews = []
    for review in all_reviews:
        review_id = review.get("review_id")
        if review_id and review_id not in seen_ids:
            seen_ids.add(review_id)
            final_reviews.append(normalize_review(review))
    print(f"{len(final_reviews)} reviews après transformation (historique + nouvelles)")
    return final_reviews
