# Configuration

Source : `config/settings.py` et `.env.example`. `load_dotenv()` charge le fichier
`.env` ; Django lit ensuite les valeurs avec `python-decouple` ou `os.environ`.
Les variables déjà présentes dans le processus ont priorité sur le fichier.
Les valeurs ci-dessous sont les **défauts du code**, pas nécessairement ceux de
`.env.example`.

## Django, réseau et stockage

| Variable | Défaut | Usage |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Aucun, requise | Secret Django et signature JWT par défaut |
| `DEBUG` | `False` | Mode debug |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Noms d'hôte acceptés, séparés par des virgules, sans protocole |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Origines navigateur avec protocole et port éventuel |
| `MEDIA_ROOT` | `<dépôt>/media` | Fichiers téléversés |
| `STATIC_ROOT` | `<dépôt>/staticfiles` | Destination de collecte des statiques Django |

`MEDIA_URL=/media/` et `STATIC_URL=static/` sont définis dans le code.
`MEDIA_URL` n'active aucune desserte publique.
La langue applicative est `en-us`, le fuseau `UTC` et `USE_TZ=True` ; la
documentation est en français indépendamment de ces réglages.

`SECURE_PROXY_SSL_HEADER` reconnaît `X-Forwarded-Proto: https`.
Les cookies de session et CSRF ont l'attribut Secure. Le proxy doit maîtriser
l'en-tête transmis ; sa configuration n'est pas fournie dans le dépôt.
CORS régit les navigateurs, ce n'est ni une authentification ni une protection
anti-spam contre les clients HTTP directs.

## PostgreSQL

| Variable | Défaut | Usage |
| --- | --- | --- |
| `POSTGRES_DB` | Aucun | Nom de base |
| `POSTGRES_USER` | Aucun | Utilisateur |
| `POSTGRES_PASSWORD` | Aucun | Mot de passe |
| `POSTGRES_HOST` | Aucun | `db` dans Compose, adresse réelle hors Docker |
| `POSTGRES_PORT` | `5432` | Port du serveur |

Compose réutilise les trois premières variables pour initialiser PostgreSQL.
Changer ces valeurs dans `.env` ne reconfigure pas automatiquement un volume
PostgreSQL déjà initialisé.

## Contact et SMTP

| Variable | Défaut | Usage |
| --- | --- | --- |
| `EMAIL_HOST` | Aucun | Hôte SMTP |
| `EMAIL_PORT` | `587` | Port SMTP, entier |
| `EMAIL_HOST_USER` | Aucun | Identifiant SMTP |
| `EMAIL_HOST_PASSWORD` | Aucun | Secret SMTP |
| `EMAIL_USE_TLS` | `True` | STARTTLS |
| `DEFAULT_FROM_EMAIL` | Aucun | Expéditeur autorisé par le SMTP |
| `CONTACT_EMAIL` | Aucun | Destinataire unique des messages |

Le backend est fixé à `django.core.mail.backends.smtp.EmailBackend`, le délai
d'attente à 10 secondes et `EMAIL_USE_SSL` à **False**. Ce dernier n'est **pas**
une variable d'environnement lue par le code. Configurer `EMAIL_USE_SSL` dans
`.env` ne change donc rien. Aucun fournisseur SMTP n'est imposé : la documentation
historique mentionnait OVH puis une réception Gmail, mais les hôtes et adresses
dépendent désormais de ces valeurs. Le préfixe du sujet et le template restent
marqués `alblanchard.fr`.

Ne pas versionner `.env`. En production, le modifier sur le serveur puis
**recréer** le conteneur API pour recharger les variables ; un simple
`docker compose restart` ne recharge pas `env_file`.
