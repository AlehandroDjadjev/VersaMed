from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.models import DoctorProfile, MedicalInstitution, PatientProfile

from .models import DoctorPatientAssignment
from .login_verification import LoginVerificationError, verify_login_challenge


User = get_user_model()


def default_medical_institution():
    institution, _ = MedicalInstitution.objects.get_or_create(
        nhif_number="VM-DEFAULT-001",
        defaults={
            "name": "VersaMed Network",
            "city": "Sofia",
            "address": "Digital Care Hub",
            "phone_number": "",
        },
    )
    return institution


class PatientProfileSerializer(serializers.ModelSerializer):
    egn = serializers.CharField(source="personal_identifier", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    middle_name = serializers.CharField(source="user.middle_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = PatientProfile
        fields = (
            "egn",
            "first_name",
            "middle_name",
            "last_name",
            "birth_date",
            "gender",
            "blood_type",
            "address",
        )
        read_only_fields = fields


class DoctorProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    middle_name = serializers.CharField(source="user.middle_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    assigned_patients_count = serializers.IntegerField(
        source="patient_assignments.count",
        read_only=True,
    )

    class Meta:
        model = DoctorProfile
        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "uin",
            "specialty",
            "assigned_patients_count",
        )
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    patient_profile = PatientProfileSerializer(read_only=True)
    doctor_profile = DoctorProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "middle_name",
            "last_name",
            "role",
            "patient_profile",
            "doctor_profile",
        )
        read_only_fields = fields


class BaseSignUpSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "password_confirm",
        )

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        user = User(
            username=attrs["username"],
            email=attrs["email"],
        )
        self.apply_user_preview(user, attrs)

        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc

        return attrs

    def apply_user_preview(self, user, attrs):
        return user

    def create_user(self, validated_data, role):
        password = validated_data.pop("password")
        validated_data.pop("password_confirm")
        user = User(role=role, **validated_data)
        user.set_password(password)
        user.save()
        return user


class PatientSignUpSerializer(BaseSignUpSerializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    birth_date = serializers.DateField()
    egn = serializers.RegexField(
        regex=r"^\d{10}$",
        max_length=10,
        min_length=10,
        error_messages={"invalid": "EGN must contain exactly 10 digits."},
    )
    gender = serializers.CharField(max_length=16)
    blood_type = serializers.CharField(max_length=8)
    address = serializers.CharField(max_length=255)

    class Meta(BaseSignUpSerializer.Meta):
        fields = BaseSignUpSerializer.Meta.fields + (
            "first_name",
            "middle_name",
            "last_name",
            "birth_date",
            "egn",
            "gender",
            "blood_type",
            "address",
        )

    def apply_user_preview(self, user, attrs):
        user.first_name = attrs.get("first_name", "")
        user.middle_name = attrs.get("middle_name", "")
        user.last_name = attrs.get("last_name", "")
        return user

    def validate_egn(self, value):
        if PatientProfile.objects.filter(personal_identifier=value).exists():
            raise serializers.ValidationError(
                "A patient profile with this EGN already exists."
            )
        return value

    def create(self, validated_data):
        patient_data = {
            "personal_identifier": validated_data.pop("egn"),
            "birth_date": validated_data.pop("birth_date"),
            "gender": validated_data.pop("gender").strip().lower(),
            "blood_type": validated_data.pop("blood_type").strip().upper(),
            "address": validated_data.pop("address").strip(),
        }
        first_name = validated_data.pop("first_name")
        middle_name = validated_data.pop("middle_name")
        last_name = validated_data.pop("last_name")

        user = self.create_user(validated_data, User.Role.PATIENT)
        user.first_name = first_name
        user.middle_name = middle_name
        user.last_name = last_name
        user.onboarding_completed = True
        user.save(
            update_fields=[
                "first_name",
                "middle_name",
                "last_name",
                "onboarding_completed",
            ]
        )
        PatientProfile.objects.create(user=user, **patient_data)
        return user


class DoctorSignUpSerializer(BaseSignUpSerializer):
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150)
    uin = serializers.RegexField(
        regex=r"^\d{10}$",
        max_length=10,
        min_length=10,
        error_messages={"invalid": "UIN must contain exactly 10 digits."},
    )
    specialty = serializers.CharField(max_length=255)

    class Meta(BaseSignUpSerializer.Meta):
        fields = BaseSignUpSerializer.Meta.fields + (
            "first_name",
            "middle_name",
            "last_name",
            "uin",
            "specialty",
        )

    def apply_user_preview(self, user, attrs):
        user.first_name = attrs.get("first_name", "")
        user.middle_name = attrs.get("middle_name", "")
        user.last_name = attrs.get("last_name", "")
        return user

    def validate_uin(self, value):
        if DoctorProfile.objects.filter(uin=value).exists():
            raise serializers.ValidationError(
                "A doctor profile with this UIN already exists."
            )
        return value

    def create(self, validated_data):
        doctor_data = {
            "uin": validated_data.pop("uin"),
            "specialty": validated_data.pop("specialty"),
            "medical_institution": default_medical_institution(),
        }
        first_name = validated_data.pop("first_name")
        middle_name = validated_data.pop("middle_name", "")
        last_name = validated_data.pop("last_name")

        user = self.create_user(validated_data, User.Role.DOCTOR)
        user.first_name = first_name
        user.middle_name = middle_name
        user.last_name = last_name
        user.onboarding_completed = True
        user.save(
            update_fields=[
                "first_name",
                "middle_name",
                "last_name",
                "onboarding_completed",
            ]
        )
        DoctorProfile.objects.create(user=user, **doctor_data)
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False, write_only=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        request = self.context["request"]
        email = (attrs.get("email") or "").strip().lower()
        username = (attrs.get("username") or "").strip()

        if not email and not username:
            raise serializers.ValidationError(
                {"email": ["Enter the email address for this account."]}
            )

        matched_user = User.objects.filter(email__iexact=email).first() if email else None
        user = authenticate(
            request=request,
            username=matched_user.username if matched_user else username or email,
            password=attrs["password"],
        )

        if user is None:
            raise serializers.ValidationError(
                {"non_field_errors": ["Invalid email or password."]}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"email": ["This account is inactive."]}
            )

        attrs["user"] = user
        attrs["email"] = user.email
        return attrs


