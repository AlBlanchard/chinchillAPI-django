# Parcours et points d'entrée API

Sources : `config/urls.py` et `projects/urls.py`. Les chemins se terminent par
`/`. Swagger est disponible sous `/api/docs/` et le schéma OpenAPI sous
`/api/schema/`. Utiliser ces outils pour les champs et réponses détaillés ;
les pages présentes expliquent les comportements transversaux.

## Routes métier

Dans ce tableau, `P` est `/api/projects/<project_slug>` et `G` est
`P/pages/<page_slug>`. « CRUD » signifie GET/POST sur la collection et
GET/PUT/PATCH/DELETE sur le détail ; les règles de permissions restent applicables.

| Chemin | Méthodes / identification | Usage |
| --- | --- | --- |
| `/api/contact/` | POST | Envoyer un formulaire |
| `/api/projects/` | CRUD, détail `<slug>/` | Projet et représentation imbriquée |
| `P/pages/` | CRUD, détail `<slug>/` | Pages du projet |
| `G/paragraphs/` | CRUD, détail `<uuid>/` | Blocs de texte |
| `G/highlights/` | CRUD, détail `<uuid>/` | Éléments courts |
| `/api/images/` | CRUD, détail `<uuid>/`, staff uniquement | Images globales |
| `P/images/` | GET, POST | Lister / téléverser dans le projet |
| `P/images/<uuid>/` | DELETE seulement | Retirer l'association au projet |
| `G/images/` | GET, POST | Lister / téléverser dans la page |
| `G/images/<uuid>/` | DELETE seulement | Retirer l'association à la page |
| `G/images/attach/` | POST | Associer une Image existante |
| `/api/images/<uuid>/file/` | GET, HEAD | Lire le fichier après contrôle d'accès |

Les pages et blocs n'ont pas de collection racine indépendante. Les parents
sont fixés par l'URL, et non par un champ JSON. Category, Skill et Technology
n'ont pas d'endpoint dédié ; ils sont gérés par les relations nommées Project.
Le router expose aussi sa racine `/api/`.

## Choisir le bon parcours

Pour créer un ensemble éditorial, commencer par le
[POST Project imbriqué](../apps/projects/nested-writes.md). Pour l'éditer,
utiliser un PATCH par ressource et respecter la distinction champ absent /
liste vide. Pour les fichiers, utiliser les routes multipart ou
[l'association d'une image existante](../apps/projects/images.md).

Les collections ne sont pas paginées par la configuration actuelle.
La lecture des brouillons dépend du rôle et de la chaîne de publication ;
une réponse vide n'indique donc pas nécessairement une base vide.

## Contrat généré et limites

Le schéma est généré par drf-spectacular à partir des contrôleurs et serializers.
La route fichier a une annotation explicite des réponses 200 et 404.
L'action `attach`, en revanche, lit `image_id` manuellement sans serializer
d'entrée dédié : son schéma généré peut ne pas décrire fidèlement ce champ.
Le contrat vérifié de cette action est explicité dans la page Images.
Ne pas déduire les écritures imbriquées autorisées de la seule forme des
représentations de lecture.
