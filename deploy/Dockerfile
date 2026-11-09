# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Immagine di produzione (gunicorn, utente non privilegiato)
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

# Debian 13: il suo client PostgreSQL (17) è quello del servizio db (pg_dump per i backup)
FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    STATIC_ROOT=/app/var/static \
    MEDIA_ROOT=/data/media \
    BACKUP_ROOT=/data/backup

# librerie di sistema per WeasyPrint (PDF) e client PostgreSQL per backup e ripristino
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    shared-mime-info fonts-dejavu-core fonts-liberation2 postgresql-client \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db python manage.py collectstatic --noinput \
 && chmod -R a+rX /app/var \
 && useradd --system --uid 1000 --home /app gestione \
 && mkdir -p /data/media /data/backup && chown -R gestione:gestione /data && chmod 700 /data/backup

USER gestione
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/salute/').status==200 else 1)"
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
# senza socket di controllo: gunicorn lo creerebbe nella home, non scrivibile
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "300", "--no-control-socket", "--access-logfile", "-"]
