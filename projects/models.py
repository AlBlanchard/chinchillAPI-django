"""
Modèles de l'application projects.

Voir le diagramme de classes Mermaid de l'app : diagrammeclass.mmd

Les modèles utilisent des UUID comme clés primaires techniques.
Les ressources destinées à être exposées dans les URL utilisent également
des slugs comme identifiants lisibles côté API.
"""

import uuid

from django.db import models


class Skill(models.Model):
    """Compétence générale associée à un projet (backend, frontend, DevOps...)."""

    # UUID généré côté application plutôt qu'un entier auto-incrémenté.
    # editable=False empêche notamment sa modification via les formulaires Django.
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # unique=True crée également une contrainte UNIQUE en base de données.
    name = models.CharField(max_length=100, unique=True)

    # Identifiant lisible destiné notamment aux URL et à l'API.
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Technology(models.Model):
    """Technologie concrète utilisée dans un projet (Python, Django, Docker...)."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    """Catégorie principale d'un projet (personnel, professionnel, formation...)."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Image(models.Model):
    """
    Image pouvant être associée à un projet ou à une page.

    `theme` est volontairement une chaîne libre : l'API ne connaît pas
    la liste des thèmes disponibles dans le frontend.

    Une valeur vide représente l'image générique/fallback.
    Exemples de variantes : "", "light", "dark", "noel".
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # ImageField stocke en BDD le chemin/référence du fichier,
    # pas directement les données binaires de l'image.
    # Le fichier sera placé dans MEDIA_ROOT/projects/.
    file = models.ImageField(upload_to="projects/")

    # Texte alternatif utilisé notamment pour l'accessibilité.
    alt = models.CharField(max_length=255)

    # Pas de TextChoices ici : les thèmes appartiennent au frontend.
    # blank=True autorise une valeur vide lors de la validation Django.
    # "" correspond à l'image par défaut, indépendante du thème.
    theme = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    # Défini automatiquement uniquement lors de la création de l'objet.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        # Afficher le thème facilite l'identification des variantes,
        # notamment dans Django Admin.
        return f"{self.alt} ({self.theme or 'default'})"


class Project(models.Model):
    """Projet présenté par l'API et destiné notamment au portfolio."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    title = models.CharField(max_length=200)

    # Le slug est unique globalement car il identifiera un projet
    # de manière lisible dans les URL de l'API.
    slug = models.SlugField(max_length=200, unique=True)

    project_type = models.CharField(max_length=100)
    description = models.TextField()

    # blank=True : ces liens sont facultatifs au niveau de la validation Django.
    github_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    client_url = models.URLField(blank=True)

    # Permet de conserver un brouillon en base sans l'exposer publiquement.
    published = models.BooleanField(default=False)

    # Plusieurs projets peuvent appartenir à une même catégorie.
    #
    # SET_NULL : supprimer une catégorie ne doit pas supprimer ses projets.
    # null=True est nécessaire en BDD puisque SET_NULL peut produire NULL.
    # related_name permet l'accès inverse : category.projects.all()
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )

    # Relations Many-to-Many :
    # un projet possède plusieurs compétences/technologies,
    # et une même compétence/technologie appartient à plusieurs projets.
    #
    # Django crée automatiquement les tables de jointure nécessaires.
    skills = models.ManyToManyField(
        Skill,
        related_name="projects",
        blank=True,
    )

    technologies = models.ManyToManyField(
        Technology,
        related_name="projects",
        blank=True,
    )

    # Date métier du projet, contrairement à created_at/updated_at
    # qui représentent le cycle de vie de l'enregistrement en BDD.
    started_at = models.DateField()

    # Un projet en cours n'a pas forcément de date de fin.
    ended_at = models.DateField(
        null=True,
        blank=True,
    )

    # Plusieurs variantes d'image peuvent être associées au même projet.
    # Exemple : fallback + light + dark.
    #
    # Une même Image peut également être réutilisée par plusieurs projets.
    images = models.ManyToManyField(
        Image,
        related_name="projects",
        blank=True,
    )

    # Cycle de vie de l'enregistrement dans la base.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class ProjectPage(models.Model):
    """Page de détail appartenant à un projet."""

    class Layout(models.TextChoices):
        """
        Dispositions supportées par le composant frontend.

        La valeur de gauche ("image-top") est stockée en BDD et exposée
        par l'API. Django génère automatiquement un label humain ("Top").
        """

        DEFAULT = "default"
        TOP = "image-top"
        BOTTOM = "image-bottom"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Une page appartient à un seul projet.
    #
    # CASCADE : une page n'a plus de raison d'exister si son projet
    # est supprimé.
    #
    # Permet l'accès inverse : project.pages.all()
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="pages",
    )

    # Le slug n'est volontairement PAS unique globalement :
    # plusieurs projets peuvent avoir une page "architecture".
    # L'unicité (project, slug) est imposée plus bas dans Meta.
    slug = models.SlugField(max_length=200)

    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=255, blank=True)

    # Contenu Mermaid facultatif pour afficher un diagramme.
    mermaid = models.TextField(blank=True)

    # choices limite les valeurs aux Layout définis ci-dessus.
    layout = models.CharField(
        max_length=20,
        choices=Layout.choices,
        default=Layout.DEFAULT,
    )

    # Ordre d'affichage de la page au sein du projet.
    position = models.PositiveIntegerField(default=0)

    published = models.BooleanField(default=False)

    # Comme pour Project, plusieurs variantes thématiques peuvent être
    # associées à la même page.
    images = models.ManyToManyField(
        Image,
        related_name="pages",
        blank=True,
    )

    class Meta:
        constraints = [
            # "architecture" peut exister dans plusieurs projets,
            # mais pas deux fois dans le même projet.
            models.UniqueConstraint(
                fields=["project", "slug"],
                name="unique_page_slug_per_project",
            )
        ]

        # project.pages.all() sera trié par position par défaut.
        ordering = ["position"]

    def __str__(self):
        return f"{self.project.title} — {self.title}"


class Paragraph(models.Model):
    """Bloc de texte ordonné appartenant à une ProjectPage."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # CASCADE : supprimer la page supprime également son contenu.
    # Accès inverse : page.paragraphs.all()
    page = models.ForeignKey(
        ProjectPage,
        on_delete=models.CASCADE,
        related_name="paragraphs",
    )

    content = models.TextField()

    # Permet de réordonner les paragraphes sans dépendre de leur ID
    # ou de leur date de création.
    position = models.PositiveIntegerField(default=0)

    class Meta:
        # page.paragraphs.all() sera automatiquement ordonné.
        ordering = ["position"]

    def __str__(self):
        # On tronque volontairement l'affichage pour éviter d'afficher
        # un paragraphe entier dans l'admin ou le shell.
        return self.content[:50]


class Highlight(models.Model):
    """Élément court mis en avant dans une ProjectPage."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Un Highlight dépend entièrement de sa page.
    # Accès inverse : page.highlights.all()
    page = models.ForeignKey(
        ProjectPage,
        on_delete=models.CASCADE,
        related_name="highlights",
    )

    # Contrairement à Paragraph, un Highlight doit rester court.
    content = models.CharField(max_length=255)

    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.content