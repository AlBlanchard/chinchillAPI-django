# API de contact chinchillAPI

## Présentation

Cette API permet de recevoir les messages envoyés depuis le formulaire de contact du portfolio.

Le frontend envoie les données du formulaire à cette API Django REST Framework qui :

* valide les informations reçues ;
* génère un email HTML et une version texte ;
* envoie le message via le serveur SMTP OVH ;
* fait parvenir le message à une boîte Gmail (ou toute autre adresse de destination).

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

* nom obligatoire ;
* email valide ;
* sujet obligatoire ;
* message obligatoire.

---

## 2. Service d'envoi

La logique métier est volontairement séparée de la vue.

La vue ne fait que :

1. valider les données ;
2. appeler `send_contact_email()` ;
3. retourner une réponse HTTP.

Toute la logique d'envoi est centralisée dans `services.py`.

Cette séparation facilite :

* les tests unitaires ;
* la maintenance ;
* la réutilisation du service.

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

* name
* visitor_email
* subject
* message

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

* un sujet personnalisé ;
* une version texte ;
* une version HTML.

Le champ `reply_to` est défini avec l'adresse du visiteur.

Ainsi, lorsque le destinataire clique sur **Répondre**, son client mail adresse directement la réponse au visiteur.

---

# Configuration SMTP

Le projet utilise le serveur SMTP d'OVH.

Variables d'environnement :

```env
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

| Variable            | Description                            |
| ------------------- | -------------------------------------- |
| EMAIL_HOST          | Serveur SMTP OVH                       |
| EMAIL_PORT          | Port SMTP                              |
| EMAIL_HOST_USER     | Compte utilisé pour l'authentification |
| EMAIL_HOST_PASSWORD | Mot de passe SMTP                      |
| DEFAULT_FROM_EMAIL  | Expéditeur affiché                     |
| CONTACT_EMAIL       | Destinataire des messages              |

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

---

# Réponses de l'API

## Succès

HTTP 201

```json
{
    "success": true,
    "message": "Votre message a bien été envoyé."
}
```

---

## Erreur de validation

HTTP 400

Les erreurs sont directement retournées par le serializer.

---

# Bonnes pratiques mises en œuvre

* Séparation de la logique métier (`services.py`)
* Validation avec Django REST Framework
* Utilisation des variables d'environnement
* Génération du HTML avec les templates Django
* Version HTML + texte des emails
* Utilisation de `reply_to`
* Échappement automatique des données utilisateur
* Gestion des erreurs et journalisation
* API REST simple et facilement testable

---

# Pistes d'amélioration

* Ajout d'un accusé de réception envoyé au visiteur
* Limitation du nombre de requêtes (rate limiting)
* Protection anti-spam (reCAPTCHA ou Cloudflare Turnstile)
* Enregistrement des messages en base de données
* Tableau d'administration pour consulter les demandes
* Tests unitaires et tests d'intégration
* Envoi asynchrone des emails avec Celery ou Django Q
