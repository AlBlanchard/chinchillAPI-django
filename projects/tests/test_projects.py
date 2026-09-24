import pytest
from rest_framework.test import APIClient

from django.contrib.auth import get_user_model
from django.core.files import File
from django.urls import reverse
from django.test import override_settings

from PIL import Image as PILImage

from projects.models import Category, Highlight, Paragraph, Project, ProjectPage, Skill, Technology, Image


@pytest.fixture
def api_client():
    """
    Fournit un client HTTP DRF aux tests.

    APIClient permet d'envoyer des requêtes à notre API presque
    comme le ferait le frontend ou Postman.
    """
    return APIClient()


@pytest.fixture
def admin_client(db):
    """
    Fournit un client authentifié comme un administrateur (is_staff=True).

    force_authenticate contourne l'authentification réelle : seule
    la couche de permissions est testée ici.
    """
    user = get_user_model().objects.create_user(
        username="admin",
        password="password",
        is_staff=True,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    return client


@pytest.mark.django_db
def test_create_project_with_relations(admin_client):
    """
    Vérifie qu'un POST peut créer un projet à partir de noms lisibles.

    Les Category, Skill et Technology inexistants doivent être créés
    automatiquement puis associés au projet.
    """

    payload = {
        "title": "Lagash",
        "slug": "lagash",
        "project_type": "Projet professionnel",
        "description": "Application de démonstration.",
        "category": "Projet pro",
        "skills": [
            "Backend",
            "Frontend",
        ],
        "technologies": [
            "Django",
            "React",
            "PostgreSQL",
        ],
        "started_at": "2026-09-01",
        "published": True,
    }

    response = admin_client.post(
        reverse("project-list"),
        payload,
        format="json",
    )

    assert response.status_code == 201

@pytest.mark.django_db
def test_create_project_reuses_existing_relations(admin_client):
    """
    Vérifie qu'une catégorie, une compétence ou une technologie
    déjà présente en base est réutilisée plutôt que dupliquée.
    """

    Category.objects.create(
        name="Projet pro",
        slug="projet-pro",
    )

    Skill.objects.create(
        name="Backend",
        slug="backend",
    )

    Technology.objects.create(
        name="Django",
        slug="django",
    )

    payload = {
        "title": "Lagash",
        "slug": "lagash",
        "project_type": "Projet professionnel",
        "description": "Application de démonstration.",
        "category": "Projet pro",
        "skills": ["Backend"],
        "technologies": ["Django"],
        "started_at": "2026-09-01",
        "published": True,
    }

    response = admin_client.post(
        reverse("project-list"),
        payload,
        format="json",
    )

    assert response.status_code == 201

    # Les objets existants doivent être réutilisés.
    assert Category.objects.filter(name="Projet pro").count() == 1
    assert Skill.objects.filter(name="Backend").count() == 1
    assert Technology.objects.filter(name="Django").count() == 1

    # Et ils doivent bien avoir été associés au nouveau projet.
    project = Project.objects.get(slug="lagash")

    assert project.category is not None
    assert project.category.name == "Projet pro"
    assert project.skills.filter(name="Backend").exists()
    assert project.technologies.filter(name="Django").exists()

@pytest.mark.django_db
def test_patch_project_keeps_skills_when_field_is_missing(admin_client):
    """
    Vérifie qu'un PATCH ne modifie pas les compétences
    lorsque le champ "skills" est absent de la requête.

    PATCH ne doit modifier que les champs explicitement envoyés.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Ancienne description.",
        started_at="2026-09-01",
    )

    backend = Skill.objects.create(
        name="Backend",
        slug="backend",
    )

    frontend = Skill.objects.create(
        name="Frontend",
        slug="frontend",
    )

    project.skills.set([backend, frontend])

    payload = {
        "description": "Nouvelle description.",
    }

    response = admin_client.patch(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        ),
        payload,
        format="json",
    )

    assert response.status_code == 200

    # Le champ envoyé doit avoir été modifié.
    project.refresh_from_db()
    assert project.description == "Nouvelle description."

    # "skills" n'était pas présent dans le PATCH :
    # les relations existantes doivent donc rester intactes.
    assert project.skills.count() == 2
    assert project.skills.filter(name="Backend").exists()
    assert project.skills.filter(name="Frontend").exists()

@pytest.mark.django_db
def test_patch_project_clears_skills_with_empty_list(admin_client):
    """
    Vérifie qu'envoyer explicitement une liste vide
    supprime toutes les compétences associées au projet.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    backend = Skill.objects.create(
        name="Backend",
        slug="backend",
    )

    frontend = Skill.objects.create(
        name="Frontend",
        slug="frontend",
    )

    project.skills.set([backend, frontend])

    response = admin_client.patch(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        ),
        {
            "skills": [],
        },
        format="json",
    )

    assert response.status_code == 200

    assert project.skills.count() == 0

