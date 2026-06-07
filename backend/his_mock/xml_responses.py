from xml.etree.ElementTree import Element, SubElement, tostring

from . import fake_data


def _add_mapping(parent, tag, values):
    element = SubElement(parent, tag)
    for key, value in values.items():
        SubElement(element, key).text = str(value)
    return element


def _response(status="SUCCESS", code="MOCK_SUCCESS", message="Mock response generated successfully"):
    root = Element("Response")
    SubElement(root, "Status").text = status
    SubElement(root, "Code").text = code
    SubElement(root, "Message").text = message
    if status == "SUCCESS":
        SubElement(root, "RequestId").text = fake_data.REQUEST_ID
        SubElement(root, "Timestamp").text = fake_data.TIMESTAMP
    return root


def _serialize(root):
    return tostring(root, encoding="unicode", xml_declaration=True)


def build_success_response():
    root = _response()
    SubElement(root, "Data")
    return _serialize(root)


def build_error_response(code, message, status=500):
    root = _response(status="ERROR", code=code, message=message)
    SubElement(root, "HttpStatus").text = str(status)
    return _serialize(root)


def build_nomenclature_response():
    root = _response(code="C002", message="Mock nomenclatures returned successfully")
    data = SubElement(root, "Data")
    items = SubElement(data, "Nomenclatures")
    for value in fake_data.NOMENCLATURES:
        _add_mapping(items, "Nomenclature", value)
    return _serialize(root)


def build_vaccine_lot_number_response():
    root = _response(code="C004", message="Mock vaccine lot numbers returned successfully")
    data = SubElement(root, "Data")
    lots = SubElement(data, "VaccineLotNumbers")
    for value in fake_data.VACCINE_LOTS:
        _add_mapping(lots, "VaccineLotNumber", value)
    return _serialize(root)


def build_immunization_issue_response():
    root = _response(code="I002", message="Mock immunization issued successfully")
    data = SubElement(root, "Data")
    SubElement(data, "DocumentId").text = fake_data.DOCUMENT_ID
    SubElement(data, "CertificateId").text = fake_data.CERTIFICATE_ID
    return _serialize(root)


def build_immunization_fetch_response():
    root = _response(code="I004", message="Mock immunization returned successfully")
    data = SubElement(root, "Data")
    _add_mapping(data, "Patient", fake_data.PATIENT)
    _add_mapping(data, "Doctor", fake_data.DOCTOR)
    _add_mapping(data, "MedicalInstitution", fake_data.MEDICAL_INSTITUTION)
    _add_mapping(data, "Immunization", fake_data.IMMUNIZATION)
    return _serialize(root)


def build_immunization_certificate_response():
    root = _response(code="I014", message="Mock immunization certificate returned successfully")
    data = SubElement(root, "Data")
    SubElement(data, "CertificateId").text = fake_data.CERTIFICATE_ID
    SubElement(data, "DocumentId").text = fake_data.DOCUMENT_ID
    SubElement(data, "CertificateStatus").text = "VALID"
    return _serialize(root)


def build_hospitalization_fetch_response():
    root = _response(code="H002", message="Mock hospitalization returned successfully")
    data = SubElement(root, "Data")
    _add_mapping(data, "Patient", fake_data.PATIENT)
    _add_mapping(data, "MedicalInstitution", fake_data.MEDICAL_INSTITUTION)
    _add_mapping(data, "Hospitalization", fake_data.HOSPITALIZATION)
    return _serialize(root)


def build_epicrisis_response():
    root = _response(code="MOCK_EPICRISIS", message="Mock epicrisis returned successfully")
    data = SubElement(root, "Data")
    _add_mapping(data, "Patient", fake_data.PATIENT)
    _add_mapping(data, "Epicrisis", fake_data.EPICRISIS)
    return _serialize(root)


def build_generic_mock_response(path):
    root = Element("Response")
    SubElement(root, "Status").text = "ERROR"
    SubElement(root, "Code").text = "MOCK_NOT_IMPLEMENTED"
    SubElement(root, "Message").text = "This HIS mock endpoint is not implemented"
    SubElement(root, "HttpStatus").text = "501"
    SubElement(root, "Path").text = path
    return _serialize(root)
