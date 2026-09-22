# API de contact chinchillAPI

## Présentation

Cette API permet de recevoir les messages envoyés depuis les formulaires de contact de différents sites.

Le frontend envoie les données du formulaire à cette API Django REST Framework qui :

- valide les informations reçues ;
- génère un email HTML et une version texte ;
- envoie le message via le serveur SMTP OVH ;
- fait parvenir le message à une boîte Gmail ou toute autre adresse de destination.

---

# Architecture

```text
React
   │
   ▼
POST /api/contact/
   │
   ▼
ContactSerializer
   │
   ▼
Contact Service
   │
   ▼
Template HTML
   │
   ▼
SMTP OVH
   │
   ▼
Boîte de réception
```

---

# Fonctionnement

## 1. Validation

Le frontend envoie une requête POST contenant :

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "subject": "Création d'un site",
  "message": "Bonjour..."
}
```

Les données sont validées par `ContactSerializer`.

Les validations portent notamment sur :

- nom obligatoire ;
- email valide ;
- sujet obligatoire ;
- message obligatoire.

---

## 2. Service d'envoi

La logique métier est volontairement séparée de la vue.

La vue ne fait que :

1. valider les données ;
2. appeler `send_contact_email()` ;
3. retourner une réponse HTTP.

Toute la logique d'envoi est centralisée dans `services.py`.

Cette séparation facilite :

- les tests unitaires ;
- la maintenance ;
- la réutilisation du service.

---

## 3. Génération du template

L'email HTML est généré grâce à :

```python
render_to_string(
    "contact/contact_email.html",
    context,
)
```

Le template reçoit le contexte :

- `name`
- `visitor_email`
- `subject`
- `message`

Django échappe automatiquement les variables afin d'éviter toute injection HTML.

Le filtre :

```django
{{ message|linebreaksbr }}
```

préserve les retours à la ligne du message.

Une version texte est également générée afin d'assurer la compatibilité avec les clients mail qui n'affichent pas le HTML.

---

## 4. Envoi de l'email

L'envoi repose sur `EmailMultiAlternatives`.

Le message contient :

- un sujet personnalisé ;
- une version texte ;
- une version HTML.

Le champ `reply_to` est défini avec l'adresse du visiteur.

Ainsi, lorsque le destinataire clique sur **Répondre**, son client mail adresse directement la réponse au visiteur.

---

# Configuration

La configuration de l'application est définie à l'aide de variables d'environnement.

Elles permettent notamment de configurer Django, les origines autorisées pour les requêtes CORS ainsi que le serveur SMTP utilisé pour l'envoi des emails.

Exemple de configuration :

```env
DJANGO_SECRET_KEY=VOTRE_SECRET_KEY

DEBUG=False

ALLOWED_HOSTS=chinchillapi.com,www.chinchillapi.com,localhost,127.0.0.1

CORS_ALLOWED_ORIGINS=http://localhost:5173,https://votresite.com,https://www.votresite.com

EMAIL_HOST=ssl0.ovh.net
EMAIL_PORT=587

EMAIL_HOST_USER=monadresse@monsite.fr
EMAIL_HOST_PASSWORD=********

EMAIL_USE_TLS=True
EMAIL_USE_SSL=False

DEFAULT_FROM_EMAIL=Monsite <monadresse@monsite.fr>

CONTACT_EMAIL=mon.adresse@gmail.com
```

Description :

| Variable | Description |
| --- | --- |
| `DJANGO_SECRET_KEY` | Clé secrète utilisée par Django pour les opérations cryptographiques |
| `DEBUG` | Active ou désactive le mode debug de Django |
| `ALLOWED_HOSTS` | Liste des noms d'hôte autorisés à servir l'application |
| `CORS_ALLOWED_ORIGINS` | Liste des origines autorisées à effectuer des requêtes vers l'API depuis un navigateur |
| `EMAIL_HOST` | Serveur SMTP utilisé pour l'envoi des emails |
| `EMAIL_PORT` | Port utilisé pour la connexion au serveur SMTP |
| `EMAIL_HOST_USER` | Compte utilisé pour l'authentification SMTP |
| `EMAIL_HOST_PASSWORD` | Mot de passe du compte SMTP |
| `EMAIL_USE_TLS` | Active la connexion TLS au serveur SMTP |
| `EMAIL_USE_SSL` | Active la connexion SSL directe au serveur SMTP |
| `DEFAULT_FROM_EMAIL` | Adresse utilisée comme expéditeur des emails |
| `CONTACT_EMAIL` | Adresse destinataire des messages envoyés via l'API de contact |

Les variables `ALLOWED_HOSTS` et `CORS_ALLOWED_ORIGINS` acceptent plusieurs valeurs séparées par des virgules.

Par exemple :

```env
CORS_ALLOWED_ORIGINS=https://site-a.fr,https://www.site-a.fr,https://site-b.fr
```

Les origines CORS doivent inclure leur protocole (`http://` ou `https://`).