@pytest.mark.django_db
def test_patch_project_replaces_skills(admin_client):
    """
    Vérifie qu'une nouvelle liste de compétences remplace
    les associations précédentes.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    old_skill = Skill.objects.create(
        name="Frontend",
        slug="frontend",
    )

    project.skills.add(old_skill)

    response = admin_client.patch(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        ),
        {
            "skills": [
                "Backend",
                "DevOps",
            ],
        },
        format="json",
    )

    assert response.status_code == 200

    project.refresh_from_db()

    assert project.skills.count() == 2

    assert project.skills.filter(
        name="Backend",
    ).exists()

    assert project.skills.filter(
        name="DevOps",
    ).exists()

    assert not project.skills.filter(
        name="Frontend",
    ).exists()

@pytest.mark.django_db
def test_patch_project_replaces_category(admin_client):
    """
    Vérifie qu'un PATCH peut remplacer la catégorie d'un projet.

    Si la nouvelle catégorie n'existe pas encore,
    le contrôleur doit la créer automatiquement.
    """

    old_category = Category.objects.create(
        name="Projet perso",
        slug="projet-perso",
    )

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        category=old_category,
    )

    response = admin_client.patch(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        ),
        {
            "category": "Projet pro",
        },
        format="json",
    )

    assert response.status_code == 200

    project.refresh_from_db()

    assert project.category is not None
    assert project.category.name == "Projet pro"
    assert project.category.slug == "projet-pro"

    # L'ancienne catégorie existe toujours.
    # On retire seulement la relation avec le projet.
    assert Category.objects.filter(
        name="Projet perso",
    ).exists()

@pytest.mark.django_db
def test_patch_project_clears_category_with_empty_string(admin_client):
    """
    Vérifie qu'une chaîne vide retire la catégorie du projet.

    Le contrat API utilise "" pour représenter l'absence
    de catégorie côté client.
    """

    category = Category.objects.create(
        name="Projet pro",
        slug="projet-pro",
    )

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        category=category,
    )

    response = admin_client.patch(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        ),
        {
            "category": "",
        },
        format="json",
    )

    assert response.status_code == 200

    project.refresh_from_db()

    assert project.category is None

    # Retirer la relation ne supprime pas l'objet Category.
    assert Category.objects.filter(
        name="Projet pro",
    ).exists()

    # Notre contrat API représente une catégorie absente par "".
    assert response.data["category"] == ""

@pytest.mark.django_db
def test_patch_project_replaces_technologies(admin_client):
    """Vérifie qu'un PATCH remplace les technologies du projet."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    django = Technology.objects.create(
        name="Django",
        slug="django",
    )

    project.technologies.add(django)

    response = admin_client.patch(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        ),
        {
            "technologies": [
                "React",
                "PostgreSQL",
            ],
        },
        format="json",
    )

    assert response.status_code == 200

    project.refresh_from_db()

    assert set(
        project.technologies.values_list(
            "name",
            flat=True,
        )
    ) == {
        "React",
        "PostgreSQL",
    }

