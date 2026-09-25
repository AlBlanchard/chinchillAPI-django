# Projects : portfolio et contenu éditorial

Projects gère les projets, leurs pages et leurs contenus ordonnés, ainsi que
les références de classification et les images. Il constitue une application
de ChinchillAPI, aux côtés de Contact.

## Parcours de gestion

1. Obtenir un [JWT staff](../../api/authentication.md).
2. Créer un Project, éventuellement avec ses pages, paragraphes et highlights
   dans le même POST. Les projets et pages sont brouillons par défaut.
3. Compléter ou modifier les contenus par leurs endpoints contextuels.
4. Téléverser des images puis, si nécessaire, partager une image existante
   avec une page via `images/attach/`.
5. Publier le projet et les pages voulues. Les visiteurs ne voient que les
   ressources dont la chaîne de publication est satisfaite.

Les [écritures imbriquées](nested-writes.md) détaillent les limites du POST
initial et des PATCH. Les [routes](../../api/overview.md) donnent les points
d'entrée sans reproduire tout le schéma OpenAPI.

## Organisation du code

`models.py` porte les relations ; `serializers.py` valide et représente les
données. `views.py` orchestre les écritures, les associations et la lecture
des fichiers. `mixins.py` partage les filtres de publication et le contexte
des enfants de page. `permissions.py` distingue lecture et écriture staff.

Category, Skill et Technology sont des modèles distincts. Ils sont résolus
par **nom** lors des écritures Project ; il n'existe actuellement aucune route
CRUD dédiée à ces trois modèles, malgré la présence de leurs serializers.
Les modèles ne sont pas enregistrés dans l'admin Django du dépôt.

Il n'y a ni pagination DRF configurée, ni filtre de recherche déclaré, ni
gestion de rôles éditoriaux supplémentaire. Le champ `mermaid` d'une page
stocke du texte ; l'API ne le compile pas et ne valide pas sa syntaxe.
Le rendu frontend et sa politique de sécurité sont hors de ce dépôt.