À l'inverse, les valeurs de `ALLOWED_HOSTS` correspondent uniquement aux noms d'hôte et ne doivent pas contenir de protocole.

En production, le fichier `.env` est conservé directement sur le serveur et n'est pas versionné dans le dépôt Git. Il contient notamment les secrets nécessaires au fonctionnement de l'application, comme `DJANGO_SECRET_KEY` et `EMAIL_HOST_PASSWORD`.

---

# Paramètres Django

Le projet utilise :

```python
APP_DIRS = True
```

afin que Django détecte automatiquement les templates situés dans :

```text
templates/
```

Les listes `ALLOWED_HOSTS` et `CORS_ALLOWED_ORIGINS` sont chargées depuis les variables d'environnement et converties à l'aide de `Csv()` :

```python
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    cast=Csv(),
    default="localhost,127.0.0.1",
)

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    cast=Csv(),
    default="http://localhost:5173",
)
```

Cela permet d'ajouter ou de retirer un domaine autorisé sans modifier directement le code de l'application.

---

# Déploiement

L'application est déployée sur le serveur de production à l'aide de Docker.

Le fichier `.env` de production est conservé sur le serveur et reste indépendant du dépôt Git. Les secrets de production ne sont donc pas stockés dans le code source.

Le déploiement de l'application est automatisé par la pipeline CI/CD du projet. Lorsqu'une nouvelle version est déployée, le code de l'application est mis à jour et les services Docker sont relancés avec la nouvelle version.

Le fichier `.env` présent sur le serveur est conservé lors des déploiements. Les variables d'environnement sont ainsi réutilisées par l'application sans avoir à les ajouter au dépôt.

Lorsqu'une variable d'environnement est ajoutée ou modifiée en production, elle doit être mise à jour directement dans le `.env` du serveur.

Par exemple, pour autoriser un nouveau frontend à utiliser l'API :

```env
CORS_ALLOWED_ORIGINS=https://site-a.fr,https://www.site-a.fr,https://nouveau-site.fr
```

Le prochain redémarrage ou redéploiement de l'application permettra à Django de charger la nouvelle configuration.

---

# Réponses de l'API

## Succès

HTTP `201 Created`

```json
{
  "success": true,
  "message": "Votre message a bien été envoyé."
}
```

---

## Erreur de validation

HTTP `400 Bad Request`

Les erreurs sont directement retournées par le serializer.

---

# Bonnes pratiques mises en œuvre

- Séparation de la logique métier (`services.py`)
- Validation avec Django REST Framework
- Utilisation des variables d'environnement
- Configuration CORS limitée aux origines autorisées
- Génération du HTML avec les templates Django
- Version HTML + texte des emails
- Utilisation de `reply_to`
- Échappement automatique des données utilisateur
- Gestion des erreurs et journalisation
- Secrets de production non versionnés
- Déploiement automatisé
- API REST simple et facilement testable

---

# Pistes d'amélioration

- Ajout d'un accusé de réception envoyé au visiteur
- Limitation du nombre de requêtes (rate limiting)
- Protection anti-spam (reCAPTCHA ou Cloudflare Turnstile)
- Enregistrement des messages en base de données
- Tableau d'administration pour consulter les demandes
- Tests unitaires et tests d'intégration
- Envoi asynchrone des emails avec Celery ou Django Q