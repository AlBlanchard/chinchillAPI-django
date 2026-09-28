import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from rest_framework.test import APIClient

from projects.models import Image, Project, ProjectPage, Paragraph, Highlight
from projects.services import delete_unused_image
from projects.tests.test_manage import staff, media, upload  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def project():
    return Project.objects.create(title="Epic CRM", slug="epic-crm", description="Avant",
                                  project_type="pro", started_at="2026-01-01")


@pytest.fixture
def page(project):
    return ProjectPage.objects.create(project=project, title="Architecture", slug="architecture")


@pytest.fixture
def image(media):
    return Image.objects.create(file=upload(), alt="Aperçu privé", theme="dark")


def patch_data(project, page=None, payload=None):
    return {"patch-project_slug": project.slug, "patch-page_slug": page.slug if page else "",
            "patch-resource_type": "page" if page else "project",
            "patch-payload": json.dumps(payload if payload is not None else {"published": True})}


def image_data(project, page=None, image=None):
    return {"add-project_slug": project.slug, "add-page_slug": page.slug if page else "",
            "add-image_id": str(image.pk) if image else "", "add-alt": "Nouvelle image", "add-theme": "dark"}


def test_patch_project_relations_and_slug(staff, project):
    changes = {"slug": "nouveau", "description": "Après", "category": "Formation",
               "skills": ["Backend"], "technologies": ["Django"], "published": True}
    response = staff.post(reverse("projects-manage-patch"), patch_data(project, payload=changes), follow=True)
    assert response.status_code == 200
    project.refresh_from_db()
    assert project.slug == "nouveau" and project.description == "Après" and project.published
    assert project.category.name == "Formation" and project.skills.get().name == "Backend"
    assert project.technologies.get().name == "Django"
    assert "nouveau" in response.content.decode()
    response = staff.post(reverse("projects-manage-patch"), patch_data(project, payload={"category": None, "skills": []}))
    assert response.status_code == 302
    project.refresh_from_db()
    assert project.category is None and not project.skills.exists()
    assert project.technologies.count() == 1


@pytest.mark.parametrize("payload,field", [({"pages": []}, "pages"), ({"title": ""}, "title"),
                                          ({"ended_at": "2025-01-01"}, "ended_at"), ([], "non_field_errors")])
def test_invalid_patch_project(staff, project, payload, field):
    data = patch_data(project, payload=payload)
    response = staff.post(reverse("projects-manage-patch"), data)
    assert response.status_code == 400
    assert field in response.content.decode()
    assert response.context["patch_form"]["payload"].value() == data["patch-payload"]
    project.refresh_from_db()
    assert project.description == "Avant"


def test_invalid_patch_json(staff, project):
    data = patch_data(project)
    data["patch-payload"] = "{invalid"
    response = staff.post(reverse("projects-manage-patch"), data)
    assert response.status_code == 400
    assert "JSON invalide" in response.content.decode()
    assert response.context["patch_form"]["payload"].value() == "{invalid"


@pytest.mark.parametrize("case", ["project", "page", "foreign_page"])
def test_patch_missing_or_wrong_destination(staff, project, page, case):
    data = patch_data(project, page)
    if case == "project":
        data["patch-project_slug"] = "missing"
    elif case == "page":
        data["patch-page_slug"] = "missing"
    else:
        other = Project.objects.create(title="Other", slug="other", project_type="pro", description="", started_at="2026-01-01")
        data["patch-project_slug"] = other.slug
    response = staff.post(reverse("projects-manage-patch"), data)
    assert response.status_code == 404
    page.refresh_from_db()
    assert not page.published


def test_patch_page_and_slug_collision(staff, project, page):
    changes = {"title": "Nouveau titre", "subtitle": "Sous-titre", "slug": "new-page", "published": True,
               "layout": "image-top", "position": 3}
    response = staff.post(reverse("projects-manage-patch"), patch_data(project, page, changes))
    assert response.status_code == 302
    page.refresh_from_db()
    assert page.title == "Nouveau titre" and page.subtitle == "Sous-titre" and page.published
    assert page.slug == "new-page" and page.layout == "image-top" and page.position == 3
    ProjectPage.objects.create(project=project, slug="taken", title="Taken")
    response = staff.post(reverse("projects-manage-patch"), patch_data(project, page, {"slug": "taken"}))
    assert response.status_code == 400
    page.refresh_from_db()
    assert page.slug == "new-page"


