REQUEST_ID = "mock-request-123"
TIMESTAMP = "2026-06-07T10:00:00Z"

INSTITUTIONS = {
    "220012345": {
        "NHIFNumber": "220012345", "Name": "University Hospital Sveta Sofia - Synthetic",
        "City": "Sofia", "Address": "15 Synthetic Health Blvd", "PhoneNumber": "+35920000101",
    },
    "160098765": {
        "NHIFNumber": "160098765", "Name": "Plovdiv Regional Medical Centre - Synthetic",
        "City": "Plovdiv", "Address": "8 Mock Care Street", "PhoneNumber": "+35932000202",
    },
}

DOCTORS = {
    "1234567890": {"UIN": "1234567890", "Name": "Dr. Elena Georgieva", "FirstName": "Elena", "LastName": "Georgieva", "Specialty": "General Practice", "NHIFNumber": "220012345"},
    "2345678901": {"UIN": "2345678901", "Name": "Dr. Petar Todorov", "FirstName": "Petar", "LastName": "Todorov", "Specialty": "Internal Medicine", "NHIFNumber": "160098765"},
}

PATIENTS = {
    "9001010000": {
        "identity": {"Identifier": "9001010000", "FirstName": "Ivan", "MiddleName": "Petrov", "LastName": "Ivanov", "BirthDate": "1990-01-01", "Gender": "male", "BloodType": "A+", "Address": "Sofia, Synthetic District"},
        "immunizations": [
            {"DocumentId": "imm-ivan-001", "NHIFNumber": "220012345", "VaccineName": "Tetanus-diphtheria booster", "LotNumber": "TD-25014", "DoseNumber": 1, "Date": "2025-03-12"},
            {"DocumentId": "imm-ivan-002", "NHIFNumber": "220012345", "VaccineName": "Seasonal influenza", "LotNumber": "FLU-25118", "DoseNumber": 1, "Date": "2025-10-18"},
        ],
        "hospitalizations": [
            {"DocumentId": "hosp-ivan-001", "NHIFNumber": "220012345", "AdmissionDate": "2025-11-02", "DischargeDate": "2025-11-06", "Department": "Pulmonology", "DiagnosisCode": "J18.9", "Diagnosis": "Pneumonia, unspecified organism"},
        ],
        "epicrises": [
            {"DocumentId": "epi-ivan-001", "HospitalizationId": "hosp-ivan-001", "Summary": "Admitted with fever, cough and radiographic evidence of pneumonia. Improved after inpatient treatment.", "Recommendations": "GP review in seven days and repeat chest imaging in six weeks."},
        ],
    },
    "8505120001": {
        "identity": {"Identifier": "8505120001", "FirstName": "Maria", "MiddleName": "Georgieva", "LastName": "Dimitrova", "BirthDate": "1985-05-12", "Gender": "female", "BloodType": "O+", "Address": "Plovdiv, Synthetic District"},
        "immunizations": [{"DocumentId": "imm-maria-001", "NHIFNumber": "160098765", "VaccineName": "Seasonal influenza", "LotNumber": "FLU-25122", "DoseNumber": 1, "Date": "2025-10-21"}],
        "hospitalizations": [{"DocumentId": "hosp-maria-001", "NHIFNumber": "160098765", "AdmissionDate": "2024-08-14", "DischargeDate": "2024-08-16", "Department": "Cardiology", "DiagnosisCode": "I10", "Diagnosis": "Essential hypertension"}],
        "epicrises": [{"DocumentId": "epi-maria-001", "HospitalizationId": "hosp-maria-001", "Summary": "Blood pressure stabilized during short inpatient observation.", "Recommendations": "Daily blood pressure diary and cardiology follow-up in one month."}],
    },
    "0203150002": {
        "identity": {"Identifier": "0203150002", "FirstName": "Nikolay", "MiddleName": "Hristov", "LastName": "Stoyanov", "BirthDate": "2002-03-15", "Gender": "male", "BloodType": "B+", "Address": "Sofia, Synthetic District"},
        "immunizations": [{"DocumentId": "imm-nikolay-001", "NHIFNumber": "220012345", "VaccineName": "Hepatitis B", "LotNumber": "HEPB-24007", "DoseNumber": 3, "Date": "2024-04-10"}],
        "hospitalizations": [],
        "epicrises": [],
    },
}

NOMENCLATURES = [{"Code": "C001", "Name": "Immunization"}, {"Code": "C002", "Name": "Hospitalization"}, {"Code": "C003", "Name": "Epicrisis"}]
VACCINE_LOTS = [{"VaccineCode": "FLU", "LotNumber": "FLU-25118", "ExpiryDate": "2026-07-31"}]

PATIENT = PATIENTS["9001010000"]["identity"]
DOCTOR = DOCTORS["1234567890"]
MEDICAL_INSTITUTION = INSTITUTIONS["220012345"]
IMMUNIZATION = PATIENTS["9001010000"]["immunizations"][0]
HOSPITALIZATION = PATIENTS["9001010000"]["hospitalizations"][0]
EPICRISIS = PATIENTS["9001010000"]["epicrises"][0]
DOCUMENT_ID = IMMUNIZATION["DocumentId"]
CERTIFICATE_ID = "mock-certificate-789"
