# Image de l'API et de ses tâches planifiées (alertes, courriels, intégrations), construite depuis
# backend/ (contexte limité par backend/.dockerignore).
FROM python:3.12-slim

# Journaux écrits aussitôt (docker compose logs), pas de fichiers .pyc dans l'image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances d'abord, lues dans pyproject.toml : une modification du code ne les réinstalle pas.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" > /tmp/dependances.txt \
    && pip install -r /tmp/dependances.txt \
    && rm /tmp/dependances.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN pip install --no-deps . \
    && useradd --system app \
    && mkdir -p /app/pieces \
    && chown app /app/pieces
USER app

EXPOSE 8000
# Les migrations s'appliquent au démarrage : la base suit toujours la version du code.
CMD ["sh", "-c", "alembic upgrade head && uvicorn hopitalia_budget.main:app --host 0.0.0.0 --port 8000"]
