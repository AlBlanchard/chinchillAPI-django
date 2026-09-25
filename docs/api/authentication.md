# Authentification JWT

Sources : `config/settings.py`, `config/urls.py` et
`projects/tests/test_jwt_auth.py`.

L'API utilise uniquement `JWTAuthentication` dans les classes
d'authentification DRF par défaut. Un cookie de session admin Django ne suffit
pas à authentifier les requêtes API. Les comptes sont ceux de Django ;
aucune route d'inscription utilisateur n'est fournie.

## Obtenir et renouveler les tokens

Envoyer `POST /api/token/` avec les identifiants d'un compte actif :

```json
{"username": "admin", "password": "votre-mot-de-passe"}
```

Une réponse 200 contient `access` et `refresh`. De mauvais identifiants
renvoient 401. L'obtention d'un token n'est pas réservée au staff : les
permissions d'écriture sont vérifiées séparément sur les endpoints métier.

Envoyer le token d'accès dans `Authorization: Bearer <access>`. Lorsqu'il
expire, appeler `POST /api/token/refresh/` :

```json
{"refresh": "votre-refresh-token"}
```

La réponse 200 contient un nouvel `access`. Un refresh invalide ou expiré est
refusé. Le dépôt ne surcharge pas `SIMPLE_JWT` : les valeurs par défaut de
SimpleJWT 5.5.1 s'appliquent, notamment 5 minutes pour l'accès, 1 jour pour
le refresh, sans rotation des refresh tokens. Aucun endpoint de blacklist,
logout serveur ou révocation n'est configuré.

## Statuts et rôle

Sans token sur une opération protégée, la réponse est **401**. Avec un token
valide d'un compte non-staff, une écriture staff renvoie **403**.
Un JWT expiré ou invalide peut aussi faire échouer une route normalement
publique : ne pas envoyer un token obsolète pour une lecture anonyme.

`is_staff=True` est le critère d'administration de l'API ; la propriété
`is_superuser` n'est pas le test effectué par les permissions Projects.
Les lecteurs authentifiés non-staff voient uniquement les contenus publics.
Voir la [matrice de permissions](permissions.md).

Pour les images privées, transmettre aussi ce Bearer token à la route fichier.
Une balise `<img>` seule ne le fait pas ; voir la
[prévisualisation frontend](../architecture/media.md).
