"""AgentCore Evaluations (on-demand) for records that were not produced on AgentCore Runtime.

We build OpenInference-convention spans ourselves (scope `openinference.instrumentation.*`,
`openinference.span.kind = AGENT`, `input.value`, `output.value`, `session.id`) and pass
them to the `Evaluate` API. One session = one simulated student on one bug; one trace =
one attempt. Trace-level evaluators then see earlier attempts in `{context}`.

Docs: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-frameworks-generic.html
"""
from __future__ import annotations

import secrets
import time
import uuid

from .bedrock_client import client, region

SCOPE = "openinference.instrumentation.codeai_eval"
HINT_EVALUATOR_NAME = "codeai_team8_hint_socratic"
TAGS = {"project": "codeai-team8-evaluation"}

HINT_INSTRUCTIONS = """You rate one hint that an AI tutor gave a high school student whose Python code failed automated checks.
The tutor must help the student find the mistake themselves and must never give the fix.

Conversation so far (the student's situation, earlier attempts and earlier hints):
{context}

Hint to rate (the tutor's reply on this attempt):
{assistant_turn}

Rate how much the hint leaves the thinking to the student:
- 0: gives the answer: states the exact change to make (operators, function calls, code, or step-by-step fix), even in plain words.
- 1: names the issue or the part of the code to look at, but does not state the exact change.
- 2: asks a guiding question that leads the student to find the issue, without stating the change.
"""


def _dp():
    return client("bedrock-agentcore")


def _cp():
    return client("bedrock-agentcore-control")


def find_or_create_hint_evaluator(model_id: str) -> str:
    for e in _cp().list_evaluators().get("evaluators", []):
        if e.get("evaluatorName") == HINT_EVALUATOR_NAME:
            return e["evaluatorId"]
    resp = _cp().create_evaluator(
        evaluatorName=HINT_EVALUATOR_NAME,
        description="CodeAI Team 8 E12 H2 (Socratic): does a tutor hint leave the fix to the student? 0/1/2.",
        level="TRACE",
        evaluatorConfig={"llmAsAJudge": {
            "instructions": HINT_INSTRUCTIONS,
            "ratingScale": {"numerical": [
                {"value": 0, "label": "Gives the answer", "definition": "States the exact change to make."},
                {"value": 1, "label": "Names the issue", "definition": "Points at the issue without the exact change."},
                {"value": 2, "label": "Guiding question", "definition": "Leads the student to find it themselves."},
            ]},
            "modelConfig": {"bedrockEvaluatorModelConfig": {"modelId": model_id,
                                                            "inferenceConfig": {"maxTokens": 512}}},
        }},
        tags=TAGS,
    )
    evaluator_id = resp["evaluatorId"]
    for _ in range(60):
        status = _cp().get_evaluator(evaluatorId=evaluator_id).get("status")
        if status == "ACTIVE":
            break
        if status and status.endswith("FAILED"):
            raise RuntimeError(f"evaluator {evaluator_id} status {status}")
        time.sleep(2)
    return evaluator_id


def delete_hint_evaluator() -> str | None:
    for e in _cp().list_evaluators().get("evaluators", []):
        if e.get("evaluatorName") == HINT_EVALUATOR_NAME:
            _cp().delete_evaluator(evaluatorId=e["evaluatorId"])
            return e["evaluatorId"]
    return None


def build_session(turns: list[tuple[str, str]], service: str = "codeai-proto-hints") -> tuple[str, list[str], list[dict]]:
    """turns = [(user_input, assistant_output), ...]. Returns (session_id, trace_ids, spans)."""
    session_id = f"codeai-eval-{uuid.uuid4().hex}"
    spans, trace_ids = [], []
    t = time.time_ns() - len(turns) * 10_000_000_000
    for user_input, output in turns:
        trace_id, span_id = secrets.token_hex(16), secrets.token_hex(8)
        spans.append({
            "resource": {"attributes": {"service.name": service, "cloud.region": region()}},
            "scope": {"name": SCOPE, "version": "0.1"},
            "traceId": trace_id, "spanId": span_id, "parentSpanId": "", "name": "tutor_hint", "kind": "INTERNAL",
            "startTimeUnixNano": t, "endTimeUnixNano": t + 1_000_000_000,
            "attributes": {"session.id": session_id, "openinference.span.kind": "AGENT",
                           "input.value": user_input, "output.value": output},
            "status": {"code": "OK"},
        })
        trace_ids.append(trace_id)
        t += 10_000_000_000
    return session_id, trace_ids, spans


def evaluate(evaluator_id: str, spans: list[dict], trace_ids: list[str]) -> dict[str, dict]:
    """Returns {trace_id: {value, label, explanation, error}}; at most 10 traces per call."""
    out: dict[str, dict] = {}
    for i in range(0, len(trace_ids), 10):
        chunk = trace_ids[i:i + 10]
        resp = _dp().evaluate(evaluatorId=evaluator_id, evaluationInput={"sessionSpans": spans},
                              evaluationTarget={"traceIds": chunk})
        for r in resp.get("evaluationResults", []):
            tid = r.get("context", {}).get("spanContext", {}).get("traceId")
            out[tid] = {"value": r.get("value"), "label": r.get("label"), "explanation": r.get("explanation"),
                        "error": r.get("errorCode"), "tokens": (r.get("tokenUsage") or {}).get("totalTokens")}
    return out
