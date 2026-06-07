import json

from django.conf import settings
from openai import OpenAI

from .scan_service import scan_image_data_url

DISCLAIMER = "This is an AI-generated preliminary explanation and not a final diagnosis."
FALLBACK = {
    "scanType": "",
    "bodyPart": "",
    "imageQuality": "Unable to assess",
    "visibleAnatomy": [],
    "possibleFindings": [],
    "simpleExplanation": "The scan could not be summarized automatically and requires professional review.",
    "recommendedDepartment": "Radiology",
    "urgency": "medium",
    "limitations": ["Automated analysis was unavailable."],
    "disclaimer": DISCLAIMER,
}
RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scanType": {"type": "string"},
        "bodyPart": {"type": "string"},
        "imageQuality": {"type": "string"},
        "visibleAnatomy": {"type": "array", "items": {"type": "string"}},
        "possibleFindings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "finding": {"type": "string"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["finding", "severity", "confidence"],
            },
        },
        "simpleExplanation": {"type": "string"},
        "recommendedDepartment": {"type": "string"},
        "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "disclaimer": {"type": "string"},
    },
    "required": ["scanType", "bodyPart", "imageQuality", "visibleAnatomy", "possibleFindings", "simpleExplanation", "recommendedDepartment", "urgency", "limitations", "disclaimer"],
}


def analyze_scan_with_ai(scan, patient_symptoms):
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.responses.create(
        model=settings.OPENAI_MODEL,
        instructions=(
            "You provide cautious preliminary medical scan summaries. "
            "Use the user's symptoms and complaint to decide what visual findings are most relevant. "
            "Do not ignore the symptoms. Do not invent findings that are not visible. "
            "If the image does not clearly show the suspected issue, say that the image is limited. "
            "For possible cancer-related cases, describe only visible suspicious features and appropriate follow-up. "
            "Separate visible observations from symptom-driven clinical concern; symptoms must not increase confidence "
            "that an abnormality is visible. Use suspicious-for-workup language rather than diagnosing malignancy. "
            "Collection context describes the research dataset, not a confirmed diagnosis for the individual image. "
            "Never state that cancer is present or absent from a single image; confirmation may require a full imaging "
            "series, comparison studies, specialist review, and tissue sampling. "
            "Never give a final diagnosis, claim the patient is healthy, invent history, or recommend medication. "
            "Use possible/may-suggest wording, require professional review, mention single-image limitations, "
            f"and always use this exact disclaimer: {DISCLAIMER}"
        ),
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": (
                        f"Title: {scan['title']}\nModality: {scan['modality']}\nBody part: {scan['bodyPart']}\n"
                        f"Patient-reported symptoms/complaint: {patient_symptoms}\n"
                        f"Dataset symptoms: {', '.join(scan['symptoms']) or 'Not provided by TCIA/NBIA'}\n"
                        f"Dataset symptoms source: {scan.get('symptomsSource', '')}\n"
                        f"Dataset complaint/context note: {scan.get('userComplaint', '')}\n"
                        f"Collection context: {scan.get('clinicalContext', '')}\n"
                        f"Focus hint: {scan.get('focusHint', '')}"
                    ),
                },
                {"type": "input_image", "image_url": scan_image_data_url(scan), "detail": "high"},
            ],
        }],
        text={"format": {"type": "json_schema", "name": "scan_summary", "strict": True, "schema": RESULT_SCHEMA}},
    )
    try:
        result = json.loads(response.output_text)
    except (json.JSONDecodeError, TypeError):
        result = FALLBACK.copy()
    result["disclaimer"] = DISCLAIMER
    return result
