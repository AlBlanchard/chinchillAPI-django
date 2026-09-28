FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app \
        --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=root:app . .

# Ces droits concernent l'image seule ; un bind mount conserve les droits de l'hôte.
RUN install -d -o app -g app -m 0750 /app/media /app/staticfiles

# Les fichiers statiques font partie de l'image déployée.
# Ces variables factices permettent uniquement à Django de charger les settings
# pendant le build ; aucune connexion PostgreSQL/SMTP n'est effectuée.
RUN DJANGO_SECRET_KEY=collectstatic-only \
    POSTGRES_DB=unused \
    POSTGRES_USER=unused \
    POSTGRES_PASSWORD=unused \
    POSTGRES_HOST=unused \
    EMAIL_HOST=unused \
    EMAIL_HOST_USER=unused \
    EMAIL_HOST_PASSWORD=unused \
    DEFAULT_FROM_EMAIL=unused@example.invalid \
    CONTACT_EMAIL=unused@example.invalid \
    python manage.py collectstatic --noinput

EXPOSE 8000

USER app

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30"]
