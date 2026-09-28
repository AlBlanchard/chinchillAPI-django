"""Écritures partagées entre API et interface interne."""
from copy import deepcopy

from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from .models import Category, Skill, Technology, Project, ProjectPage, Paragraph, Highlight, Image


def get_or_create_named_object(model, name):
    """
    Récupère un objet à partir de son nom.

    S'il n'existe pas encore, il est créé automatiquement
    avec un slug généré depuis son nom.

    Cette méthode peut être utilisée avec Category, Skill
    et Technology car ces modèles possèdent tous `name`
    et `slug`.
    """

    obj, _ = model.objects.get_or_create(
        name=name,
        defaults={
            "slug": slugify(name),
        },
    )

    return obj

def resolve_many_to_many(model, names):
    """
    Transforme une liste de noms en liste d'objets Django.

    Exemple :
        ["React", "Django"]

    devient :
        [<Technology: React>, <Technology: Django>]

    Chaque objet est récupéré s'il existe déjà,
    ou créé automatiquement sinon.
    """

    return [
        get_or_create_named_object(model, name)
        for name in names
    ]

def create_pages(project, pages_data):
    for page_data in pages_data:
        paragraphs_data = page_data.pop("paragraphs", [])
        highlights_data = page_data.pop("highlights", [])

        page = ProjectPage.objects.create(
            project=project,
            **page_data,
        )

        Paragraph.objects.bulk_create(
            Paragraph(
                page=page,
                **paragraph_data,
            )
            for paragraph_data in paragraphs_data
        )

        Highlight.objects.bulk_create(
            Highlight(
                page=page,
                **highlight_data,
            )
            for highlight_data in highlights_data
        )


@transaction.atomic
def create_project(serializer):
    """
    Crée un projet ainsi que ses relations.

    Toute l'opération est atomique :
    si une étape échoue, PostgreSQL annule l'ensemble.
    """

    # On travaille sur les données déjà validées par le serializer.
    validated_data = deepcopy(serializer.validated_data)

    # Les relations sont retirées car elles nécessitent
    # un traitement spécifique.
    category_name = validated_data.pop("category", None)
    skill_names = validated_data.pop("skills", [])
    technology_names = validated_data.pop("technologies", [])

    pages_data = validated_data.pop("pages", [])

    # création de Project + category/skills/technologies...
    project = Project.objects.create(**validated_data)

    # ----- Category -----

    if category_name:
        project.category = get_or_create_named_object(
            Category,
            category_name,
        )

        project.save(update_fields=["category"])

    # ----- Skills -----

    skills = resolve_many_to_many(
        Skill,
        skill_names,
    )

    project.skills.set(skills)

    # ----- Technologies -----

    technologies = resolve_many_to_many(
        Technology,
        technology_names,
    )

    project.technologies.set(technologies)

    create_pages(project, pages_data)

    # DRF doit connaître l'instance finalement créée pour
    # pouvoir construire correctement la réponse HTTP.
    serializer.instance = project

    return project


def image_file_response(image):
    """Ouvre le stockage uniquement après le contrôle d'accès de la vue."""
    if not image.file or not image.file.name:
        raise Http404
    try:
        return FileResponse(image.file.storage.open(image.file.name, "rb"))
    except FileNotFoundError:
        raise Http404 from None


def validate_image_theme(owner, theme, image_id=None):
    conflicts = owner.images.filter(theme=theme)
    if image_id is not None:
        conflicts = conflicts.exclude(pk=image_id)
    if conflicts.exists():
        label = "Ce projet" if isinstance(owner, Project) else "Cette page"
        raise ValidationError({"theme": f"{label} possède déjà une image pour ce thème."})


@transaction.atomic
def attach_image(owner, image):
    """Idempotent ; le verrou Image coordonne l'association et sa suppression."""
    owner = get_object_or_404(type(owner).objects.select_for_update(), pk=owner.pk)
    image = get_object_or_404(Image.objects.select_for_update(), pk=image.pk)
    validate_image_theme(owner, image.theme, image.pk)
    owner.images.add(image)
    return image


def upload_owner_image(owner, serializer):
    """Upload Project/Page validé, avec compensation si INSERT/association/commit échoue."""
    image = Image(**serializer.validated_data)
    try:
        with transaction.atomic():
            owner = get_object_or_404(type(owner).objects.select_for_update(), pk=owner.pk)
            validate_image_theme(owner, image.theme)
            image.save()
            owner.images.add(image)
    except Exception:
        if image.file and image.file._committed:
            image.file.storage.delete(image.file.name)
        raise
    serializer.instance = image
    return image


