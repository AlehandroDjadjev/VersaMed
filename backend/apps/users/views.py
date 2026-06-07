from django.contrib.auth import login, logout
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .login_verification import create_login_challenge
from .models import DoctorPatientAssignment, User
from .serializers import (
    DoctorPatientAssignmentSerializer,
    DoctorPatientLookupSerializer,
    DoctorSignUpSerializer,
    LoginSerializer,
    LoginVerificationSerializer,
    PatientSignUpSerializer,
    UserSerializer,
)


class DoctorRequiredMixin:
    def ensure_doctor(self, request):
        if request.user.role != User.Role.DOCTOR or not getattr(
            request.user, "doctor_profile", None
        ):
            return Response(
                {"detail": "Doctor profile required."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class PatientSignUpView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PatientSignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(
            {"user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class DoctorSignUpView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DoctorSignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(
            {"user": UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        challenge = create_login_challenge(user)
        response_data = {
            "challenge_id": challenge.challenge_id,
            "expires_in": challenge.expires_in,
            "email": serializer.validated_data["email"],
        }

        if challenge.dev_code:
            response_data["dev_code"] = challenge.dev_code

        return Response(response_data, status=status.HTTP_202_ACCEPTED)


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class VerifyLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response({"user": UserSerializer(user).data})


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(ensure_csrf_cookie, name="dispatch")
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"user": None})

        return Response({"user": UserSerializer(request.user).data})


class DoctorPatientAssignmentView(DoctorRequiredMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        doctor_error = self.ensure_doctor(request)
        if doctor_error:
            return doctor_error

        assignments = DoctorPatientAssignment.objects.filter(
            doctor=request.user.doctor_profile
        ).select_related("patient__user")
        return Response(
            {
                "assignments": DoctorPatientAssignmentSerializer(
                    assignments,
                    many=True,
                ).data
            }
        )

    def post(self, request):
        doctor_error = self.ensure_doctor(request)
        if doctor_error:
            return doctor_error

        serializer = DoctorPatientLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.validated_data["patient"]
        assignment, created = DoctorPatientAssignment.objects.get_or_create(
            doctor=request.user.doctor_profile,
            patient=patient,
        )
        return Response(
            {
                "assignment": DoctorPatientAssignmentSerializer(assignment).data,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