@pytest.mark.django_db
def test_get_project_returns_readable_relations(api_client):
    """
    Vérifie que l'API expose les relations sous une forme lisible.

    Le frontend reçoit les noms des relations et n'a pas besoin
    de connaître leurs UUID internes.
    """

    category = Category.objects.create(
        name="Projet pro",
        slug="projet-pro",
    )

    backend = Skill.objects.create(
        name="Backend",
        slug="backend",
    )

    frontend = Skill.objects.create(
        name="Frontend",
        slug="frontend",
    )

    django = Technology.objects.create(
        name="Django",
        slug="django",
    )

    postgresql = Technology.objects.create(
        name="PostgreSQL",
        slug="postgresql",
    )

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        category=category,
        started_at="2026-09-01",
        published=True,
    )

    project.skills.set([
        backend,
        frontend,
    ])

    project.technologies.set([
        django,
        postgresql,
    ])

    response = api_client.get(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        )
    )

    assert response.status_code == 200

    assert response.data["title"] == "Lagash"
    assert response.data["slug"] == "lagash"
    assert response.data["category"] == "Projet pro"

    assert set(response.data["skills"]) == {
        "Backend",
        "Frontend",
    }

    assert set(response.data["technologies"]) == {
        "Django",
        "PostgreSQL",
    }

@pytest.mark.django_db
def test_get_project_returns_empty_string_without_category(api_client):
    """
    Vérifie que l'absence de catégorie est représentée
    par une chaîne vide conformément au contrat API.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        published=True,
    )

    response = api_client.get(
        reverse(
            "project-detail",
            kwargs={"slug": project.slug},
        )
    )

    assert response.status_code == 200

    assert response.data["category"] == ""
    assert response.data["skills"] == []
    assert response.data["technologies"] == []

@pytest.mark.django_db
def test_get_project_by_slug(api_client):
    """
    Vérifie qu'un projet est accessible publiquement par son slug
    plutôt que par son UUID interne.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        published=True,
    )

    response = api_client.get(
        reverse(
            "project-detail",
            kwargs={"slug": "lagash"},
        )
    )

    assert response.status_code == 200
    assert response.data["id"] == str(project.id)
    assert response.data["slug"] == "lagash"


@pytest.mark.django_db
def test_list_project_pages_scoped_to_project(api_client):
    """
    Vérifie que la liste des pages ne renvoie que celles
    du projet ciblé par l'URL.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        published=True,
    )

    other_project = Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Autre projet.",
        started_at="2026-09-01",
        published=True,
    )

    ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=True,
    )

    ProjectPage.objects.create(
        project=other_project,
        slug="architecture",
        title="Architecture Uruk",
        published=True,
    )

    response = api_client.get(
        reverse(
            "project-pages-list",
            kwargs={"project_slug": "lagash"},
        )
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["title"] == "Architecture"


@pytest.mark.django_db
def test_create_project_page(admin_client):
    """Vérifie qu'un POST crée une page rattachée au bon projet."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    payload = {
        "slug": "architecture",
        "title": "Architecture",
    }

    response = admin_client.post(
        reverse(
            "project-pages-list",
            kwargs={"project_slug": "lagash"},
        ),
        payload,
        format="json",
    )

    assert response.status_code == 201

    page = ProjectPage.objects.get(slug="architecture")
    assert page.project == project


@pytest.mark.django_db
def test_get_project_page_by_slug(api_client):
    """Vérifie qu'une page est accessible par le slug du projet et de la page."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        published=True,
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
            kwargs={"project_slug": "lagash", "slug": "architecture"},
        )
    )

    assert response.status_code == 200
    assert response.data["id"] == str(page.id)
    assert response.data["title"] == "Architecture"


@pytest.mark.django_db
def test_patch_project_page(admin_client):
    """Vérifie qu'un PATCH modifie une page existante."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
    )

    response = admin_client.patch(
        reverse(
            "project-pages-detail",
            kwargs={"project_slug": "lagash", "slug": "architecture"},
        ),
        {
            "title": "Architecture technique",
        },
        format="json",
    )

    assert response.status_code == 200

    page = ProjectPage.objects.get(slug="architecture")
    assert page.title == "Architecture technique"


