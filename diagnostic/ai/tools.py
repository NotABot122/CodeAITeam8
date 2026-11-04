"""Structured-output tools. The model must answer by calling one of these (forced tool use)."""
from __future__ import annotations

from engine.ai import ToolSpec

STANCES = ("STANCE_REINFORCE", "STANCE_ADVANCE", "STANCE_BRIDGE", "STANCE_PROJECT_SYNTHESIS")

_READING_PROPERTIES = {
    "stage": {"type": "integer", "minimum": 0, "maximum": 3},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "rationale": {"type": "string", "description": "One short sentence for a teacher."},
    "evidence_quotes": {
        "type": "array", "items": {"type": "string"},
        "description": "Short quotes copied exactly from the student's own words.",
    },
}

GRADE_TOOL = ToolSpec(
    name="grade_explanation",
    description="Report the stage (0-3) the student's explanation shows, with evidence from their own words.",
    schema={
        "type": "object",
        "properties": dict(_READING_PROPERTIES),
        "required": ["stage", "confidence", "rationale", "evidence_quotes"],
    },
)

ADVISE_TOOL = ToolSpec(
    name="advise_placement",
    description="Judge each concept's stage from all the evidence, say where to focus first for the student's goal, "
                "and write short kind messages.",
    schema={
        "type": "object",
        "properties": {
            "concepts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"concept": {"type": "string"}, **_READING_PROPERTIES},
                    "required": ["concept", "stage", "confidence", "rationale", "evidence_quotes"],
                },
            },
            "focus_order": {"type": "array", "items": {"type": "string"},
                            "description": "Concept ids, the one to work on first listed first."},
            "stance": {"type": "string", "enum": list(STANCES)},
            "goal_connection": {"type": "string", "description": "One sentence linking the goal to the next steps."},
            "student_message": {"type": "string", "description": "At most 3 short, kind sentences for a child."},
            "teacher_note": {"type": "string", "description": "At most 2 sentences for the teacher."},
        },
        "required": ["concepts", "focus_order", "stance", "goal_connection", "student_message", "teacher_note"],
    },
)
