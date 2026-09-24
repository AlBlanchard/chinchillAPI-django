from io import BytesIO
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image as PILImage
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from projects.models import Image, Project, ProjectPage
from projects.serializers import ImageSerializer


@pytest.fixture
def stored_image(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "private-media"
    buffer = BytesIO()
    PILImage.new("RGB", (2, 2), color="red").save(buffer, format="PNG")
    content = buffer.getvalue()
    image = Image.objects.create(
        file=SimpleUploadedFile("sample.png", content, content_type="image/png"),
        alt="Sample",
    )
    return image, content


def associate(image, kind, suffix="owner"):
    if kind == "unowned":
        return None
    project = Project.objects.create(
        title="Project", slug=suffix, project_type="demo", description="Demo",
        started_at="2026-01-01", published=kind in {"public_project", "public_page", "draft_page"},
    )
    if kind in {"public_project", "draft_project"}:
        project.images.add(image)
        return project
    page = ProjectPage.objects.create(
        project=project, slug="page", title="Page", published=kind != "draft_page",
    )
    page.images.add(image)
    return page


def client_for(role):
    client = APIClient()
    if role != "anonymous":
        user = get_user_model().objects.create_user(username=role, is_staff=role == "staff")
        # Vérifie l'authentification réelle de la route fichier, sans la contourner.
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return client


@pytest.mark.parametrize("role", ["anonymous", "visitor", "staff"])
@pytest.mark.parametrize("kind", [
    "public_project", "draft_project", "public_page", "draft_page",
    "page_of_draft_project", "unowned",
])
def test_image_file_publication(stored_image, role, kind):
    image, content = stored_image
    associate(image, kind)
    response = client_for(role).get(reverse("image-file", kwargs={"pk": image.pk}))
    allowed = role == "staff" or kind in {"public_project", "public_page"}
    assert response.status_code == (200 if allowed else 404)
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    if allowed:
        assert response.streaming
        assert response["Content-Type"] == "image/png"
        assert int(response["Content-Length"]) == len(content)
        try:
            assert b"".join(response.streaming_content) == content
        finally:
            response.close()


@pytest.mark.parametrize("owners,public", [
    (["draft_project", "public_project"], True),
    (["draft_page", "public_page"], True),
    (["draft_project", "public_page"], True),
    (["public_project", "page_of_draft_project"], True),
    (["draft_page", "page_of_draft_project"], False),
])
def test_shared_image_requires_one_really_public_owner(stored_image, owners, public):
    image, content = stored_image
    for index, kind in enumerate(owners):
        associate(image, kind, suffix=f"owner-{index}")
    response = APIClient().get(reverse("image-file", kwargs={"pk": image.pk}))
    assert response.status_code == (200 if public else 404)
    if public:
        try:
            assert b"".join(response.streaming_content) == content
        finally:
            response.close()


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["anonymous", "staff"])
def test_unknown_image_uuid_returns_404(role):
    response = client_for(role).get(reverse("image-file", kwargs={"pk": uuid4()}))
    assert response.status_code == 404


@pytest.mark.parametrize("role", ["anonymous", "staff"])
def test_missing_image_file_returns_404(stored_image, role):
    image, _ = stored_image
    associate(image, "public_project")
    image.file.storage.delete(image.file.name)
    response = client_for(role).get(reverse("image-file", kwargs={"pk": image.pk}))
    assert response.status_code == 404


def test_private_image_does_not_open_storage(stored_image, monkeypatch):
    image, _ = stored_image
    def unexpected_open(*args, **kwargs):
        pytest.fail("Un visiteur ne doit pas ouvrir le fichier privé.")
    monkeypatch.setattr(image.file.storage, "open", unexpected_open)
    assert APIClient().get(reverse("image-file", kwargs={"pk": image.pk})).status_code == 404


def test_unpublishing_image_owner_revokes_public_access(stored_image):
    image, content = stored_image
    project = associate(image, "public_project")
    assert isinstance(project, Project)
    url = reverse("image-file", kwargs={"pk": image.pk})
    response = APIClient().get(url)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    assert b"".join(response.streaming_content) == content
    project.published = False
    project.save(update_fields=["published"])
    assert APIClient().get(url).status_code == 404


@pytest.mark.parametrize("with_request", [False, True])
def test_serializer_file_is_controlled_url(stored_image, with_request):
    image, _ = stored_image
    context = {"request": APIRequestFactory().get("/")} if with_request else {}
    data = ImageSerializer(image, context=context).data
    path = reverse("image-file", kwargs={"pk": image.pk})
    assert data["file"] == (f"http://testserver{path}" if with_request else path)
    assert set(data) == {"id", "file", "alt", "theme", "created_at"}
    assert image.file.name not in data["file"]


def test_nested_image_urls_use_controlled_route(stored_image):
    image, _ = stored_image
    project = associate(image, "public_project")
    assert isinstance(project, Project)
    page = ProjectPage.objects.create(project=project, slug="page", title="Page", published=True)
    page.images.add(image)
    response = APIClient().get(reverse("project-detail", kwargs={"slug": project.slug}))
    expected = f"http://testserver{reverse('image-file', kwargs={'pk': image.pk})}"
    assert response.data["images"][0]["file"] == expected
    assert response.data["pages"][0]["images"][0]["file"] == expected


@pytest.mark.parametrize("debug", [False, True])
def test_storage_url_is_not_served_directly(stored_image, settings, debug):
    image, _ = stored_image
    settings.DEBUG = debug
    assert APIClient().get(f"/media/{image.file.name}").status_code == 404


@pytest.mark.parametrize("public", [False, True])
def test_head_obeys_publication(stored_image, public):
    image, _ = stored_image
    associate(image, "public_project" if public else "draft_project")
    response = APIClient().head(reverse("image-file", kwargs={"pk": image.pk}))
    assert response.status_code == (200 if public else 404)
    response.close()


def test_image_file_route_does_not_accept_writes(stored_image):
    image, _ = stored_image
    response = client_for("staff").post(reverse("image-file", kwargs={"pk": image.pk}))
    assert response.status_code == 405


def test_file_request_accepts_image_content_type(stored_image):
    image, content = stored_image
    associate(image, "public_project")
    response = APIClient().get(
        reverse("image-file", kwargs={"pk": image.pk}), HTTP_ACCEPT="image/png",
    )
    assert response.status_code == 200
    try:
        assert b"".join(response.streaming_content) == content
    finally:
        response.close()


def test_empty_file_reference_returns_404_and_null_url(stored_image):
    image, _ = stored_image
    image.file = ""
    image.save(update_fields=["file"])
    assert ImageSerializer(image).data["file"] is None
    assert client_for("staff").get(reverse("image-file", kwargs={"pk": image.pk})).status_code == 404


def test_multipart_upload_returns_usable_controlled_url(stored_image):
    _, content = stored_image
    client = client_for("staff")
    response = client.post(reverse("image-list"), {
        "file": SimpleUploadedFile("new.png", content, content_type="image/png"),
        "alt": "New",
    }, format="multipart")
    assert response.status_code == 201
    expected_path = reverse("image-file", kwargs={"pk": response.data["id"]})
    assert response.data["file"] == f"http://testserver{expected_path}"
    file_response = client.get(expected_path)
    assert file_response.status_code == 200
    try:
        assert b"".join(file_response.streaming_content) == content
    finally:
        file_response.close()
