# ChinchillAPI

[![Documentation](https://img.shields.io/badge/docs-Read%20the%20Docs-blue)](https://chinchillapi-django.readthedocs.io/fr/latest/)

API Django REST Framework composée de deux applications : **Contact**, pour
recevoir les formulaires et envoyer des emails, et **Projects**, pour gérer
un portfolio, ses pages, contenus et images partagées.

> 📚 **[Consulter la documentation complète](https://chinchillapi-django.readthedocs.io/fr/latest/)**

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

## Documentation

📚 **[Consulter la documentation technique complète sur Read the Docs](https://chinchillapi-django.readthedocs.io/fr/latest/)**

Elle couvre notamment l'architecture de ChinchillAPI, les applications
Contact et Projects, l'authentification, les permissions, la publication,
la gestion des médias ainsi que le déploiement.

La documentation est construite avec **Sphinx**, **MyST** et **Mermaid** et
publiée sur **Read the Docs**.

### Construire la documentation localement

```console
python -m pip install -r docs/requirements.txt
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Ouvrir ensuite `docs/_build/html/index.html`.

Voir également le [guide de maintenance](docs/getting-started/development.md).