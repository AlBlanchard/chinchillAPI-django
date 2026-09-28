"""Interface interne : session Django, staff et CSRF, sans JWT."""
import json
import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from rest_framework.exceptions import ValidationError

from .models import Image, Project, ProjectPage
from .manage_forms import AddImageForm, PatchResourceForm
from .serializers import ImageSerializer, ProjectSerializer, ProjectPageSerializer
from .services import (
    create_project_with_image, image_file_response, update_project,
    attach_image, upload_owner_image, delete_project, delete_unused_image,
    image_associations, ImageFileCleanupError,
)

logger = logging.getLogger(__name__)


def staff_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), reverse("admin:login"))
        if not request.user.is_active or not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def error_rows(detail, path=""):
    """Conserve les chemins de champs et les indices des contenus imbriqués."""
    if isinstance(detail, dict):
        for key, value in detail.items():
            yield from error_rows(value, f"{path}.{key}" if path else str(key))
    elif isinstance(detail, list):
        for index, value in enumerate(detail):
            yield from error_rows(value, f"{path}[{index}]" if isinstance(value, (dict, list)) else path)
    else:
        yield {"field": path, "message": str(detail)}


@never_cache
@staff_required
@require_http_methods(["GET", "POST"])
def projects_manage(request):
    payload = request.POST.get("payload", "")
    alt = request.POST.get("alt", "")
    theme = request.POST.get("theme", "")
    errors = []
    response_status = 200
    if request.method == "POST":
        try:
            data = json.loads(payload)
        except (ValueError, RecursionError) as exc:
            errors = [{"field": "JSON", "message": f"JSON invalide : {exc}"}]
        else:
            project_serializer = ProjectSerializer(data=data, context={"request": request})
            project_serializer.is_valid()
            errors.extend(error_rows(project_serializer.errors, "project"))
            image_serializer = None
            if request.FILES.get("file"):
                image_serializer = ImageSerializer(data={
                    "file": request.FILES["file"], "alt": alt, "theme": theme,
                }, context={"request": request})
                image_serializer.is_valid()
                errors.extend(error_rows(image_serializer.errors, "image"))
            if not errors:
                try:
                    project = create_project_with_image(project_serializer, image_serializer)
                except ValidationError as exc:
                    errors.extend(error_rows(exc.detail))
                except (DatabaseError, OSError):
                    logger.exception("Échec de création Project depuis l'interface staff")
                    response_status = 503
                    errors = [{"field": "Enregistrement", "message":
                        "Écriture en base ou dans le stockage impossible. Le projet n'a pas été créé. "
                        "Réessayez ; si le problème persiste, consultez les journaux serveur."}]
                else:
                    messages.success(request, f"Projet « {project.title} » créé (slug : {project.slug}).")
                    return redirect("projects-manage")
        if errors and response_status == 200:
            response_status = 400
    return render_workspace(request, errors=errors, status=response_status,
                            payload=payload, alt=alt, theme=theme)



@never_cache
@staff_required
@require_GET
def staff_image(request, pk):
    return image_file_response(get_object_or_404(Image, pk=pk))


def render_workspace(request, *, errors=(), status=200, active_form="create", **context):
    images = Paginator(Image.objects.order_by("-created_at", "id"), 24).get_page(request.GET.get("page"))
    projects = Project.objects.order_by("title", "slug").prefetch_related("pages")
    defaults = {
        "images": images, "projects": projects, "errors": errors, "active_form": active_form,
        "patch_form": PatchResourceForm(prefix="patch"), "image_form": AddImageForm(prefix="add"),
    }
    defaults.update(context)
    return render(request, "projects/manage.html", defaults, status=status)


def resolve_destination(data):
    project = get_object_or_404(Project, slug=data["project_slug"])
    if data.get("page_slug"):
        page = ProjectPage.objects.filter(project=project, slug=data["page_slug"]).first()
        if page is None:
            raise Http404("Cette page n'existe pas dans le projet indiqué.")
        return page
    return project


