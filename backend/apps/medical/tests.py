from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status

from apps.medical.models import AIRun, Diagnosis, DiagnosisProblemLink, Patient, Problem


def model_output_create_problem():
    return {
        "diagnosis": {
            "title": "Blood test showing possible iron deficiency pattern",
            "summary": "The blood test shows low hemoglobin and low ferritin.",
            "description": (
                "In prior context, these findings may relate to a possible iron "
                "deficiency or anemia pattern."
            ),
            "extracted_findings": [
                {
                    "name": "Hemoglobin",
                    "value": "10.2",
                    "unit": "g/dL",
                    "interpretation": "low",
                    "meaning": "Low hemoglobin can be associated with anemia.",
                }
            ],
            "keywords": ["hemoglobin", "ferritin", "anemia"],
            "body_areas": [],
        },
        "problem_action": {
            "action": "create_problem",
            "target_problem_id": None,
            "problem": {
                "title": "Possible iron deficiency / anemia pattern",
                "summary": "Low hemoglobin and ferritin suggest a possible pattern.",
                "body_area": "",
                "keywords": ["iron deficiency", "anemia"],
            },
            "reasoning": "No existing problem covers this pattern.",
        },
        "links": [
            {
                "problem_id": None,
                "problem_title": "Possible iron deficiency / anemia pattern",
                "strength": "strong",
                "reason": "The diagnosis directly supports the created problem.",
            }
        ],
    }


def model_output_no_problem():
    return {
        "diagnosis": {
            "title": "General wellness note",
            "summary": "The note does not contain a clear tracked issue.",
            "description": "No strong connection to a tracked problem was found.",
            "extracted_findings": [],
            "keywords": [],
            "body_areas": [],
        },
        "problem_action": {
            "action": "no_problem",
            "target_problem_id": None,
            "problem": None,
            "reasoning": "No clear tracked problem was identified.",
        },
        "links": [],
    }


class AnalyzeDiagnosisTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            email="tester@example.com",
            password="password",
        )
        self.client.force_login(self.user)
        self.patient = Patient.objects.create(user=self.user, name="Test Patient")
        self.query_patcher = patch(
            "apps.medical.services.generate_research_query",
            return_value=("low hemoglobin ferritin anemia evidence", "{}"),
        )
        self.research_patcher = patch(
            "apps.medical.services.run_medical_research",
            return_value={
                "query": "low hemoglobin ferritin anemia evidence",
                "answer": "Research evidence summary for anemia patterns.",
                "accepted": [],
                "trace_path": "",
                "answer_path": "",
                "state_path": "",
            },
        )
        self.query_patcher.start()
        self.research_patcher.start()
        self.addCleanup(self.query_patcher.stop)
        self.addCleanup(self.research_patcher.stop)

    @patch("apps.medical.services.call_medical_model")
    def test_analyze_diagnosis_creates_problem(self, call_medical_model):
        call_medical_model.return_value = (model_output_create_problem(), "{}")

        response = self.client.post(
            reverse("api:medical:diagnoses-analyze"),
            {
                "patient_id": self.patient.id,
                "kind": "blood_test",
                "title": "Blood test",
                "raw_text": "Hemoglobin 10.2 low. Ferritin 8 low.",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Diagnosis.objects.filter(patient=self.patient).count(), 1)
        self.assertEqual(Problem.objects.filter(patient=self.patient).count(), 1)
        self.assertEqual(DiagnosisProblemLink.objects.count(), 1)
        self.assertEqual(AIRun.objects.count(), 2)

    @patch("apps.medical.services.call_medical_model")
    def test_analyze_diagnosis_no_problem(self, call_medical_model):
        call_medical_model.return_value = (model_output_no_problem(), "{}")

        response = self.client.post(
            reverse("api:medical:diagnoses-analyze"),
            {
                "patient_id": self.patient.id,
                "kind": "user_note",
                "title": "General note",
                "raw_text": "Patient feels fine. No symptoms reported.",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Diagnosis.objects.filter(patient=self.patient).count(), 1)
        self.assertEqual(Problem.objects.filter(patient=self.patient).count(), 0)
        self.assertEqual(DiagnosisProblemLink.objects.count(), 0)
        self.assertEqual(AIRun.objects.count(), 2)

    @patch("apps.medical.services.call_medical_model")
    def test_analyze_diagnosis_saves_ai_run_error(self, call_medical_model):
        call_medical_model.side_effect = RuntimeError("model unavailable")
        self.client.raise_request_exception = False

        response = self.client.post(
            reverse("api:medical:diagnoses-analyze"),
            {
                "patient_id": self.patient.id,
                "kind": "user_note",
                "title": "General note",
                "raw_text": "Patient feels fine.",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(Diagnosis.objects.filter(patient=self.patient).count(), 1)
        self.assertEqual(AIRun.objects.count(), 2)
        self.assertEqual(AIRun.objects.filter(error="model unavailable").count(), 1)

    @patch("apps.medical.services.call_medical_model")
    def test_analyze_scan_diagnosis_saves_enrichment_and_problem(
        self,
        call_medical_model,
    ):
        call_medical_model.return_value = (model_output_create_problem(), "{}")

        response = self.client.post(
            reverse("api:medical:diagnoses-analyze"),
            {
                "patient_id": self.patient.id,
                "kind": "radiology",
                "title": "Chest CT scan",
                "raw_text": "Scan uploaded for review.",
                "raw_json": {
                    "scan": {
                        "title": "Chest CT scan",
                        "modality": "CT",
                        "bodyPart": "Chest / lungs",
                    },
                    "scan_analysis": {
                        "scanType": "CT",
                        "bodyPart": "Chest / lungs",
                        "imageQuality": "Limited single image",
                        "visibleAnatomy": ["lungs"],
                        "possibleFindings": [
                            {
                                "finding": "possible pulmonary opacity",
                                "severity": "medium",
                                "confidence": 0.51,
                            }
                        ],
                        "simpleExplanation": "The image may show a chest finding for review.",
                        "recommendedDepartment": "Radiology",
                        "urgency": "medium",
                        "limitations": ["Single image only."],
                        "disclaimer": "AI generated.",
                    },
                },
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        diagnosis = Diagnosis.objects.get(patient=self.patient)
        problem = Problem.objects.get(patient=self.patient)
        self.assertEqual(problem.title, "Possible iron deficiency / anemia pattern")
        self.assertEqual(DiagnosisProblemLink.objects.get().problem, problem)
        self.assertIn("SCAN IMAGE ANALYSIS JSON", diagnosis.raw_text)
        self.assertIn("RESEARCH SUMMARY", diagnosis.raw_text)
        self.assertEqual(
            diagnosis.raw_json["agent_enrichment"]["scan_analysis"]["ai_result"]["scanType"],
            "CT",
        )
        self.assertEqual(
            diagnosis.raw_json["agent_enrichment"]["research"]["answer"],
            "Research evidence summary for anemia patterns.",
        )
        self.assertEqual(diagnosis.summary, "The blood test shows low hemoglobin and low ferritin.")
        self.assertEqual(AIRun.objects.filter(task="diagnosis_enrichment").count(), 1)
        self.assertEqual(AIRun.objects.filter(task="diagnosis_analysis").count(), 1)
