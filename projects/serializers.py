from django.utils.text import slugify
from django.urls import reverse
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

    MAX_FILE_SIZE = 10 * 1024 * 1024

    def validate_file(self, file):
        if file.size > self.MAX_FILE_SIZE:
            raise serializers.ValidationError("L'image ne doit pas dépasser 10 Mio.")
        return file

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.file:
            url = reverse("image-file", kwargs={"pk": instance.pk})
            request = self.context.get("request")
            data["file"] = request.build_absolute_uri(url) if request else url
        return data

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
        required=False,
    )

    highlights = HighlightSerializer(
        many=True,
        required=False,
    )

    images = ImageSerializer(
        many=True,
        read_only=True,
    )

    def validate(self, attrs):
        # Seul le POST Project orchestre la création de ces enfants.
        if self.parent is None:
            errors = {
                field: "Utilisez l'endpoint dédié pour modifier ce contenu."
                for field in ("paragraphs", "highlights")
                if field in attrs
            }
            if errors:
                raise serializers.ValidationError(errors)
            if "slug" in attrs:
                project = self.context.get("project")
                if self.instance is not None:
                    project = self.instance.project
                conflicts = ProjectPage.objects.filter(project=project, slug=attrs["slug"])
                if self.instance is not None:
                    conflicts = conflicts.exclude(pk=self.instance.pk)
                if conflicts.exists():
                    raise serializers.ValidationError({
                        "slug": "Ce projet possède déjà une page avec ce slug.",
                    })
        return attrs

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
        max_length=100,
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
        required=False,
    )

    def _validate_named_relations(self, model, names):
        # La résolution/création reste dans le ViewSet ; ici on valide seulement.
        pending_slugs = {}
        for name in names:
            if model.objects.filter(name=name).exists():
                continue
            slug = slugify(name)
            if not slug:
                raise serializers.ValidationError(
                    f"Le nom « {name} » ne permet pas de générer un slug valide.",
                )
            # La normalisation Unicode peut allonger un nom pourtant <= 100 caractères.
            if len(slug) > 100:
                raise serializers.ValidationError("Le slug généré ne doit pas dépasser 100 caractères.")
            if (
                slug in pending_slugs and pending_slugs[slug] != name
            ) or model.objects.filter(slug=slug).exists():
                raise serializers.ValidationError(
                    f"Le slug « {slug} » est déjà utilisé par un autre nom.",
                )
            pending_slugs[slug] = name
        return names

    def validate_category(self, name):
        if name:
            self._validate_named_relations(Category, [name])
        return name

    def validate_skills(self, names):
        return self._validate_named_relations(Skill, names)

    def validate_technologies(self, names):
        return self._validate_named_relations(Technology, names)

    def validate_pages(self, pages):
        slugs = [page["slug"] for page in pages if "slug" in page]
        if len(slugs) != len(set(slugs)):
            raise serializers.ValidationError("Les slugs des pages doivent être uniques dans le projet.")
        return pages

    def validate(self, attrs):
        if self.instance is not None and "pages" in attrs:
            raise serializers.ValidationError({
                "pages": "Utilisez les endpoints des pages pour modifier le contenu du projet.",
            })
        started_at = attrs.get("started_at", getattr(self.instance, "started_at", None))
        ended_at = attrs.get("ended_at", getattr(self.instance, "ended_at", None))
        if started_at is not None and ended_at is not None and ended_at < started_at:
            raise serializers.ValidationError({
                "ended_at": "La date de fin doit être postérieure ou égale à la date de début.",
            })
        return attrs

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



