"""Annotation pack for E01 (grader vs. humans) and E10 (human vs. human).

  make   -> evaluation/annotation/rating_sheet_<rater>.xlsx for each rater, plus a
            key file that maps blind item IDs back to submissions. Raters never see
            target stages, model stages, or each other's ratings.
  score  -> reads the filled sheets, computes human-human agreement (E10, the
            ceiling) and grader-human agreement (E01) using the same metrics as the
            harness, and writes results/E01_E10_agreement_report.md.

Sources:
  --source real  : data/benchmark/submissions.jsonl (human-written or real student
                   work, same fields as mock_submissions.jsonl). Use this for the
                   reported E01 / E10 numbers.
  --source mock  : a stratified sample of synthetic submissions. ONLY for rater
                   calibration practice; never report agreement from it.

Usage:
  python -m evaluation.harness.annotation make --source mock --n 30 --raters A B
  python -m evaluation.harness.annotation score --grader-log results/event_log_<run>.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from . import metrics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "annotation"
RESULTS = ROOT / "results"
RUBRIC = ROOT / "rubrics" / "concept3_task_rubric.json"
YELLOW = PatternFill("solid", fgColor="FFF2CC")


def _load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _sample_mock(n: int, seed: int) -> list[dict]:
    """Stratify on the target stage of the sub-skill with the thinnest cells."""
    rows = _load(DATA / "mock_submissions.jsonl")
    rng = random.Random(seed)
    by = {}
    for r in rows:
        by.setdefault(r["target_stage"]["evaluation"], []).append(r)
    picked, k = [], 0
    pools = {s: rng.sample(v, len(v)) for s, v in by.items()}
    while len(picked) < n and any(pools.values()):
        s = sorted(pools)[k % len(pools)]
        if pools[s]:
            picked.append(pools[s].pop())
        k += 1
    return picked


def make(source: str, n: int, raters: list[str], seed: int) -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    subs = rubric["subskill_order"]
    if source == "real":
        path = DATA / "benchmark" / "submissions.jsonl"
        if not path.exists():
            raise SystemExit(f"{path} not found. Put human-written or real submissions there first.")
        items = _load(path)
    else:
        items = _sample_mock(n, seed)
    rng = random.Random(seed + 1)
    rng.shuffle(items)
    OUT.mkdir(parents=True, exist_ok=True)
    key = [{"item_id": f"I{i:03d}", "submission_id": r["submission_id"], "source": source,
            "input_hash_fields": {k: r.get(k) for k in ("student_id", "task_id", "attempt_no")}}
           for i, r in enumerate(items, 1)]
    (OUT / f"key_{source}.json").write_text(json.dumps(key, indent=2), encoding="utf-8")

    for rater in raters:
        wb = Workbook()
        ws = wb.active
        ws.title = "Instructions"
        lines = [
            f"Rating sheet for rater {rater} ({'CALIBRATION PRACTICE, synthetic' if source == 'mock' else 'BENCHMARK'})",
            "",
            "1. Read the rubric on the 'Rubric' sheet and the task the student was given.",
            "2. On the 'Ratings' sheet, give each sub-skill a stage 0-3, or leave it blank and write 'unscorable' in Notes.",
            "3. Score each sub-skill on its own part of the answer. A higher stage needs all evidence of the lower stage.",
            "4. Use only what the student wrote. Do not guess intent.",
            "5. Work alone. Do not discuss items with the other rater until both sheets are returned.",
            "6. Put a short quote that justified the stage in the Evidence column when you can.",
            "",
            "The student text is shown exactly as submitted. IDs are blind; do not try to match them to students.",
        ]
        for i, l in enumerate(lines, 1):
            ws.cell(i, 1, l)
        ws["A1"].font = Font(bold=True, size=13)
        ws.column_dimensions["A"].width = 120

        rs = wb.create_sheet("Rubric")
        rs.append(["Task", rubric["task"]["student_instructions"]])
        rs.append(["AI output shown to student", rubric["task"]["fixed_ai_output_summary"]])
        rs.append([])
        rs.append(["Sub-skill", "Stage", "Description"])
        for s in subs:
            for st, d in rubric["subskills"][s]["stages"].items():
                rs.append([s, int(st), d])
        rs.column_dimensions["A"].width = 26
        rs.column_dimensions["C"].width = 110
        for row in rs.iter_rows():
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")

        ra = wb.create_sheet("Ratings")
        header = ["item_id", "submission_text"] + [f"stage_{s}" for s in subs] + ["evidence", "notes"]
        ra.append(header)
        for c in ra[1]:
            c.font = Font(bold=True)
        dv = DataValidation(type="whole", operator="between", formula1="0", formula2="3", allow_blank=True,
                            error="Stage must be a whole number 0-3, or blank if unscorable.")
        ra.add_data_validation(dv)
        for k, r in zip(key, items):
            ra.append([k["item_id"], r["submission_text"]] + [None] * len(subs) + [None, None])
        last = ra.max_row
        for j in range(len(subs)):
            col = chr(ord("C") + j)
            dv.add(f"{col}2:{col}{last}")
            for i in range(2, last + 1):
                ra[f"{col}{i}"].fill = YELLOW
        for col, w in zip("ABCDEFG", (8, 90, 14, 14, 18, 40, 30)):
            ra.column_dimensions[col].width = w
        for row in ra.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ra.freeze_panes = "C2"
        path = OUT / f"rating_sheet_{source}_{rater}.xlsx"
        wb.save(path)
        print(f"wrote {path.relative_to(ROOT)} ({len(items)} items)")


def _read_sheet(path: Path, subs: list[str]) -> dict:
    ws = load_workbook(path, data_only=True)["Ratings"]
    header = [c.value for c in ws[1]]
    idx = {h: i for i, h in enumerate(header)}
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue
        out[row[0]] = {s: (int(row[idx[f"stage_{s}"]]) if row[idx[f"stage_{s}"]] not in (None, "") else None)
                       for s in subs}
    return out


def score(source: str, grader_log: str | None) -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    subs = rubric["subskill_order"]
    key = {k["item_id"]: k for k in json.loads((OUT / f"key_{source}.json").read_text())}
    sheets = sorted(OUT.glob(f"rating_sheet_{source}_*.xlsx"))
    if len(sheets) < 2:
        raise SystemExit("Need at least two filled rating sheets.")
    ratings = {p.stem.rsplit("_", 1)[-1]: _read_sheet(p, subs) for p in sheets}
    names = sorted(ratings)
    a, b = ratings[names[0]], ratings[names[1]]
    items = sorted(key)
    filled = [i for i in items if any(a.get(i, {}).get(s) is not None for s in subs)]
    if not filled:
        raise SystemExit("Sheets are empty; nothing to score yet.")

    grader = {}
    if grader_log:
        for e in _load(Path(grader_log)):
            if e.get("tool") != "validate_submission":
                continue
            # v0.2 rows carry a `stages` map; v0.1 rows only the flat stage_* columns
            e["stages"] = e.get("stages") or {s: e.get(f"stage_{s}") for s in subs}
            grader.setdefault(f"{e['student_id']}|{e['attempt_no']}", e)  # first pass only
    L = [f"# E01 / E10 agreement report ({source})", "",
         f"Raters: {names[0]}, {names[1]}. Items with ratings: {len(filled)}/{len(items)}.", ""]
    if source == "mock":
        L += ["> Synthetic calibration set. These numbers are for rater training only; do not report them.", ""]
    L += ["## E10 human vs. human (the ceiling)", "",
          "| Sub-skill | n | Exact | Adjacent | QWK |", "|---|---|---|---|---|"]
    hh = {}
    for s in subs:
        m = metrics.summarize([a.get(i, {}).get(s) for i in items], [b.get(i, {}).get(s) for i in items])
        hh[s] = m
        L.append(f"| {s} | {m['n']} | {m['exact']} | {m['adjacent']} | {m['qwk']} |")
    if grader:
        L += ["", "## E01 grader vs. each human, and vs. agreed items", "",
              "| Sub-skill | vs. " + names[0] + " QWK | vs. " + names[1] + " QWK | on items where humans agree: exact | QWK | n |",
              "|---|---|---|---|---|---|"]
        for s in subs:
            g = []
            for i in items:
                f = key[i]["input_hash_fields"]
                e = grader.get(f"{f['student_id']}|{f['attempt_no']}")
                g.append(e["stages"].get(s) if e else None)
            ma = metrics.summarize([a.get(i, {}).get(s) for i in items], g)
            mb = metrics.summarize([b.get(i, {}).get(s) for i in items], g)
            agreed = [(a[i][s], gi) for i, gi in zip(items, g)
                      if a.get(i, {}).get(s) is not None and a[i][s] == b.get(i, {}).get(s)]
            mg = metrics.summarize([x for x, _ in agreed], [y for _, y in agreed])
            L.append(f"| {s} | {ma['qwk']} | {mb['qwk']} | {mg['exact']} | {mg['qwk']} | {mg['n']} |")
        L += ["", "Pass threshold: set from the E10 numbers above (see README, Benchmark plan step 5)."]
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"E01_E10_agreement_report_{source}.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("make")
    m.add_argument("--source", choices=["mock", "real"], default="mock")
    m.add_argument("--n", type=int, default=30)
    m.add_argument("--raters", nargs="+", default=["A", "B"])
    m.add_argument("--seed", type=int, default=8)
    s = sp.add_parser("score")
    s.add_argument("--source", choices=["mock", "real"], default="mock")
    s.add_argument("--grader-log", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "make":
        make(args.source, args.n, args.raters, args.seed)
    else:
        score(args.source, args.grader_log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
