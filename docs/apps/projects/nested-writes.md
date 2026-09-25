# Création et modification des relations

Sources : `ProjectSerializer`, `ProjectPageSerializer` et `ProjectViewSet`.

## POST Project : création imbriquée acceptée

`POST /api/projects/`, avec JWT staff, peut créer simultanément un projet,
ses références nommées et ses pages avec Paragraph et Highlight :

```json
{
  "title": "Portfolio",
  "slug": "portfolio",
  "project_type": "Personnel",
  "description": "Présentation des réalisations.",
  "started_at": "2026-09-01",
  "category": "Personnel",
  "skills": ["Backend"],
  "technologies": ["Django"],
  "pages": [
    {
      "slug": "architecture",
      "title": "Architecture",
      "position": 0,
      "paragraphs": [{"content": "Une API Django.", "position": 0}],
      "highlights": [{"content": "Médias contrôlés", "position": 0}]
    }
  ]
}
```

Le résultat est un **201** avec la représentation du projet. Les flags de
publication omis restent False, indépendamment pour le projet et ses pages.
Les images imbriquées sont en lecture seule : les envoyer dans ce JSON ne crée
ni fichier ni association. Utiliser les endpoints [images](images.md).

Le contrôleur crée d'abord Project, résout les noms avec `get_or_create`,
assigne les ManyToMany, puis crée les pages et leurs blocs (`bulk_create`
pour Paragraph et Highlight). `perform_create` est atomique en base : un
échec pendant cette orchestration annule l'ensemble des écritures de base.

## Résolution des noms et validation

Un nom existant est réutilisé avec son slug actuel. Pour un nouveau nom,
`slugify(name)` génère le slug. Le serializer refuse un slug généré vide,
trop long ou déjà utilisé par un autre nom, y compris une collision à
l'intérieur d'une même liste. Les noms sont limités à 100 caractères.

Deux pages du POST ne peuvent avoir le même slug. Lors d'une création ou
modification de page contextuelle, l'unicité est vérifiée dans le projet parent.
La base maintient aussi la contrainte `(project, slug)`.
`ended_at` ne peut précéder `started_at` ; un PATCH de date est validé en
tenant compte de la date existante non envoyée.

## PATCH : absent, vide et remplacement

`PATCH /api/projects/<slug>/` distingue les champs absents des valeurs vides :

| Champ | Absent | Valeur explicite |
| --- | --- | --- |
| `category` | Conservée | Nom : résout/remplace ; `""` ou `null` : retire |
| `skills` | Conservées | Liste : remplace tout ; `[]` : vide ; `null` refusé |
| `technologies` | Conservées | Liste : remplace tout ; `[]` : vide ; `null` refusé |
| `pages` | Pages conservées | Toute liste, même `[]`, est refusée en mise à jour |
| `images` | Associations conservées | Lecture seule, ne pilote pas les associations |

Par exemple, `{"title": "Nouveau titre"}` conserve les relations et
`{"skills": []}` retire uniquement les compétences associées au projet,
sans supprimer les objets Skill. Une catégorie absente en base est représentée
par `""` à la lecture.

`perform_update` utilise une sentinelle pour détecter les champs absents et
`transaction.atomic` pour grouper les écritures. `PUT` n'active pas de mise à
jour récursive non plus : ses champs requis suivent la validation DRF et
`pages` reste refusé. Les relations optionnelles absentes sont conservées.

## Modifier les enfants explicitement

Créer ou modifier une page via `/api/projects/<project_slug>/pages/…` ne permet
pas d'envoyer `paragraphs` ou `highlights`, même vides : **400**.
Ces créations imbriquées ne sont acceptées que dans le POST Project initial.
Utiliser les collections contextuelles `paragraphs/` et `highlights/`, puis
le détail par UUID pour modifier ou supprimer un bloc.

Le parent est déduit de l'URL et n'est pas un champ réaffectable du serializer.
Les requêtes de détail sont limitées au contexte demandé : un UUID d'une autre
page ne permet pas d'accéder à son contenu sous une fausse URL parent.
Les [choix actuels](../../decisions/design.md) expliquent les conséquences de
ce contrat, sans supposer de PATCH récursif implicite.
