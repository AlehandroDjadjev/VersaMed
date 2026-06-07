DIAGNOSIS_ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["diagnosis", "problem_action", "links"],
    "properties": {
        "diagnosis": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "title",
                "summary",
                "description",
                "extracted_findings",
                "keywords",
                "body_areas",
            ],
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "extracted_findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "name",
                            "value",
                            "unit",
                            "interpretation",
                            "meaning",
                        ],
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "string"},
                            "unit": {"type": "string"},
                            "interpretation": {
                                "type": "string",
                                "enum": [
                                    "normal",
                                    "low",
                                    "high",
                                    "abnormal",
                                    "critical",
                                    "unknown",
                                ],
                            },
                            "meaning": {"type": "string"},
                        },
                    },
                },
                "keywords": {"type": "array", "items": {"type": "string"}},
                "body_areas": {"type": "array", "items": {"type": "string"}},
            },
        },
        "problem_action": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action", "target_problem_id", "problem", "reasoning"],
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "create_problem",
                        "update_problem",
                        "link_existing_problem",
                        "no_problem",
                    ],
                },
                "target_problem_id": {"type": ["integer", "null"]},
                "problem": {
                    "type": ["object", "null"],
                    "additionalProperties": False,
                    "required": ["title", "summary", "body_area", "keywords"],
                    "properties": {
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "body_area": {"type": "string"},
                        "keywords": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "reasoning": {"type": "string"},
            },
        },
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["problem_id", "problem_title", "strength", "reason"],
                "properties": {
                    "problem_id": {"type": ["integer", "null"]},
                    "problem_title": {"type": ["string", "null"]},
                    "strength": {
                        "type": "string",
                        "enum": ["weak", "moderate", "strong"],
                    },
                    "reason": {"type": "string"},
                },
            },
        },
    },
}
