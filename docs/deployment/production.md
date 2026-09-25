# Exploiter la production

Cette page décrit les prérequis de la configuration du dépôt, pas un état
vérifié du serveur distant. Sources : `.env.example`, `compose.yaml`,
`Dockerfile` et `.github/workflows/deploy.yml`.

## Préparer l'hôte

Prévoir Docker avec Compose, l'accès Tailscale/SSH du compte de déploiement,
`rsync`, le répertoire `/srv/apps/chinchillapi`, le stockage média et les droits
de l'utilisateur 10001. Préparer le `.env` directement sur le serveur :
secrets Django/PostgreSQL/SMTP, `DEBUG=False`, domaines et origines réels,
`POSTGRES_HOST=db`, `MEDIA_ROOT=/app/media`, `STATIC_ROOT=/app/staticfiles`.

Le reverse proxy doit terminer HTTPS et transmettre vers `127.0.0.1:8001`.
Il doit maîtriser `X-Forwarded-Proto`, préserver un hôte autorisé et laisser
les médias passer par l'API. La documentation historique évoquait Caddy,
mais aucun fichier de configuration de proxy n'est fourni : ne pas considérer
son installation comme garantie par ce dépôt.

Configurer les secrets GitHub décrits dans le [pipeline](ci-cd.md). Un push
sur `main` lance les tests puis le déploiement. Pour une intervention manuelle,
suivre la [séquence Docker](docker.md) après sauvegarde des données si nécessaire.

## Vérifier et diagnostiquer

```sh
docker compose ps --all
docker compose logs --tail 100 api db
curl -i http://127.0.0.1:8001/api/contact/
```

Le dernier appel doit renvoyer 405. Vérifier aussi la lecture publique d'un
projet publié et d'une image, et le refus public d'un brouillon. La validation
SMTP de bout en bout nécessite un POST Contact réel et la vérification de la
boîte destinataire ; elle n'est pas effectuée par le healthcheck du workflow.

| Symptôme | Vérification utile |
| --- | --- |
| 400 lié à l'hôte | `ALLOWED_HOSTS` et en-tête Host du proxy |
| Blocage CORS navigateur | Origine exacte avec protocole/port dans `CORS_ALLOWED_ORIGINS` |
| 401 / 403 en écriture | Validité du JWT puis `is_staff` |
| Image 404 | Publication et associations, référence, présence du fichier |
| Upload impossible | Droits du bind mount, taille et validité du fichier |
| Contact 503 | Logs API, paramètres et connectivité SMTP |
| Admin sans CSS | Desserte statique encore non configurée |

Pour recharger un `.env` modifié, recréer le conteneur API, par exemple
`docker compose up -d --force-recreate api`. La synchronisation du code
conserve ce fichier ; elle ne met pas ses variables à jour automatiquement.

## Limites opérationnelles

Le pipeline n'assure ni absence d'interruption de service, ni rollback
automatique, ni sauvegarde, ni surveillance continue. Une migration échouée
arrête la séquence ; un changement de schéma réussi n'est pas automatiquement
annulé si l'étape HTTP échoue ensuite. Les procédures de sauvegarde/restauration,
la desserte statique, le proxy et la validation SMTP doivent être complétés
et vérifiés dans l'environnement réel.
