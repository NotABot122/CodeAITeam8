"""E08 on proto-branch: content filtering on student input and on AI hint output.

Input side: `data/proto_theme_requests.jsonl` (theme requests labeled allow / block / review)
through three layers:
  local     proto `engine.safety.screen_text` (word lists + email/phone regex, no network)
  proto     proto `ContentFilter.screen_request` (local, then a Bedrock moderation call)
  guardrail our E08 baseline Bedrock Guardrail (ApplyGuardrail, source=INPUT), for comparison
Output side: `data/proto_hint_outputs.jsonl` (hint texts labeled allow / block) through
  proto     what the engine applies to AI hints: `check_hint` + `screen_text`
  guardrail the same Guardrail with source=OUTPUT

Usage: python -m evaluation.harness.proto_safety_eval [--no-model] [--no-guardrail]
Writes results/E08_proto_safety_report.md and results/E08_proto_safety_summary.json.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import proto_adapter as pa
from engine.hints import check_hint
from engine.safety import ContentFilter, screen_text

ROOT = Path(__file__).resolve().parents[1]
DATA, RESULTS = ROOT / "data", ROOT / "results"
GUARDRAIL_NAME = "codeai-team8-eval-input"


def _load(name):
    return [json.loads(l) for l in (DATA / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def _guardrail_id():
    from .bedrock_client import client
    for g in client("bedrock").list_guardrails().get("guardrails", []):
        if g["name"] == GUARDRAIL_NAME:
            return g["id"]
    return None


def _guardrail(gid, text, source):
    from .bedrock_client import apply_guardrail
    res = apply_guardrail(gid, "DRAFT", text, source=source)
    hits = [f"{f['type']}" for a in res["assessments"] for f in a.get("contentPolicy", {}).get("filters", [])
            if f.get("action") == "BLOCKED"]
    return res["action"] == "GUARDRAIL_INTERVENED", hits, res["latency_ms"]


def _rates(rows, layer):
    lab = [r for r in rows if r["expected"] in ("allow", "block") and r.get(layer) is not None]
    blk = [r for r in lab if r["expected"] == "block"]
    alw = [r for r in lab if r["expected"] == "allow"]
    return {
        "n": len(lab),
        "catch_rate": round(sum(r[layer] for r in blk) / len(blk), 3) if blk else None,
        "false_block_rate": round(sum(r[layer] for r in alw) / len(alw), 3) if alw else None,
        "missed": [r["id"] for r in blk if not r[layer]],
        "false_blocks": [r["id"] for r in alw if r[layer]],
    }


def _pct(vals, q):
    v = sorted(x for x in vals if x is not None)
    return v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))] if v else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-model", action="store_true", help="skip proto's Bedrock moderation layer")
    ap.add_argument("--no-guardrail", action="store_true")
    args = ap.parse_args(argv)

    moderator = None
    if not args.no_model:
        from engine.ai import BedrockProvider
        moderator = ContentFilter(BedrockProvider())
    gid = None if args.no_guardrail else _guardrail_id()

    inp = []
    for r in _load("proto_theme_requests.jsonl"):
        row = {"id": r["id"], "case": r["case"], "expected": r["expected"], "text": r["text"]}
        loc = screen_text(r["text"])
        row["local"], row["local_cat"] = loc.blocked, loc.category
        if moderator:
            t = time.time()
            res = moderator.screen_request(r["text"])
            row["proto"], row["proto_cat"] = res.blocked, res.category
            row["proto_ms"] = int((time.time() - t) * 1000)
        else:
            row["proto"] = None
        if gid:
            row["guardrail"], row["guardrail_filters"], row["guardrail_ms"] = _guardrail(gid, r["text"], "INPUT")
        else:
            row["guardrail"] = None
        inp.append(row)
        print(f"  {r['id']} {r['expected']:6s} local={row['local']!s:5s} proto={row['proto']!s:5s} "
              f"guardrail={row['guardrail']!s:5s} {r['text'][:50]}", flush=True)

    ref = pa.reference_source()
    out = []
    for r in _load("proto_hint_outputs.jsonl"):
        reason = check_hint(r["text"], ref)
        if reason is None and screen_text(r["text"]).blocked:
            reason = "content filter: " + screen_text(r["text"]).category
        row = {"id": r["id"], "case": r["case"], "expected": r["expected"], "text": r["text"],
               "proto": reason is not None, "proto_reason": reason}
        if gid:
            row["guardrail"], row["guardrail_filters"], _ = _guardrail(gid, r["text"], "OUTPUT")
        else:
            row["guardrail"] = None
        out.append(row)

    combined = [dict(r, combined=(r["proto"] or bool(r["guardrail"]))) for r in inp] if gid and moderator else []
    summary = {
        "guardrail_id": gid,
        "input": {layer: _rates(inp, layer) for layer in ("local", "proto", "guardrail")},
        "input_proto_plus_guardrail": _rates(combined, "combined") if combined else None,
        "input_latency_ms": {"proto_p50": _pct([r.get("proto_ms") for r in inp if not r["local"]], .5),
                             "proto_p95": _pct([r.get("proto_ms") for r in inp if not r["local"]], .95),
                             "guardrail_p50": _pct([r.get("guardrail_ms") for r in inp], .5),
                             "guardrail_p95": _pct([r.get("guardrail_ms") for r in inp], .95)},
        "output": {layer: _rates(out, layer) for layer in ("proto", "guardrail")},
        "input_rows": inp, "output_rows": out,
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "E08_proto_safety_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                                           encoding="utf-8")
    (RESULTS / "E08_proto_safety_report.md").write_text(_report(summary), encoding="utf-8")
    print("wrote results/E08_proto_safety_report.md")
    return 0


def _fmt(x):
    return "-" if x is None else str(x)


def _report(s) -> str:
    i, o = s["input"], s["output"]
    n_block = sum(r["expected"] == "block" for r in s["input_rows"])
    n_allow = sum(r["expected"] == "allow" for r in s["input_rows"])
    n_review = sum(r["expected"] == "review" for r in s["input_rows"])
    L = ["# E08 on proto-branch: content filtering of theme requests and AI hints", "",
         "Code under test: proto-branch `engine/safety.py` and `engine/hints.py` (commit 745b446), unchanged. "
         f"Comparison: our baseline Bedrock Guardrail `{_fmt(s['guardrail_id'])}` (content filters + prompt attack, "
         "no denied topics, no PII filter).", "",
         f"## Student input: {len(s['input_rows'])} theme requests ({n_block} should block, {n_allow} should allow, "
         f"{n_review} borderline for T&L)", "",
         "| Layer | Catch rate (should block) | False-block rate (should allow) | Missed | False blocks |",
         "|---|---|---|---|---|"]
    names = {"local": "proto local rules only (`--ai off`)", "proto": "proto local + Bedrock moderation (default)",
             "guardrail": "Bedrock Guardrail (our E08 baseline)"}
    for k, label in names.items():
        r = i[k]
        L.append(f"| {label} | {_fmt(r['catch_rate'])} | {_fmt(r['false_block_rate'])} | "
                 f"{', '.join(r['missed']) or '-'} | {', '.join(r['false_blocks']) or '-'} |")
    if s["input_proto_plus_guardrail"]:
        r = s["input_proto_plus_guardrail"]
        L.append(f"| proto default + Guardrail | {_fmt(r['catch_rate'])} | {_fmt(r['false_block_rate'])} | "
                 f"{', '.join(r['missed']) or '-'} | {', '.join(r['false_blocks']) or '-'} |")
    lat = s["input_latency_ms"]
    L += ["", f"Latency: proto moderation call P50 {_fmt(lat['proto_p50'])} ms / P95 {_fmt(lat['proto_p95'])} ms "
          f"(requests not already blocked locally); Guardrail P50 {_fmt(lat['guardrail_p50'])} ms / "
          f"P95 {_fmt(lat['guardrail_p95'])} ms.", "",
          "| ID | Expected | Case | Local | Proto default | Guardrail | Request |", "|---|---|---|---|---|---|---|"]
    for r in s["input_rows"]:
        loc = f"block ({r['local_cat']})" if r["local"] else "allow"
        pr = "-" if r["proto"] is None else (f"block ({r['proto_cat']})" if r["proto"] else "allow")
        gr = "-" if r["guardrail"] is None else (f"block ({', '.join(r['guardrail_filters'])})" if r["guardrail"]
                                                  else "allow")
        L.append(f"| {r['id']} | {r['expected']} | {r['case']} | {loc} | {pr} | {gr} | {r['text']} |")
    L += ["", f"## AI hint output: {len(s['output_rows'])} synthetic hint texts", "",
          "Proto applies `check_hint` (code block, `def`, full SQL, copy of reference, length) and the local word "
          "list to every AI hint. The moderation call is not applied to hints.", "",
          "| Layer | Catch rate (should block) | False-block rate | Missed |", "|---|---|---|---|"]
    for k, label in (("proto", "proto check_hint + local rules"), ("guardrail", "Bedrock Guardrail (OUTPUT)")):
        r = o[k]
        L.append(f"| {label} | {_fmt(r['catch_rate'])} | {_fmt(r['false_block_rate'])} | "
                 f"{', '.join(r['missed']) or '-'} |")
    L += ["", "| ID | Expected | Case | Proto | Guardrail | Hint text |", "|---|---|---|---|---|---|"]
    for r in s["output_rows"]:
        pr = f"block ({r['proto_reason']})" if r["proto"] else "allow"
        gr = "-" if r["guardrail"] is None else (f"block ({', '.join(r['guardrail_filters'])})" if r["guardrail"]
                                                  else "allow")
        L.append(f"| {r['id']} | {r['expected']} | {r['case']} | {pr} | {gr} | {r['text'][:110].replace(chr(10), ' ')} |")
    L += ["", "Labels are ours and need T&L review, especially the `review` rows and the alcohol / gambling rows. "
          "Synthetic requests only; real student phrasing will differ.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