@pytest.mark.django_db
def test_delete_project_page(admin_client):
    """Vérifie qu'un DELETE supprime la page ciblée."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
    )

    response = admin_client.delete(
        reverse(
            "project-pages-detail",
            kwargs={"project_slug": "lagash", "slug": "architecture"},
        )
    )

    assert response.status_code == 204
    assert not ProjectPage.objects.filter(slug="architecture").exists()


@pytest.mark.django_db
def test_get_project_page_wrong_project_returns_404(api_client):
    """
    Vérifie qu'une page n'est pas accessible via le slug
    d'un autre projet que celui auquel elle appartient.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    Project.objects.create(
        title="Uruk",
        slug="uruk",
        project_type="Projet professionnel",
        description="Autre projet.",
        started_at="2026-09-01",
    )

    ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
    )

    response = api_client.get(
        reverse(
            "project-pages-detail",
            kwargs={"project_slug": "uruk", "slug": "architecture"},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_create_paragraph_attached_to_correct_page(admin_client):
    """Vérifie qu'un POST rattache le paragraphe à la bonne page."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    payload = {
        "content": "Introduction",
        "position": 0,
    }

    response = admin_client.post(
        reverse(
            "paragraphs-list",
            kwargs={"project_slug": "lagash", "page_slug": "presentation"},
        ),
        payload,
        format="json",
    )

    assert response.status_code == 201

    paragraph = Paragraph.objects.get(content="Introduction")
    assert paragraph.page == page


@pytest.mark.django_db
def test_list_paragraphs_ordered_by_position(api_client):
    """Vérifie que les paragraphes sont renvoyés triés par position."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        published=True,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
        published=True,
    )

    Paragraph.objects.create(page=page, content="Conclusion", position=2)
    Paragraph.objects.create(page=page, content="Introduction", position=0)
    Paragraph.objects.create(page=page, content="Architecture", position=1)

    response = api_client.get(
        reverse(
            "paragraphs-list",
            kwargs={"project_slug": "lagash", "page_slug": "presentation"},
        )
    )

    assert response.status_code == 200
    assert [item["content"] for item in response.data] == [
        "Introduction",
        "Architecture",
        "Conclusion",
    ]


@pytest.mark.django_db
def test_patch_paragraph(admin_client):
    """Vérifie qu'un PATCH modifie un paragraphe existant."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    paragraph = Paragraph.objects.create(
        page=page,
        content="Introduction",
        position=0,
    )

    response = admin_client.patch(
        reverse(
            "paragraphs-detail",
            kwargs={
                "project_slug": "lagash",
                "page_slug": "presentation",
                "pk": paragraph.pk,
            },
        ),
        {
            "content": "Introduction modifiée",
        },
        format="json",
    )

    assert response.status_code == 200

    paragraph.refresh_from_db()
    assert paragraph.content == "Introduction modifiée"


@pytest.mark.django_db
def test_delete_paragraph(admin_client):
    """Vérifie qu'un DELETE supprime le paragraphe ciblé."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    paragraph = Paragraph.objects.create(
        page=page,
        content="Introduction",
        position=0,
    )

    response = admin_client.delete(
        reverse(
            "paragraphs-detail",
            kwargs={
                "project_slug": "lagash",
                "page_slug": "presentation",
                "pk": paragraph.pk,
            },
        )
    )

    assert response.status_code == 204
    assert not Paragraph.objects.filter(pk=paragraph.pk).exists()


@pytest.mark.django_db
def test_get_paragraph_wrong_page_returns_404(api_client):
    """
    Vérifie qu'un paragraphe n'est pas accessible via l'URL
    d'une autre page ou d'un autre projet.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    other_page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
    )

    paragraph = Paragraph.objects.create(
        page=page,
        content="Introduction",
        position=0,
    )

    response = api_client.get(
        reverse(
            "paragraphs-detail",
            kwargs={
                "project_slug": "lagash",
                "page_slug": other_page.slug,
                "pk": paragraph.pk,
            },
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_create_highlight_attached_to_correct_page(admin_client):
    """Vérifie qu'un POST rattache le highlight à la bonne page."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    payload = {
        "content": "Zero downtime",
        "position": 0,
    }

    response = admin_client.post(
        reverse(
            "highlights-list",
            kwargs={"project_slug": "lagash", "page_slug": "presentation"},
        ),
        payload,
        format="json",
    )

    assert response.status_code == 201

    highlight = Highlight.objects.get(content="Zero downtime")
    assert highlight.page == page