@pytest.mark.parametrize("changes", [{"layout": "invalid"}, {"paragraphs": []}, {"highlights": []}])
def test_page_validation_unchanged(staff, project, page, changes):
    response = staff.post(reverse("projects-manage-patch"), patch_data(project, page, changes))
    assert response.status_code == 400
    assert next(iter(changes)) in response.content.decode()


@pytest.mark.parametrize("changes", [{"patch-resource_type": "invalid"}, {"patch-resource_type": "page"},
                                      {"patch-page_slug": "unwanted"}, {"patch-project_slug": "bad slug"}])
def test_patch_target_form_validation(staff, project, changes):
    data = patch_data(project)
    data.update(changes)
    assert staff.post(reverse("projects-manage-patch"), data).status_code == 400


def test_patch_database_failure_preserves_input(staff, project):
    data = patch_data(project)
    with patch("projects.services.Project.save", side_effect=IntegrityError("fail")):
        response = staff.post(reverse("projects-manage-patch"), data)
    assert response.status_code == 503
    assert response.context["patch_form"]["payload"].value() == data["patch-payload"]


@pytest.mark.parametrize("destination", ["project", "page"])
def test_attach_uuid_idempotent(staff, project, page, image, destination):
    owner = project if destination == "project" else page
    data = image_data(project, page if destination == "page" else None, image)
    for _ in range(2):
        response = staff.post(reverse("projects-manage-add-image"), data)
        assert response.status_code == 302
    assert owner.images.count() == 1
    assert Image.objects.count() == 1


@pytest.mark.parametrize("case,status", [("invalid_uuid", 400), ("missing_image", 404),
                                         ("missing_project", 404), ("wrong_page", 404),
                                         ("both_sources", 400), ("neither", 400), ("invalid_file", 400),
                                         ("blank_alt", 400), ("large_file", 400)])
def test_image_input_errors(staff, project, page, image, case, status):
    data = image_data(project, image=image)
    if case == "invalid_uuid":
        data["add-image_id"] = "wrong"
    elif case == "missing_image":
        data["add-image_id"] = str(uuid4())
    elif case == "missing_project":
        data["add-project_slug"] = "missing"
    elif case == "wrong_page":
        other = Project.objects.create(title="Other", slug="other", project_type="pro", description="", started_at="2026-01-01")
        data.update({"add-project_slug": other.slug, "add-page_slug": page.slug})
    elif case == "both_sources":
        data["add-file"] = upload()
    elif case == "neither":
        data["add-image_id"] = ""
    else:
        data["add-image_id"] = ""
        data["add-file"] = upload()
        if case == "invalid_file":
            data["add-file"] = SimpleUploadedFile("bad.png", b"not an image")
        elif case == "blank_alt":
            data["add-alt"] = ""
        else:
            data["add-file"] = SimpleUploadedFile("big.png", upload().read() + b"x" * (10 * 1024 * 1024))
    response = staff.post(reverse("projects-manage-add-image"), data)
    assert response.status_code == status
    assert not project.images.exists() and not page.images.exists()
    assert Image.objects.count() == 1
    assert response.context["image_form"]["project_slug"].value() == data["add-project_slug"]


@pytest.mark.parametrize("destination", ["project", "page"])
def test_upload_to_owner(staff, project, page, media, destination):
    owner = project if destination == "project" else page
    data = image_data(project, page if destination == "page" else None)
    data["add-file"] = upload()
    response = staff.post(reverse("projects-manage-add-image"), data)
    assert response.status_code == 302
    image = owner.images.get()
    assert image.alt == "Nouvelle image" and image.theme == "dark"
    assert image.file.storage.exists(image.file.name)
    if destination == "page":
        assert not project.images.exists()


@pytest.mark.parametrize("destination", ["project", "page"])
@pytest.mark.parametrize("source", ["uuid", "upload"])
def test_theme_conflicts(staff, project, page, image, destination, source, media):
    owner = project if destination == "project" else page
    owner.images.add(image)
    second = Image.objects.create(alt="Other", theme="dark", file="")
    data = image_data(project, page if destination == "page" else None, second if source == "uuid" else None)
    if source == "upload":
        data["add-file"] = upload()
    before = list(media.rglob("*.png"))
    response = staff.post(reverse("projects-manage-add-image"), data)
    assert response.status_code == 400
    assert "theme" in response.content.decode()
    assert list(owner.images.all()) == [image]
    assert Image.objects.count() == 2
    assert list(media.rglob("*.png")) == before


