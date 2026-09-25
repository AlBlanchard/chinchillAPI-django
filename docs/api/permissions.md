# Permissions et contexte des ressources

Sources : `projects/permissions.py`, `projects/mixins.py`, `projects/views.py`
et `contact/views.py`.

| Opération | Anonyme | Authentifié non-staff | Staff authentifié |
| --- | --- | --- | --- |
| POST Contact | Autorisé | Autorisé | Autorisé |
| Lecture Project / page / bloc | Publié uniquement | Publié uniquement | Tout |
| Écriture Project / page / bloc | 401 | 403 | Autorisée |
| Collection globale et détail Image | 401 | 403 | Autorisés |
| Lecture collection d'images contextuelle | Selon propriétaire publié | Selon propriétaire publié | Tout |
| Upload contextuel, attach ou retrait d'image | 401 | 403 | Autorisé |
| GET / HEAD fichier Image | Association publique requise | Association publique requise | Y compris privé / sans propriétaire |

Cette matrice suppose des credentials absents ou valides. Des credentials
invalides peuvent provoquer un 401 avant la permission. Une opération
autorisée reste soumise à la validation et à l'existence des ressources.

`IsAdminOrReadOnly` laisse passer les méthodes sûres GET, HEAD et OPTIONS.
Pour les autres méthodes, il exige un utilisateur authentifié staff.
`ImageViewSet` global utilise `IsAdminUser`, y compris pour lire ses métadonnées.
`ContactAPIView` utilise `AllowAny`. Les routes de schéma et Swagger ne
déclarent pas de restriction staff dans la configuration actuelle.

## Permissions puis visibilité

La permission d'effectuer une lecture ne suffit pas à rendre un brouillon
visible : les QuerySets sont filtrés selon le rôle. Une ressource masquée
renvoie 404 en détail ; sa collection ne la contient pas. Les listes
contextuelles d'un propriétaire absent ou invisible renvoient `[]`.

Les pages sont filtrées par slug du projet ; les Paragraph et Highlight par
projet et page. L'UUID d'un contenu d'une autre page renvoie donc 404 sous
un contexte incorrect, même pour le staff. La création déduit son parent
de l'URL et vérifie son existence.

Les fichiers Image appliquent leur propre règle « au moins un propriétaire
public ». Un fichier public ne rend pas l'endpoint global de métadonnées public.
Le détail des règles figure dans [publication](../apps/projects/publication.md).

Il n'existe pas de propriété par utilisateur, de groupe d'éditeurs ou de
permission par projet dans ce code : le staff a accès à l'ensemble des
ressources métier.
