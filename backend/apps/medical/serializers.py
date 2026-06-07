from rest_framework import serializers

from apps.medical.models import Diagnosis, DiagnosisProblemLink, Patient, Problem


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["id", "name", "created_at"]


class DiagnosisAnalyzeInputSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=Diagnosis.Kind.choices)
    title = serializers.CharField(max_length=255)
    happened_at = serializers.DateField(required=False, allow_null=True)
    raw_text = serializers.CharField(required=False, allow_blank=True)
    raw_json = serializers.JSONField(required=False)


class ProblemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Problem
        fields = [
            "id",
            "title",
            "summary",
            "body_area",
            "keywords",
            "created_at",
            "updated_at",
        ]


class DiagnosisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Diagnosis
        fields = [
            "id",
            "kind",
            "title",
            "raw_text",
            "raw_json",
            "happened_at",
            "summary",
            "description",
            "extracted_findings",
            "keywords",
            "body_areas",
            "created_at",
        ]


class DiagnosisProblemLinkSerializer(serializers.ModelSerializer):
    problem = ProblemSerializer()

    class Meta:
        model = DiagnosisProblemLink
        fields = [
            "id",
            "problem",
            "strength",
            "reason",
            "created_at",
        ]
