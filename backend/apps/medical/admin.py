from django.contrib import admin

from apps.medical.models import AIRun, Diagnosis, DiagnosisProblemLink, Patient, Problem


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "user", "created_at")
    search_fields = ("name", "user__username", "user__email")


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "patient", "body_area", "updated_at")
    search_fields = ("title", "summary", "patient__name")


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "patient", "kind", "happened_at", "created_at")
    search_fields = ("title", "summary", "description", "patient__name")
    list_filter = ("kind",)


@admin.register(DiagnosisProblemLink)
class DiagnosisProblemLinkAdmin(admin.ModelAdmin):
    list_display = ("id", "diagnosis", "problem", "strength", "created_at")
    list_filter = ("strength",)


@admin.register(AIRun)
class AIRunAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "patient", "diagnosis", "created_at")
    search_fields = ("task", "error", "raw_response")