class LoginVerificationSerializer(serializers.Serializer):
    challenge_id = serializers.CharField()
    code = serializers.CharField(max_length=6, trim_whitespace=True)

    def validate_code(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Enter the 6-digit verification code.")
        if not normalized.isdigit() or len(normalized) != 6:
            raise serializers.ValidationError("Enter a valid 6-digit verification code.")
        return normalized

    def validate(self, attrs):
        try:
            user = verify_login_challenge(
                attrs["challenge_id"],
                attrs["code"],
            )
        except LoginVerificationError as exc:
            raise serializers.ValidationError({exc.field_name: [str(exc)]}) from exc

        attrs["user"] = user
        return attrs


class DoctorPatientLookupSerializer(serializers.Serializer):
    egn = serializers.RegexField(
        regex=r"^\d{10}$",
        max_length=10,
        min_length=10,
        error_messages={"invalid": "EGN must contain exactly 10 digits."},
    )
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate(self, attrs):
        try:
            patient = PatientProfile.objects.select_related("user").get(
                personal_identifier=attrs["egn"],
                user__first_name__iexact=attrs["first_name"].strip(),
                user__middle_name__iexact=attrs["middle_name"].strip(),
                user__last_name__iexact=attrs["last_name"].strip(),
            )
        except PatientProfile.DoesNotExist as exc:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "No patient profile matches that EGN and three-name combination."
                    ]
                }
            ) from exc

        attrs["patient"] = patient
        return attrs


class AssignedPatientSerializer(serializers.ModelSerializer):
    egn = serializers.CharField(source="personal_identifier", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    middle_name = serializers.CharField(source="user.middle_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = PatientProfile
        fields = (
            "egn",
            "first_name",
            "middle_name",
            "last_name",
            "birth_date",
            "user",
        )
        read_only_fields = fields


class DoctorPatientAssignmentSerializer(serializers.ModelSerializer):
    patient = AssignedPatientSerializer(read_only=True)

    class Meta:
        model = DoctorPatientAssignment
        fields = ("id", "assigned_at", "patient")
        read_only_fields = fields
