from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import DoctorPatientAssignment, User


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


@admin.register(DoctorPatientAssignment)
class DoctorPatientAssignmentAdmin(admin.ModelAdmin):
    list_display = ("doctor", "patient", "assigned_at")
    search_fields = (
        "doctor__uin",
        "doctor__user__first_name",
        "doctor__user__last_name",
        "patient__personal_identifier",
        "patient__user__first_name",
        "patient__user__middle_name",
        "patient__user__last_name",
    )
