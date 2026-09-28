# Interface interne Projects

L'interface **`/manage/projects/`** permet de créer, modifier et administrer les projets
sans Postman. Elle utilise les templates Django, un style SCSS mobile first et
un petit script natif pour copier les UUID et les slugs. Elle ne remplace pas Django Admin.

## Connexion et accès

Se connecter avec un compte Django actif ayant `is_staff=True`. Une visite
anonyme redirige vers `/admin/login/?next=/manage/projects/` ; un utilisateur
connecté non-staff reçoit un refus 403. Le formulaire utilise la session Django
et une protection CSRF. Aucun JWT ni secret n'est transmis dans la page.

La configuration actuelle impose des cookies de session et CSRF sécurisés :
utiliser HTTPS, notamment pour un environnement de préproduction. Pour un
serveur local HTTP, les éventuelles dérogations de cookies doivent rester dans
une configuration locale distincte, jamais dans les paramètres de production.

## Créer un projet

1. Coller dans le grand champ JSON le payload habituel de `POST /api/projects/`.
2. Inclure si nécessaire les relations nommées, pages, paragraphes et highlights.
3. Ajouter éventuellement un fichier image, son texte alternatif `alt` et son
   `theme` (vide pour l'image générique).
4. Cliquer sur **Créer le projet**.

Un [exemple complet](nested-writes.md) décrit les écritures imbriquées.
Le serializer API reste la référence : aucun champ `image_id` n'est ajouté au
contrat Project. Le fichier facultatif est associé au Project, pas à une page.
La validation utilise `ImageSerializer` : fichier image valide, maximum 10 Mio,
`alt` obligatoire et thème libre de 50 caractères maximum.

Les erreurs indiquent les champs et indices concernés, par exemple
`project.pages[0].paragraphs[0].content`. Le JSON, le texte alternatif et le thème
restent dans le formulaire. Pour des raisons propres aux navigateurs, le fichier
doit être sélectionné de nouveau après une erreur. Le succès affiche le titre
et le slug, puis redirige vers un formulaire vide pour éviter une nouvelle
soumission lors d'un rafraîchissement.

## Bibliothèque et miniatures privées

La bibliothèque affiche 24 images par page, les plus récentes en premier :
miniature, UUID complet sélectionnable, texte alternatif, thème et bouton
**Copier l'UUID**. Un message confirme la copie. Si le presse-papiers est
indisponible, l'UUID est sélectionné pour une copie manuelle.

Les miniatures passent par la route contrôlée
`/manage/projects/images/<uuid>/file/`, réservée aux sessions staff et sans cache.
Elle partage l'ouverture du fichier dans le stockage avec l'API. Aucun chemin
`/media/` n'est construit. L'API `/api/images/<uuid>/file/` conserve son contrôle
de publication et son authentification JWT ; les images privées restent privées.
Les images sont affichées à taille réduite, mais le fichier original est transmis.

## Architecture et fichiers

`projects/manage_views.py` orchestre le formulaire et la bibliothèque.
`ProjectSerializer` et `ImageSerializer` assurent la validation commune.
`projects/services.py` contient la création Project imbriquée, appelée par
`ProjectViewSet` et l'interface, et l'upload associé au projet, également partagé.
Les templates et ressources se trouvent dans `projects/templates/projects/`
et `projects/static/projects/`. Les fichiers CSS et JS sont collectés par
`collectstatic` comme les ressources Django habituelles.

Les deux entrées sont validées avant toute écriture. La création imbriquée est
exécutée avant l'upload dans une transaction. L'instance Image est conservée avant
sa sauvegarde pour pouvoir supprimer le fichier même si l'INSERT échoue après
son écriture. Une erreur d'association ou de commit déclenche aussi une
compensation du stockage. Cette protection ne rend pas le stockage transactionnel :
un arrêt brutal du processus ou une panne empêchant la suppression peut encore
nécessiter un nettoyage opérationnel. Le service d'orchestration doit rester le
propriétaire de sa transaction (pas de transaction extérieure qui serait annulée
après son retour).

## Modifier les styles

Le CSS compilé est versionné : aucun compilateur n'est nécessaire en production.
Pour modifier le SCSS et régénérer le CSS :

```console
python -m pip install -r requirements-dev.txt
python scripts/build_styles.py
```

Le compilateur Python LibSass est une dépendance de développement uniquement.
La feuille reste simple, avec deux points de rupture et sans framework frontend.

## Modifier un Project ou une Page

Ouvrir **Modifier une ressource**, choisir le type et saisir le `project_slug`.
Pour une Page, saisir également son `page_slug` ; elle doit appartenir au projet
indiqué. Coller uniquement les champs à modifier, par exemple :

```json
{"description": "Nouvelle description", "published": true}
```

Pour une Page :

```json
{"title": "Nouveau titre", "subtitle": "Sous-titre", "published": true}
```

Le formulaire envoie un POST avec CSRF à la vue HTML. Celle-ci utilise les
serializers API en `partial=True` et le service partagé `update_project` pour
les relations nommées. Un champ absent conserve sa valeur ; une liste vide
vide volontairement la relation correspondante. Un changement de slug est
possible : le nouveau slug apparaît dans le message de succès et le navigateur.

Le PATCH Project refuse toujours `pages`. Le PATCH Page refuse toujours
`paragraphs` et `highlights` ; les contraintes de slug, de layout, de dates et
de publication restent celles de l'API. Les erreurs conservent le JSON et la
cible dans le formulaire, qui reste ouvert. Une ressource absente ou une page
hors du projet indiqué donne une erreur 404 explicite.

## Navigateur Projects / Pages

La section **Projects / Pages** inclut aussi les brouillons. Chaque projet
présente son titre et son slug ; ouvrir sa liste de pages pour voir leurs titres
et slugs, classés par `position`. Les boutons **Copier le slug** utilisent le même
mécanisme de presse-papiers que les UUID, avec sélection manuelle en secours.
Les champs Project proposent les slugs existants via une liste de suggestions.

## Ajouter une image à une ressource existante

Dans **Ajouter une image à un projet existant**, saisir le Project slug et,
facultativement, le Page slug. Une page renseignée devient la destination ;
son appartenance au projet est vérifiée.

Choisir exactement une source :

- **UUID existant** : format UUID validé, Image existante obligatoire. Réassocier
  la même image au même propriétaire est idempotent.
- **Upload** : fichier, texte alternatif obligatoire et thème facultatif.
  Le même `ImageSerializer` valide l'image ; le service partagé écrit puis
  associe le fichier, avec compensation en cas d'échec.

Un UUID et un fichier simultanés, ou aucune source, donnent une erreur. Un
propriétaire ne peut pas recevoir deux images différentes de même thème, y
compris pour le thème vide. Les services verrouillent le propriétaire pour
sérialiser leurs ajouts et l'Image existante pendant une association.
La navigation interne donne accès aux slugs et à la bibliothèque.

## Supprimer une image

La croix de chaque carte ouvre une **page de confirmation** avec le texte
alternatif et l'UUID. Cette consultation GET ne supprime rien. Seul le bouton
**Confirmer la suppression définitive** envoie le POST protégé par CSRF.
Un POST sans confirmation explicite est refusé.

La suppression interne globale est limitée aux images **sans aucune association**.
Une image utilisée est conservée ; ses projets et pages sont affichés et le
bouton de confirmation n'est pas proposé. Les associations sont de nouveau
vérifiées côté serveur au POST, même si elles ont changé depuis la confirmation.
Il faut d'abord retirer les associations via les endpoints contextuels existants.
Attention : le retrait de la dernière association via ces endpoints supprime
déjà l'objet et son fichier, selon leur comportement historique.

Pour une image inutilisée, la ligne est supprimée en transaction et le fichier
est effacé **après commit**. Un fichier déjà absent ne bloque pas l'opération.
Un rollback ne déclenche pas la suppression physique. Si le stockage refuse
l'effacement après commit, un message indique que l'objet a été supprimé mais
qu'un nettoyage du stockage reste nécessaire ; l'erreur est journalisée.
Un arrêt brutal entre commit et effacement reste une limite sans tâche durable
de nettoyage.

Cette politique protectrice est propre au service interne `delete_unused_image`.
Le contrat historique de `DELETE /api/images/<uuid>/` reste inchangé : il retire
l'objet et ses associations sans nettoyage physique personnalisé. L'interface
ne l'appelle pas. Aucun endpoint public supplémentaire n'est créé.

## Supprimer un Project

La croix du navigateur ouvre une confirmation affichant le titre du projet.
Le POST confirmé appelle le même service de suppression que l'API : les pages,
paragraphes et highlights disparaissent par CASCADE. Les liens M2M sont retirés,
mais **tous les objets Image et leurs fichiers sont conservés**, partagés ou non.
Les images devenues inutilisées peuvent ensuite être supprimées explicitement
depuis la bibliothèque. Les catégories, compétences et technologies restent aussi
conservées.

## Routes et organisation

Toutes les routes sont sous `/manage/projects/`, réservées aux sessions staff
actives. Les opérations réussies utilisent POST/Redirect/GET ; les erreurs
réaffichent les champs concernés. Aucun appel HTTP de Django vers sa propre API.

| Route relative | Méthodes | Fonction |
| --- | --- | --- |
| `/` | GET, POST | Tableau de travail et création Project |
| `patch/` | POST | PATCH Project ou Page |
| `images/add/` | POST | Association UUID ou upload Project/Page |
| `<uuid>/delete/` | GET, POST | Confirmation puis suppression Project |
| `images/<uuid>/delete/` | GET, POST | Confirmation puis suppression Image inutilisée |
| `images/<uuid>/file/` | GET | Miniature privée |

Les nouveaux champs de ciblage sont validés par `projects/manage_forms.py`.
La logique métier reste dans les serializers et `projects/services.py` :
création, mise à jour Project, upload Project/Page, association idempotente,
retrait contextuel, suppression Project et suppression interne Image protégée.
`ProjectPageSerializer.save()` reste le chemin de mise à jour Page partagé avec
DRF. Les templates héritent de `manage_base.html`, avec une confirmation séparée.
Les sections de formulaires sont repliables pour limiter la longueur de la page.

## Limites actuelles

Pas de PATCH récursif, de création de Page indépendante depuis l'interface,
de modification de paragraphes/highlights, de recherche d'images, d'upload sans
destination ni de formulaire de retrait d'association. Les endpoints existants
restent disponibles pour ces opérations. Le navigateur de projets affiche toute
la liste ; seule la bibliothèque d'images est paginée. Les miniatures transmettent
les fichiers originaux. Aucun changement de modèle ni migration n'est requis.
Django Admin et Contact restent inchangés.
