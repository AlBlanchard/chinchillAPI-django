# Stockage persistant et sauvegardes

Sources : `compose.yaml`, `Dockerfile`, `config/settings.py` et le workflow
de déploiement.

| Données | Emplacement conteneur | Persistance |
| --- | --- | --- |
| PostgreSQL | `/var/lib/postgresql/data` | Volume Compose `postgres_data` |
| Images | `/app/media/projects/…` | Hôte `/srv/media/chinchillapi/projects/…` |
| Statiques Django | `/app/staticfiles` | Répertoire de l'image, sans volume partagé |
| Configuration secrète | Variables du conteneur | `.env` dans `/srv/apps/chinchillapi/` sur l'hôte |

## Médias

`MEDIA_ROOT=/app/media` dans le `.env` de production doit correspondre au
montage Compose. Un autre chemin pourrait écrire dans le filesystem éphémère
du conteneur. Le dossier hôte doit être accessible en lecture/écriture par
UID/GID 10001. Pour un répertoire neuf, la préparation Linux peut utiliser :

```sh
sudo install -d -o 10001 -g 10001 -m 0750 /srv/media/chinchillapi
```

Pour des données existantes, contrôler leurs droits et transférer les fichiers
en conservant les chemins relatifs enregistrés en base. Changer `MEDIA_ROOT`
ne déplace aucun fichier automatiquement. La recréation du conteneur ne doit
pas toucher le bind mount.

Le reverse proxy ne doit publier ni `/srv/media/chinchillapi` ni `/app/media`.
Toute lecture de fichier passe par la [route contrôlée](../architecture/media.md).

## Sauvegarde et restauration

Le dépôt n'automatise pas les sauvegardes. Une procédure d'exploitation doit
sauvegarder PostgreSQL **et** le répertoire média, ainsi que la configuration
secrète dans un stockage protégé. Restaurer uniquement la base laisse des
références sans fichiers ; restaurer uniquement les fichiers ne rétablit pas
les propriétaires ni les droits de publication.

Prévoir une restauration cohérente des deux stockages, préserver les chemins
relatifs et tester les lectures par l'API après restauration. Ne pas utiliser
`docker compose down -v` pour une mise à jour : cette option détruirait le
volume SQL. La politique de rétention et la destination des sauvegardes restent
à définir hors de la configuration actuelle.

## Statiques Django

Les CSS/JS de l'admin Django sont distincts des images téléversées. Le workflow
saute `collectstatic`, car un conteneur de commande jetable ne partagerait pas
son résultat avec le conteneur API. Ni volume statique ni desserte dédiée ne
sont configurés. Il reste à définir ce parcours avant de compter sur une
interface admin correctement habillée en production.
