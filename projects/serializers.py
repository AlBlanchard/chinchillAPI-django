from rest_framework import serializers

from .models import (
    Category,
    Highlight,
    Image,
    Paragraph,
    Project,
    ProjectPage,
    Skill,
    Technology,
)


class SkillSerializer(serializers.ModelSerializer):
    """Sérialise une compétence associable à un projet."""

    class Meta:
        model = Skill
        fields = ["id", "name", "slug"]
        read_only_fields = ["id"]


class TechnologySerializer(serializers.ModelSerializer):
    """Sérialise une technologie associable à un projet."""

    class Meta:
        model = Technology
        fields = ["id", "name", "slug"]
        read_only_fields = ["id"]


class CategorySerializer(serializers.ModelSerializer):
    """Sérialise une catégorie de projet."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]
        read_only_fields = ["id"]


class ImageSerializer(serializers.ModelSerializer):
    """
    Sérialise une image et sa variante de thème éventuelle.

    Un thème vide représente l'image générique/fallback.
    La liste des thèmes n'est volontairement pas validée ici :
    elle reste sous la responsabilité du frontend.
    """

    class Meta:
        model = Image
        fields = ["id", "file", "alt", "theme", "created_at"]

        # Ces valeurs sont générées par le serveur et ne peuvent
        # donc pas être choisies par le client lors d'un POST/PATCH.
        read_only_fields = ["id", "created_at"]


class ParagraphSerializer(serializers.ModelSerializer):
    """Sérialise un paragraphe appartenant à une page de projet."""

    class Meta:
        model = Paragraph
        fields = ["id", "content", "position"]

        # L'UUID est généré automatiquement par le modèle.
        read_only_fields = ["id"]


class HighlightSerializer(serializers.ModelSerializer):
    """Sérialise un élément court mis en avant dans une page."""

    class Meta:
        model = Highlight
        fields = ["id", "content", "position"]
        read_only_fields = ["id"]


class ProjectPageSerializer(serializers.ModelSerializer):

    # DRF utilise ici les related_name définis dans les modèles
    # many=True indique qu'il s'agit d'une collection d'objets.
    paragraphs = ParagraphSerializer(
        many=True,
        read_only=True,
    )

    highlights = HighlightSerializer(
        many=True,
        read_only=True,
    )

    images = ImageSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = ProjectPage
        fields = [
            "id",
            "slug",
            "title",
            "subtitle",
            "mermaid",
            "layout",
            "position",
            "published",
            "images",
            "paragraphs",
            "highlights",
        ]

        read_only_fields = ["id"]


class NamedRelationListField(serializers.ListField):
    """
    Champ utilisé pour représenter une relation ManyToMany
    sous forme d'une simple liste de noms.

    Entrée :
        ["Django", "React"]

    Sortie :
        ["Django", "React"]

    En écriture, ListField conserve son comportement normal et valide
    une liste de chaînes.

    En lecture, Django fournit un ManyRelatedManager. On récupère donc
    explicitement les objets liés avec .all() avant d'en extraire les noms.
    """

    child = serializers.CharField(max_length=100)

    def to_representation(self, data):
        return [
            obj.name
            for obj in data.all()
        ]


class NamedRelationField(serializers.CharField):
    """
    Champ utilisé pour représenter une ForeignKey par son nom.

    Entrée :
        "Projet pro"

    Sortie :
        "Projet pro"
    """

    def get_attribute(self, instance):
        # Serializer.to_representation court-circuite to_representation()
        # quand l'attribut vaut None : il écrit directement None dans la
        # sortie. On retourne donc "" ici pour forcer l'appel de
        # to_representation() et respecter le contrat API ("").
        value = super().get_attribute(instance)

        if value is None:
            return ""

        return value

    def to_representation(self, value):
        # La relation peut être absente (cf. get_attribute ci-dessus).
        if not value:
            return ""

        # En lecture, `value` est un objet Category.
        # On expose uniquement son nom dans le JSON.
        return value.name

class ProjectSerializer(serializers.ModelSerializer):
    """
    Sérialise un projet avec des relations lisibles.

    Les UUID restent internes à la base de données.

    Exemple en entrée comme en sortie :
        "category": "Projet pro"
        "skills": ["Backend", "Frontend"]
        "technologies": ["Python", "Django"]
    """

    category = NamedRelationField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )

    skills = NamedRelationListField(
        required=False,
    )

    technologies = NamedRelationListField(
        required=False,
    )

    images = ImageSerializer(
        many=True,
        read_only=True,
    )

    pages = ProjectPageSerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Project

        fields = [
            "id",
            "title",
            "slug",
            "project_type",
            "description",
            "github_url",
            "website_url",
            "client_url",
            "published",
            "category",
            "skills",
            "technologies",
            "started_at",
            "ended_at",
            "images",
            "pages",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]



