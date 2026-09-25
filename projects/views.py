from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from drf_spectacular.utils import extend_schema, OpenApiResponse

from projects.mixins import StaffPublicationMixin, ProjectPageChildMixin

from .models import (
    Category,
    Highlight,
    Paragraph,
    Project,
    ProjectPage,
    Skill,
    Technology,
    Image,
)
from .serializers import (
    HighlightSerializer,
    ParagraphSerializer,
    ProjectPageSerializer,
    ProjectSerializer,
    ImageSerializer,
)
from .permissions import IsAdminOrReadOnly


class ProjectViewSet(StaffPublicationMixin, viewsets.ModelViewSet):
    """
    Contrôleur CRUD des projets.

    Le serializer valide les données reçues.
    Le contrôleur orchestre la création/modification du Project
    et de ses relations.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAdminOrReadOnly]
    publication_filters = {"published": True}

    # L'UUID reste la clé primaire technique en base,
    # mais l'API identifie les projets par leur slug lisible.
    lookup_field = "slug"

    def get_queryset(self):  # type: ignore[override]
        """Cache les brouillons aux visiteurs non-staff."""
        pages = ProjectPage.objects.all()
        if not self._is_staff_request():
            pages = pages.filter(published=True)

        queryset = Project.objects.select_related("category").prefetch_related(
            "skills",
            "technologies",
            "images",
            Prefetch(
                "pages",
                queryset=pages.prefetch_related("images", "paragraphs", "highlights"),
            ),
        )

        return self.filter_public_queryset(queryset)

    def _get_or_create_named_object(self, model, name):
        """
        Récupère un objet à partir de son nom.

        S'il n'existe pas encore, il est créé automatiquement
        avec un slug généré depuis son nom.

        Cette méthode peut être utilisée avec Category, Skill
        et Technology car ces modèles possèdent tous `name`
        et `slug`.
        """

        obj, _ = model.objects.get_or_create(
            name=name,
            defaults={
                "slug": slugify(name),
            },
        )

        return obj

    def _resolve_many_to_many(self, model, names):
        """
        Transforme une liste de noms en liste d'objets Django.

        Exemple :
            ["React", "Django"]

        devient :
            [<Technology: React>, <Technology: Django>]

        Chaque objet est récupéré s'il existe déjà,
        ou créé automatiquement sinon.
        """

        return [
            self._get_or_create_named_object(model, name)
            for name in names
        ]

    def _create_pages(self, project, pages_data):
        for page_data in pages_data:
            paragraphs_data = page_data.pop("paragraphs", [])
            highlights_data = page_data.pop("highlights", [])

            page = ProjectPage.objects.create(
                project=project,
                **page_data,
            )

            Paragraph.objects.bulk_create(
                Paragraph(
                    page=page,
                    **paragraph_data,
                )
                for paragraph_data in paragraphs_data
            )

            Highlight.objects.bulk_create(
                Highlight(
                    page=page,
                    **highlight_data,
                )
                for highlight_data in highlights_data
            )

    @transaction.atomic
    def perform_create(self, serializer):
        """
        Crée un projet ainsi que ses relations.

        Toute l'opération est atomique :
        si une étape échoue, PostgreSQL annule l'ensemble.
        """

        # On travaille sur les données déjà validées par le serializer.
        validated_data = serializer.validated_data

        # Les relations sont retirées car elles nécessitent
        # un traitement spécifique.
        category_name = validated_data.pop("category", None)
        skill_names = validated_data.pop("skills", [])
        technology_names = validated_data.pop("technologies", [])

        pages_data = validated_data.pop("pages", [])

        # création de Project + category/skills/technologies...
        project = Project.objects.create(**validated_data)

        # ----- Category -----

        if category_name:
            project.category = self._get_or_create_named_object(
                Category,
                category_name,
            )

            project.save(update_fields=["category"])

        # ----- Skills -----

        skills = self._resolve_many_to_many(
            Skill,
            skill_names,
        )

        project.skills.set(skills)

        # ----- Technologies -----

        technologies = self._resolve_many_to_many(
            Technology,
            technology_names,
        )

        project.technologies.set(technologies)

        self._create_pages(project, pages_data)

        # DRF doit connaître l'instance finalement créée pour
        # pouvoir construire correctement la réponse HTTP.
        serializer.instance = project

    @transaction.atomic
    def perform_update(self, serializer):
        """
        Met à jour un projet et, uniquement si elles sont présentes
        dans la requête, ses relations.

        C'est particulièrement important pour PATCH :
        un champ absent signifie "ne pas modifier cette valeur".
        """

        # Une sentinelle permet de distinguer :
        #
        # - champ absent
        # - champ présent mais volontairement vide
        #
        # None ou [] ne peuvent pas jouer ce rôle puisqu'ils peuvent
        # eux-mêmes être des valeurs valides.
        missing = object()

        validated_data = serializer.validated_data

        category_name = validated_data.pop("category", missing)
        skill_names = validated_data.pop("skills", missing)
        technology_names = validated_data.pop("technologies", missing)

        # serializer.save() peut ici gérer normalement tous les champs
        # simples restants :
        #
        # title, description, published, dates, URLs...
        project = serializer.save()

        # ----- Category -----

        # Le champ n'était pas présent dans le PATCH :
        # on conserve la catégorie actuelle.
        if category_name is not missing:

            # Une valeur vide/null retire volontairement la catégorie.
            if category_name:
                project.category = self._get_or_create_named_object(
                    Category,
                    category_name,
                )
            else:
                project.category = None

            project.save(update_fields=["category"])

        # ----- Skills -----

        if skill_names is not missing:
            skills = self._resolve_many_to_many(
                Skill,
                skill_names,
            )

            # [] donnera naturellement project.skills.set([]),
            # ce qui vide volontairement la relation.
            project.skills.set(skills)

        # ----- Technologies -----

        if technology_names is not missing:
            technologies = self._resolve_many_to_many(
                Technology,
                technology_names,
            )

            project.technologies.set(technologies)


class ProjectPageViewSet(StaffPublicationMixin, viewsets.ModelViewSet):
    # Nécessaire pour que django-stubs infère le bon type de retour
    # pour get_queryset() ci-dessous ; la valeur réelle est ignorée.
    queryset = ProjectPage.objects.all()
    serializer_class = ProjectPageSerializer
    permission_classes = [IsAdminOrReadOnly]
    publication_filters = {
        "published": True,
        "project__published": True,
    }
    lookup_field = "slug"

    # DRF déclare `queryset = None` sans annotation, donc Pylance infère
    # un retour "Never" pour get_queryset() de la classe de base : le
    # type: ignore ci-dessous supprime ce faux positif.
    def get_queryset(self):  # type: ignore[override]
        """
        Une page n'existe dans l'API que dans le contexte
        du projet auquel elle appartient.

        Les visiteurs non-staff ne doivent voir que les pages publiées
        d'un projet lui-même publié.
        """
        queryset = ProjectPage.objects.filter(
            project__slug=self.kwargs["project_slug"],
        )

        return self.filter_public_queryset(queryset)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == "create":
            context["project"] = get_object_or_404(
                Project, slug=self.kwargs["project_slug"],
            )
        return context

    def perform_create(self, serializer):
        """
        Le projet parent vient de l'URL et non du JSON envoyé
        par le client.
        """
        serializer.save(project=serializer.context["project"])


class ParagraphViewSet(ProjectPageChildMixin, viewsets.ModelViewSet):
    queryset = Paragraph.objects.all()
    serializer_class = ParagraphSerializer
    permission_classes = [IsAdminOrReadOnly]

    # Ceci ne sert strictement à rien, c'est un pont de typage sinon l'IDE panique
    def get_queryset(self) -> QuerySet[Paragraph]:  # type: ignore[override]
        return ProjectPageChildMixin.get_queryset(self)



class HighlightViewSet(ProjectPageChildMixin, viewsets.ModelViewSet):
    queryset = Highlight.objects.all()
    serializer_class = HighlightSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self) -> QuerySet[Highlight]:  # type: ignore[override]
        return ProjectPageChildMixin.get_queryset(self)


@method_decorator(never_cache, name="dispatch")
class ImageFileView(StaffPublicationMixin, APIView):
    """Transmet un fichier après contrôle de publication, sans URL directe du stockage."""

    permission_classes = [IsAdminOrReadOnly]

    def perform_content_negotiation(self, request, force=False):
        # Le succès est un FileResponse ; conserver un renderer pour les erreurs
        # sans rejeter les clients qui demandent uniquement un type image.
        # Ouai le force=True est une bidouille
        # Ca va c'est plutôt cool non ?
        return super().perform_content_negotiation(request, force=True)


    # Documentation de l'API pour la récupération d'un fichier image.
    @extend_schema(
        responses={
            200: OpenApiResponse(
                response=bytes,
                description="Fichier image après contrôle des droits d'accès.",
            ),
            404: OpenApiResponse(
                description="Image inaccessible, inexistante ou fichier absent.",
            ),
        },
    )
    def get(self, request, pk):
        image = get_object_or_404(Image, pk=pk)
        if not self._is_staff_request():
            # Les deux conditions de page doivent porter sur la même association.
            public = Project.objects.filter(
                images=image, published=True,
            ).exists() or ProjectPage.objects.filter(
                images=image, published=True, project__published=True,
            ).exists()
            if not public:
                raise Http404

        if not image.file:
            raise Http404

        storage = image.file.storage
        file_name = image.file.name

        if not file_name or not storage.exists(file_name):
            raise Http404

        file = storage.open(file_name, "rb")

        return FileResponse(file)


class ImageViewSet(viewsets.ModelViewSet):
    """
    Gère les images indépendamment de leur association
    future à un projet ou à une page.
    """

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminUser]


def remove_image_from_owner(owner, image):
    """
    Retire une image de son propriétaire (Project ou ProjectPage).

    Si l'image n'est plus associée à aucun projet ni aucune page,
    supprime également l'objet Image et son fichier physique.
    """
    owner.images.remove(image)

    if image.projects.exists() or image.pages.exists():
        return

    # Mémorisés avant la suppression de l'objet, qui invaliderait
    # l'accès au fichier associé.
    storage = image.file.storage
    file_name = image.file.name

    image.delete()

    if file_name:
        storage.delete(file_name)


class ProjectImageViewSet(StaffPublicationMixin, viewsets.ModelViewSet):
    """
    Images accessibles dans le contexte d'un projet précis,
    plutôt que via la route racine /images/.
    """

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminOrReadOnly]
    publication_filters = {"published": True}

    def get_queryset(self):  # type: ignore[override]
        """
        Limite les images à celles associées au projet de l'URL.

        Les visiteurs non-staff ne doivent voir que les images
        d'un projet publié.
        """
        project_slug = self.kwargs["project_slug"]

        owners = self.filter_public_queryset(Project.objects.filter(slug=project_slug))
        owner = owners.first()
        # Conserve le contrat des listes : propriétaire absent/invisible -> [].
        if owner is None:
            return Image.objects.none()
        return owner.images.all()

    def perform_create(self, serializer):
        """
        Crée l'image puis l'associe au projet de l'URL.

        Un projet ne peut pas avoir deux images du même thème.
        """
        project = get_object_or_404(
            Project,
            slug=self.kwargs["project_slug"],
        )

        theme = serializer.validated_data.get("theme", "")

        if project.images.filter(theme=theme).exists():
            raise ValidationError(
                {"theme": "Ce projet possède déjà une image pour ce thème."}
            )

        image = serializer.save()
        project.images.add(image)

    def destroy(self, request, *args, **kwargs):
        """
        Retire l'image du projet de l'URL (et la supprime réellement
        si plus aucun autre projet/page ne l'utilise).

        `get_object_or_404(project.images, ...)` garantit que l'image
        appartient bien à ce projet : impossible de supprimer via
        l'URL d'un autre projet l'association d'une image qui ne lui
        appartient pas.
        """
        project = get_object_or_404(
            Project,
            slug=self.kwargs["project_slug"],
        )

        image = get_object_or_404(
            project.images,
            pk=self.kwargs["pk"],
        )

        remove_image_from_owner(project, image)

        return Response(status=status.HTTP_204_NO_CONTENT)

# Ce décorateur permet d'ajouter une action personnalisée "attach" au ViewSet.
# Pour les images associées à une page spécifique, cette action permet de les attacher via une requête POST.
# Comme ça une même image peut être attachée à plusieurs pages sans être recréée.

class ProjectPageImageViewSet(StaffPublicationMixin, viewsets.ModelViewSet):
    """
    Images accessibles dans le contexte d'une page précise,
    plutôt que via la route racine /images/.
    """

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminOrReadOnly]
    publication_filters = {
        "published": True,
        "project__published": True,
    }

    def get_queryset(self):  # type: ignore[override]
        """
        Limite les images à celles associées à la page de l'URL.

        Les visiteurs non-staff ne doivent voir que les images d'une
        page publiée appartenant à un projet publié.
        """
        project_slug = self.kwargs["project_slug"]
        page_slug = self.kwargs["page_slug"]

        owners = ProjectPage.objects.filter(
            project__slug=project_slug,
            slug=page_slug,
        )
        owner = self.filter_public_queryset(owners).first()
        if owner is None:
            return Image.objects.none()
        return owner.images.all()

    def perform_create(self, serializer):
        """
        Crée l'image puis l'associe à la page de l'URL.

        Une page ne peut pas avoir deux images du même thème.
        L'unicité ne s'applique qu'à la page : le même thème peut
        exister sur une autre page ou sur le Project parent.
        """
        page = get_object_or_404(
            ProjectPage,
            project__slug=self.kwargs["project_slug"],
            slug=self.kwargs["page_slug"],
        )

        theme = serializer.validated_data.get("theme", "")

        if page.images.filter(theme=theme).exists():
            raise ValidationError(
                {"theme": "Cette page possède déjà une image pour ce thème."}
            )

        image = serializer.save()
        page.images.add(image)

    @action(detail=False, methods=["post"], url_path="attach")
    def attach(self, request, project_slug=None, page_slug=None):
        """
        Associe à la page une Image déjà existante.
        Aucun nouveau fichier ni objet Image n'est créé.
        """
        page = get_object_or_404(
            ProjectPage,
            project__slug=project_slug,
            slug=page_slug,
        )

        image_id = request.data.get("image_id")

        if not image_id:
            raise ValidationError(
                {"image_id": "L'identifiant de l'image est requis."}
            )

        image = get_object_or_404(Image, pk=image_id)

        if page.images.filter(theme=image.theme).exclude(pk=image.pk).exists():
            raise ValidationError(
                {"theme": "Cette page possède déjà une image pour ce thème."}
            )

        page.images.add(image)

        return Response(
            ImageSerializer(
                image,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        """
        Retire l'image de la page de l'URL (et la supprime réellement
        si plus aucun autre projet/page ne l'utilise).
        """
        page = get_object_or_404(
            ProjectPage,
            project__slug=self.kwargs["project_slug"],
            slug=self.kwargs["page_slug"],
        )

        image = get_object_or_404(
            page.images,
            pk=self.kwargs["pk"],
        )

        remove_image_from_owner(page, image)

        return Response(status=status.HTTP_204_NO_CONTENT)
