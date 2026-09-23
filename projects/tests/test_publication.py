import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from projects.models import Highlight, Image, Paragraph, Project, ProjectPage


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def staff_client(db):
    user = get_user_model().objects.create_user(
        username="admin",
        password="password123",
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_public_project_list_hides_drafts(api_client):
    """La liste publique ne renvoie que les projets published=True."""

    Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Publié.",
        started_at="2026-09-01",
        published=True,
    )

    Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Brouillon.",
        started_at="2026-09-01",
        published=False,
    )

    response = api_client.get(reverse("project-list"))

    assert response.status_code == 200
    assert [item["slug"] for item in response.data] == ["lagash"]


@pytest.mark.django_db
def test_public_cannot_access_draft_project_detail(api_client):
    """Un accès direct à un projet brouillon renvoie 404 pour le public."""

    project = Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Brouillon.",
        started_at="2026-09-01",
        published=False,
    )

    response = api_client.get(
        reverse("project-detail", kwargs={"slug": project.slug})
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_staff_sees_draft_projects(staff_client):
    """Un staff authentifié voit aussi les brouillons."""

    Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Brouillon.",
        started_at="2026-09-01",
        published=False,
    )

    list_response = staff_client.get(reverse("project-list"))
    assert list_response.status_code == 200
    assert [item["slug"] for item in list_response.data] == ["uruk"]

    detail_response = staff_client.get(
        reverse("project-detail", kwargs={"slug": "uruk"})
    )
    assert detail_response.status_code == 200


@pytest.mark.django_db
def test_public_cannot_access_draft_page_of_published_project(api_client):
    """Une page brouillon d'un projet publié reste invisible au public."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Publié.",
        started_at="2026-09-01",
        published=True,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=False,
    )

    response = api_client.get(
        reverse(
            "project-pages-detail",
            kwargs={"project_slug": project.slug, "slug": page.slug},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_public_cannot_access_published_page_of_draft_project(api_client):
    """
    Une page marquée published=True n'est pas accessible publiquement
    si son projet parent est lui-même un brouillon.
    """

    project = Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Brouillon.",
        started_at="2026-09-01",
        published=False,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=True,
    )

    response = api_client.get(
        reverse(
            "project-pages-detail",
            kwargs={"project_slug": project.slug, "slug": page.slug},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_staff_sees_draft_pages(staff_client):
    """Un staff authentifié voit les pages brouillons d'un projet brouillon."""

    project = Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Brouillon.",
        started_at="2026-09-01",
        published=False,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=False,
    )

    response = staff_client.get(
        reverse(
            "project-pages-detail",
            kwargs={"project_slug": project.slug, "slug": page.slug},
        )
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_public_cannot_access_paragraphs_of_draft_page(api_client):
    """
    Impossible de contourner la publication en listant les paragraphes
    d'une page brouillon.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Publié.",
        started_at="2026-09-01",
        published=True,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=False,
    )

    Paragraph.objects.create(page=page, content="Secret", position=0)

    response = api_client.get(
        reverse(
            "paragraphs-list",
            kwargs={"project_slug": project.slug, "page_slug": page.slug},
        )
    )

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_public_cannot_access_highlights_of_draft_project(api_client):
    """
    Impossible de contourner la publication en listant les highlights
    d'une page dont le projet est un brouillon.
    """

    project = Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Brouillon.",
        started_at="2026-09-01",
        published=False,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=True,
    )

    Highlight.objects.create(page=page, content="Secret", position=0)

    response = api_client.get(
        reverse(
            "highlights-list",
            kwargs={"project_slug": project.slug, "page_slug": page.slug},
        )
    )

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_public_cannot_access_images_of_draft_project(api_client):
    """
    Impossible de contourner la publication en listant les images
    d'un projet brouillon.
    """

    project = Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Brouillon.",
        started_at="2026-09-01",
        published=False,
    )

    image = Image.objects.create(
        file="projects/uruk.png",
        alt="Uruk",
        theme="dark",
    )

    project.images.add(image)

    response = api_client.get(
        reverse(
            "project-image-list",
            kwargs={"project_slug": project.slug},
        )
    )

    assert response.status_code == 200
    assert response.data == []


@pytest.mark.django_db
def test_public_cannot_access_images_of_draft_page(api_client):
    """
    Impossible de contourner la publication en listant les images
    d'une page brouillon d'un projet publié.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Publié.",
        started_at="2026-09-01",
        published=True,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=False,
    )

    image = Image.objects.create(
        file="projects/architecture.png",
        alt="Architecture",
        theme="dark",
    )

    page.images.add(image)

    response = api_client.get(
        reverse(
            "project-page-image-list",
            kwargs={"project_slug": project.slug, "page_slug": page.slug},
        )
    )

    assert response.status_code == 200
    assert response.data == []
