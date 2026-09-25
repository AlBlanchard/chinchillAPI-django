# Conteneurs Docker

Sources : `Dockerfile`, `.dockerignore` et `compose.yaml`.

## API et PostgreSQL

| Service | Configuration actuelle |
| --- | --- |
| `api` | Image construite depuis `python:3.13-slim`, conteneur `chinchillapi` |
| Processus | Gunicorn `config.wsgi:application`, 2 workers, timeout 30 s, écoute `0.0.0.0:8000` |
| Port hôte | `127.0.0.1:8001:8000`, accessible sur la boucle locale du serveur |
| Environnement | `.env` via `env_file` |
| Média | Bind mount `/srv/media/chinchillapi:/app/media` |
| `db` | `postgres:17`, conteneur `chinchillapi_db`, sans port publié |
| Données SQL | Volume nommé `postgres_data` vers `/var/lib/postgresql/data` |
| Redémarrage | `unless-stopped` sur les deux services |

L'API dépend de l'état `service_healthy` de PostgreSQL. Le healthcheck SQL lance
`pg_isready` avec le rôle et la base configurés, toutes les 10 secondes, avec
timeout 5 secondes et 5 tentatives. Compose ne déclare pas de healthcheck API.
Le contrôle HTTP de déploiement est effectué par le workflow séparément.

## Utilisateur et droits

Le Dockerfile crée l'utilisateur système `app`, UID/GID **10001**, sans shell
interactif ni répertoire personnel. Le code appartient à `root:app`. Les
répertoires `/app/media` et `/app/staticfiles` de l'image appartiennent à `app`
avec le mode 0750, puis le processus s'exécute avec `USER app`.

Un bind mount conserve les droits de l'hôte et masque ceux du répertoire de
l'image. Préparer le répertoire média sur le serveur avec des droits compatibles
avec UID/GID 10001. Voir [stockage](storage.md) avant de déplacer des fichiers
déjà existants.

`.dockerignore` exclut notamment `.env`, `.git`, `.venv`, les caches de tests,
les médias et les statiques. Les secrets et uploads sont fournis au runtime,
pas copiés dans l'image. Le Dockerfile installe `requirements.txt`, sans les
dépendances spécifiques de documentation.

## Exécution manuelle sur un hôte préparé

Depuis le répertoire contenant `compose.yaml` et le `.env` de cet environnement :

```sh
docker compose build
docker compose up -d db
# Attendre que docker compose ps indique db healthy.
docker compose run --rm --no-deps -T api python manage.py migrate --noinput </dev/null
docker compose up -d --force-recreate api
docker compose ps
```

La redirection et `-T` correspondent à la procédure non interactive actuelle.
Les migrations sont une étape explicite, pas une action automatique du CMD.
Le Compose fourni est destiné à l'hôte Linux de production : adapter les chemins
pour un environnement local distinct, sans réutiliser les données de production.
