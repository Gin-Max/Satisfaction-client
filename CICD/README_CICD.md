# CI/CD du projet Satisfaction Client

## Contenu
- `ci.yml` : vérifie le code à chaque push/PR
- `docker-publish.yml` : build et push les images Docker sur GHCR après merge sur `main`
- `deploy-staging.yml` : déploie automatiquement l'environnement de test depuis `develop`
- `requirements-dev.txt` : dépendances pour lint/tests
- `tests/` : premiers tests automatiques

## Fonctionnement
### 1. Intégration continue (CI)
À chaque push ou pull request :
- Black vérifie le formatage
- Flake8 vérifie la qualité du code
- Pytest lance les tests
- Docker vérifie que les images `api` et `scraping` buildent correctement

### 2. Publication des images Docker
À chaque merge sur `main` :
- GitHub Actions construit les images Docker
- les pousse sur GitHub Container Registry (`ghcr.io`)
- applique les tags `latest` et `sha-<commit>`

### 3. Déploiement staging
À chaque push sur `develop` :
- connexion SSH au serveur de test
- mise à jour du repo
- redémarrage des services avec `docker compose`

## Secrets GitHub à créer
Dans `Settings > Secrets and variables > Actions` :
- `STAGING_HOST`
- `STAGING_USER`
- `STAGING_SSH_KEY`
- `STAGING_APP_DIR`

## Conseils d'équipe
- développer sur `feature/...`
- ouvrir une PR vers `develop`
- laisser le workflow CI valider
- merger vers `main` uniquement quand c'est stable
