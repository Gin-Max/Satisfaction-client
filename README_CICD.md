# CI/CD du projet Satisfaction Client

## Workflows
- `ci.yml` : lint, tests, validation des imports, build Docker
- `docker-publish.yml` : publication des images API et scraping sur GHCR
- `deploy-staging.yml` : déploiement automatique de l'environnement staging depuis `develop`

## Emplacement des workflows
Place les fichiers dans `.github/workflows/` pour que GitHub Actions les détecte.

## Secrets GitHub à créer
- `STAGING_HOST`
- `STAGING_USER`
- `STAGING_SSH_KEY`
- `STAGING_APP_DIR`

## Remarques
- Le projet a été ajusté au minimum pour fiabiliser les imports Python, les DAGs Airflow et la CI.
- Le code métier a été gardé autant que possible, avec seulement les corrections nécessaires au bon fonctionnement CI/CD.
