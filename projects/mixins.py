from django.http import HttpRequest
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from .models import ProjectPage

class StaffPublicationMixin:
    """
    Gère la visibilité du contenu selon l'utilisateur.

    Le staff authentifié voit toutes les ressources.
    Les autres utilisateurs ne voient que le contenu public.
    """

    publication_filters = {}
    request: HttpRequest

    def _is_staff_request(self):
        user = self.request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_staff
        )

    def filter_public_queryset(self, queryset):
        if self._is_staff_request():
            return queryset

        return queryset.filter(**self.publication_filters)



class ProjectPageChildMixin(StaffPublicationMixin):
    """
    Comportement commun aux ressources appartenant à une ProjectPage.
    """

    publication_filters = {
        "page__published": True,
        "page__project__published": True,
    }
    queryset: QuerySet
    kwargs: dict[str, str]

    def get_page(self):
        return get_object_or_404(
            ProjectPage,
            project__slug=self.kwargs["project_slug"],
            slug=self.kwargs["page_slug"],
        )

    def get_queryset(self):
        queryset = self.queryset.filter(
            page__project__slug=self.kwargs["project_slug"],
            page__slug=self.kwargs["page_slug"],
        )

        return self.filter_public_queryset(queryset)

    def perform_create(self, serializer):
        serializer.save(page=self.get_page())