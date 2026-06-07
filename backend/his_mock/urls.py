from django.urls import path, re_path

from . import views

urlpatterns = [
    path("v1/nomenclatures/all/get", views.nomenclatures_all_get),
    path("v1/nomenclatures/all/vaccinelotnumber", views.vaccine_lot_number),
    path("v1/eimmunization/immunization/issue", views.immunization_issue),
    path("v1/eimmunization/immunization/fetch", views.immunization_fetch),
    path("v1/eimmunization/immunization/certificate", views.immunization_certificate),
    path("v1/ehospitalization/hospitalization/fetch", views.hospitalization_fetch),
    path("v1/ehospitalization/epicrisis", views.epicrisis),
    re_path(r"^v1/.*$", views.catch_all),
]