@pytest.mark.parametrize("destination", ["project", "page"])
def test_upload_association_failure_cleans_file(staff, project, page, media, destination):
    owner = project if destination == "project" else page
    data = image_data(project, page if destination == "page" else None)
    data["add-file"] = upload()
    with patch.object(type(owner).images.related_manager_cls, "add", side_effect=IntegrityError("fail")):
        response = staff.post(reverse("projects-manage-add-image"), data)
    assert response.status_code == 503
    assert not Image.objects.exists() and not list(media.rglob("*.png"))


@pytest.mark.parametrize("missing", [False, True])
def test_delete_orphan_image(staff, image, missing, django_capture_on_commit_callbacks):
    pk, storage, name = image.pk, image.file.storage, image.file.name
    if missing:
        storage.delete(name)
    url = reverse("projects-manage-delete-image", args=[pk])
    response = staff.get(url)
    assert response.status_code == 200 and str(pk) in response.content.decode()
    assert image.alt in response.content.decode()
    assert Image.objects.filter(pk=pk).exists()
    assert staff.post(url, {}).status_code == 400
    assert Image.objects.filter(pk=pk).exists()
    with django_capture_on_commit_callbacks(execute=True):
        response = staff.post(url, {"confirm": str(pk)})
        assert storage.exists(name) == (not missing)  # Aucun effacement avant commit.
    assert response.status_code == 302
    assert not Image.objects.filter(pk=pk).exists() and not storage.exists(name)


@pytest.mark.parametrize("destination", ["project", "page"])
def test_delete_used_image_refused(staff, project, page, image, destination):
    owner = project if destination == "project" else page
    owner.images.add(image)
    url = reverse("projects-manage-delete-image", args=[image.pk])
    response = staff.get(url)
    assert owner.title in response.content.decode()
    response = staff.post(url, {"confirm": str(image.pk)})
    assert response.status_code == 400
    assert owner.slug in response.content.decode()
    assert Image.objects.filter(pk=image.pk).exists() and image.file.storage.exists(image.file.name)


