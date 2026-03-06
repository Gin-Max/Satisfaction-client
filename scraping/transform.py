def clean_text(text):
    if text is None:
        return ""
    return text.strip().replace("\n", " ")


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
        "consumer_reviews_same_domain": int(review.get("consumer_reviews_same_domain", 0)),
        "author_is_verified": bool(review.get("author_is_verified", False)),
        "verification_is_verified": bool(review.get("verification_is_verified", False)),
        "review_source_name": review.get("review_source_name"),
        "has_reply": bool(review.get("has_reply")),
        "reply_published_date": review.get("reply_published_date"),
        "reply_message": clean_text(review.get("reply_message")),
    }


def transform(existing_reviews, new_reviews):
    """
    Fusionne les reviews historiques et les nouvelles,
    supprime les doublons, et normalise chaque review.
    """
    # Fusionne historique + nouvelles
    all_reviews = existing_reviews + new_reviews

    # Supprime les doublons par review_id et normalise
    seen_ids = set()
    final_reviews = []
    for r in all_reviews:
        rid = r.get("review_id")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            final_reviews.append(normalize_review(r))

    print(f"{len(final_reviews)} reviews après transformation (historique + nouvelles)")
    return final_reviews