# Image de la démonstration en ligne (docker-compose.dokploy.yml), construite depuis la racine du
# dépôt (contexte limité par simulation/Dockerfile.dockerignore). Elle sert deux services :
# l'Hopitalia simulé, et le remplissage de la base avec le jeu de démonstration, qui réutilise les
# étapes des tests automatisés. Jamais en production face à un vrai Hopitalia.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /depot

# Dépendances d'abord : une modification du code ne les réinstalle pas.
COPY backend/pyproject.toml backend/pyproject.toml
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('backend/pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/dependances.txt \
    && pip install -r /tmp/dependances.txt pytest \
    && rm /tmp/dependances.txt

COPY backend/src backend/src
RUN pip install --no-deps ./backend

# Étapes des tests réutilisées par la répétition, nomenclature de référence, scripts.
COPY backend/tests backend/tests
COPY docs/cadrage/nomenclature-budgetaire.csv docs/cadrage/nomenclature-budgetaire.csv
COPY simulation simulation
RUN mkdir -p docs/recette && useradd --system app && chown -R app docs/recette
USER app

EXPOSE 8090
CMD ["uvicorn", "--app-dir", "simulation", "hopitalia_simule:app", "--host", "0.0.0.0", "--port", "8090"]
