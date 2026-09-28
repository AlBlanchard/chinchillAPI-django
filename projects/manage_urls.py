from django.urls import path
from . import manage_views as views

urlpatterns = [
    path("patch/", views.patch_resource, name="projects-manage-patch"),
    path("images/add/", views.add_image, name="projects-manage-add-image"),
    path("images/<uuid:pk>/delete/", views.delete_image_view, name="projects-manage-delete-image"),
    path("<uuid:pk>/delete/", views.delete_project_view, name="projects-manage-delete-project"),
    path("", views.projects_manage, name="projects-manage"),
    path("images/<uuid:pk>/file/", views.staff_image, name="projects-manage-image"),
]
