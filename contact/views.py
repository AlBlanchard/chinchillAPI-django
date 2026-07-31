import logging

from django.core.mail import BadHeaderError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ContactSerializer
from .services import send_contact_email


logger = logging.getLogger(__name__)


class ContactAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            send_contact_email(serializer.validated_data)

        except BadHeaderError:
            return Response(
                {
                    "success": False,
                    "message": "Le contenu du message est invalide.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            logger.exception(
                "Une erreur est survenue pendant l'envoi "
                "du message de contact."
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "Le message n'a pas pu être envoyé. "
                        "Veuillez réessayer plus tard."
                    ),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "success": True,
                "message": "Votre message a bien été envoyé.",
            },
            status=status.HTTP_201_CREATED,
        )