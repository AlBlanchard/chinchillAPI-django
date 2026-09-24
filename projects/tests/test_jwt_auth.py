import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from projects.models import Project


@pytest.fixture
def admin_user(db):
    return get_user_model().objects.create_user(
        username="admin",
        password="password123",
        is_staff=True,
    )


@pytest.fixture
def visitor_user(db):
    """Utilisateur Django standard, sans droits d'administration."""
    return get_user_model().objects.create_user(
        username="visitor",
        password="password123",
        is_staff=False,
    )


def obtain_tokens(username, password):
    return APIClient().post(
        reverse("token_obtain_pair"),
        {"username": username, "password": password},
        format="json",
    )


@pytest.mark.django_db
def test_admin_can_obtain_tokens_with_valid_credentials(admin_user):
    """Des identifiants admin valides renvoient un access et un refresh token."""

    response = obtain_tokens("admin", "password123")

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_token_obtain_rejects_wrong_password(admin_user):
    """Un mauvais mot de passe est refusé."""

    response = obtain_tokens("admin", "wrong-password")

    assert response.status_code == 401


@pytest.mark.django_db
def test_admin_access_token_authorizes_protected_write(admin_user):
    """Un access token admin autorise un POST protégé."""

    tokens = obtain_tokens("admin", "password123").data

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    payload = {
        "title": "Lagash",
        "slug": "lagash",
        "project_type": "Projet professionnel",
        "description": "Application de démonstration.",
        "started_at": "2026-09-01",
    }

    response = client.post(
        reverse("project-list"),
        payload,
        format="json",
    )

    assert response.status_code == 201
    assert Project.objects.filter(slug="lagash").exists()


@pytest.mark.django_db
def test_non_staff_access_token_forbids_protected_write(visitor_user):
    """Un access token d'un utilisateur non-staff refuse le POST protégé."""

    tokens = obtain_tokens("visitor", "password123").data

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    payload = {
        "title": "Lagash",
        "slug": "lagash",
        "project_type": "Projet professionnel",
        "description": "Application de démonstration.",
        "started_at": "2026-09-01",
    }

    response = client.post(
        reverse("project-list"),
        payload,
        format="json",
    )

    assert response.status_code == 403
    assert not Project.objects.filter(slug="lagash").exists()


@pytest.mark.django_db
def test_no_token_forbids_protected_write():
    """Sans token, l'écriture reste refusée (401 : aucune credential fournie)."""

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

    assert response.status_code == 401
    assert not Project.objects.filter(slug="lagash").exists()


@pytest.mark.django_db
def test_refresh_token_provides_new_access_token(admin_user):
    """Un refresh token valide permet d'obtenir un nouvel access token."""

    tokens = obtain_tokens("admin", "password123").data

    response = APIClient().post(
        reverse("token_refresh"),
        {"refresh": tokens["refresh"]},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data

    # Le nouvel access token doit lui aussi autoriser une écriture admin.
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    payload = {
        "title": "Lagash",
        "slug": "lagash",
        "project_type": "Projet professionnel",
        "description": "Application de démonstration.",
        "started_at": "2026-09-01",
    }

    write_response = client.post(
        reverse("project-list"),
        payload,
        format="json",
    )

    assert write_response.status_code == 201
