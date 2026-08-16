import re
from collections import Counter
from elasticsearch import Elasticsearch

# -------------------------------------------------------------------------
# 1. Configuration et Connexion Elasticsearch
# -------------------------------------------------------------------------
ES_HOST = "http://localhost:9200"
INDEX_NAME = "reviews"
SAMPLE_SIZE = 5000  # Analyse sur un échantillon de 5000 avis 'Autre'

client = Elasticsearch([ES_HOST], request_timeout=60)

# Liste de mots vides (stopwords) à ignorer pour ne garder que les termes porteurs de sens
STOPWORDS = {
    "a", "au", "aux", "avec", "ce", "ces", "dans", "de", "des", "du", "elle",
    "en", "est", "et", "eux", "il", "ils", "je", "la", "le", "les", "leur",
    "lui", "ma", "mais", "me", "meme", "mes", "moi", "mon", "ne", "nos",
    "notre", "nous", "on", "ou", "par", "pas", "pour", "qu", "que", "qui",
    "sa", "se", "ses", "son", "sur", "ta", "te", "tes", "toi", "ton", "tous",
    "tout", "une", "un", "vos", "votre", "vous", "c", "d", "j", "l", "m",
    "n", "s", "t", "y", "ete", "etre", "avoir", "fait", "faire", "plus",
    "tres", "bien", "merci", "bon", "bonne", "avis", "tout", "tous"
}

# -------------------------------------------------------------------------
# 2. Récupération des avis étiquetés 'Autre'
# -------------------------------------------------------------------------
print(f"[INFO] Récupération de {SAMPLE_SIZE} avis étiquetés 'Autre'...")

query = {
    "query": {
        "term": {
            "thematique_predite.keyword": "Autre"
        }
    },
    "_source": ["text"],
    "size": SAMPLE_SIZE
}

try:
    response = client.search(index=INDEX_NAME, body=query)
    hits = response["hits"]["hits"]
    print(f"[INFO] {len(hits)} avis récupérés pour l'analyse.")
except Exception as e:
    print(f"[ERREUR] Erreur lors de la requête Elasticsearch : {e}")
    exit(1)

# -------------------------------------------------------------------------
# 3. Extraction et comptage des termes les plus fréquents
# -------------------------------------------------------------------------
word_counter = Counter()

for hit in hits:
    text = hit.get("_source", {}).get("text", "")
    if not text:
        continue
    
    # Nettoyage : suppression des caractères spéciaux et passage en minuscules
    tokens = re.findall(r"\b[a-zA-Zàâäéèêëîïôöùûüç]{3,}\b", text.lower())
    
    # Filtrage des stopwords
    meaningful_words = [word for word in tokens if word not in STOPWORDS]
    word_counter.update(meaningful_words)

# -------------------------------------------------------------------------
# 4. Affichage des résultats
# -------------------------------------------------------------------------
print("\n=== TOP 30 DES TERMES LES PLUS FRÉQUENTS DANS 'AUTRE' ===")
for word, count in word_counter.most_common(30):
    print(f"{word:<20} : {count} occurrences")

print("\n=== ÉCHANTILLON DE 5 TEXTES BRUTS ===")
for i, hit in enumerate(hits[:5], 1):
    text_preview = hit.get("_source", {}).get("text", "")[:120].strip()
    print(f"[{i}] {text_preview}...")