from datetime import date

from django.db import transaction
from django.utils import timezone

from his_mock.client import MockHospitalAPIClient

from .models import DoctorProfile, Epicrisis, Hospitalization, Immunization, MedicalInstitution, PatientProfile


def _date(value):
    return date.fromisoformat(value) if value else None


def _institution(client, nhif_number):
    data = client.fetch_institution(nhif_number)
    institution, _ = MedicalInstitution.objects.update_or_create(
        nhif_number=nhif_number,
        defaults={"name": data["Name"], "city": data["City"], "address": data["Address"], "phone_number": data["PhoneNumber"]},
    )
    return institution


@transaction.atomic
def sync_user_from_mock_hospital(user, identifier):
    client = MockHospitalAPIClient()
    if user.role not in {"patient", "doctor"}:
        raise ValueError("Only patient and doctor accounts can sync hospital data.")
    if user.role == "doctor":
        data = client.fetch_doctor(identifier)
        if not data:
            raise ValueError("Mock doctor not found.")
        profile, _ = DoctorProfile.objects.update_or_create(
            user=user,
            defaults={"uin": data["UIN"], "specialty": data["Specialty"], "medical_institution": _institution(client, data["NHIFNumber"])},
        )
        user.first_name = data["FirstName"]
        user.last_name = data["LastName"]
        user.onboarding_completed = True
        user.onboarding_completed_at = timezone.now()
        user.save(update_fields=["first_name", "last_name", "onboarding_completed", "onboarding_completed_at"])
        return profile

    data = client.fetch_patient(identifier)
    if not data:
        raise ValueError("Mock patient not found.")
    identity = data["identity"]
    user.first_name = identity["FirstName"]
    user.middle_name = identity["MiddleName"]
    user.last_name = identity["LastName"]
    profile, _ = PatientProfile.objects.update_or_create(
        user=user,
        defaults={
            "personal_identifier": identity["Identifier"], "birth_date": _date(identity["BirthDate"]),
            "gender": identity["Gender"], "blood_type": identity["BloodType"], "address": identity["Address"],
        },
    )
    for item in data["immunizations"]:
        Immunization.objects.update_or_create(
            his_document_id=item["DocumentId"],
            defaults={"patient": profile, "medical_institution": _institution(client, item["NHIFNumber"]), "vaccine_name": item["VaccineName"], "lot_number": item["LotNumber"], "dose_number": item["DoseNumber"], "immunization_date": _date(item["Date"])},
        )
    hospitalizations = {}
    for item in data["hospitalizations"]:
        hospitalization, _ = Hospitalization.objects.update_or_create(
            his_document_id=item["DocumentId"],
            defaults={"patient": profile, "medical_institution": _institution(client, item["NHIFNumber"]), "admission_date": _date(item["AdmissionDate"]), "discharge_date": _date(item["DischargeDate"]), "department": item["Department"], "diagnosis_code": item["DiagnosisCode"], "diagnosis": item["Diagnosis"]},
        )
        hospitalizations[item["DocumentId"]] = hospitalization
    for item in data["epicrises"]:
        Epicrisis.objects.update_or_create(
            his_document_id=item["DocumentId"],
            defaults={"hospitalization": hospitalizations[item["HospitalizationId"]], "summary": item["Summary"], "recommendations": item["Recommendations"]},
        )
    user.onboarding_completed = True
    user.onboarding_completed_at = timezone.now()
    user.save(update_fields=["first_name", "middle_name", "last_name", "onboarding_completed", "onboarding_completed_at"])
    return profile
