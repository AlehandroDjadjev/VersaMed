from django.db import transaction

from apps.medical.ai_client import call_medical_model
from apps.medical.models import AIRun, Diagnosis, DiagnosisProblemLink, Patient, Problem
from apps.medical.prompts import build_diagnosis_analysis_prompt


def ensure_medical_patient(user):
    patient, created = Patient.objects.get_or_create(
        user=user,
        defaults={"name": user.get_full_name().strip() or user.username},
    )

    desired_name = user.get_full_name().strip() or user.username
    if not created and patient.name != desired_name:
        patient.name = desired_name
        patient.save(update_fields=["name"])

    return patient


class DiagnosisAnalysisService:
    def analyze_and_save(
        self,
        *,
        patient_id,
        kind,
        title,
        raw_text="",
        raw_json=None,
        happened_at=None,
    ):
        raw_json = raw_json or {}
        patient = Patient.objects.get(id=patient_id)

        diagnosis = Diagnosis.objects.create(
            patient=patient,
            kind=kind,
            title=title,
            raw_text=raw_text,
            raw_json=raw_json,
            happened_at=happened_at,
        )

        context = self.build_context(diagnosis)
        prompt = build_diagnosis_analysis_prompt(context)

        try:
            model_output, raw_response = call_medical_model(prompt)
        except Exception as exc:
            AIRun.objects.create(
                patient=patient,
                diagnosis=diagnosis,
                task="diagnosis_analysis",
                input_context=context,
                prompt=prompt,
                error=str(exc),
            )
            raise

        with transaction.atomic():
            AIRun.objects.create(
                patient=patient,
                diagnosis=diagnosis,
                task="diagnosis_analysis",
                input_context=context,
                output_json=model_output,
                prompt=prompt,
                raw_response=raw_response,
            )

            self.apply_model_output(diagnosis, model_output)

        diagnosis.refresh_from_db()
        return diagnosis

    def build_context(self, diagnosis):
        patient = diagnosis.patient

        previous_problems = [
            {
                "id": problem.id,
                "title": problem.title,
                "summary": problem.summary,
                "body_area": problem.body_area,
                "keywords": problem.keywords,
                "linked_diagnosis_ids": list(
                    problem.diagnosis_links.values_list("diagnosis_id", flat=True)
                ),
            }
            for problem in patient.problems.order_by("-updated_at")
        ]

        previous_diagnoses = []
        queryset = (
            patient.diagnoses.exclude(id=diagnosis.id).order_by(
                "-happened_at", "-created_at"
            )[:20]
        )

        for item in queryset:
            previous_diagnoses.append(
                {
                    "id": item.id,
                    "kind": item.kind,
                    "title": item.title,
                    "happened_at": item.happened_at.isoformat()
                    if item.happened_at
                    else None,
                    "summary": item.summary,
                    "description": item.description,
                    "extracted_findings": item.extracted_findings,
                    "keywords": item.keywords,
                    "body_areas": item.body_areas,
                    "linked_problem_ids": list(
                        item.problem_links.values_list("problem_id", flat=True)
                    ),
                }
            )

        return {
            "new_diagnosis": {
                "id": diagnosis.id,
                "kind": diagnosis.kind,
                "title": diagnosis.title,
                "happened_at": diagnosis.happened_at.isoformat()
                if diagnosis.happened_at
                else None,
                "raw_text": diagnosis.raw_text,
                "raw_json": diagnosis.raw_json,
            },
            "previous_problems": previous_problems,
            "previous_diagnoses": previous_diagnoses,
        }

    def apply_model_output(self, diagnosis, output):
        diagnosis_data = output.get("diagnosis", {})
        diagnosis.title = diagnosis_data.get("title") or diagnosis.title
        diagnosis.summary = diagnosis_data.get("summary", "")
        diagnosis.description = diagnosis_data.get("description", "")
        diagnosis.extracted_findings = diagnosis_data.get("extracted_findings", [])
        diagnosis.keywords = diagnosis_data.get("keywords", [])
        diagnosis.body_areas = diagnosis_data.get("body_areas", [])
        diagnosis.embedding_text = self.build_diagnosis_embedding_text(diagnosis)
        diagnosis.save()

        action_data = output.get("problem_action", {})
        action = action_data.get("action")
        problem = None

        if action == "create_problem":
            problem = self.create_problem(diagnosis, action_data)
        elif action == "update_problem":
            problem = self.update_problem(diagnosis, action_data)
        elif action == "link_existing_problem":
            problem = self.get_target_problem(diagnosis, action_data)

        if problem:
            DiagnosisProblemLink.objects.get_or_create(
                diagnosis=diagnosis,
                problem=problem,
                defaults={
                    "strength": self.get_link_strength(output, problem),
                    "reason": action_data.get("reasoning", ""),
                },
            )

        self.apply_extra_links(diagnosis, output)

    def create_problem(self, diagnosis, action_data):
        problem_data = action_data.get("problem") or {}
        problem = Problem.objects.create(
            patient=diagnosis.patient,
            title=problem_data.get("title", "Untitled problem"),
            summary=problem_data.get("summary", ""),
            body_area=problem_data.get("body_area", ""),
            keywords=problem_data.get("keywords", []),
        )
        problem.embedding_text = self.build_problem_embedding_text(problem)
        problem.save(update_fields=["embedding_text"])
        return problem

    def update_problem(self, diagnosis, action_data):
        problem = self.get_target_problem(diagnosis, action_data)
        if not problem:
            return None

        problem_data = action_data.get("problem") or {}
        problem.title = problem_data.get("title") or problem.title
        problem.summary = problem_data.get("summary") or problem.summary
        problem.body_area = problem_data.get("body_area", problem.body_area)
        problem.keywords = problem_data.get("keywords", problem.keywords)
        problem.embedding_text = self.build_problem_embedding_text(problem)
        problem.save()
        return problem

    def get_target_problem(self, diagnosis, action_data):
        target_problem_id = action_data.get("target_problem_id")
        if not target_problem_id:
            return None

        return Problem.objects.filter(
            patient=diagnosis.patient,
            id=target_problem_id,
        ).first()

    def apply_extra_links(self, diagnosis, output):
        for link in output.get("links", []):
            problem_id = link.get("problem_id")

            if not problem_id:
                continue

            problem = Problem.objects.filter(
                patient=diagnosis.patient,
                id=problem_id,
            ).first()

            if not problem:
                continue

            DiagnosisProblemLink.objects.get_or_create(
                diagnosis=diagnosis,
                problem=problem,
                defaults={
                    "strength": link.get("strength", "moderate"),
                    "reason": link.get("reason", ""),
                },
            )

    def get_link_strength(self, output, problem):
        for link in output.get("links", []):
            if link.get("problem_id") == problem.id:
                return link.get("strength", "moderate")

        return "strong"

    def build_diagnosis_embedding_text(self, diagnosis):
        findings = diagnosis.extracted_findings or []
        finding_text = " ".join(
            f"{finding.get('name', '')} {finding.get('value', '')} "
            f"{finding.get('unit', '')} {finding.get('interpretation', '')} "
            f"{finding.get('meaning', '')}"
            for finding in findings
        )

        return f"""
Diagnosis: {diagnosis.title}
Kind: {diagnosis.kind}
Summary: {diagnosis.summary}
Description: {diagnosis.description}
Findings: {finding_text}
Keywords: {", ".join(diagnosis.keywords or [])}
Body areas: {", ".join(diagnosis.body_areas or [])}
""".strip()

    def build_problem_embedding_text(self, problem):
        linked_summaries = " ".join(
            link.diagnosis.summary
            for link in problem.diagnosis_links.select_related("diagnosis").all()[:20]
            if link.diagnosis.summary
        )

        return f"""
Problem: {problem.title}
Summary: {problem.summary}
Body area: {problem.body_area}
Keywords: {", ".join(problem.keywords or [])}
Linked diagnoses: {linked_summaries}
""".strip()
