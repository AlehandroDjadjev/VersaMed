import json


def build_diagnosis_analysis_prompt(context):
    return f"""
You are organizing a user's medical history.

You are not making a final medical diagnosis or giving treatment advice.
You are structuring medical information into diagnoses and tracked problems.

A Diagnosis is a raw medical event or record, such as a scan result, blood test, exam, doctor diagnosis, or note.
A Problem is a long-term tracked issue that may be created or updated based on diagnoses.

Your task:
1. Create a contextual description of the new diagnosis.
2. Extract important findings from the new diagnosis.
3. Decide whether this diagnosis should create a new problem, update an existing problem, link to an existing problem, or create no problem.
4. Avoid duplicate problems.
5. Prefer updating an existing problem if it describes the same underlying issue.
6. Use previous problems and previous diagnoses as context.
7. Use enrichment.research and enrichment.scan_analysis as supporting context when present.
8. Preserve clear provenance: scan analysis and research are supporting evidence, while raw_text/raw_json are the saved source record.

Allowed problem actions:
- create_problem
- update_problem
- link_existing_problem
- no_problem

Context JSON:
{json.dumps(context, indent=2)}
""".strip()
