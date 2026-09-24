import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from projects.models import Highlight, Image, Paragraph, Project, ProjectPage


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["anonymous", "visitor", "staff"])
@pytest.mark.parametrize("endpoint", ["list", "detail"])
def test_project_representation_filters_nested_drafts(role, endpoint):
    client = APIClient()
    if role != "anonymous":
        user = get_user_model().objects.create_user(
            username=role, is_staff=role == "staff",
        )
        client.force_authenticate(user=user)
    project = Project.objects.create(
        title="Public", slug="public", project_type="demo",
        description="Public", started_at="2026-01-01", published=True,
    )
    public_page = ProjectPage.objects.create(
        project=project, slug="public", title="Public", published=True,
    )
    draft_page = ProjectPage.objects.create(
        project=project, slug="draft", title="Draft", published=False,
    )
    Paragraph.objects.create(page=draft_page, content="Secret paragraph")
    Highlight.objects.create(page=draft_page, content="Secret highlight")
    Paragraph.objects.create(page=public_page, content="Public paragraph")
    url = reverse("project-list") if endpoint == "list" else reverse(
        "project-detail", kwargs={"slug": project.slug},
    )
    response = client.get(url)
    assert response.status_code == 200
    data = response.data[0] if endpoint == "list" else response.data
    pages = {page["slug"]: page for page in data["pages"]}
    assert pages["public"]["paragraphs"][0]["content"] == "Public paragraph"
    if role == "staff":
        assert set(pages) == {"public", "draft"}
        assert pages["draft"]["paragraphs"][0]["content"] == "Secret paragraph"
        assert pages["draft"]["highlights"][0]["content"] == "Secret highlight"
    else:
        assert set(pages) == {"public"}
        assert "Secret" not in str(response.data)


@pytest.mark.django_db
def test_project_list_queries_do_not_grow_with_nested_content(django_assert_num_queries):
    for index in range(3):
        project = Project.objects.create(
            title="Public", slug=f"public-{index}", project_type="demo",
            description="Public", started_at="2026-01-01", published=True,
        )
        for position in range(2):
            page = ProjectPage.objects.create(
                project=project, slug=f"page-{position}", title="Page", published=True,
            )
            Paragraph.objects.create(page=page, content="Paragraph")
            Highlight.objects.create(page=page, content="Highlight")
    with django_assert_num_queries(8):
        response = APIClient().get(reverse("project-list"))
    assert response.status_code == 200
    assert len(response.data) == 3


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
@pytest.mark.parametrize("role,status_code", [("anonymous", 401), ("visitor", 403), ("staff", 200)])
@pytest.mark.parametrize("endpoint", ["list", "detail"])
def test_global_images_are_staff_only(role, status_code, endpoint):
    image = Image.objects.create(file="projects/unowned.png", alt="Unowned")
    client = APIClient()
    if role != "anonymous":
        user = get_user_model().objects.create_user(username=role, is_staff=role == "staff")
        client.force_authenticate(user=user)
    url = reverse("image-list") if endpoint == "list" else reverse(
        "image-detail", kwargs={"pk": image.pk},
    )
    assert client.get(url).status_code == status_code


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["anonymous", "visitor", "staff"])
@pytest.mark.parametrize("owner_type", ["project", "page", "page_of_draft_project"])
def test_shared_image_visibility_is_scoped_to_requested_owner(role, owner_type):
    client = APIClient()
    if role != "anonymous":
        user = get_user_model().objects.create_user(username=role, is_staff=role == "staff")
        client.force_authenticate(user=user)
    image = Image.objects.create(file="projects/shared.png", alt="Shared")
    urls = []
    for index in range(3):
        published = index != 0
        project = Project.objects.create(
            title="Project", slug=f"project-{index}", project_type="demo",
            description="Demo", started_at="2026-01-01",
            published=published if owner_type != "page" else True,
        )
        if owner_type == "project":
            project.images.add(image)
            urls.append(reverse("project-image-list", kwargs={"project_slug": project.slug}))
        else:
            page = ProjectPage.objects.create(
                project=project, slug="page", title="Page",
                published=published if owner_type == "page" else True,
            )
            page.images.add(image)
            urls.append(reverse("project-page-image-list", kwargs={
                "project_slug": project.slug, "page_slug": page.slug,
            }))
    for index, url in enumerate(urls):
        response = client.get(url)
        assert response.status_code == 200
        expected_ids = [str(image.pk)] if index != 0 or role == "staff" else []
        assert [item["id"] for item in response.data] == expected_ids


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
