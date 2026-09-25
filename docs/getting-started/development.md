# Développement, tests et documentation

## Vérifier l'application

Après l'[installation](installation.md), utiliser une base de développement
PostgreSQL et un rôle autorisé à créer la base de test : pytest-django prépare
une base distincte, puis la détruit en fin d'exécution. Ne pas pointer les tests
sur l'environnement de production.

```console
python manage.py check
python -m pytest
```

`pytest.ini` sélectionne `config.settings`, collecte `tests.py`, `test_*.py` et
`*_tests.py`, mesure la couverture de `projects` et exige au moins **80 %**.
La CI exécute cette même commande avec PostgreSQL 17.

| Fichier | Comportements protégés |
| --- | --- |
| `projects/tests/test_projects.py` | CRUD, relations nommées, création imbriquée, upload et suppression d'associations |
| `test_validation.py` | Slugs, collisions, dates, écritures imbriquées refusées, limite de taille |
| `test_permissions.py` | Lecture publique et écritures staff |
| `test_publication.py` | Brouillons, isolation par propriétaire, représentations imbriquées, nombre de requêtes ORM |
| `test_jwt_auth.py` | Obtention, refresh, écriture avec JWT, refus non-staff |
| `test_media.py` | URL contrôlée, visibilité, fichiers absents, HEAD, cache, négociation de contenu |

Les tests qui écrivent des médias utilisent des répertoires temporaires.
`contact/tests.py` est un squelette sans test effectif. L'action `images/attach/`
n'a pas non plus de test dédié dans la suite actuelle ; les tests d'images
partagées vérifient d'autres parcours. La couverture Projects ne prouve donc
pas la validation du SMTP ni de chaque action HTTP.

## Construire la documentation

La documentation n'importe pas Django : ni PostgreSQL ni `.env` ni SMTP ne sont
nécessaires pour la compiler. Ses dépendances sont séparées du runtime API.

```console
python -m pip install -r docs/requirements.txt
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

Ouvrir `docs/_build/html/index.html`. Pour servir la sortie localement :

```console
python -m http.server 8080 --directory docs/_build/html
```

Les pages sont écrites en Markdown MyST. Ajouter chaque nouvelle page à un
`toctree` de `docs/index.md`. Les blocs clôturés `mermaid` sont convertis en
directives par `myst_fence_as_directive`. Le HTML charge Mermaid côté navigateur
depuis le CDN de l'extension, avec une version fixée dans `docs/conf.py`.
Un build Sphinx réussi vérifie la structure et les liens documentaires, mais
ne garantit pas à lui seul le rendu JavaScript des diagrammes : les ouvrir
dans un navigateur avec accès au CDN.

## Maintenir et publier

Toute modification de contrat doit être rapprochée des URLs, serializers,
contrôleurs, permissions et tests correspondants. Les pages indiquent leurs
sources de code ; les anciens README servent seulement de points d'entrée.
Ne pas transformer une piste d'évolution en fonctionnalité présente.

`.readthedocs.yaml` utilise Python 3.13, `docs/conf.py` et les dépendances dédiées,
avec les avertissements traités comme erreurs. La CI documentaire séparée
construit également le HTML pour les pull requests et les push sur `main`.

Il reste à importer le dépôt dans Read the Docs, autoriser son accès, activer
les versions souhaitées et vérifier un premier build hébergé. L'URL publique
ne peut être renseignée qu'après création du projet. La configuration du dépôt
ne crée pas à elle seule ce projet distant.

Références de configuration : [Read the Docs v2](https://docs.readthedocs.com/platform/stable/config-file/v2.html),
[Sphinx build](https://www.sphinx-doc.org/en/master/man/sphinx-build.html) et
[extension Mermaid](https://sphinxcontrib-mermaid-demo.readthedocs.io/en/latest/).
