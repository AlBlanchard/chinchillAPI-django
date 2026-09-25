# Contact : réception des formulaires

Sources : `contact/urls.py`, `contact/views.py`, `contact/serializers.py`.

`POST /api/contact/` reçoit un formulaire, le valide puis appelle le service
d'envoi. `ContactAPIView` est le contrôleur HTTP ; `ContactSerializer` valide
les données et `send_contact_email` porte la construction et l'envoi du message.
L'appel SMTP est synchrone, dans le traitement de la requête.

## Entrée et validation

```json
{
  "name": "Camille Martin",
  "email": "camille@example.org",
  "subject": "Demande de contact",
  "message": "Bonjour, je souhaite échanger au sujet de votre projet."
}
```

Les quatre champs sont requis et n'acceptent ni chaîne vide ni `null`.

| Champ | Validation |
| --- | --- |
| `name` | Chaîne, entre 2 et 100 caractères |
| `email` | Format email DRF, au plus 254 caractères |
| `subject` | Chaîne, entre 3 et 150 caractères |
| `message` | Chaîne, entre 10 et 5 000 caractères |

Les espaces en début et fin sont retirés par les champs texte ; les contrôles
de longueur portent sur la valeur normalisée. L'adresse du visiteur est une
adresse de réponse, pas l'expéditeur SMTP.

## Réponses

| Statut | Situation | Corps |
| --- | --- | --- |
| 201 | Service terminé sans exception | `{"success": true, "message": "Votre message a bien été envoyé."}` |
| 400 | Validation du serializer | Dictionnaire DRF des erreurs par champ |
| 400 | `BadHeaderError` lors de l'envoi | `success: false`, message « Le contenu du message est invalide. » |
| 503 | Autre exception du service | `success: false`, message « Le message n'a pas pu être envoyé. Veuillez réessayer plus tard. » |
| 405 | GET | Méthode non prise en charge |

Le contrôleur journalise la trace des exceptions donnant un 503. Le service
retourne un nombre d'emails envoyés, mais le contrôleur ne vérifie pas ce nombre.
Un 201 ne garantit donc ni livraison finale ni lecture dans la boîte destinataire.

## Accès et limites actuelles

La permission est `AllowAny` : aucun JWT n'est requis. L'authentification JWT
globale reste active ; envoyer un token invalide peut provoquer un 401 avant le
traitement. Les origines navigateur autorisées sont configurables via CORS.

Le dépôt ne fournit ni limitation de débit DRF, ni CAPTCHA, ni enregistrement
des messages en base, ni accusé de réception au visiteur, ni file asynchrone.
Ces pistes figuraient dans la documentation historique, mais ne sont pas
implémentées. `contact/tests.py` ne contient pas de tests effectifs.

Pour le template, les protections email et le réglage SMTP, consulter le
[flux d'envoi](email-flow.md).
