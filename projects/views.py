from django.db.models import Prefetch, QuerySet
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
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
    Highlight,
    Paragraph,
    Project,
    ProjectPage,
    Image,
)
from .serializers import (
    HighlightSerializer,
    ParagraphSerializer,
    ProjectPageSerializer,
    ProjectSerializer,
    ImageSerializer,
)
from .services import (
    create_project,
    image_file_response, upload_project_image, upload_owner_image,
    update_project, attach_image, remove_image_from_owner, delete_project,
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

    def perform_create(self, serializer):
        create_project(serializer)

    def perform_update(self, serializer):
        update_project(serializer)

    def perform_destroy(self, instance):
        delete_project(instance)


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

        return image_file_response(image)


class ImageViewSet(viewsets.ModelViewSet):
    """
    Gère les images indépendamment de leur association
    future à un projet ou à une page.
    """

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminUser]



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

        upload_project_image(project, serializer)

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

        upload_owner_image(page, serializer)

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

        attach_image(page, image)

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
