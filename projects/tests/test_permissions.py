import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from projects.models import Project, ProjectPage
from projects.permissions import IsAdminOrReadOnly


class DummyRequest:
    """Simule uniquement les attributs lus par IsAdminOrReadOnly."""

    def __init__(self, method, user):
        self.method = method
        self.user = user


class DummyUser:
    def __init__(self, is_authenticated, is_staff):
        self.is_authenticated = is_authenticated
        self.is_staff = is_staff


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_permission_allows_safe_methods_for_anyone(method):
    request = DummyRequest(method, DummyUser(is_authenticated=False, is_staff=False))
    assert IsAdminOrReadOnly().has_permission(request, view=None) is True


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_permission_denies_write_methods_for_anonymous(method):
    request = DummyRequest(method, DummyUser(is_authenticated=False, is_staff=False))
    assert IsAdminOrReadOnly().has_permission(request, view=None) is False


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_permission_denies_write_methods_for_non_staff_user(method):
    request = DummyRequest(method, DummyUser(is_authenticated=True, is_staff=False))
    assert IsAdminOrReadOnly().has_permission(request, view=None) is False


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_permission_allows_write_methods_for_staff_user(method):
    request = DummyRequest(method, DummyUser(is_authenticated=True, is_staff=True))
    assert IsAdminOrReadOnly().has_permission(request, view=None) is True


@pytest.fixture
def project(db):
    return Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )


@pytest.fixture
def staff_client(db):
    """Client authentifié comme administrateur (is_staff=True)."""
    user = get_user_model().objects.create_user(
        username="admin",
        password="password",
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def authenticated_client(db):
    """Client authentifié mais sans droits d'administration."""
    user = get_user_model().objects.create_user(
        username="visitor",
        password="password",
        is_staff=False,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_anonymous_can_read_project_list():
    """GET reste public même sans authentification."""

    response = APIClient().get(reverse("project-list"))

    assert response.status_code == 200


@pytest.mark.django_db
def test_anonymous_cannot_create_project():
    """POST anonyme est refusé."""

    payload = {
        "title": "Lagash",
        "slug": "lagash",
        "project_type": "Projet professionnel",
        "description": "Application de démonstration.",
        "started_at": "2026-09-01",
    }

    response = APIClient().post(
        reverse("project-list"),
        payload,
        format="json",
    )

    # 401 : DRF distingue "pas de credentials" (NotAuthenticated) de
    # "credentials insuffisants" (PermissionDenied) une fois un backend
    # d'authentification (JWT) configuré.
    assert response.status_code == 401
    assert not Project.objects.filter(slug="lagash").exists()


@pytest.mark.django_db
def test_anonymous_cannot_patch_project(project):
    """PATCH anonyme est refusé."""

    response = APIClient().patch(
        reverse("project-detail", kwargs={"slug": project.slug}),
        {"title": "Nouveau titre"},
        format="json",
    )

    assert response.status_code == 401

    project.refresh_from_db()
    assert project.title == "Lagash"


@pytest.mark.django_db
def test_anonymous_cannot_delete_project(project):
    """DELETE anonyme est refusé."""

    response = APIClient().delete(
        reverse("project-detail", kwargs={"slug": project.slug})
    )

    assert response.status_code == 401
    assert Project.objects.filter(pk=project.pk).exists()


@pytest.mark.django_db
def test_authenticated_non_staff_cannot_write_project(
    authenticated_client,
    project,
):
    """Un utilisateur authentifié mais non-staff ne peut pas écrire."""

    response = authenticated_client.patch(
        reverse("project-detail", kwargs={"slug": project.slug}),
        {"title": "Nouveau titre"},
        format="json",
    )

    assert response.status_code == 403

    project.refresh_from_db()
    assert project.title == "Lagash"


@pytest.mark.django_db
def test_staff_user_can_write_project(staff_client, project):
    """Un utilisateur is_staff=True peut écrire."""

    response = staff_client.patch(
        reverse("project-detail", kwargs={"slug": project.slug}),
        {"title": "Nouveau titre"},
        format="json",
    )

    assert response.status_code == 200

    project.refresh_from_db()
    assert project.title == "Nouveau titre"


@pytest.mark.django_db
def test_anonymous_cannot_create_project_page(project):
    """
    La permission s'applique aussi aux ViewSets imbriqués
    (ProjectPageViewSet ici), pas seulement à ProjectViewSet.
    """

    response = APIClient().post(
        reverse("project-pages-list", kwargs={"project_slug": project.slug}),
        {"slug": "architecture", "title": "Architecture"},
        format="json",
    )

    assert response.status_code == 401
    assert not ProjectPage.objects.filter(slug="architecture").exists()
