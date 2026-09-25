# Choix actuels et conséquences

Ces explications décrivent le code présent. Elles ne constituent pas des ADR
historiques et n'attribuent pas aux auteurs des motivations non documentées.

## UUID et slugs

Les huit modèles Projects utilisent des UUID générés par `uuid.uuid4` comme
identifiants techniques. Les slugs Project et ProjectPage fournissent des
identifiants lisibles pour les URL ; le slug de page est contextualisé par le
projet. Les images et blocs utilisent leurs UUID dans les routes.

Conséquence : l'identité technique est distincte du libellé ou du chemin humain.
Changer un slug modifie l'URL correspondante ; aucune redirection automatique
n'est implémentée. Un UUID difficile à deviner ne remplace pas les permissions.
Les IDs restent présents dans les représentations JSON, même quand le détail
est recherché par slug.

## Médias contrôlés

La visibilité dépend des associations et de la publication en base, donc
`ImageFileView` vérifie ces conditions avant d'ouvrir le fichier. Exposer
directement le répertoire média court-circuiterait ce contrôle. Une seule Image
peut être partagée sans copier ses octets ; une association publique suffit
à rendre son fichier public.

Cette organisation implique un passage par l'API pour chaque lecture, des
réponses sans cache et un téléchargement authentifié explicite pour les
prévisualisations privées. Le stockage reste un filesystem persistant monté,
accessible par l'abstraction storage de Django ; aucun stockage objet distant
n'est configuré. Voir [médias](../architecture/media.md).

## Création imbriquée bornée

Le POST Project orchestre la création d'un ensemble cohérent en transaction.
Les modifications ultérieures passent par les endpoints des ressources :
un PATCH récursif devrait définir si un enfant absent est conservé, remplacé
ou supprimé. Le contrat actuel évite cette ambiguïté en refusant `pages` lors
d'une mise à jour Project et les blocs dans une écriture directe de page.

En revanche, les relations nommées définissent explicitement le remplacement
par liste, la conservation par absence et la suppression d'association par
liste vide. Voir [écritures imbriquées](../apps/projects/nested-writes.md).

## Limites assumées de cette description

Le code ne fournit pas de collecte générale des fichiers orphelins, de frontend
d'administration, de rôles fins, de pagination, de blacklist JWT ou de traitement
email asynchrone. Ce sont des sujets possibles d'évolution, pas des capacités
à supposer lors d'une intégration. Les décisions futures doivent rester liées
à un besoin et à un contrat vérifiable dans le code et les tests.
