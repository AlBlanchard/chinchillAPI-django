# Persistance et intégrité

Source : `config/settings.py`, `projects/models.py` et
`projects/migrations/0001_initial.py`.

Le backend est `django.db.backends.postgresql`. Les migrations Django créent les
tables métier et les tables des applications intégrées. Les huit modèles
Projects ont une clé primaire `UUIDField(default=uuid.uuid4, editable=False)`.
Les tables Django intégrées conservent leurs propres conventions.

## Contraintes et relations

Les noms et slugs de Category, Skill et Technology sont uniques séparément.
Le slug Project est unique globalement. La contrainte
`unique_page_slug_per_project` impose l'unicité du couple `(project, slug)`.
Les tables ManyToMany relient les projets aux compétences, technologies et
images, ainsi que les pages aux images ; il n'y a pas de modèle intermédiaire
métier avec ordre ou thème propre à une association.

Supprimer une catégorie met `Project.category` à `NULL`. Supprimer un projet
supprime ses pages, puis les Paragraph et Highlight par cascade. Une suppression
de propriétaire retire ses liens ManyToMany, sans supprimer automatiquement
l'objet Image ni son fichier. Voir le [cycle de vie des images](../apps/projects/images.md).

Les contrôles de dates, de collision de slug issu d'un nom, de taille d'image
et de thème lors de certains parcours appartiennent au code API. Ils ne doivent
pas être présentés comme des contraintes SQL universelles.

## Transactions et fichiers

`ProjectViewSet.perform_create` et `perform_update` sont décorés par
`transaction.atomic`. L'opération sur Project et ses relations est validée
ensemble ou annulée en cas d'erreur de base. Les validations du serializer
précèdent cette orchestration ; elles ne constituent pas un verrou concurrent.

Les octets d'une image sont dans le storage, la base ne conservant que le chemin
relatif (par exemple `projects/photo.png`) et les métadonnées. Une transaction
PostgreSQL ne peut pas annuler automatiquement une écriture ou une suppression
physique de fichier. Le code n'installe pas de transaction distribuée entre ces
deux stockages ni de service général de collecte des orphelins.

Pour les cardinalités et champs fonctionnels, consulter le
[modèle Projects](../apps/projects/data-model.md). Pour sauvegarder l'ensemble,
voir le [stockage de production](../deployment/storage.md).
