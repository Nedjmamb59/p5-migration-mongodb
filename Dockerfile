# Image du service de migration (script Python + tests)
FROM python:3.13-slim

# Messages affichés tout de suite dans les logs, pas de fichiers .pyc
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Les dépendances d'abord : Docker garde cette étape en mémoire (cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Notre code et nos tests (le CSV arrivera par un volume)
COPY app/ ./app/
COPY tests/ ./tests/

# Un utilisateur sans privilèges, par sécurité
RUN useradd --create-home --uid 1000 migrator \
    && mkdir -p /app/exports && chown -R migrator:migrator /app
USER migrator

# Au démarrage : la migration, puis les tests
CMD ["sh", "-c", "python -m app.migrate && python -m pytest -v"]