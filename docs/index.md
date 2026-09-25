# ChinchillAPI

ChinchillAPI est une API Django REST Framework composée de deux applications :
**Contact**, pour recevoir un formulaire et envoyer un email, et **Projects**, pour
gérer un portfolio, ses pages, ses contenus et ses images réutilisables.

Cette documentation explique l'architecture et les comportements du dépôt.
Le schéma `/api/schema/` et Swagger `/api/docs/` constituent la référence HTTP
de l'instance exécutée. Les exemples ci-dessous utilisent une instance locale.

Commencer par l'[installation](getting-started/installation.md), puis lire
l'[architecture](architecture/overview.md). Pour intégrer un frontend, consulter
les [parcours API](api/overview.md) et les [permissions](api/permissions.md).

```{toctree}
:caption: Démarrer
:maxdepth: 2

getting-started/installation
getting-started/configuration
getting-started/development
```

```{toctree}
:caption: Architecture
:maxdepth: 2

architecture/overview
architecture/database
architecture/media
```

```{toctree}
:caption: Applications
:maxdepth: 2

apps/contact/overview
apps/contact/email-flow
apps/projects/overview
apps/projects/data-model
apps/projects/nested-writes
apps/projects/publication
apps/projects/images
```

```{toctree}
:caption: API
:maxdepth: 2

api/overview
api/authentication
api/permissions
```

```{toctree}
:caption: Exploitation et choix actuels
:maxdepth: 2

deployment/docker
deployment/ci-cd
deployment/storage
deployment/production
decisions/design
```
