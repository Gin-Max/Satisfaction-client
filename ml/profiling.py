import requests
import pandas as pd

# 1. Récupération des données depuis l'API
URL_API = "http://localhost:8000/avis"
print("🔄 Connexion à l'API et récupération des données...")

try:
    response = requests.get(URL_API)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    print(f"❌ Erreur de connexion à l'API : {e}")
    print("Vérifie que ton conteneur Docker 'api' est bien démarré.")
    exit()

# 2. Chargement dans un DataFrame Pandas
df = pd.DataFrame(data["avis"])

print("\n" + "="*50)
print("PROFILING DU JEU DE DONNÉES (10 000 AVIS)")
print("="*50)

# Statistique 1 : Nombre total de lignes et colonnes reçues
print(f"Dimensions de la matrice de données : {df.shape[0]} lignes, {df.shape[1]} colonnes")

# Statistique 2 : Répartition précise des notes (1 à 5 étoiles)
print("\n RÉPARTITION DES NOTES DE LA BASE DE DONNÉES :")
counts = df['rating'].value_counts().sort_index()
percentages = df['rating'].value_counts(normalize=True).sort_index() * 100

for note in range(1, 6):
    nb_avis = counts.get(note, 0)
    pct_avis = percentages.get(note, 0)
    # On affiche une petite barre visuelle pour le terminal
    barre = "█" * int(pct_avis / 2)
    print(f"  ⭐ {note} Étoile(s) : {nb_avis:>4} avis ({pct_avis:>5.2f}%) {barre}")

# Statistique 3 : Analyse du déséquilibre (Ce qui sera gardé vs supprimé)
print("\n IMPACT DU FILTRAGE DES 3 ÉTOILES (NEUTRES) :")
nb_neutres = counts.get(3, 0)
nb_utiles = len(df) - nb_neutres
print(f"  • Avis neutres (3 étoiles) qui seront supprimés : {nb_neutres} ({percentages.get(3, 0):.2f}%)")
print(f"  • Avis utiles pour le ML (Positifs & Négatifs)  : {nb_utiles} ({100 - percentages.get(3, 0):.2f}%)")

# Statistique 4 : Longueur des commentaires (En nombre de caractères)
df['longueur_texte'] = df['text'].apply(lambda x: len(str(x)))
print("\n LONGUEUR DES COMMENTAIRES CLIENTS (Caractères) :")
print(f"  • Plus court commentaire : {df['longueur_texte'].min()} caractères")
print(f"  • Longueur moyenne       : {int(df['longueur_texte'].mean())} caractères")
print(f"  • Plus long commentaire  : {df['longueur_texte'].max()} caractères")

# Statistique 5 : Répartition par plateforme source
if 'source' in df.columns:
    print("\n RÉPARTITION PAR PLATEFORME SOURCE :")
    sources = df['source'].value_counts()
    for src, total in sources.items():
        print(f"  • {src} : {total} avis")

print("\n" + "="*50)
print("Fin du profiling.")
print("="*50)