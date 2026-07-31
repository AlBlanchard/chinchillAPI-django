from rest_framework import serializers


class ContactSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )
    email = serializers.EmailField(
        max_length=254,
    )
    subject = serializers.CharField(
        max_length=150,
        trim_whitespace=True,
    )
    message = serializers.CharField(
        max_length=5000,
        trim_whitespace=True,
    )

    def validate_name(self, value: str) -> str:
        if len(value) < 2:
            raise serializers.ValidationError(
                "Le nom doit contenir au moins 2 caractères."
            )

        return value

    def validate_subject(self, value: str) -> str:
        if len(value) < 3:
            raise serializers.ValidationError(
                "Le sujet doit contenir au moins 3 caractères."
            )

        return value

    def validate_message(self, value: str) -> str:
        if len(value) < 10:
            raise serializers.ValidationError(
                "Le message doit contenir au moins 10 caractères."
            )

        return value