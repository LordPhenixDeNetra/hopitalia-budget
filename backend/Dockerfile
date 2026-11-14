FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml alembic.ini ./
COPY src ./src
COPY migrations ./migrations
RUN pip install --no-cache-dir . && useradd --system app && mkdir -p /app/pieces && chown app /app/pieces
USER app
EXPOSE 8000
# Les migrations s'appliquent au démarrage : la base suit toujours la version du code.
CMD ["sh", "-c", "alembic upgrade head && uvicorn hopitalia_budget.main:app --host 0.0.0.0 --port 8000"]
