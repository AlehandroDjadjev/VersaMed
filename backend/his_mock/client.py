from .fake_data import DOCTORS, INSTITUTIONS, PATIENTS


class MockHospitalAPIClient:
    def fetch_patient(self, personal_identifier):
        return PATIENTS.get(personal_identifier)

    def fetch_doctor(self, uin):
        return DOCTORS.get(uin)

    def fetch_institution(self, nhif_number):
        return INSTITUTIONS.get(nhif_number)
