from functools import wraps
from xml.etree.ElementTree import ParseError, fromstring

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .xml_responses import (
    build_epicrisis_response,
    build_error_response,
    build_generic_mock_response,
    build_hospitalization_fetch_response,
    build_immunization_certificate_response,
    build_immunization_fetch_response,
    build_immunization_issue_response,
    build_nomenclature_response,
    build_vaccine_lot_number_response,
)
from .fake_data import PATIENTS


def xml_response(xml, status=200):
    return HttpResponse(xml, status=status, content_type="application/xml")


def xml_endpoint(method):
    def decorator(builder):
        @csrf_exempt
        @wraps(builder)
        def view(request):
            if request.method != method:
                return xml_response(
                    build_error_response("METHOD_NOT_ALLOWED", f"Use {method} for this mock endpoint", 405),
                    status=405,
                )
            if method == "POST" and request.content_type != "application/xml":
                return xml_response(
                    build_error_response("XML_REQUIRED", "Content-Type must be application/xml", 415),
                    status=415,
                )
            return xml_response(builder())

        return view

    return decorator


def patient_identifier(request):
    if request.method == "GET":
        return request.GET.get("patient_id")
    try:
        root = fromstring(request.body)
    except ParseError:
        return None
    return root.findtext(".//PatientId")


def patient_response(request, builder):
    identifier = patient_identifier(request)
    if not identifier:
        return xml_response(build_error_response("PATIENT_ID_REQUIRED", "PatientId is required", 400), 400)
    if identifier not in PATIENTS:
        return xml_response(build_error_response("MOCK_PATIENT_NOT_FOUND", "Synthetic patient not found", 404), 404)
    return xml_response(builder(identifier))


@xml_endpoint("POST")
def nomenclatures_all_get():
    return build_nomenclature_response()


@xml_endpoint("POST")
def vaccine_lot_number():
    return build_vaccine_lot_number_response()


@xml_endpoint("POST")
def immunization_issue():
    return build_immunization_issue_response()


@csrf_exempt
def immunization_fetch(request):
    if request.method != "POST":
        return xml_response(build_error_response("METHOD_NOT_ALLOWED", "Use POST for this mock endpoint", 405), 405)
    if request.content_type != "application/xml":
        return xml_response(build_error_response("XML_REQUIRED", "Content-Type must be application/xml", 415), 415)
    return patient_response(request, build_immunization_fetch_response)


@xml_endpoint("POST")
def immunization_certificate():
    return build_immunization_certificate_response()


@csrf_exempt
def hospitalization_fetch(request):
    if request.method != "POST":
        return xml_response(build_error_response("METHOD_NOT_ALLOWED", "Use POST for this mock endpoint", 405), 405)
    if request.content_type != "application/xml":
        return xml_response(build_error_response("XML_REQUIRED", "Content-Type must be application/xml", 415), 415)
    return patient_response(request, build_hospitalization_fetch_response)


@csrf_exempt
def epicrisis(request):
    if request.method != "GET":
        return xml_response(build_error_response("METHOD_NOT_ALLOWED", "Use GET for this mock endpoint", 405), 405)
    return patient_response(request, build_epicrisis_response)


@csrf_exempt
def catch_all(request):
    return xml_response(build_generic_mock_response(request.path), status=501)
