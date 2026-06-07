import concurrent.futures as futures
import json
import logging
import time

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from apps.api.ai_vision_service import analyze_scan_with_ai
from apps.api.scan_service import get_scan, scan_image_path
from apps.medical.ai_client import call_medical_model, generate_research_query
from apps.medical.models import AIRun, Diagnosis, DiagnosisProblemLink, Patient, Problem
from apps.medical.prompts import build_diagnosis_analysis_prompt
from apps.medical.research import run_medical_research

logger = logging.getLogger(__name__)


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
        include_enrichment=True,
    ):
        started = time.perf_counter()
        raw_json = raw_json or {}
        patient = Patient.objects.get(id=patient_id)
        logger.warning(
            "diagnosis_pipeline.start patient_id=%s kind=%s title=%s",
            patient_id,
            kind,
            title,
        )

        diagnosis = Diagnosis.objects.create(
            patient=patient,
            kind=kind,
            title=title,
            raw_text=raw_text,
            raw_json=raw_json,
            happened_at=happened_at,
        )
        logger.warning(
            "diagnosis_pipeline.created diagnosis_id=%s patient_id=%s",
            diagnosis.id,
            patient_id,
        )

        enrichment_started = time.perf_counter()
        enrichment = self.enrich_diagnosis(diagnosis) if include_enrichment else None
        logger.warning(
            "diagnosis_pipeline.enrichment.done diagnosis_id=%s elapsed_ms=%d errors=%s",
            diagnosis.id,
            int((time.perf_counter() - enrichment_started) * 1000),
            len(enrichment.get("errors", [])) if enrichment else 0,
        )
        if enrichment:
            diagnosis.raw_json = {
                **diagnosis.raw_json,
                "agent_enrichment": enrichment,
            }
            diagnosis.raw_text = self.build_enriched_raw_text(diagnosis.raw_text, enrichment)
            diagnosis.save(update_fields=["raw_text", "raw_json"])

            AIRun.objects.create(
                patient=patient,
                diagnosis=diagnosis,
                task="diagnosis_enrichment",
                input_context={
                    "title": diagnosis.title,
                    "kind": diagnosis.kind,
                    "raw_text": raw_text,
                    "raw_json": raw_json,
                },
                output_json=enrichment,
                prompt=enrichment.get("research_query", ""),
                raw_response=enrichment.get("research_query_raw_response", ""),
                error="; ".join(enrichment.get("errors", [])),
            )

        context = self.build_context(diagnosis)
        prompt = build_diagnosis_analysis_prompt(context)

        try:
            analysis_started = time.perf_counter()
            model_output, raw_response = call_medical_model(prompt)
            logger.warning(
                "diagnosis_pipeline.model.done diagnosis_id=%s elapsed_ms=%d",
                diagnosis.id,
                int((time.perf_counter() - analysis_started) * 1000),
            )
        except Exception as exc:
            logger.exception(
                "diagnosis_pipeline.model.error diagnosis_id=%s error=%s",
                diagnosis.id,
                str(exc),
            )
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
        logger.warning(
            "diagnosis_pipeline.done diagnosis_id=%s total_ms=%d",
            diagnosis.id,
            int((time.perf_counter() - started) * 1000),
        )
        return diagnosis

    def enrich_diagnosis(self, diagnosis):
        started = time.perf_counter()
        raw_json = diagnosis.raw_json or {}
        scan_id = raw_json.get("scan_id")
        query_payload = {
            "title": diagnosis.title,
            "kind": diagnosis.kind,
            "raw_text": diagnosis.raw_text,
            "raw_json": raw_json,
        }
        enrichment = {
            "research_query": "",
            "research_query_raw_response": "",
            "research": None,
            "scan_analysis": None,
            "errors": [],
        }

        try:
            query_started = time.perf_counter()
            query, query_raw_response = generate_research_query(query_payload)
            enrichment["research_query"] = query
            enrichment["research_query_raw_response"] = query_raw_response
            logger.warning(
                "diagnosis_enrichment.query.done diagnosis_id=%s elapsed_ms=%d",
                diagnosis.id,
                int((time.perf_counter() - query_started) * 1000),
            )
        except Exception as exc:
            enrichment["errors"].append(f"research_query: {exc}")
            logger.exception(
                "diagnosis_enrichment.query.error diagnosis_id=%s error=%s",
                diagnosis.id,
                str(exc),
            )
            return enrichment

        tasks = {}
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            tasks[executor.submit(run_medical_research, enrichment["research_query"])] = "research"

            # Prefer scan analysis already generated during upload processing.
            if raw_json.get("scan_analysis"):
                enrichment["scan_analysis"] = {
                    "scan": raw_json.get("scan", {}),
                    "ai_result": raw_json.get("scan_analysis"),
                }
            elif scan_id:
                tasks[executor.submit(self.analyze_scan, scan_id)] = "scan_analysis"

            timeout_seconds = getattr(settings, "TEXT_RESEARCH_TIMEOUT_SECONDS", 120)
            try:
                for future in futures.as_completed(tasks, timeout=timeout_seconds):
                    task_name = tasks[future]
                    try:
                        enrichment[task_name] = future.result()
                        logger.warning(
                            "diagnosis_enrichment.task.done diagnosis_id=%s task=%s",
                            diagnosis.id,
                            task_name,
                        )
                    except Exception as exc:
                        enrichment["errors"].append(f"{task_name}: {exc}")
                        logger.exception(
                            "diagnosis_enrichment.task.error diagnosis_id=%s task=%s error=%s",
                            diagnosis.id,
                            task_name,
                            str(exc),
                        )
            except futures.TimeoutError:
                logger.warning(
                    "diagnosis_enrichment.task.timeout diagnosis_id=%s timeout_s=%s",
                    diagnosis.id,
                    timeout_seconds,
                )
                enrichment["errors"].append(
                    f"research: timed out after {timeout_seconds} seconds"
                )
                for future in tasks:
                    future.cancel()

        logger.warning(
            "diagnosis_enrichment.done diagnosis_id=%s total_ms=%d",
            diagnosis.id,
            int((time.perf_counter() - started) * 1000),
        )
        return enrichment

    def analyze_scan(self, scan_id):
        scan = get_scan(scan_id)
        image_path = scan_image_path(scan)
        upload = SimpleUploadedFile(
            image_path.name,
            image_path.read_bytes(),
            content_type="image/png",
        )
        return {
            "scan": {
                "id": scan["id"],
                "title": scan["title"],
                "modality": scan["modality"],
                "bodyPart": scan["bodyPart"],
                "symptoms": scan.get("symptoms", []),
                "userComplaint": scan.get("userComplaint", ""),
                "clinicalContext": scan.get("clinicalContext", ""),
            },
            "ai_result": analyze_scan_with_ai(scan, upload),
        }

    def build_enriched_raw_text(self, raw_text, enrichment):
        sections = [raw_text.strip()] if raw_text else []

        if enrichment.get("scan_analysis"):
            sections.append(
                "SCAN IMAGE ANALYSIS JSON:\n"
                + json.dumps(enrichment["scan_analysis"], indent=2, default=str)
            )

        if enrichment.get("research"):
            research = enrichment["research"]
            sections.append(
                "RESEARCH SUMMARY:\n"
                f"Query: {research.get('query', enrichment.get('research_query', ''))}\n"
                f"{research.get('answer', '')}"
            )

        if enrichment.get("errors"):
            sections.append("ENRICHMENT ERRORS:\n" + "\n".join(enrichment["errors"]))

        return "\n\n".join(section for section in sections if section)

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
