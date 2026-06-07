from rest_framework import serializers
from rest_framework.permissions import BasePermission


class CanSendEmailNotification(BasePermission):
    message = "Only doctors, admins, and staff may send email notifications."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_staff or user.role in {"doctor", "admin"})
        )


class EmailNotificationSerializer(serializers.Serializer):
    to_email = serializers.EmailField()
    subject = serializers.CharField(max_length=255, trim_whitespace=True)
    message = serializers.CharField(max_length=10000, trim_whitespace=True)

    def validate_subject(self, value):
        if not value:
            raise serializers.ValidationError("Subject cannot be empty.")
        if "\r" in value or "\n" in value:
            raise serializers.ValidationError("Subject cannot contain line breaks.")
        return value

    def validate_message(self, value):
        if not value:
            raise serializers.ValidationError("Message cannot be empty.")
        return value
