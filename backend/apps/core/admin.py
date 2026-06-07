from django.contrib import admin

from .models import DoctorProfile, EmailNotification, Epicrisis, Hospitalization, Immunization, MedicalInstitution, PatientProfile

admin.site.register([DoctorProfile, Epicrisis, Hospitalization, Immunization, MedicalInstitution, PatientProfile])


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = ("to_email", "subject", "status", "sent_at", "created_at")
    list_filter = ("status", "created_at", "sent_at")
    search_fields = ("to_email", "subject")
    readonly_fields = ("id", "status", "error_message", "sent_at", "created_at")
