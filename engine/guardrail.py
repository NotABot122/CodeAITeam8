"""Our classroom safety rules as an Amazon Bedrock Guardrail.

The local rules in engine/safety.py (word lists by category, emails and phone numbers) and diagnostic/safety.py
(prompt-injection phrases, "my address is ...") are converted into one Bedrock Guardrail:

    local rule                                   ->  guardrail policy
    category word lists                          ->  word filter (same words) + AWS managed profanity list
    moderation categories (+ gambling)           ->  denied topics, one per category
    emails, phone numbers, addresses             ->  sensitive information filter (block)
    prompt-injection phrases                     ->  prompt-attack filter on student input
    (implicit)                                   ->  content filters: sexual, violence, hate, insults, misconduct

At runtime engine.safety.screen_text asks the guardrail (ApplyGuardrail: INPUT for what students type, OUTPUT for
what a model wrote). If the guardrail isn't configured or the call fails, the local rules decide, as before.

    python -m engine.guardrail sync      # create or update the guardrail from the rules, publish a version
    python -m engine.guardrail show      # print the policy that sync would send
    python -m engine.guardrail check "some text" [--output]

`sync` writes config/bedrock_guardrail.json (id, version, region); the web server reads it at start. Needs boto3 and
Bedrock permissions (run with ~/.venvs/codeai/bin/python on the workshop box).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .safety import CATEGORY_WORDS, FilterResult

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "bedrock_guardrail.json"
NAME = "codeai-team8-student-safety"
REGION = os.environ.get("CODEAI_AWS_REGION", "us-west-2")

BLOCKED_INPUT = "That can't be used in class. Please try something else."
BLOCKED_OUTPUT = "That answer couldn't be shown. Please try again."

# One denied topic per local category (names may only use letters, digits, spaces and - _ ! ? .).
TOPICS = [
    ("sexual", "Sexual content",
     "Sexual or sexually suggestive content, nudity, pornography, erotic material, or adult-content creators and sites.",
     ["a project about porn sites", "onlyfans creators and their earnings", "make it about sexy models"]),
    ("violence", "Real-world violence and weapons",
     "Real-world weapons, shootings, terrorism, murder, torture or graphic gore involving people.",
     ["a project about school shootings", "rank the best guns for killing", "terrorist bomb attacks"]),
    ("self_harm", "Self-harm", "Suicide, self-harm, or encouraging someone to hurt themselves.",
     ["ways to kill myself", "a project about cutting myself", "suicide methods"]),
    ("hate_or_harassment", "Hate and harassment",
     "Hate speech, slurs, extremist groups, or bullying and harassing a person or group.",
     ["a project about the nazis being right", "jokes using racial slurs", "make fun of a classmate"]),
    ("drugs_or_alcohol", "Drugs and alcohol",
     "Illegal drugs, drug dealing, vaping, or drinking alcohol, including how to get, sell or use them.",
     ["a project about selling weed", "rank the best vodka", "how to buy vapes", "我想做一个关于毒品交易的项目"]),
    ("gambling", "Gambling", "Betting money, casinos, sports betting, poker for money, or lottery gambling.",
     ["a casino betting game", "sports betting odds tracker", "online poker for real money"]),
    ("personal_information", "Private details about real people",
     "Home addresses, schedules, contact details or other private information about a specific real person, "
     "such as a classmate, teacher or neighbor.",
     ["my classmate's home address and schedule", "where my teacher lives", "track my neighbor's daily routine"]),
]

CONTENT_FILTERS = [
    {"type": "SEXUAL", "inputStrength": "HIGH", "outputStrength": "HIGH"},
    {"type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
    {"type": "VIOLENCE", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},     # game combat themes stay allowed
    {"type": "INSULTS", "inputStrength": "MEDIUM", "outputStrength": "HIGH"},
    {"type": "MISCONDUCT", "inputStrength": "MEDIUM", "outputStrength": "MEDIUM"},
    {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
]
PII = ["EMAIL", "PHONE", "ADDRESS"]
# Words from the local lists that are fine in other senses ("shooting stars", "weed the garden", "Beer-Lambert law",
# "Moby Dick", "water guns"). The guardrail's topics and content filters judge them in context; the local fallback
# still lists them.
AMBIGUOUS = {"shooting", "shooter", "weed", "beer", "dick", "gun", "guns"}


def policy() -> Dict[str, Any]:
    """The CreateGuardrail / UpdateGuardrail request built from the local rules."""
    words = sorted({w for ws in CATEGORY_WORDS.values() for w in ws} - AMBIGUOUS)
    return {
        "name": NAME,
        "description": "CodeAI Team 8: classroom safety for high school students (converted from engine/safety.py).",
        "topicPolicyConfig": {"topicsConfig": [
            {"name": name, "definition": definition, "examples": examples, "type": "DENY"}
            for _, name, definition, examples in TOPICS]},
        "contentPolicyConfig": {"filtersConfig": CONTENT_FILTERS},
        "wordPolicyConfig": {"wordsConfig": [{"text": w} for w in words],
                             "managedWordListsConfig": [{"type": "PROFANITY"}]},
        "sensitiveInformationPolicyConfig": {"piiEntitiesConfig": [{"type": t, "action": "BLOCK"} for t in PII]},
        "blockedInputMessaging": BLOCKED_INPUT,
        "blockedOutputsMessaging": BLOCKED_OUTPUT,
    }


def _hash(p: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:12]


def sync(region: str = REGION) -> Dict[str, Any]:
    """Create or update the guardrail from the rules and publish a version. Writes CONFIG."""
    import boto3
    bedrock = boto3.client("bedrock", region_name=region)
    request = policy()
    existing = next((g for g in bedrock.list_guardrails(maxResults=100).get("guardrails", []) if g["name"] == NAME), None)
    if existing is None:
        made = bedrock.create_guardrail(**request)
        gid = made["guardrailId"]
    else:
        gid = existing["id"]
        bedrock.update_guardrail(guardrailIdentifier=gid, **request)
    for _ in range(60):                                   # wait until the draft is ready
        if bedrock.get_guardrail(guardrailIdentifier=gid)["status"] == "READY":
            break
        time.sleep(2)
    version = bedrock.create_guardrail_version(guardrailIdentifier=gid,
                                               description=f"rules {_hash(request)}")["version"]
    info = {"id": gid, "version": version, "name": NAME, "region": region, "rules": _hash(request),
            "synced_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(info, indent=2) + "\n")
    return info


def load_config() -> Optional[Dict[str, Any]]:
    """$CODEAI_GUARDRAIL_ID / $CODEAI_GUARDRAIL_VERSION, else config/bedrock_guardrail.json, else None."""
    if os.environ.get("CODEAI_GUARDRAIL_ID"):
        return {"id": os.environ["CODEAI_GUARDRAIL_ID"], "version": os.environ.get("CODEAI_GUARDRAIL_VERSION", "DRAFT"),
                "region": REGION, "name": NAME}
    if CONFIG.is_file():
        try:
            return json.loads(CONFIG.read_text())
        except ValueError:
            return None
    return None


# Category names match the local rules (engine/safety.py) so callers and logs don't change.
_CONTENT = {"SEXUAL": "sexual", "VIOLENCE": "violence", "HATE": "hate_or_harassment",
            "INSULTS": "hate_or_harassment", "MISCONDUCT": "misconduct", "PROMPT_ATTACK": "instruction_override"}
_TOPIC = {name: key for key, name, _, _ in TOPICS}
_WORD = {w.lower(): cat for cat, ws in CATEGORY_WORDS.items() for w in ws}


def _categories(assessments: List[dict]) -> List[str]:
    """Every reason the guardrail blocked, as local category names, most specific first."""
    out: List[str] = []
    for a in assessments:
        for f in (a.get("sensitiveInformationPolicy") or {}).get("piiEntities", []):
            if f.get("action") in ("BLOCKED", "ANONYMIZED"):
                out.append("personal_information")
        for t in (a.get("topicPolicy") or {}).get("topics", []):
            if t.get("action") == "BLOCKED":
                out.append(_TOPIC.get(t.get("name"), "other"))
        words = a.get("wordPolicy") or {}
        for w in words.get("customWords", []):
            if w.get("action") == "BLOCKED":
                out.append(_WORD.get(str(w.get("match", "")).lower(), "other"))
        for w in words.get("managedWordLists", []):
            if w.get("action") == "BLOCKED":
                out.append("profanity")
        for f in (a.get("contentPolicy") or {}).get("filters", []):
            if f.get("action") == "BLOCKED":
                out.append(_CONTENT.get(f.get("type"), "other"))
    return out or ["other"]


class BedrockGuardrail:
    """ApplyGuardrail on one piece of text. check() returns None when the guardrail can't answer (caller falls back)."""

    def __init__(self, guardrail_id: str, version: str, region: str = REGION, trace=None, timeout_s: float = 5.0):
        import boto3
        from botocore.config import Config
        self.id, self.version, self.trace = guardrail_id, str(version), trace
        self.client = boto3.client("bedrock-runtime", region_name=region,
                                   config=Config(retries={"max_attempts": 2, "mode": "standard"},
                                                 connect_timeout=3, read_timeout=timeout_s))

    @property
    def label(self) -> str:
        return f"Bedrock Guardrail {self.id} v{self.version}"

    def check(self, text: str, source: str = "INPUT", ignore: tuple = ()) -> Optional[FilterResult]:
        """ignore: categories that don't count here (student code isn't a prompt, so instruction_override)."""
        if not text or not text.strip():
            return FilterResult(True)
        started = time.monotonic()
        try:
            r = self.client.apply_guardrail(guardrailIdentifier=self.id, guardrailVersion=self.version,
                                            source=source, content=[{"text": {"text": text[:20000]}}])
        except Exception as exc:                          # network, permissions, throttling: local rules decide
            self._record(text, source, started, error=str(exc)[:300])
            return None
        reasons = [c for c in _categories(r.get("assessments") or []) if c not in ignore] \
            if r.get("action") == "GUARDRAIL_INTERVENED" else []
        result = FilterResult(False, reasons[0]) if reasons else FilterResult(True)
        self._record(text, source, started, result=result)
        return result

    def _record(self, text: str, source: str, started: float, result: Optional[FilterResult] = None,
                error: Optional[str] = None) -> None:
        """Show the check in the dev AI inspector (only when the server runs with --dev)."""
        if self.trace is None:
            return
        from .ai_trace import current_student
        verdict = None if result is None else ("allowed" if result.allowed else f"blocked: {result.category}")
        self.trace.add({
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "feature": {"name": f"Safety guardrail ({'student input' if source == 'INPUT' else 'model output'})",
                        "what": "Amazon Bedrock Guardrail: our classroom rules (topics, words, personal info, "
                                "content and prompt-attack filters). Local rules decide if it can't answer."},
            "model": self.label, "student": current_student.get(), "system": f"ApplyGuardrail source={source}",
            "input": text[:20000], "maxTokens": 0, "tools": [], "requireTool": False,
            "ok": error is None, "error": error, "latencyMs": int((time.monotonic() - started) * 1000),
            "outputText": verdict,
        })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engine.guardrail")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync", help="create or update the guardrail from the local rules and publish a version")
    sub.add_parser("show", help="print the policy sync would send")
    check = sub.add_parser("check", help="run one text through the configured guardrail")
    check.add_argument("text")
    check.add_argument("--output", action="store_true", help="check as model output instead of student input")
    args = parser.parse_args(argv)
    if args.cmd == "show":
        print(json.dumps(policy(), indent=2))
        return 0
    if args.cmd == "sync":
        print(json.dumps(sync(), indent=2))
        return 0
    cfg = load_config()
    if not cfg:
        print("No guardrail configured. Run: python -m engine.guardrail sync", file=sys.stderr)
        return 1
    g = BedrockGuardrail(cfg["id"], cfg["version"], cfg.get("region", REGION))
    print(g.check(args.text, "OUTPUT" if args.output else "INPUT"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
