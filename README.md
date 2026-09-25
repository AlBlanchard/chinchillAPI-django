# ChinchillAPI

API Django REST Framework composée de deux applications : **Contact**, pour
recevoir les formulaires et envoyer des emails, et **Projects**, pour gérer
un portfolio, ses pages, contenus et images partagées.

Stack : Python 3.13 (Docker/CI), Django 5.2, DRF, PostgreSQL 17, SimpleJWT,
drf-spectacular, Gunicorn et Docker Compose.

## Démarrage rapide

Avec Python 3.13 et une base PostgreSQL de développement accessible :

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Compléter `.env` : secrets, PostgreSQL et paramètres SMTP. Hors Docker, utiliser
l'adresse réelle de PostgreSQL à la place de `db` et adapter les chemins
`MEDIA_ROOT` / `STATIC_ROOT`. Ne pas écraser un `.env` existant.

```console
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

[Installation détaillée](docs/getting-started/installation.md) ·
[Configuration](docs/getting-started/configuration.md) ·
[Docker et production](docs/deployment/docker.md)

## Tests et contrat HTTP

```console
python -m pytest
```

Les tests utilisent PostgreSQL avec un rôle pouvant créer la base de test.
Le seuil de couverture Projects est de 80 %.

- [Swagger local](http://127.0.0.1:8000/api/docs/)
- [OpenAPI local](http://127.0.0.1:8000/api/schema/)
- [JWT et permissions](docs/api/authentication.md)

## Documentation complète

La [documentation technique](docs/index.md) couvre l'architecture, Contact,
Projects, la publication, les médias, l'API et le déploiement.
Elle est écrite en français avec Sphinx, MyST et Mermaid.

```console
python -m pip install -r docs/requirements.txt
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Ouvrir `docs/_build/html/index.html`. Read the Docs est configuré dans
`.readthedocs.yaml` ; **URL publique à renseigner après création du projet
Read the Docs**. Voir le [guide de maintenance](docs/getting-started/development.md).
