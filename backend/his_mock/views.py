from functools import wraps

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


@xml_endpoint("POST")
def nomenclatures_all_get():
    return build_nomenclature_response()


@xml_endpoint("POST")
def vaccine_lot_number():
    return build_vaccine_lot_number_response()


@xml_endpoint("POST")
def immunization_issue():
    return build_immunization_issue_response()


@xml_endpoint("POST")
def immunization_fetch():
    return build_immunization_fetch_response()


@xml_endpoint("POST")
def immunization_certificate():
    return build_immunization_certificate_response()


@xml_endpoint("POST")
def hospitalization_fetch():
    return build_hospitalization_fetch_response()


@xml_endpoint("GET")
def epicrisis():
    return build_epicrisis_response()


@csrf_exempt
def catch_all(request):
    return xml_response(build_generic_mock_response(request.path), status=501)
