"""
Routes de l'application projects.

DefaultRouter génère automatiquement les routes CRUD standards
à partir des ViewSets enregistrés.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    HighlightViewSet,
    ImageFileView,
    ImageViewSet,
    ParagraphViewSet,
    ProjectImageViewSet,
    ProjectPageImageViewSet,
    ProjectPageViewSet,
    ProjectViewSet,
)


router = DefaultRouter()

# Génère notamment :
# GET    /projects/{slug}/       -> liste
# POST   /projects/{slug}/       -> création
# GET    /projects/{slug}/  -> détail
# PUT    /projects/{slug}/  -> remplacement
# PATCH  /projects/{slug}/  -> modification partielle
# DELETE /projects/{slug}/  -> suppression
router.register(
    "projects",
    ProjectViewSet,
    basename="project",
)

router.register(
    "images",
    ImageViewSet,
    basename="image",
)

# ProjectPageViewSet n'est pas un ViewSet racine : ses pages
# n'existent que dans le contexte d'un projet, d'où ce routage
# manuel plutôt qu'un simple router.register().
project_pages_list = ProjectPageViewSet.as_view({
    "get": "list",
    "post": "create",
})

project_pages_detail = ProjectPageViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
})

# Idem pour les paragraphes : ils n'existent que dans le contexte
# d'une page, elle-même dans le contexte d'un projet.
paragraphs_list = ParagraphViewSet.as_view({
    "get": "list",
    "post": "create",
})

paragraphs_detail = ParagraphViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
})

# Idem pour les highlights : ils n'existent que dans le contexte
# d'une page, elle-même dans le contexte d'un projet.
highlights_list = HighlightViewSet.as_view({
    "get": "list",
    "post": "create",
})

highlights_detail = HighlightViewSet.as_view({
    "get": "retrieve",
    "put": "update",
    "patch": "partial_update",
    "delete": "destroy",
})

# Idem pour les images d'un projet : elles n'existent dans ce contexte
# que via la route du projet, pas via un enregistrement au router.
project_images_list = ProjectImageViewSet.as_view({
    "get": "list",
    "post": "create",
})

project_images_detail = ProjectImageViewSet.as_view({
    "delete": "destroy",
})

# Idem pour les images d'une page : elles n'existent dans ce contexte
# que via la route de la page.
project_page_images_list = ProjectPageImageViewSet.as_view({
    "get": "list",
    "post": "create",
})

project_page_images_detail = ProjectPageImageViewSet.as_view({
    "delete": "destroy",
})

urlpatterns = router.urls + [
    path(
        "images/<uuid:pk>/file/",
        ImageFileView.as_view(),
        name="image-file",
    ),
    path(
        "projects/<slug:project_slug>/pages/",
        project_pages_list,
        name="project-pages-list",
    ),
    path(
        "projects/<slug:project_slug>/pages/<slug:slug>/",
        project_pages_detail,
        name="project-pages-detail",
    ),
    path(
        "projects/<slug:project_slug>/pages/<slug:page_slug>/paragraphs/",
        paragraphs_list,
        name="paragraphs-list",
    ),
    path(
        "projects/<slug:project_slug>/pages/<slug:page_slug>/paragraphs/<uuid:pk>/",
        paragraphs_detail,
        name="paragraphs-detail",
    ),
    path(
        "projects/<slug:project_slug>/pages/<slug:page_slug>/highlights/",
        highlights_list,
        name="highlights-list",
    ),
    path(
        "projects/<slug:project_slug>/pages/<slug:page_slug>/highlights/<uuid:pk>/",
        highlights_detail,
        name="highlights-detail",
    ),
    path(
        "projects/<slug:project_slug>/images/",
        project_images_list,
        name="project-image-list",
    ),
    path(
        "projects/<slug:project_slug>/images/<uuid:pk>/",
        project_images_detail,
        name="project-image-detail",
    ),
    path(
        "projects/<slug:project_slug>/pages/<slug:page_slug>/images/",
        project_page_images_list,
        name="project-page-image-list",
    ),
    path(
        "projects/<slug:project_slug>/pages/<slug:page_slug>/images/<uuid:pk>/",
        project_page_images_detail,
        name="project-page-image-detail",
    ),
]
