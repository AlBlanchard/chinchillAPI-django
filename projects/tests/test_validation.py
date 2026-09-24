from datetime import date
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image as PILImage
from rest_framework.test import APIClient

from projects.models import Category, Highlight, Image, Paragraph, Project, ProjectPage, Skill, Technology


@pytest.fixture
def staff_client(db):
    user = get_user_model().objects.create_user(username="staff", is_staff=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def project(db):
    return Project.objects.create(
        title="Original", slug="original", project_type="demo",
        description="Original", started_at="2026-01-01",
    )


def project_payload(**changes):
    return {
        "title": "New", "slug": "new", "project_type": "demo",
        "description": "New", "started_at": "2026-01-01", **changes,
    }


@pytest.mark.parametrize("method", ["patch", "put"])
@pytest.mark.parametrize("pages", [[], [{"slug": "page", "title": "Page"}]])
def test_project_update_rejects_nested_pages(staff_client, project, method, pages):
    page = ProjectPage.objects.create(project=project, slug="existing", title="Existing")
    response = getattr(staff_client, method)(
        reverse("project-detail", kwargs={"slug": project.slug}),
        project_payload(pages=pages), format="json",
    )
    assert response.status_code == 400
    assert "pages" in response.data
    project.refresh_from_db()
    assert project.title == "Original"
    assert ProjectPage.objects.get(pk=page.pk).title == "Existing"


@pytest.mark.parametrize("method", ["post", "patch", "put"])
@pytest.mark.parametrize("field", ["paragraphs", "highlights"])
@pytest.mark.parametrize("children", [[], [{"content": "Nested"}]])
def test_page_writes_reject_nested_content(staff_client, project, method, field, children):
    page = ProjectPage.objects.create(project=project, slug="existing", title="Existing")
    paragraph = Paragraph.objects.create(page=page, content="Original paragraph")
    highlight = Highlight.objects.create(page=page, content="Original highlight")
    url = reverse("project-pages-list", kwargs={"project_slug": project.slug}) if method == "post" else reverse(
        "project-pages-detail", kwargs={"project_slug": project.slug, "slug": page.slug},
    )
    response = getattr(staff_client, method)(
        url, {"slug": "new-page", "title": "Changed", field: children}, format="json",
    )
    assert response.status_code == 400
    assert field in response.data
    page.refresh_from_db()
    assert page.title == "Existing"
    assert ProjectPage.objects.filter(project=project).count() == 1
    assert Paragraph.objects.get(pk=paragraph.pk).content == "Original paragraph"
    assert Highlight.objects.get(pk=highlight.pk).content == "Original highlight"


@pytest.mark.parametrize("method", ["post", "patch", "put"])
def test_page_slug_conflict_returns_400(staff_client, project, method):
    ProjectPage.objects.create(project=project, slug="taken", title="Taken")
    page = ProjectPage.objects.create(project=project, slug="original", title="Original")
    url = reverse("project-pages-list", kwargs={"project_slug": project.slug}) if method == "post" else reverse(
        "project-pages-detail", kwargs={"project_slug": project.slug, "slug": page.slug},
    )
    response = getattr(staff_client, method)(url, {"slug": "taken", "title": "Changed"}, format="json")
    assert response.status_code == 400
    assert "slug" in response.data
    page.refresh_from_db()
    assert page.slug == "original"
    assert ProjectPage.objects.filter(project=project).count() == 2


def test_nested_page_slug_conflict_creates_nothing(staff_client):
    response = staff_client.post(reverse("project-list"), project_payload(pages=[
        {"slug": "same", "title": "First", "paragraphs": [{"content": "Text"}]},
        {"slug": "same", "title": "Second"},
    ]), format="json")
    assert response.status_code == 400
    assert "pages" in response.data
    assert not Project.objects.exists()
    assert not ProjectPage.objects.exists()
    assert not Paragraph.objects.exists()


def test_page_slug_can_be_reused_in_another_project_and_unchanged(staff_client, project):
    other = Project.objects.create(**project_payload())
    ProjectPage.objects.create(project=other, slug="same", title="Other")
    response = staff_client.post(
        reverse("project-pages-list", kwargs={"project_slug": project.slug}),
        {"slug": "same", "title": "Local"}, format="json",
    )
    assert response.status_code == 201
    response = staff_client.patch(reverse("project-pages-detail", kwargs={
        "project_slug": project.slug, "slug": "same",
    }), {"slug": "same", "title": "Updated"}, format="json")
    assert response.status_code == 200
    assert response.data["title"] == "Updated"


@pytest.mark.parametrize("field,model", [("category", Category), ("skills", Skill), ("technologies", Technology)])
@pytest.mark.parametrize("invalid_name", ["C#", "!!!", "x" * 101, "ﬃ" * 34])
@pytest.mark.parametrize("method", ["post", "patch"])
def test_invalid_named_relation_returns_400(staff_client, project, field, model, invalid_name, method):
    model.objects.create(name="C++", slug="c")
    value = invalid_name if field == "category" else [invalid_name]
    url = reverse("project-list") if method == "post" else reverse("project-detail", kwargs={"slug": project.slug})
    response = getattr(staff_client, method)(url, project_payload(**{field: value}), format="json")
    assert response.status_code == 400
    assert field in response.data
    project.refresh_from_db()
    assert project.title == "Original"
    assert Project.objects.count() == 1
    assert model.objects.count() == 1


@pytest.mark.parametrize("field,model", [("skills", Skill), ("technologies", Technology)])
def test_named_slug_collision_inside_one_payload(staff_client, field, model):
    response = staff_client.post(
        reverse("project-list"), project_payload(**{field: ["C++", "C#"]}), format="json",
    )
    assert response.status_code == 400
    assert field in response.data
    assert not model.objects.exists()
    assert not Project.objects.exists()


@pytest.mark.parametrize("field,model", [("category", Category), ("skills", Skill), ("technologies", Technology)])
def test_existing_named_relation_keeps_its_custom_slug(staff_client, field, model):
    existing = model.objects.create(name="C++", slug="cpp")
    value = "C++" if field == "category" else ["C++", "C++"]
    response = staff_client.post(reverse("project-list"), project_payload(**{field: value}), format="json")
    assert response.status_code == 201
    assert model.objects.count() == 1
    existing.refresh_from_db()
    assert existing.slug == "cpp"


def test_project_create_rejects_reversed_dates(staff_client):
    response = staff_client.post(reverse("project-list"), project_payload(
        ended_at="2025-12-31",
    ), format="json")
    assert response.status_code == 400
    assert "ended_at" in response.data
    assert not Project.objects.exists()


@pytest.mark.parametrize("changes", [
    {"ended_at": "2025-12-31"},
    {"started_at": "2026-03-01"},
])
def test_project_patch_dates_uses_existing_values(staff_client, project, changes):
    project.ended_at = date(2026, 2, 1)
    project.save()
    response = staff_client.patch(reverse("project-detail", kwargs={"slug": project.slug}), changes, format="json")
    assert response.status_code == 400
    assert "ended_at" in response.data
    project.refresh_from_db()
    assert str(project.started_at) == "2026-01-01"
    assert str(project.ended_at) == "2026-02-01"


@pytest.mark.parametrize("changes", [
    {"ended_at": None},
    {"ended_at": "2026-01-01"},
    {"started_at": "2026-03-01", "ended_at": "2026-03-02"},
])
def test_project_patch_accepts_valid_dates(staff_client, project, changes):
    response = staff_client.patch(reverse("project-detail", kwargs={"slug": project.slug}), changes, format="json")
    assert response.status_code == 200
    for field, value in changes.items():
        assert response.data[field] == value


def uploaded_image(size):
    buffer = BytesIO()
    PILImage.new("RGB", (1, 1)).save(buffer, format="PNG")
    content = buffer.getvalue().ljust(size, b"\0")
    return SimpleUploadedFile("test.png", content, content_type="image/png")


@pytest.mark.parametrize("route", ["global", "project", "page"])
@pytest.mark.parametrize("size,status_code", [(10 * 1024 * 1024, 201), (10 * 1024 * 1024 + 1, 400)])
def test_image_upload_size_limit(staff_client, project, settings, tmp_path, route, size, status_code):
    settings.MEDIA_ROOT = tmp_path
    if route == "global":
        url = reverse("image-list")
    elif route == "project":
        url = reverse("project-image-list", kwargs={"project_slug": project.slug})
    else:
        page = ProjectPage.objects.create(project=project, slug="page", title="Page")
        url = reverse("project-page-image-list", kwargs={"project_slug": project.slug, "page_slug": page.slug})
    response = staff_client.post(url, {"file": uploaded_image(size), "alt": "Test"}, format="multipart")
    assert response.status_code == status_code
    if status_code == 400:
        assert "file" in response.data
        assert not Image.objects.exists()
        assert not list(tmp_path.rglob("*.png"))
    else:
        assert Image.objects.count() == 1


def test_oversized_image_replacement_keeps_original(staff_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    image = Image.objects.create(file=uploaded_image(100), alt="Original")
    original_name = image.file.name
    response = staff_client.patch(reverse("image-detail", kwargs={"pk": image.pk}), {
        "file": uploaded_image(10 * 1024 * 1024 + 1), "alt": "Changed",
    }, format="multipart")
    assert response.status_code == 400
    assert "file" in response.data
    image.refresh_from_db()
    assert image.file.name == original_name
    assert image.alt == "Original"
    assert image.file.storage.exists(original_name)
