from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape


def send_contact_email(contact_data: dict[str, Any]) -> int:
    """
    Envoie à l'administrateur un email contenant les données
    validées du formulaire de contact.

    Args:
        contact_data: Données validées par ContactSerializer.

    Returns:
        Le nombre d'emails envoyés.
    """

    name = str(contact_data["name"])
    visitor_email = str(contact_data["email"])
    subject = str(contact_data["subject"])
    message = str(contact_data["message"])

    email_subject = f"[Lagash] Nouveau message — {subject}"

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

    safe_name = escape(name) #escape contre les attaques XSS
    safe_email = escape(visitor_email)
    safe_subject = escape(subject)
    safe_message = escape(message).replace("\n", "<br>")

    html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nouveau message depuis Lagash</title>
</head>

<body style="
    margin: 0;
    padding: 0;
    background-color: #f3f4f6;
    font-family: Arial, Helvetica, sans-serif;
    color: #1f2937;
">
    <table
        role="presentation"
        width="100%"
        cellspacing="0"
        cellpadding="0"
        border="0"
        style="background-color: #f3f4f6;"
    >
        <tr>
            <td align="center" style="padding: 40px 16px;">
                <table
                    role="presentation"
                    width="100%"
                    cellspacing="0"
                    cellpadding="0"
                    border="0"
                    style="
                        max-width: 680px;
                        background-color: #ffffff;
                        border-radius: 14px;
                        overflow: hidden;
                        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
                    "
                >
                    <tr>
                        <td style="
                            padding: 28px 32px;
                            background-color: #111827;
                            color: #ffffff;
                            border-bottom: 4px solid #d6a84b;
                        ">
                            <p style="
                                margin: 0 0 8px;
                                font-size: 13px;
                                letter-spacing: 2px;
                                text-transform: uppercase;
                                color: #d6a84b;
                            ">
                                alblanchard.fr
                            </p>

                            <h1 style="
                                margin: 0;
                                font-size: 24px;
                                line-height: 1.3;
                                font-weight: 700;
                            ">
                                Nouveau message reçu
                            </h1>
                        </td>
                    </tr>

                    <tr>
                        <td style="padding: 32px;">
                            <table
                                role="presentation"
                                width="100%"
                                cellspacing="0"
                                cellpadding="0"
                                border="0"
                            >
                                <tr>
                                    <td style="
                                        padding-bottom: 22px;
                                        border-bottom: 1px solid #e5e7eb;
                                    ">
                                        <p style="
                                            margin: 0 0 6px;
                                            font-size: 12px;
                                            font-weight: 700;
                                            letter-spacing: 1px;
                                            text-transform: uppercase;
                                            color: #6b7280;
                                        ">
                                            Nom
                                        </p>

                                        <p style="
                                            margin: 0;
                                            font-size: 17px;
                                            line-height: 1.5;
                                            color: #111827;
                                        ">
                                            {safe_name}
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="
                                        padding: 22px 0;
                                        border-bottom: 1px solid #e5e7eb;
                                    ">
                                        <p style="
                                            margin: 0 0 6px;
                                            font-size: 12px;
                                            font-weight: 700;
                                            letter-spacing: 1px;
                                            text-transform: uppercase;
                                            color: #6b7280;
                                        ">
                                            Email
                                        </p>

                                        <p style="
                                            margin: 0;
                                            font-size: 17px;
                                            line-height: 1.5;
                                        ">
                                            <a
                                                href="mailto:{safe_email}"
                                                style="
                                                    color: #9a6d16;
                                                    text-decoration: none;
                                                "
                                            >
                                                {safe_email}
                                            </a>
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="
                                        padding: 22px 0;
                                        border-bottom: 1px solid #e5e7eb;
                                    ">
                                        <p style="
                                            margin: 0 0 6px;
                                            font-size: 12px;
                                            font-weight: 700;
                                            letter-spacing: 1px;
                                            text-transform: uppercase;
                                            color: #6b7280;
                                        ">
                                            Sujet
                                        </p>

                                        <p style="
                                            margin: 0;
                                            font-size: 17px;
                                            line-height: 1.5;
                                            color: #111827;
                                        ">
                                            {safe_subject}
                                        </p>
                                    </td>
                                </tr>

                                <tr>
                                    <td style="padding-top: 22px;">
                                        <p style="
                                            margin: 0 0 12px;
                                            font-size: 12px;
                                            font-weight: 700;
                                            letter-spacing: 1px;
                                            text-transform: uppercase;
                                            color: #6b7280;
                                        ">
                                            Message
                                        </p>

                                        <div style="
                                            padding: 20px;
                                            background-color: #f9fafb;
                                            border-left: 4px solid #d6a84b;
                                            border-radius: 8px;
                                            font-size: 16px;
                                            line-height: 1.7;
                                            color: #374151;
                                        ">
                                            {safe_message}
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <tr>
                        <td style="
                            padding: 22px 32px;
                            background-color: #f9fafb;
                            border-top: 1px solid #e5e7eb;
                        ">
                            <p style="
                                margin: 0;
                                font-size: 13px;
                                line-height: 1.5;
                                color: #6b7280;
                            ">
                                Message envoyé automatiquement depuis le
                                formulaire de contact de
                                <strong>alblanchard.fr</strong>.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    email = EmailMultiAlternatives(
        subject=email_subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.CONTACT_EMAIL],
        reply_to=[visitor_email],
    )

    email.attach_alternative(html_content, "text/html")

    return email.send(fail_silently=False)