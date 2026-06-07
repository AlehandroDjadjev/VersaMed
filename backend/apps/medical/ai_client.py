import json
import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.medical.schemas import DIAGNOSIS_ANALYSIS_SCHEMA

logger = logging.getLogger(__name__)


class MedicalModelError(Exception):
    pass


def _openai_api_key():
    return getattr(settings, "OPENAI_API_KEY", "") or getattr(settings, "CHAT_API_KEY", "")


def _openai_model():
    return getattr(settings, "CHAT_MODEL", "") or getattr(settings, "OPENAI_MODEL", "")


def call_medical_model(prompt):
    started = time.perf_counter()
    api_key = _openai_api_key()

    if not api_key:
        raise ImproperlyConfigured(
            "Missing OpenAI API key. Set OPENAI_API_KEY in the environment."
        )

    payload = {
        "model": _openai_model(),
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Return only JSON matching the provided schema. "
                            "Do not include medical advice, treatment instructions, or markdown."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "diagnosis_analysis",
                "strict": True,
                "schema": DIAGNOSIS_ANALYSIS_SCHEMA,
            }
        },
    }

    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.CHAT_API_TIMEOUT_SECONDS) as response:
            raw_response = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise MedicalModelError(f"OpenAI request failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise MedicalModelError(f"OpenAI request failed: {exc.reason}") from exc

    response_json = json.loads(raw_response)
    output_text = _extract_output_text(response_json)

    if not output_text:
        raise MedicalModelError("OpenAI response did not include output text.")

    try:
        model_output = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise MedicalModelError("OpenAI response was not valid JSON.") from exc

    logger.warning(
        "medical_model.call.done model=%s elapsed_ms=%d",
        _openai_model(),
        int((time.perf_counter() - started) * 1000),
    )
    return model_output, raw_response


def generate_research_query(diagnosis_payload):
    started = time.perf_counter()
    api_key = _openai_api_key()

    if not api_key:
        raise ImproperlyConfigured(
            "Missing OpenAI API key. Set OPENAI_API_KEY in the environment."
        )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": "A concise medical literature query for the researcher.",
            }
        },
    }
    payload = {
        "model": _openai_model(),
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Create one concise, evidence-seeking medical research query. "
                            "Do not diagnose the patient. Prefer terms from the record, body area, "
                            "modality, findings, differential patterns, and follow-up questions."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": json.dumps(diagnosis_payload, indent=2, default=str),
                    }
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "medical_research_query",
                "strict": True,
                "schema": schema,
            }
        },
    }

    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.CHAT_API_TIMEOUT_SECONDS) as response:
            raw_response = response.read().decode("utf-8")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise MedicalModelError(f"OpenAI research-query request failed: {exc.code} {error_body}") from exc
    except URLError as exc:
        raise MedicalModelError(f"OpenAI research-query request failed: {exc.reason}") from exc

    response_json = json.loads(raw_response)
    output_text = _extract_output_text(response_json)

    if not output_text:
        raise MedicalModelError("OpenAI research-query response did not include output text.")

    try:
        query_json = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise MedicalModelError("OpenAI research-query response was not valid JSON.") from exc

    logger.warning(
        "medical_model.research_query.done model=%s elapsed_ms=%d",
        _openai_model(),
        int((time.perf_counter() - started) * 1000),
    )
    return query_json["query"], raw_response


def _extract_output_text(response_json):
    if response_json.get("output_text"):
        return response_json["output_text"]

    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]

    return ""
