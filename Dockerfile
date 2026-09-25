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

EXPOSE 8000

USER app

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "30"]
