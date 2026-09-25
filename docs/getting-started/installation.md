# Installation et lancement

## Prérequis

Le Dockerfile et la CI utilisent **Python 3.13** ; Compose utilise **PostgreSQL 17**.
Les versions Python des dépendances sont fixées dans `requirements.txt`.
Prévoir une base PostgreSQL locale accessible pour une exécution hors Docker.
Le projet n'a pas de configuration SQLite de remplacement.

Depuis la racine du dépôt, dans PowerShell :

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Sous un shell POSIX, les équivalents sont `python3.13 -m venv .venv`,
`. .venv/bin/activate` et `cp .env.example .env`.
Ne pas écraser un `.env` déjà configuré.

## Adapter l'environnement

Compléter les [variables](configuration.md), notamment `DJANGO_SECRET_KEY` et
les identifiants PostgreSQL. Pour une base locale, remplacer `POSTGRES_HOST=db`
par `127.0.0.1` et utiliser le port de cette base. Le service PostgreSQL du Compose
fourni n'expose pas son port à l'hôte.

L'exemple `.env` vise le conteneur : hors Docker, remplacer `MEDIA_ROOT=/app/media`
et `STATIC_ROOT=/app/staticfiles` par des chemins locaux accessibles en écriture,
ou retirer ces lignes pour utiliser les répertoires `media/` et `staticfiles/`
du dépôt. Définir les variables email même si Contact n'est pas utilisé ;
l'envoi effectif demande un SMTP fonctionnel.

```console
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

L'API écoute alors sur `http://127.0.0.1:8000`. Le superutilisateur permet
d'obtenir un JWT staff. L'admin Django utilise des cookies sécurisés : sa
connexion nécessite un contexte HTTPS compatible avec cette configuration.
Le dépôt n'enregistre pas encore les modèles Projects dans `projects/admin.py`.

## Première vérification

Ouvrir [Swagger local](http://127.0.0.1:8000/api/docs/) ou interroger
`GET /api/projects/`. Une base vide renvoie une liste vide.
`GET /api/contact/` renvoie normalement **405** : Contact accepte les POST.
Les migrations préparent la base ; elles ne créent ni compte ni données métier.

Pour une exécution conteneurisée, suivre [Docker](../deployment/docker.md) :
le Compose fourni utilise des chemins de production Linux, pas un montage
de développement portable.
