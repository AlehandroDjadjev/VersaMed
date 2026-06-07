import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.medical.schemas import DIAGNOSIS_ANALYSIS_SCHEMA


class MedicalModelError(Exception):
    pass


def call_medical_model(prompt):
    api_key = getattr(settings, "CHAT_API_KEY", "")

    if not api_key:
        raise ImproperlyConfigured(
            "Missing OpenAI API key. Set the chat_api_key environment variable."
        )

    payload = {
        "model": settings.CHAT_MODEL,
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

    return model_output, raw_response


def _extract_output_text(response_json):
    if response_json.get("output_text"):
        return response_json["output_text"]

    for item in response_json.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]

    return ""
