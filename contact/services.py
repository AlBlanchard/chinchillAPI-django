from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_contact_email(contact_data: dict[str, Any]) -> int:
    """
    Envoie un email contenant les données validées
    du formulaire de contact.

    Args:
        contact_data: Données validées par ContactSerializer.

    Returns:
        Le nombre d'emails envoyés.
    """

    name = str(contact_data["name"])
    visitor_email = str(contact_data["email"])
    subject = str(contact_data["subject"])
    message = str(contact_data["message"])

    email_subject = f"[alblanchard.fr] Nouveau message — {subject}"

    context = {
        "name": name,
        "visitor_email": visitor_email,
        "subject": subject,
        "message": message,
    }

    html_content = render_to_string(
        "contact/contact_email.html",
        context,
    )

    text_content = (
        "NOUVEAU MESSAGE DEPUIS LE FORMULAIRE DE CONTACT\n"
        "================================================\n\n"
        f"Nom : {name}\n"
        f"Email : {visitor_email}\n"
        f"Sujet : {subject}\n\n"
        "MESSAGE\n"
        "-------\n\n"
        f"{message}\n\n"
        "================================================\n"
        "Message envoyé depuis le formulaire de contact "
        "de alblanchard.fr.\n"
    )

    email = EmailMultiAlternatives(
        subject=email_subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL, #envoie à OVH
        to=[settings.CONTACT_EMAIL], #l'adresse gmail finale
        reply_to=[visitor_email], #Permet de répondre directement à l'expéditeur du message
    )

    email.attach_alternative(
        html_content,
        "text/html",
    )

    return email.send(fail_silently=False)