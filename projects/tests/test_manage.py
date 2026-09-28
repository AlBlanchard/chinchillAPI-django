import json
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from PIL import Image as PILImage

from projects.models import Category, Image, Project, ProjectPage
from projects.serializers import ImageSerializer, ProjectSerializer
from projects.services import create_project_with_image

pytestmark = pytest.mark.django_db


def upload():
    buffer = BytesIO()
    PILImage.new("RGB", (3, 3), "green").save(buffer, format="PNG")
    return SimpleUploadedFile("test.png", buffer.getvalue(), content_type="image/png")


@pytest.fixture
def staff(client):
    user = get_user_model().objects.create_user("staff", password="test-password", is_staff=True)
    client.force_login(user)
    return client


@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


@pytest.fixture
def payload():
    return {"title": "Démo", "slug": "demo", "description": "Texte", "project_type": "perso",
            "started_at": "2026-09-01", "category": "Pro", "technologies": ["Django"],
            "skills": ["Backend"], "pages": [{"title": "Page", "slug": "page",
            "paragraphs": [{"content": "Paragraphe"}], "highlights": [{"content": "Point clé"}]}]}


def test_anonymous_redirect(client):
    response = client.get(reverse("projects-manage"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("admin:login") + "?next=")


def test_nonstaff_denied(client):
    client.force_login(get_user_model().objects.create_user("visitor"))
    assert client.get(reverse("projects-manage")).status_code == 403
    assert client.post(reverse("projects-manage"), {}).status_code == 403


def test_staff_screen(staff):
    response = staff.get(reverse("projects-manage"))
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert b"csrfmiddlewaretoken" in response.content
    assert b"manage.css" in response.content


@pytest.mark.parametrize("raw,expected", [('not json', 'JSON invalide'), ('[]', 'dictionary'),
                                         ('null', 'No data'), ('{}', 'title')])
def test_invalid_payload_preserved(staff, raw, expected):
    response = staff.post(reverse("projects-manage"), {"payload": raw})
    assert response.status_code == 400
    assert response.context["payload"] == raw
    assert expected in response.content.decode()
    assert not Project.objects.exists()


def test_nested_error_path(staff, payload):
    payload["pages"][0]["paragraphs"][0]["content"] = ""
    response = staff.post(reverse("projects-manage"), {"payload": json.dumps(payload)})
    assert response.status_code == 400
    assert b"project.pages[0].paragraphs[0].content" in response.content


def test_create_nested_without_image(staff, payload):
    response = staff.post(reverse("projects-manage"), {"payload": json.dumps(payload)}, follow=True)
    assert response.status_code == 200
    project = Project.objects.get()
    assert project.category.name == "Pro"
    assert project.skills.get().name == "Backend"
    assert project.technologies.get().name == "Django"
    assert project.pages.get().paragraphs.get().content == "Paragraphe"
    assert project.pages.get().highlights.get().content == "Point clé"
    assert not Image.objects.exists()
    assert "créé" in response.content.decode()
    staff.get(reverse("projects-manage"))
    assert Project.objects.count() == 1


def test_upload_and_private_library(staff, client, payload, media):
    response = staff.post(reverse("projects-manage"), {"payload": json.dumps(payload),
                         "file": upload(), "alt": "Image privée", "theme": "dark"}, follow=True)
    assert response.status_code == 200
    image = Image.objects.get()
    assert Project.objects.get().images.get() == image
    assert image.file.storage.exists(image.file.name)
    html = response.content.decode()
    assert str(image.pk) in html and "Image privée" in html and "dark" in html
    url = reverse("projects-manage-image", args=[image.pk])
    assert url in html
    assert "/media/" not in html
    response = staff.get(url)
    assert response.status_code == 200
    assert "private" in response["Cache-Control"] and "no-store" in response["Cache-Control"]
    assert b"".join(response.streaming_content).startswith(b"\x89PNG")
    anonymous = Client()
    assert anonymous.get(url).status_code == 302
    anonymous.force_login(get_user_model().objects.create_user("visitor"))
    assert anonymous.get(url).status_code == 403
    # Une session staff ne donne toujours aucun droit sur l'API JWT.
    assert staff.get(reverse("image-file", args=[image.pk])).status_code == 404
    image.file.delete(save=False)
    assert staff.get(url).status_code == 404


@pytest.mark.parametrize("case", ["file", "alt", "theme", "size", "project"])
def test_invalid_upload_no_writes(staff, payload, media, case):
    data = {"payload": json.dumps(payload), "file": upload(), "alt": "Image", "theme": ""}
    if case == "file":
        data["file"] = SimpleUploadedFile("fake.png", b"invalid")
    elif case == "alt":
        data["alt"] = ""
    elif case == "theme":
        data["theme"] = "x" * 51
    elif case == "size":
        data["file"] = SimpleUploadedFile("large.png", upload().read() + b"x" * ImageSerializer.MAX_FILE_SIZE)
    else:
        data["payload"] = "{}"
    response = staff.post(reverse("projects-manage"), data)
    assert response.status_code == 400
    assert not Project.objects.exists() and not Image.objects.exists()
    assert not list(media.rglob("*.png"))


@pytest.mark.parametrize("failure", ["pages", "insert", "attach"])
def test_failure_compensates_storage(staff, payload, media, failure):
    if failure == "pages":
        target = "projects.services.create_pages"
    elif failure == "insert":
        target = "insert"
    else:
        target = "attach"
    effect = IntegrityError("write failed")
    if failure == "attach":
        context = patch.object(Project.images.related_manager_cls, "add", side_effect=effect)
    elif failure == "insert":
        field = Image._meta.get_field("file")
        original = field.pre_save
        def fail_after_file_write(instance, add):
            original(instance, add)
            assert list(media.rglob("*.png"))
            raise IntegrityError("INSERT failed after file write")
        context = patch.object(field, "pre_save", side_effect=fail_after_file_write)
    else:
        context = patch(target, side_effect=effect)
    with context:
        response = staff.post(reverse("projects-manage"), {"payload": json.dumps(payload),
                              "file": upload(), "alt": "Image"})
    assert response.status_code == 503
    assert response.context["payload"] == json.dumps(payload)
    assert not Project.objects.exists() and not ProjectPage.objects.exists()
    assert not Category.objects.exists() and not Image.objects.exists()
    assert not list(media.rglob("*.png"))


@pytest.mark.django_db(transaction=True)
def test_commit_failure_compensates_file(payload, media):
    project = ProjectSerializer(data=payload)
    image = ImageSerializer(data={"file": upload(), "alt": "Image"})
    assert project.is_valid() and image.is_valid()
    from django.db import connection
    with patch.object(connection, "commit", side_effect=IntegrityError("commit failed")):
        with pytest.raises(IntegrityError):
            create_project_with_image(project, image)
    assert not Project.objects.exists() and not Image.objects.exists()
    assert not list(media.rglob("*.png"))


def test_csrf_required(staff, payload):
    client = Client(enforce_csrf_checks=True)
    client.force_login(get_user_model().objects.get(username="staff"))
    url = reverse("projects-manage")
    assert client.post(url, {"payload": json.dumps(payload)}).status_code == 403
    client.get(url)
    response = client.post(url, {"payload": json.dumps(payload),
                           "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
    assert response.status_code == 302


def test_library_pagination(staff):
    Image.objects.bulk_create([Image(alt=f"Image {n}", file="") for n in range(25)])
    response = staff.get(reverse("projects-manage"))
    assert len(response.context["images"]) == 24
    response = staff.get(reverse("projects-manage"), {"page": 2})
    assert len(response.context["images"]) == 1
