from typing import Any

from django.conf import settings
from django.core.mail import EmailMessage


def send_contact_email(contact_data: dict[str, Any]) -> int:
    name = contact_data["name"]
    email = contact_data["email"]
    subject = contact_data["subject"]
    message = contact_data["message"]

    email_subject = f"[Portfolio Lagash] {subject}"

    email_body = (
        "Nouveau message depuis le formulaire de contact\n\n"
        f"Nom : {name}\n"
        f"Adresse email : {email}\n"
        f"Sujet : {subject}\n\n"
        "Message :\n"
        f"{message}"
    )

    contact_email = EmailMessage(
        subject=email_subject,
        body=email_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.CONTACT_EMAIL],
        reply_to=[email],
    )

    return contact_email.send(fail_silently=False)
    