@never_cache
@staff_required
@require_POST
def patch_resource(request):
    form = PatchResourceForm(request.POST, prefix="patch")
    errors = []
    response_status = 400
    if form.is_valid():
        try:
            data = json.loads(form.cleaned_data["payload"])
            target = resolve_destination(form.cleaned_data)
            serializer_class = ProjectSerializer if isinstance(target, Project) else ProjectPageSerializer
            serializer = serializer_class(target, data=data, partial=True, context={"request": request})
            serializer.is_valid(raise_exception=True)
            if isinstance(target, Project):
                update_project(serializer)
            else:
                serializer.save()
        except (ValueError, RecursionError) as exc:
            errors = [{"field": "JSON", "message": f"JSON invalide : {exc}"}]
        except Http404 as exc:
            errors = [{"field": "Destination", "message": str(exc)}]
            response_status = 404
        except ValidationError as exc:
            errors = list(error_rows(exc.detail))
        except DatabaseError:
            logger.exception("Échec du PATCH interne")
            errors = [{"field": "Enregistrement", "message": "Échec d'écriture en base. Rechargez la ressource et réessayez."}]
            response_status = 503
        else:
            messages.success(request, f"« {target.title} » modifié (slug : {target.slug}).")
            return redirect("projects-manage")
    else:
        errors = list(error_rows(form.errors))
    return render_workspace(request, errors=errors, status=response_status,
                            active_form="patch", patch_form=form)


@never_cache
@staff_required
@require_POST
def add_image(request):
    form = AddImageForm(request.POST, request.FILES, prefix="add")
    errors = []
    response_status = 400
    if form.is_valid():
        data = form.cleaned_data
        try:
            owner = resolve_destination(data)
            if data["image_id"]:
                image = get_object_or_404(Image, pk=data["image_id"])
                attach_image(owner, image)
            else:
                serializer = ImageSerializer(data={field: data[field] for field in ("file", "alt", "theme")})
                serializer.is_valid(raise_exception=True)
                upload_owner_image(owner, serializer)
        except Http404 as exc:
            errors = [{"field": "Destination / Image", "message": str(exc)}]
            response_status = 404
        except ValidationError as exc:
            errors = list(error_rows(exc.detail))
        except (DatabaseError, OSError):
            logger.exception("Échec d'ajout d'image depuis l'interface staff")
            errors = [{"field": "Enregistrement", "message": "L'image n'a pas été ajoutée. Échec en base ou dans le stockage ; réessayez."}]
            response_status = 503
        else:
            messages.success(request, f"Image associée à « {owner.title} » ({owner.slug}).")
            return redirect("projects-manage")
    else:
        errors = list(error_rows(form.errors))
    return render_workspace(request, errors=errors, status=response_status,
                            active_form="image", image_form=form)


def confirm_deletion(request, instance, *, kind, delete):
    """GET affiche seulement la confirmation ; POST doit porter le choix explicite."""
    errors = []
    response_status = 200
    label = instance.title if kind == "project" else instance.alt
    identity = str(instance.pk)
    if request.method == "POST":
        if request.POST.get("confirm") != identity:
            errors = [{"field": "Confirmation", "message": "Confirmez explicitement la suppression."}]
            response_status = 400
        else:
            try:
                delete(instance)
            except ValidationError as exc:
                errors = list(error_rows(exc.detail))
                response_status = 400
            except ImageFileCleanupError as exc:
                logger.exception("Fichier à nettoyer après suppression Image")
                messages.error(request, str(exc))
                return redirect("projects-manage")
            except DatabaseError:
                logger.exception("Échec de suppression depuis l'interface staff")
                errors = [{"field": "Suppression", "message": "Suppression impossible en base. Réessayez."}]
                response_status = 503
            else:
                messages.success(request, f"« {label} » supprimé.")
                return redirect("projects-manage")
    return render(request, "projects/confirm_delete.html", {
        "kind": kind, "label": label, "identity": identity, "errors": errors,
        "associations": image_associations(instance) if kind == "image" else [],
    }, status=response_status)


@never_cache
@staff_required
@require_http_methods(["GET", "POST"])
def delete_project_view(request, pk):
    return confirm_deletion(request, get_object_or_404(Project, pk=pk), kind="project", delete=delete_project)


@never_cache
@staff_required
@require_http_methods(["GET", "POST"])
def delete_image_view(request, pk):
    return confirm_deletion(request, get_object_or_404(Image, pk=pk), kind="image", delete=delete_unused_image)