@pytest.mark.django_db
def test_list_highlights_ordered_by_position(api_client):
    """Vérifie que les highlights sont renvoyés triés par position."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        published=True,
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
        published=True,
    )

    Highlight.objects.create(page=page, content="Scalable", position=2)
    Highlight.objects.create(page=page, content="Rapide", position=0)
    Highlight.objects.create(page=page, content="Sécurisé", position=1)

    response = api_client.get(
        reverse(
            "highlights-list",
            kwargs={"project_slug": "lagash", "page_slug": "presentation"},
        )
    )

    assert response.status_code == 200
    assert [item["content"] for item in response.data] == [
        "Rapide",
        "Sécurisé",
        "Scalable",
    ]


@pytest.mark.django_db
def test_patch_highlight(admin_client):
    """Vérifie qu'un PATCH modifie un highlight existant."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    highlight = Highlight.objects.create(
        page=page,
        content="Rapide",
        position=0,
    )

    response = admin_client.patch(
        reverse(
            "highlights-detail",
            kwargs={
                "project_slug": "lagash",
                "page_slug": "presentation",
                "pk": highlight.pk,
            },
        ),
        {
            "content": "Très rapide",
        },
        format="json",
    )

    assert response.status_code == 200

    highlight.refresh_from_db()
    assert highlight.content == "Très rapide"


@pytest.mark.django_db
def test_delete_highlight(admin_client):
    """Vérifie qu'un DELETE supprime le highlight ciblé."""

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    highlight = Highlight.objects.create(
        page=page,
        content="Rapide",
        position=0,
    )

    response = admin_client.delete(
        reverse(
            "highlights-detail",
            kwargs={
                "project_slug": "lagash",
                "page_slug": "presentation",
                "pk": highlight.pk,
            },
        )
    )

    assert response.status_code == 204
    assert not Highlight.objects.filter(pk=highlight.pk).exists()


@pytest.mark.django_db
def test_get_highlight_wrong_page_returns_404(api_client):
    """
    Vérifie qu'un highlight n'est pas accessible via l'URL
    d'une autre page ou d'un autre projet.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    other_page = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
    )

    highlight = Highlight.objects.create(
        page=page,
        content="Rapide",
        position=0,
    )

    response = api_client.get(
        reverse(
            "highlights-detail",
            kwargs={
                "project_slug": "lagash",
                "page_slug": other_page.slug,
                "pk": highlight.pk,
            },
        )
    )

    assert response.status_code == 404

@pytest.fixture
def image_file(tmp_path):
    """
    Crée une véritable petite image PNG pour tester ImageField.

    ImageField utilise Pillow pour vérifier que le fichier reçu
    est réellement une image valide.
    """
    path = tmp_path / "test.png"

    image = PILImage.new(
        "RGB",
        (10, 10),
    )
    image.save(path)

    return path


@pytest.mark.django_db
def test_upload_image(admin_client, image_file, tmp_path):
    """
    Vérifie qu'une image envoyée en multipart est validée,
    enregistrée sur disque et créée en base de données.
    """

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            response = admin_client.post(
                reverse("image-list"),
                {
                    "file": file,
                    "alt": "Capture de Lagash",
                    "theme": "dark",
                },
                format="multipart",
            )

        assert response.status_code == 201

        image = Image.objects.get()

        assert image.alt == "Capture de Lagash"
        assert image.theme == "dark"

        # Le chemin stocké en BDD est relatif à MEDIA_ROOT.
        assert image.file.name.startswith("projects/")

        # Vérifie que Django a réellement écrit le fichier.
        assert image.file.path
        assert image.file.storage.exists(image.file.name)


@pytest.mark.django_db
def test_upload_invalid_image(admin_client, tmp_path):
    """
    Vérifie qu'un fichier qui n'est pas réellement une image
    est refusé, même s'il possède une extension .png.
    """

    fake_image = tmp_path / "fake.png"
    fake_image.write_text("Ceci n'est pas une image.")

    with fake_image.open("rb") as file:
        response = admin_client.post(
            reverse("image-list"),
            {
                "file": file,
                "alt": "Fausse image",
                "theme": "dark",
            },
            format="multipart",
        )

    assert response.status_code == 400
    assert Image.objects.count() == 0


@pytest.mark.django_db
def test_create_project_image(admin_client, image_file, tmp_path):
    """
    Vérifie qu'une image uploadée depuis la route d'un projet
    est créée puis associée automatiquement à ce projet.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            response = admin_client.post(
                reverse(
                    "project-image-list",
                    kwargs={"project_slug": project.slug},
                ),
                {
                    "file": file,
                    "alt": "Interface de Lagash",
                    "theme": "dark",
                },
                format="multipart",
            )

    assert response.status_code == 201

    image = Image.objects.get()

    assert image.alt == "Interface de Lagash"
    assert image.theme == "dark"

    # L'image doit appartenir au projet fourni dans l'URL.
    assert project.images.filter(pk=image.pk).exists()


