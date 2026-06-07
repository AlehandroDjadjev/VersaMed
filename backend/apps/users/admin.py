from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "onboarding_completed", "is_active")
    list_filter = ("role", "onboarding_completed", "is_active", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "VersaMed",
            {
                "fields": (
                    "middle_name",
                    "phone_number",
                    "role",
                    "onboarding_completed",
                    "onboarding_completed_at",
                )
            },
        ),
    )
