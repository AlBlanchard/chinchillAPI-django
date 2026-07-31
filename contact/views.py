from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ContactSerializer


class ContactAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        contact_data = serializer.validated_data

        # Temporaire : nous brancherons ici l'envoi de l'email.
        print(contact_data)

        return Response(
            {
                "success": True,
                "message": "Votre message a bien été reçu.",
            },
            status=status.HTTP_201_CREATED,
        )