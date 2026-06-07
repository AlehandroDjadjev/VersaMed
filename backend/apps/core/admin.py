from django.contrib import admin

from .models import DoctorProfile, Epicrisis, Hospitalization, Immunization, MedicalInstitution, PatientProfile

admin.site.register([DoctorProfile, Epicrisis, Hospitalization, Immunization, MedicalInstitution, PatientProfile])