def upload_project_image(project, serializer):
    # Point d'entrée V1 conservé pour ses appelants.
    return upload_owner_image(project, serializer)


def create_project_with_image(project_serializer, image_serializer=None):
    """Les deux serializers doivent être validés avant toute écriture."""
    image = None
    try:
        with transaction.atomic():
            project = create_project(project_serializer)
            if image_serializer is not None:
                image = upload_project_image(project, image_serializer)
        return project
    except Exception:
        if image is not None and image.file:
            image.file.storage.delete(image.file.name)
        raise


@transaction.atomic
def update_project(serializer):
    """
    Met à jour un projet et, uniquement si elles sont présentes
    dans la requête, ses relations.

    C'est particulièrement important pour PATCH :
    un champ absent signifie "ne pas modifier cette valeur".
    """

    # Une sentinelle permet de distinguer :
    #
    # - champ absent
    # - champ présent mais volontairement vide
    #
    # None ou [] ne peuvent pas jouer ce rôle puisqu'ils peuvent
    # eux-mêmes être des valeurs valides.
    missing = object()

    validated_data = serializer.validated_data

    category_name = validated_data.pop("category", missing)
    skill_names = validated_data.pop("skills", missing)
    technology_names = validated_data.pop("technologies", missing)

    # serializer.save() peut ici gérer normalement tous les champs
    # simples restants :
    #
    # title, description, published, dates, URLs...
    project = serializer.save()

    # ----- Category -----

    # Le champ n'était pas présent dans le PATCH :
    # on conserve la catégorie actuelle.
    if category_name is not missing:

        # Une valeur vide/null retire volontairement la catégorie.
        if category_name:
            project.category = get_or_create_named_object(
                Category,
                category_name,
            )
        else:
            project.category = None

        project.save(update_fields=["category"])

    # ----- Skills -----

    if skill_names is not missing:
        skills = resolve_many_to_many(
            Skill,
            skill_names,
        )

        # [] donnera naturellement project.skills.set([]),
        # ce qui vide volontairement la relation.
        project.skills.set(skills)

    # ----- Technologies -----

    if technology_names is not missing:
        technologies = resolve_many_to_many(
            Technology,
            technology_names,
        )

        project.technologies.set(technologies)

    return project

def remove_image_from_owner(owner, image):
    """
    Retire une image de son propriétaire (Project ou ProjectPage).

    Si l'image n'est plus associée à aucun projet ni aucune page,
    supprime également l'objet Image et son fichier physique.
    """
    owner.images.remove(image)

    if image.projects.exists() or image.pages.exists():
        return

    # Mémorisés avant la suppression de l'objet, qui invaliderait
    # l'accès au fichier associé.
    storage = image.file.storage
    file_name = image.file.name

    image.delete()

    if file_name:
        storage.delete(file_name)


@transaction.atomic
def delete_project(project):
    """CASCADE pages/blocs ; les Image et fichiers restent dans la bibliothèque."""
    project.delete()


def image_associations(image):
    return [f"Projet « {project.title} » ({project.slug})" for project in image.projects.all()] + [
        f"Page « {page.title} » ({page.project.slug}/{page.slug})"
        for page in image.pages.select_related("project").all()
    ]


class ImageFileCleanupError(OSError):
    """La suppression en base a réussi, celle du fichier doit être reprise."""


def _delete_committed_file(storage, name):
    if not name:
        return
    try:
        storage.delete(name)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ImageFileCleanupError(
            "L'image a été supprimée de la base, mais son fichier n'a pas pu être effacé. "
            "Un nettoyage du stockage est nécessaire ; consultez les journaux serveur."
        ) from exc


@transaction.atomic
def delete_unused_image(image):
    """Suppression globale interne : refuser toute association, nettoyer après commit."""
    image = get_object_or_404(Image.objects.select_for_update(), pk=image.pk)
    associations = image_associations(image)
    if associations:
        raise ValidationError({"image": [
            "Impossible de supprimer cette image : elle est encore utilisée. "
            "Retirez d'abord ses associations.", *associations,
        ]})
    storage, name = image.file.storage, image.file.name
    image.delete()
    transaction.on_commit(lambda: _delete_committed_file(storage, name))
