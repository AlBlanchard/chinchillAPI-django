from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

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


def _is_staff_request(request):
    """
    Un staff authentifié voit tout le contenu, publié ou non.

    Les autres (anonymes ou authentifiés non-staff) ne doivent voir
    que le contenu publié : c'est une question de queryset, distincte
    de la permission d'écrire (IsAdminOrReadOnly).
    """
    return bool(
        request.user
        and request.user.is_authenticated
        and request.user.is_staff
    )


class ProjectViewSet(viewsets.ModelViewSet):
    """
    Contrôleur CRUD des projets.

    Le serializer valide les données reçues.
    Le contrôleur orchestre la création/modification du Project
    et de ses relations.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [IsAdminOrReadOnly]

    # L'UUID reste la clé primaire technique en base,
    # mais l'API identifie les projets par leur slug lisible.
    lookup_field = "slug"

    def get_queryset(self):  # type: ignore[override]
        """Cache les brouillons aux visiteurs non-staff."""
        queryset = Project.objects.all()

        if _is_staff_request(self.request):
            return queryset

        return queryset.filter(published=True)

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

        # Création des champs directs du Project.
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


class ProjectPageViewSet(viewsets.ModelViewSet):
    # Nécessaire pour que django-stubs infère le bon type de retour
    # pour get_queryset() ci-dessous ; la valeur réelle est ignorée.
    queryset = ProjectPage.objects.all()
    serializer_class = ProjectPageSerializer
    permission_classes = [IsAdminOrReadOnly]
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

        if _is_staff_request(self.request):
            return queryset

        return queryset.filter(published=True, project__published=True)

    def perform_create(self, serializer):
        """
        Le projet parent vient de l'URL et non du JSON envoyé
        par le client.
        """
        project = get_object_or_404(
            Project,
            slug=self.kwargs["project_slug"],
        )

        serializer.save(project=project)


class ParagraphViewSet(viewsets.ModelViewSet):
    queryset = Paragraph.objects.all()
    serializer_class = ParagraphSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):  # type: ignore[override]
        """
        Limite les paragraphes à la page et au projet présents dans l'URL.

        Le filtrage sur toute la hiérarchie empêche d'accéder à un
        paragraphe depuis l'URL d'une autre page ou d'un autre projet.

        Les visiteurs non-staff ne doivent voir que les paragraphes
        d'une page publiée appartenant à un projet publié.
        """
        queryset = Paragraph.objects.filter(
            page__project__slug=self.kwargs["project_slug"],
            page__slug=self.kwargs["page_slug"],
        )

        if _is_staff_request(self.request):
            return queryset

        return queryset.filter(
            page__published=True,
            page__project__published=True,
        )

    def perform_create(self, serializer):
        """
        La page parente est déterminée par l'URL.

        Le client n'a donc pas à envoyer l'UUID de la page
        dans le corps de la requête.
        """
        page = get_object_or_404(
            ProjectPage,
            project__slug=self.kwargs["project_slug"],
            slug=self.kwargs["page_slug"],
        )

        serializer.save(page=page)


class HighlightViewSet(viewsets.ModelViewSet):
    queryset = Highlight.objects.all()
    serializer_class = HighlightSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):  # type: ignore[override]
        """
        Limite les highlights à la page et au projet présents dans l'URL.

        Le filtrage sur toute la hiérarchie empêche d'accéder à un
        highlight depuis l'URL d'une autre page ou d'un autre projet.

        Les visiteurs non-staff ne doivent voir que les highlights
        d'une page publiée appartenant à un projet publié.
        """
        queryset = Highlight.objects.filter(
            page__project__slug=self.kwargs["project_slug"],
            page__slug=self.kwargs["page_slug"],
        )

        if _is_staff_request(self.request):
            return queryset

        return queryset.filter(
            page__published=True,
            page__project__published=True,
        )

    def perform_create(self, serializer):
        """
        La page parente est déterminée par l'URL.

        Le client n'a donc pas à envoyer l'UUID de la page
        dans le corps de la requête.
        """
        page = get_object_or_404(
            ProjectPage,
            project__slug=self.kwargs["project_slug"],
            slug=self.kwargs["page_slug"],
        )

        serializer.save(page=page)


class ImageViewSet(viewsets.ModelViewSet):
    """
    Gère les images indépendamment de leur association
    future à un projet ou à une page.
    """

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminOrReadOnly]


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


class ProjectImageViewSet(viewsets.ModelViewSet):
    """
    Images accessibles dans le contexte d'un projet précis,
    plutôt que via la route racine /images/.
    """

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):  # type: ignore[override]
        """
        Limite les images à celles associées au projet de l'URL.

        Les visiteurs non-staff ne doivent voir que les images
        d'un projet publié.
        """
        project_slug = self.kwargs["project_slug"]

        if _is_staff_request(self.request):
            return Image.objects.filter(projects__slug=project_slug)

        return Image.objects.filter(
            projects__slug=project_slug,
            projects__published=True,
        )

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


class ProjectPageImageViewSet(viewsets.ModelViewSet):
    """
    Images accessibles dans le contexte d'une page précise,
    plutôt que via la route racine /images/.
    """

    queryset = Image.objects.all()
    serializer_class = ImageSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):  # type: ignore[override]
        """
        Limite les images à celles associées à la page de l'URL.

        Les visiteurs non-staff ne doivent voir que les images d'une
        page publiée appartenant à un projet publié.
        """
        project_slug = self.kwargs["project_slug"]
        page_slug = self.kwargs["page_slug"]

        if _is_staff_request(self.request):
            return Image.objects.filter(
                pages__project__slug=project_slug,
                pages__slug=page_slug,
            )

        return Image.objects.filter(
            pages__project__slug=project_slug,
            pages__slug=page_slug,
            pages__published=True,
            pages__project__published=True,
        )

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