@pytest.mark.django_db
def test_list_project_images_scoped_to_project(api_client):
    """
    Vérifie que la route d'un projet ne retourne
    que les images qui lui sont associées.
    """

    lagash = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Lagash.",
        started_at="2026-09-01",
        published=True,
    )

    chinchillapi = Project.objects.create(
        title="ChinchillAPI",
        slug="chinchillapi",
        project_type="Projet personnel",
        description="ChinchillAPI.",
        started_at="2026-08-01",
        published=True,
    )

    lagash_image = Image.objects.create(
        file="projects/lagash.png",
        alt="Lagash",
        theme="dark",
    )

    chinchillapi_image = Image.objects.create(
        file="projects/chinchillapi.png",
        alt="ChinchillAPI",
        theme="dark",
    )

    lagash.images.add(lagash_image)
    chinchillapi.images.add(chinchillapi_image)

    response = api_client.get(
        reverse(
            "project-image-list",
            kwargs={"project_slug": lagash.slug},
        )
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["alt"] == "Lagash"


@pytest.mark.django_db
def test_create_project_image_rejects_duplicate_theme(
    admin_client,
    image_file,
    tmp_path,
):
    """
    Vérifie qu'un projet ne peut pas avoir deux images
    utilisant le même thème.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    existing_image = Image.objects.create(
        file="projects/existing.png",
        alt="Image existante",
        theme="dark",
    )

    project.images.add(existing_image)

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            response = admin_client.post(
                reverse(
                    "project-image-list",
                    kwargs={"project_slug": project.slug},
                ),
                {
                    "file": file,
                    "alt": "Deuxième image dark",
                    "theme": "dark",
                },
                format="multipart",
            )

    assert response.status_code == 400

    # L'image refusée ne doit pas être créée.
    assert Image.objects.count() == 1
    assert project.images.count() == 1


@pytest.mark.django_db
def test_create_project_page_image(admin_client, image_file, tmp_path):
    """
    Vérifie qu'une image uploadée depuis la route d'une page
    est créée puis associée automatiquement à cette page.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            response = admin_client.post(
                reverse(
                    "project-page-image-list",
                    kwargs={
                        "project_slug": project.slug,
                        "page_slug": page.slug,
                    },
                ),
                {
                    "file": file,
                    "alt": "Capture de la présentation",
                    "theme": "dark",
                },
                format="multipart",
            )

    assert response.status_code == 201

    image = Image.objects.get()

    assert image.alt == "Capture de la présentation"
    assert image.theme == "dark"

    # L'image doit appartenir à la page fournie dans l'URL.
    assert page.images.filter(pk=image.pk).exists()


@pytest.mark.django_db
def test_list_project_page_images_scoped_to_page(api_client):
    """
    Vérifie que la route d'une page ne retourne
    que les images qui lui sont associées.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
        published=True,
    )

    presentation = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
        published=True,
    )

    architecture = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
        published=True,
    )

    presentation_image = Image.objects.create(
        file="projects/presentation.png",
        alt="Présentation",
        theme="dark",
    )

    architecture_image = Image.objects.create(
        file="projects/architecture.png",
        alt="Architecture",
        theme="dark",
    )

    presentation.images.add(presentation_image)
    architecture.images.add(architecture_image)

    response = api_client.get(
        reverse(
            "project-page-image-list",
            kwargs={
                "project_slug": project.slug,
                "page_slug": presentation.slug,
            },
        )
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["alt"] == "Présentation"


@pytest.mark.django_db
@pytest.mark.parametrize("theme", ["", "dark"])
def test_create_project_page_image_rejects_duplicate_theme_on_same_page(
    admin_client,
    image_file,
    tmp_path,
    theme,
):
    """
    Vérifie qu'une page ne peut pas avoir deux images utilisant
    le même thème, y compris le thème générique "".
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    existing_image = Image.objects.create(
        file="projects/existing.png",
        alt="Image existante",
        theme=theme,
    )

    page.images.add(existing_image)

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            response = admin_client.post(
                reverse(
                    "project-page-image-list",
                    kwargs={
                        "project_slug": project.slug,
                        "page_slug": page.slug,
                    },
                ),
                {
                    "file": file,
                    "alt": "Deuxième image",
                    "theme": theme,
                },
                format="multipart",
            )

    assert response.status_code == 400

    # L'image refusée ne doit jamais avoir été créée.
    assert Image.objects.count() == 1
    assert page.images.count() == 1


@pytest.mark.django_db
def test_create_project_page_image_accepts_same_theme_on_different_page(
    admin_client,
    image_file,
    tmp_path,
):
    """
    Vérifie que l'unicité du thème ne s'applique qu'à une page :
    deux pages différentes peuvent chacune avoir une image "dark".
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    presentation = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    architecture = ProjectPage.objects.create(
        project=project,
        slug="architecture",
        title="Architecture",
    )

    existing_image = Image.objects.create(
        file="projects/existing.png",
        alt="Image existante",
        theme="dark",
    )

    presentation.images.add(existing_image)

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            response = admin_client.post(
                reverse(
                    "project-page-image-list",
                    kwargs={
                        "project_slug": project.slug,
                        "page_slug": architecture.slug,
                    },
                ),
                {
                    "file": file,
                    "alt": "Architecture dark",
                    "theme": "dark",
                },
                format="multipart",
            )

    assert response.status_code == 201
    assert architecture.images.filter(theme="dark").exists()


@pytest.mark.django_db
def test_create_project_page_image_accepts_same_theme_as_parent_project(
    admin_client,
    image_file,
    tmp_path,
):
    """
    Vérifie que l'unicité du thème sur une page n'est pas affectée
    par une image du même thème déjà associée au Project parent.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    project_image = Image.objects.create(
        file="projects/project.png",
        alt="Image du projet",
        theme="dark",
    )

    project.images.add(project_image)

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            response = admin_client.post(
                reverse(
                    "project-page-image-list",
                    kwargs={
                        "project_slug": project.slug,
                        "page_slug": page.slug,
                    },
                ),
                {
                    "file": file,
                    "alt": "Image de la page",
                    "theme": "dark",
                },
                format="multipart",
            )

    assert response.status_code == 201
    assert page.images.filter(theme="dark").exists()


@pytest.mark.django_db
def test_delete_project_image_removes_image_and_file_when_only_owner(
    admin_client,
    image_file,
    tmp_path,
):
    """
    Vérifie qu'un DELETE retire l'association et supprime réellement
    l'objet Image et son fichier quand le projet est le seul propriétaire.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            image = Image.objects.create(
                file=File(file, name="lagash.png"),
                alt="Interface de Lagash",
                theme="dark",
            )

        project.images.add(image)

        storage = image.file.storage
        file_name = image.file.name

        assert storage.exists(file_name)

        response = admin_client.delete(
            reverse(
                "project-image-detail",
                kwargs={"project_slug": project.slug, "pk": image.pk},
            )
        )

        assert response.status_code == 204
        assert not project.images.filter(pk=image.pk).exists()
        assert not Image.objects.filter(pk=image.pk).exists()
        assert not storage.exists(file_name)


@pytest.mark.django_db
def test_delete_project_image_shared_with_page_keeps_image_until_last_owner(
    admin_client,
    image_file,
    tmp_path,
):
    """
    Vérifie le cycle complet d'une image partagée entre un Project
    et une ProjectPage :

    - DELETE depuis le projet retire seulement cette association,
      l'image reste car la page l'utilise encore.
    - DELETE depuis la page ensuite supprime réellement
      l'objet Image et son fichier, faute de propriétaire restant.
    """

    project = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    page = ProjectPage.objects.create(
        project=project,
        slug="presentation",
        title="Présentation",
    )

    media_root = tmp_path / "media"

    with override_settings(MEDIA_ROOT=media_root):
        with image_file.open("rb") as file:
            image = Image.objects.create(
                file=File(file, name="lagash.png"),
                alt="Interface de Lagash",
                theme="dark",
            )

        project.images.add(image)
        page.images.add(image)

        storage = image.file.storage
        file_name = image.file.name

        # DELETE depuis le projet : la page utilise encore l'image.
        response = admin_client.delete(
            reverse(
                "project-image-detail",
                kwargs={"project_slug": project.slug, "pk": image.pk},
            )
        )

        assert response.status_code == 204
        assert not project.images.filter(pk=image.pk).exists()
        assert Image.objects.filter(pk=image.pk).exists()
        assert storage.exists(file_name)

        # DELETE depuis la page : plus aucun propriétaire.
        response = admin_client.delete(
            reverse(
                "project-page-image-detail",
                kwargs={
                    "project_slug": project.slug,
                    "page_slug": page.slug,
                    "pk": image.pk,
                },
            )
        )

        assert response.status_code == 204
        assert not page.images.filter(pk=image.pk).exists()
        assert not Image.objects.filter(pk=image.pk).exists()
        assert not storage.exists(file_name)


@pytest.mark.django_db
def test_delete_project_image_from_wrong_project_returns_404(admin_client):
    """
    Vérifie qu'on ne peut pas supprimer, via l'URL d'un projet,
    l'association d'une image appartenant à un autre projet.
    """

    lagash = Project.objects.create(
        title="Lagash",
        slug="lagash",
        project_type="Projet professionnel",
        description="Application de démonstration.",
        started_at="2026-09-01",
    )

    chinchillapi = Project.objects.create(
        title="ChinchillAPI",
        slug="chinchillapi",
        project_type="Projet personnel",
        description="ChinchillAPI.",
        started_at="2026-08-01",
    )

    image = Image.objects.create(
        file="projects/chinchillapi.png",
        alt="ChinchillAPI",
        theme="dark",
    )

    chinchillapi.images.add(image)

    response = admin_client.delete(
        reverse(
            "project-image-detail",
            kwargs={"project_slug": lagash.slug, "pk": image.pk},
        )
    )

    assert response.status_code == 404

    # Rien n'a été modifié.
    assert chinchillapi.images.filter(pk=image.pk).exists()
    assert Image.objects.filter(pk=image.pk).exists()


@pytest.mark.django_db
def test_create_project_with_nested_content(admin_client):
    """Vérifie qu'un projet complet peut être créé en une seule requête."""

    payload = {
        "title": "Lagash",
        "slug": "lagash",
        "project_type": "Projet professionnel",
        "description": "Solutions numériques sur mesure.",
        "category": "Projet professionnel",
        "skills": ["Backend", "Frontend"],
        "technologies": ["Python", "Django", "React"],
        "started_at": "2026-09-01",
        "published": True,
        "pages": [
            {
                "slug": "presentation",
                "title": "Présentation",
                "subtitle": "Une solution adaptée à l'entreprise",
                "layout": "default",
                "position": 0,
                "published": True,
                "paragraphs": [
                    {
                        "content": "Premier paragraphe.",
                        "position": 0,
                    },
                    {
                        "content": "Deuxième paragraphe.",
                        "position": 1,
                    },
                ],
                "highlights": [
                    {
                        "content": "Premier point fort",
                        "position": 0,
                    }
                ],
            },
            {
                "slug": "architecture",
                "title": "Architecture",
                "layout": "image-top",
                "position": 1,
                "published": True,
                "paragraphs": [],
                "highlights": [],
            },
        ],
    }

    response = admin_client.post(
        reverse("project-list"),
        payload,
        format="json",
    )

    assert response.status_code == 201

    project = Project.objects.get(slug="lagash")

    assert project.category is not None
    assert project.category.name == "Projet professionnel"
    assert set(project.skills.values_list("name", flat=True)) == {
        "Backend",
        "Frontend",
    }
    assert set(project.technologies.values_list("name", flat=True)) == {
        "Python",
        "Django",
        "React",
    }

    pages = project.pages.all()  # type: ignore[attr-defined]

    assert pages.count() == 2

    presentation = pages.get(slug="presentation")
    architecture = pages.get(slug="architecture")

    assert presentation.paragraphs.count() == 2
    assert presentation.highlights.count() == 1

    assert list(
        presentation.paragraphs.values_list("content", flat=True)
    ) == [
        "Premier paragraphe.",
        "Deuxième paragraphe.",
    ]

    assert presentation.highlights.get().content == "Premier point fort"

    assert architecture.paragraphs.count() == 0
    assert architecture.highlights.count() == 0
