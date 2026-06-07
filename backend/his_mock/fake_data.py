REQUEST_ID = "mock-request-123"
DOCUMENT_ID = "mock-document-456"
CERTIFICATE_ID = "mock-certificate-789"
TIMESTAMP = "2026-06-07T10:00:00Z"

PATIENT = {
    "Identifier": "9001010000",
    "FirstName": "Ivan",
    "MiddleName": "Petrov",
    "LastName": "Ivanov",
    "BirthDate": "1990-01-01",
}

DOCTOR = {
    "UIN": "1234567890",
    "Name": "Dr. Elena Georgieva",
    "Specialty": "General Practice",
}

MEDICAL_INSTITUTION = {
    "NHIFNumber": "220012345",
    "Name": "Mock Medical Center Sofia",
    "City": "Sofia",
}

IMMUNIZATION = {
    "DocumentId": DOCUMENT_ID,
    "VaccineCode": "COVID19-MOCK",
    "VaccineName": "MockVax",
    "LotNumber": "MV-2026-001",
    "DoseNumber": "2",
    "Date": "2026-05-20",
}

HOSPITALIZATION = {
    "DocumentId": "mock-hospitalization-321",
    "AdmissionDate": "2026-05-01",
    "DischargeDate": "2026-05-06",
    "Department": "Internal Medicine",
    "DiagnosisCode": "J18.9",
    "Diagnosis": "Mock pneumonia, unspecified organism",
}

EPICRISIS = {
    "DocumentId": "mock-epicrisis-654",
    "HospitalizationId": HOSPITALIZATION["DocumentId"],
    "Summary": "Patient discharged in stable condition after mock treatment.",
    "Recommendations": "Follow up with the general practitioner in seven days.",
}

NOMENCLATURES = [
    {"Code": "C001", "Name": "Mock immunization"},
    {"Code": "C002", "Name": "Mock hospitalization"},
    {"Code": "C003", "Name": "Mock epicrisis"},
]

VACCINE_LOTS = [
    {"VaccineCode": "COVID19-MOCK", "LotNumber": "MV-2026-001", "ExpiryDate": "2027-05-31"},
    {"VaccineCode": "FLU-MOCK", "LotNumber": "FLU-2026-042", "ExpiryDate": "2027-01-31"},
]