def test_delete_image_rollback_keeps_file(image, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                delete_unused_image(image)
                raise IntegrityError("rollback")
    assert not callbacks
    assert Image.objects.filter(pk=image.pk).exists() and image.file.storage.exists(image.file.name)


@pytest.mark.django_db(transaction=True)
def test_delete_image_storage_failure_reported(staff, image):
    pk = image.pk
    with patch.object(image.file.storage, "delete", side_effect=PermissionError("locked")):
        response = staff.post(reverse("projects-manage-delete-image", args=[pk]), {"confirm": str(pk)}, follow=True)
    assert response.status_code == 200
    assert "nettoyage du stockage" in response.content.decode()
    assert not Image.objects.filter(pk=pk).exists()
    assert image.file.storage.exists(image.file.name)


@pytest.mark.parametrize("file_case", ["empty", "missing_raises"])
def test_delete_file_edge_cases(staff, media, file_case, django_capture_on_commit_callbacks):
    image = Image.objects.create(alt="Absent", file="" if file_case == "empty" else "gone.png")
    with patch.object(image.file.storage, "delete", side_effect=FileNotFoundError):
        with django_capture_on_commit_callbacks(execute=True):
            response = staff.post(reverse("projects-manage-delete-image", args=[image.pk]), {"confirm": str(image.pk)})
    assert response.status_code == 302 and not Image.objects.exists()


def test_delete_project_cascades_and_retains_images(staff, project, page, image):
    project.images.add(image)
    page.images.add(image)
    Paragraph.objects.create(page=page, content="Text")
    Highlight.objects.create(page=page, content="Highlight")
    other = Project.objects.create(title="Other", slug="other", project_type="pro", description="", started_at="2026-01-01")
    other.images.add(image)
    orphan = Image.objects.create(alt="Projet seulement", file="", theme="light")
    project.images.add(orphan)
    url = reverse("projects-manage-delete-project", args=[project.pk])
    assert staff.get(url).status_code == 200
    assert Project.objects.filter(pk=project.pk).exists()
    assert staff.post(url, {}).status_code == 400
    response = staff.post(url, {"confirm": str(project.pk)})
    assert response.status_code == 302
    assert not Project.objects.filter(pk=project.pk).exists()
    assert not ProjectPage.objects.exists() and not Paragraph.objects.exists() and not Highlight.objects.exists()
    assert other.images.get() == image and Image.objects.filter(pk=orphan.pk).exists()
    assert image.file.storage.exists(image.file.name)


@pytest.mark.parametrize("kind", ["image", "project"])
def test_delete_missing_target(staff, kind):
    url = reverse(f"projects-manage-delete-{kind}", args=[uuid4()])
    assert staff.get(url).status_code == 404
    assert staff.post(url, {"confirm": "yes"}).status_code == 404


def test_delete_database_failure(staff, project):
    with patch("projects.services.Project.delete", side_effect=IntegrityError("fail")):
        response = staff.post(reverse("projects-manage-delete-project", args=[project.pk]), {"confirm": str(project.pk)})
    assert response.status_code == 503 and Project.objects.filter(pk=project.pk).exists()


@pytest.mark.parametrize("route", ["patch", "add-image", "delete-project", "delete-image"])
def test_mutation_access_and_csrf(client, staff, project, image, route):
    pk = image.pk if route == "delete-image" else project.pk
    url = reverse(f"projects-manage-{route}", args=[pk] if route.startswith("delete") else [])
    anonymous = Client()
    assert anonymous.post(url, {}).status_code == 302
    anonymous.force_login(get_user_model().objects.create_user("visitor"))
    assert anonymous.post(url, {}).status_code == 403
    assert anonymous.get(url).status_code == 403
    secure = Client(enforce_csrf_checks=True)
    secure.force_login(get_user_model().objects.get(username="staff"))
    assert secure.post(url, {}).status_code == 403
    assert staff.delete(url).status_code == 405
    if route in ("patch", "add-image"):
        assert staff.get(url).status_code == 405


def test_navigation_order_and_copy(staff, project):
    late = ProjectPage.objects.create(project=project, title="Dernière", slug="last", position=8)
    early = ProjectPage.objects.create(project=project, title="Première", slug="first", position=1)
    response = staff.get(reverse("projects-manage"))
    html = response.content.decode()
    assert project.title in html and f'data-copy="{project.slug}"' in html
    assert html.index(f'data-copy="{early.slug}"') < html.index(f'data-copy="{late.slug}"')
    assert list(response.context["projects"][0].pages.all()) == [early, late]


def test_api_page_attach_shared_service(staff, project, page, image):
    api = APIClient()
    api.force_authenticate(get_user_model().objects.get(username="staff"))
    url = reverse("project-page-image-attach", kwargs={"project_slug": project.slug, "page_slug": page.slug})
    assert api.post(url, {}, format="json").status_code == 400
    for _ in range(2):
        assert api.post(url, {"image_id": str(image.pk)}, format="json").status_code == 200
    assert page.images.count() == 1
    second = Image.objects.create(alt="Other", theme=image.theme, file="")
    assert api.post(url, {"image_id": str(second.pk)}, format="json").status_code == 400


def test_image_associated_after_confirmation_is_protected(staff, project, image):
    url = reverse("projects-manage-delete-image", args=[image.pk])
    assert staff.get(url).status_code == 200
    project.images.add(image)
    response = staff.post(url, {"confirm": str(image.pk)})
    assert response.status_code == 400
    assert project.title in response.content.decode()
    assert Image.objects.filter(pk=image.pk).exists()


def test_api_project_delete_keeps_image_contract(staff, project, page, image):
    project.images.add(image)
    page.images.add(image)
    api = APIClient()
    api.force_authenticate(get_user_model().objects.get(username="staff"))
    response = api.delete(reverse("project-detail", kwargs={"slug": project.slug}))
    assert response.status_code == 204
    assert not Project.objects.exists() and not ProjectPage.objects.exists()
    assert Image.objects.filter(pk=image.pk).exists() and image.file.storage.exists(image.file.name)


def test_api_global_image_delete_keeps_historical_contract(staff, project, image):
    project.images.add(image)
    api = APIClient()
    api.force_authenticate(get_user_model().objects.get(username="staff"))
    response = api.delete(reverse("image-detail", kwargs={"pk": image.pk}))
    assert response.status_code == 204
    assert not Image.objects.exists() and not project.images.exists()
    assert image.file.storage.exists(image.file.name)
