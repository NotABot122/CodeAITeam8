"""Simulated cohort data for evaluation items that need whole learning paths,
not single submissions. No model calls; reproducible from --seed.

Writes, under evaluation/data/:
  routing_sim_events.jsonl   event-log rows (validate_submission + route_next) for the
                             same cohort under 4 routing policies             (E06, E07)
  prepost_synthetic.jsonl    pre-test, post-test, and unaided transfer stages for an
                             adaptive group and a non-adaptive control group  (E04)
  telemetry_synthetic.jsonl  lesson-mode editor telemetry with ground-truth "stuck"
                             episodes, for testing proactive-hint triggers
and results/synthetic_cohort_report.md + synthetic_cohort_summary.json.

EVERYTHING HERE IS SIMULATED. The learning model is an assumption, and the
"agent" policy is a stand-in for the teammates' Stance Decider. The numbers
check that the analyses run end to end; they are not evidence about any policy.

Students come from data/mock_students.json (start stage, learning rate,
writing style), so these sets share IDs with the text submissions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"

SUBSKILLS = ("prompting", "evaluation", "prompt_revision")
LESSON = "L6"
MASTERY = 2          # lesson goal: Stage 2 on every sub-skill (assumption)
MAX_STEPS = 12       # about 45 minutes at ~4 minutes per task
FALLBACK_P = 0.03    # chance that one validate_submission call fails

_PREFIX = {"prompting": "P", "evaluation": "E", "prompt_revision": "R"}
TASKS = {f"C3-L6-{_PREFIX[s]}{lvl}": (s, lvl) for s in SUBSKILLS for lvl in (1, 2, 3)}
TASKS["C3-L6-X1"] = ("all", 2)   # cross-sub-skill "full iterate cycle" (BRIDGE stance)
FIXED_ORDER = ["C3-L6-P1", "C3-L6-E1", "C3-L6-R1", "C3-L6-P2", "C3-L6-E2", "C3-L6-R2",
               "C3-L6-X1", "C3-L6-P3", "C3-L6-E3", "C3-L6-R3"]
COMPLETE = "LESSON_COMPLETE"

# Learning model (assumption): a task one level above the current stage moves
# the student up with probability GAIN_P; far above rarely helps; at or below
# does nothing.
GAIN_P = {"slow": 0.35, "medium": 0.55, "fast": 0.75}

# Simulated grader noise, taken from run-20261103T233814Z-ec13d5 (Sonnet 4.6
# on the synthetic set): ~0.67 exact, ~0.97 within one stage.
P_EXACT, P_ADJ = 0.67, 0.97


def _rng(*parts) -> random.Random:
    return random.Random(int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16))


def _clamp(x: int) -> int:
    return max(0, min(3, x))


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def observe(true_stage: int, rng: random.Random) -> int:
    r = rng.random()
    if r < P_EXACT:
        return true_stage
    step = 1 if r < P_ADJ else 2
    return _clamp(true_stage + rng.choice((-step, step)))


def practice(true: dict, task: str, rate: str, rng: random.Random) -> list[str]:
    sub, lvl = TASKS[task]
    g = GAIN_P[rate]
    moved = []
    for s in (SUBSKILLS if sub == "all" else (sub,)):
        cur = true[s]
        if sub == "all":
            p = g * 0.5 if cur in (1, 2) else g * 0.1 if cur == 0 else 0.0
        elif lvl == cur + 1:
            p = g
        elif lvl > cur + 1:
            p = g * 0.15
        else:
            p = 0.0
        if cur < 3 and rng.random() < p:
            true[s] = cur + 1
            moved.append(s)
    return moved


def _task_for(sub: str, lvl: int) -> str:
    return f"C3-L6-{_PREFIX[sub]}{max(1, min(3, lvl))}"


# ---- policies: (observed stages, task history, rng) -> (task, stance, reason)

def pol_stage_rules(obs, hist, rng):
    s = min(SUBSKILLS, key=lambda k: (obs[k], SUBSKILLS.index(k)))
    return _task_for(s, obs[s] + 1), "STANCE_ADVANCE", f"weakest observed sub-skill {s}={obs[s]}"


def pol_agent(obs, hist, rng):
    """Stand-in for the Stance Decider: stage rules plus BRIDGE and REINFORCE."""
    below = [s for s in SUBSKILLS if obs[s] < MASTERY]
    if len(below) == 1 and min(obs.values()) >= 1 and "C3-L6-X1" not in hist[-3:]:
        return "C3-L6-X1", "STANCE_BRIDGE", f"only {below[0]} below mastery; cross-skill task"
    s = min(SUBSKILLS, key=lambda k: (obs[k], SUBSKILLS.index(k)))
    nxt = _task_for(s, obs[s] + 1)
    if len(hist) >= 2 and hist[-1] == hist[-2] == nxt:
        return _task_for(s, obs[s]), "STANCE_REINFORCE", f"{nxt} twice without progress; step back on {s}"
    return nxt, "STANCE_ADVANCE", f"advance {s} from observed {obs[s]}"


def pol_fixed_order(obs, hist, rng):
    done = sum(t in FIXED_ORDER for t in hist)
    return FIXED_ORDER[done % len(FIXED_ORDER)], None, "next task in authored order"


def pol_random(obs, hist, rng):
    return rng.choice(list(TASKS)), None, "uniform random task"


POLICIES = {"stage_rules": pol_stage_rules, "agent": pol_agent,
            "fixed_order": pol_fixed_order, "random": pol_random}


CONTRACT_VERSION = "0.2"
RUBRIC_ID = "C3-L6-v0.1-draft"


def _row(run_id, sid, ts, task, tool, obs, step, **extra):
    row = {"timestamp": ts.isoformat(), "contract_version": CONTRACT_VERSION, "run_id": run_id,
           "student_id": sid, "lesson_id": LESSON, "task_id": task, "rubric_id": RUBRIC_ID,
           "attempt_no": step, "tool": tool, "stages": dict(obs), "needs_review": False,
           "temperature": 0.0, "filter_result": [], "error": None}
    row.update(extra)
    return row


def run_episode(profile, policy, run_id, t0, events, seed, max_steps=MAX_STEPS):
    """One student, one policy. events (list or None) receives event-log rows."""
    sid = profile["student_id"]
    rng = _rng(seed, sid, policy)
    true = dict(profile["start_stage"])
    obs = {s: observe(true[s], rng) for s in SUBSKILLS}    # diagnostic reading = pre-test
    hist: list[str] = []
    res = {"student_id": sid, "policy": policy, "start_true": dict(true), "pre_obs": dict(obs),
           "true_mastery_step": 0 if all(v >= MASTERY for v in true.values()) else None,
           "declared_complete_step": None, "premature_complete": False,
           "wasted_steps": 0, "repeats": 0, "loops": 0,
           "fallbacks": 0, "fallback_steps": 0, "stages_reset_after_failure": 0,
           "last_gain_step": {s: None for s in SUBSKILLS}}
    use_fallback = False
    for step in range(1, max_steps + 1):
        ts = t0 + timedelta(minutes=4 * step)
        if all(v >= MASTERY for v in obs.values()):
            task, stance, reason = COMPLETE, "STANCE_PROJECT_SYNTHESIS", "all observed stages at mastery"
        elif use_fallback:
            task, stance, reason = pol_fixed_order(obs, hist, rng)
            reason = "fallback after validation failure: " + reason
            res["fallback_steps"] += 1
        else:
            task, stance, reason = POLICIES[policy](obs, hist, rng)
        out = {"contract_version": CONTRACT_VERSION, "next_task_id": task, "reason": reason,
               "policy": "fixed_order" if use_fallback else policy, "fallback": use_fallback}
        if stance:
            out["stance"] = stance
        if events is not None:
            events.append(_row(run_id, sid, ts, task, "route_next", obs, step,
                               input_hash=_hash([sid, policy, obs, step]), output=out,
                               model_id=f"sim-policy:{policy}", tokens_in=0, tokens_out=0,
                               cost_usd=0.0, latency_ms=700 if policy == "agent" else 40,
                               fallback_triggered=use_fallback,
                               sim={"true_stage": dict(true), "step": step}))
        if task == COMPLETE:
            res["declared_complete_step"] = step - 1
            res["premature_complete"] = not all(v >= MASTERY for v in true.values())
            break

        sub, lvl = TASKS[task]
        if sub != "all" and lvl <= true[sub]:
            res["wasted_steps"] += 1
        if hist and hist[-1] == task:
            res["repeats"] += 1
        if len(hist) >= 3 and hist[-1] != task and hist[-2] == task and hist[-3] == hist[-1]:
            res["loops"] += 1
        hist.append(task)

        for s in practice(true, task, profile["learning_rate"], rng):
            res["last_gain_step"][s] = step

        failed = rng.random() < FALLBACK_P
        before = dict(obs)
        if failed:
            res["fallbacks"] += 1
            # contract: on failure keep the last known stages (progress preserved)
        else:
            for s in (SUBSKILLS if sub == "all" else (sub,)):
                obs[s] = observe(true[s], rng)
        if failed and any(obs[s] < before[s] for s in SUBSKILLS):
            res["stages_reset_after_failure"] += 1
        use_fallback = failed
        if events is not None:
            events.append(_row(run_id, sid, ts + timedelta(minutes=3), task, "validate_submission", obs, step,
                               input_hash=_hash([sid, task, step]), output={"simulated": True},
                               model_id="sim-grader",
                               tokens_in=0 if failed else 1169, tokens_out=0 if failed else 496,
                               cost_usd=None,
                               latency_ms=0 if failed else int(rng.lognormvariate(8.4, 0.15)),
                               fallback_triggered=failed,
                               error="SimulatedServiceError: validation unavailable" if failed else None,
                               sim={"true_stage": dict(true), "step": step, "policy": policy,
                                    "pre_obs": res["pre_obs"]}))
        if res["true_mastery_step"] is None and all(v >= MASTERY for v in true.values()):
            res["true_mastery_step"] = step
    res["end_true"], res["end_obs"], res["steps_used"] = dict(true), dict(obs), len(hist)
    return res


# ---------------------------------------------------------------- E05

def lesson_funnel(events, policy="agent"):
    """E05, computed from observed stages in the event log (not from the `sim`
    ground truth), the way it would run on real logs.
    - per task: attempts, and the share after which the observed stage of the
      task's sub-skill went up (did the task move students?);
    - per sub-skill: share of students whose highest observed stage reached
      1, 2, 3 (stage-transition funnel; the Stage 3 column = Stage 3 evidence coverage).
    The starting stages come from the diagnostic reading; in real logs that is
    the pre-test row."""
    by_student = {}
    for e in events:
        if e["tool"] == "validate_submission" and e["sim"]["policy"] == policy:
            by_student.setdefault(e["student_id"], []).append(e)
    task_stats, best = {}, {s: {} for s in SUBSKILLS}
    for sid, evs in by_student.items():
        evs.sort(key=lambda e: e["attempt_no"])
        prev = evs[0]["sim"]["pre_obs"]
        for s in SUBSKILLS:
            best[s][sid] = prev[s]
        for e in evs:
            sub = TASKS[e["task_id"]][0]
            touched = SUBSKILLS if sub == "all" else (sub,)
            st = task_stats.setdefault(e["task_id"], {"attempts": 0, "moved_up": 0, "failed_calls": 0})
            st["attempts"] += 1
            if e["fallback_triggered"]:
                st["failed_calls"] += 1
            elif any(e["stages"][s] > prev[s] for s in touched):
                st["moved_up"] += 1
            prev = e["stages"]
            for s in SUBSKILLS:
                best[s][sid] = max(best[s][sid], prev[s])
    n = len(by_student)
    tasks = [{"task_id": t, **v, "moved_up_rate": round(v["moved_up"] / v["attempts"], 3)}
             for t, v in sorted(task_stats.items())]
    funnel = {s: {f"reached_{k}": round(sum(v >= k for v in best[s].values()) / n, 3) for k in (1, 2, 3)}
              for s in SUBSKILLS}
    return {"policy": policy, "students": n, "tasks": tasks, "funnel": funnel}


# ---------------------------------------------------------------- E04

def transfer_stage(true_stage, gained_late, rng):
    """Unaided transfer task (assumption): gains made in the last few steps,
    with AI help, hold up less often without it."""
    drop = 0.3 if gained_late else 0.1
    return _clamp(true_stage - (1 if rng.random() < drop else 0))


def run_prepost(profiles, seed, run_id, t0):
    order = sorted(profiles, key=lambda p: _rng(seed, "assign", p["student_id"]).random())
    rows = []
    for i, p in enumerate(order):
        condition = "adaptive" if i % 2 == 0 else "control"
        policy = "agent" if condition == "adaptive" else "fixed_order"
        ep = run_episode(p, policy, run_id, t0, None, seed + 1)
        rng = _rng(seed, "post", p["student_id"])
        last = ep["steps_used"]
        post = {s: observe(ep["end_true"][s], rng) for s in SUBSKILLS}
        transfer = {s: observe(transfer_stage(ep["end_true"][s],
                                              (ep["last_gain_step"][s] or -9) >= last - 2, rng), rng)
                    for s in SUBSKILLS}
        rows.append({"student_id": p["student_id"], "condition": condition, "policy": policy,
                     "writing_style": p["writing_style"], "learning_rate": p["learning_rate"],
                     "pre": ep["pre_obs"], "post": post, "transfer": transfer,
                     "minutes": 4 * ep["steps_used"], "synthetic": True,
                     "sim": {"start_true": ep["start_true"], "end_true": ep["end_true"]}})
    return rows


# ---------------------------------------------------------------- telemetry

ERROR_TYPES = ["unclosed_tag", "css_syntax", "broken_image_path", "layout_mismatch"]


def sim_telemetry(p, seed, t0, duration_s=1800):
    rng = _rng(seed, "telemetry", p["student_id"])
    level = statistics.mean(p["start_stage"].values())
    p_err, p_stuck, p_recover = 0.45 - 0.1 * level, 0.5 - 0.12 * level, 0.12 + 0.05 * level
    sess = f"TEL-{p['student_id']}"
    state = {"t": 0, "seq": 0, "stuck": False, "ep": None, "n": 0, "err": None}
    events = []

    def emit(etype, **payload):
        state["seq"] += 1
        events.append({"timestamp": (t0 + timedelta(seconds=state["t"])).isoformat(),
                       "session_id": sess, "student_id": p["student_id"], "lesson_id": LESSON,
                       "task_id": "C3-L6-STUDIO", "seq": state["seq"], "event_type": etype, **payload,
                       "sim": {"stuck": state["stuck"], "episode": state["ep"]}})

    emit("session_start")
    while state["t"] < duration_s:
        if not state["stuck"]:
            a = rng.choices(["edit", "run", "ai_prompt", "idle"], [0.55, 0.2, 0.1, 0.15])[0]
            if a == "edit":
                state["t"] += rng.randint(10, 60)
                emit("edit", chars_added=rng.randint(10, 200), chars_deleted=rng.randint(0, 40))
            elif a == "run":
                state["t"] += 3
                if rng.random() < p_err:
                    state["err"] = rng.choice(ERROR_TYPES)
                    if rng.random() < p_stuck:
                        state["stuck"], state["n"] = True, state["n"] + 1
                        state["ep"] = f"{sess}-S{state['n']}"
                    emit("run", run_result="error", error_type=state["err"])
                else:
                    emit("run", run_result="ok")
            elif a == "ai_prompt":
                state["t"] += 20
                emit("ai_prompt", prompt_chars=rng.randint(40, 400))
            else:
                # reading / thinking pauses; some are long, so the trigger can misfire
                secs = rng.randint(10, 120)
                state["t"] += secs
                emit("idle", idle_seconds=secs)
        else:
            a = rng.choices(["idle", "run", "edit", "hint"], [0.4, 0.3, 0.2, 0.1])[0]
            recover = p_recover
            if a == "idle":
                secs = rng.randint(40, 180)
                state["t"] += secs
                emit("idle", idle_seconds=secs)
            elif a == "run":
                state["t"] += 3
                emit("run", run_result="error", error_type=state["err"])
            elif a == "edit":
                state["t"] += rng.randint(10, 40)
                emit("edit", chars_added=rng.randint(0, 20), chars_deleted=rng.randint(10, 80))
            else:
                state["t"] += 5
                emit("hint_shown", hint_source="student_request")
                recover = 0.6
            if rng.random() < recover:
                state["stuck"], state["ep"] = False, None
                state["t"] += rng.randint(15, 60)
                emit("run", run_result="ok")
    emit("session_end")
    return events


def detect_stuck(events, idle_threshold=60, repeat_errors=3, cooldown=120):
    """Baseline proactive-hint trigger to be evaluated (teammates can swap in
    theirs): long idle within 3 events of an error, or the same error N times
    in a row; cooldown between hints."""
    triggers, last_err, same, since_err, last_fire = [], None, 0, 99, None
    for e in events:
        ts = datetime.fromisoformat(e["timestamp"])
        fire = False
        if e["event_type"] == "run":
            if e.get("run_result") == "error":
                same = same + 1 if e.get("error_type") == last_err else 1
                last_err, since_err = e.get("error_type"), 0
                fire = same >= repeat_errors
            else:
                last_err, same, since_err = None, 0, 99
        else:
            since_err += 1
            if e["event_type"] == "idle" and e.get("idle_seconds", 0) >= idle_threshold and since_err <= 3:
                fire = True
        if fire and (last_fire is None or (ts - last_fire).total_seconds() >= cooldown):
            triggers.append(e)
            last_fire = ts
    return triggers


def evaluate_triggers(sessions):
    episodes, detected, delays, tp, fp = 0, 0, [], 0, 0
    for events in sessions:
        starts = {}
        for e in events:
            ep = e["sim"]["episode"]
            if ep and ep not in starts:
                starts[ep] = datetime.fromisoformat(e["timestamp"])
        episodes += len(starts)
        hit = set()
        for tr in detect_stuck(events):
            ep = tr["sim"]["episode"]
            if not ep:
                fp += 1
                continue
            tp += 1
            if ep not in hit:
                hit.add(ep)
                delays.append((datetime.fromisoformat(tr["timestamp"]) - starts[ep]).total_seconds())
        detected += len(hit)
    return {"sessions": len(sessions), "stuck_episodes": episodes, "episodes_detected": detected,
            "episode_recall": round(detected / episodes, 3) if episodes else None,
            "trigger_precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "false_triggers_per_session": round(fp / len(sessions), 2),
            "median_detection_delay_s": statistics.median(delays) if delays else None}


# ---------------------------------------------------------------- summaries and report

def _mean(xs):
    return round(statistics.mean(xs), 2) if xs else None


def policy_table(eps):
    rows = []
    for pol in POLICIES:
        e = [x for x in eps if x["policy"] == pol]
        n = len(e)
        mastered = [x["true_mastery_step"] for x in e if x["true_mastery_step"] is not None]
        with_fb = [x for x in e if x["fallbacks"]]
        rows.append({
            "policy": pol, "n": n,
            "mastered_rate": round(len(mastered) / n, 3),
            "median_steps_to_mastery": statistics.median(mastered) if mastered else None,
            "declared_complete_rate": round(sum(x["declared_complete_step"] is not None for x in e) / n, 3),
            "premature_complete_rate": round(sum(x["premature_complete"] for x in e) / n, 3),
            "wasted_steps_per_student": _mean([x["wasted_steps"] for x in e]),
            "repeats_per_student": _mean([x["repeats"] for x in e]),
            "loops_per_student": _mean([x["loops"] for x in e]),
            "validation_failures": sum(x["fallbacks"] for x in e),
            "students_with_failure": len(with_fb),
            "fallback_steps": sum(x["fallback_steps"] for x in e),
            "stages_reset_after_failure": sum(x["stages_reset_after_failure"] for x in e),
            "mastered_rate_after_failure": round(sum(x["true_mastery_step"] is not None for x in with_fb)
                                                 / len(with_fb), 3) if with_fb else None,
        })
    return rows


def prepost_table(rows):
    out = {}
    for cond in ("adaptive", "control"):
        r = [x for x in rows if x["condition"] == cond]
        out[cond] = {"n": len(r), "minutes": _mean([x["minutes"] for x in r])}
        for s in SUBSKILLS:
            out[cond][s] = {"pre": _mean([x["pre"][s] for x in r]), "post": _mean([x["post"][s] for x in r]),
                            "transfer": _mean([x["transfer"][s] for x in r]),
                            "gain_post": _mean([x["post"][s] - x["pre"][s] for x in r]),
                            "gain_transfer": _mean([x["transfer"][s] - x["pre"][s] for x in r])}
    g = {c: [statistics.mean(x["transfer"][s] - x["pre"][s] for s in SUBSKILLS)
             for x in rows if x["condition"] == c] for c in ("adaptive", "control")}
    sd = statistics.pstdev(g["adaptive"] + g["control"]) or 1.0
    diff = statistics.mean(g["adaptive"]) - statistics.mean(g["control"])
    out["transfer_gain_diff"] = round(diff, 2)
    out["standardized_transfer_diff"] = round(diff / sd, 2)
    return out


def write_report(path, run_id, n, pol, pp, tel, seed, fun):
    L = [f"# Synthetic cohort report: `{run_id}`", "",
         f"- Students: {n} (from `data/mock_students.json`), seed {seed}",
         f"- Lesson budget: {MAX_STEPS} tasks (~45 min); mastery = Stage {MASTERY} on every sub-skill",
         f"- Simulated grader noise: {P_EXACT} exact, {P_ADJ} within one stage (from the first harness run)",
         f"- Simulated validation failure rate per call: {FALLBACK_P}", "",
         "> **Everything here is simulated.** The learning model and the `agent` policy are assumptions "
         "written by the evaluation workstream. These tables check that the E04 / E06 / E07 / telemetry "
         "analyses run end to end; they say nothing about whether a real policy works.", "",
         "## E06 routing policy comparison (same cohort, 4 policies)", "",
         "| Policy | Mastered in budget | Median steps to mastery | Declared complete | "
         "Declared complete too early | Wasted steps / student | Repeats / student | A-B-A-B loops / student |",
         "|---|---|---|---|---|---|---|---|"]
    for r in pol:
        L.append(f"| {r['policy']} | {r['mastered_rate']} | {r['median_steps_to_mastery']} | "
                 f"{r['declared_complete_rate']} | {r['premature_complete_rate']} | "
                 f"{r['wasted_steps_per_student']} | {r['repeats_per_student']} | {r['loops_per_student']} |")
    L += ["", "Wasted = a task at or below the student's true stage. Declared complete too early = the "
          "observed stages reached mastery because of grader noise while the true stages had not.", "",
          "## E07 fallback (validation failure → next step from the authored order)", "",
          "| Policy | Validation failures | Students affected | Fallback steps | Stages reset after failure | "
          "Mastered rate of affected students |", "|---|---|---|---|---|---|"]
    L += [f"| {r['policy']} | {r['validation_failures']} | {r['students_with_failure']} | {r['fallback_steps']} | "
          f"{r['stages_reset_after_failure']} | {r['mastered_rate_after_failure']} |" for r in pol]
    L += ["", "## E05 lesson funnel (agent policy, observed stages from the event log)", "",
          "| Task | Attempts | Observed stage went up | Rate | Failed calls |", "|---|---|---|---|---|"]
    L += [f"| {t['task_id']} | {t['attempts']} | {t['moved_up']} | {t['moved_up_rate']} | {t['failed_calls']} |"
          for t in fun["tasks"]]
    L += ["", "Share of students whose highest observed stage reached each level "
          "(Stage 3 column = Stage 3 evidence coverage):", "",
          "| Sub-skill | ≥ 1 | ≥ 2 | ≥ 3 |", "|---|---|---|---|"]
    L += [f"| {s} | {d['reached_1']} | {d['reached_2']} | {d['reached_3']} |" for s, d in fun["funnel"].items()]
    L += ["", "## E04 pre / post / unaided transfer (adaptive = agent policy, control = fixed order)", "",
          "| Group | Sub-skill | Pre | Post | Transfer | Gain (post) | Gain (transfer) |",
          "|---|---|---|---|---|---|---|"]
    for cond in ("adaptive", "control"):
        for s in SUBSKILLS:
            d = pp[cond][s]
            L.append(f"| {cond} (n={pp[cond]['n']}) | {s} | {d['pre']} | {d['post']} | {d['transfer']} | "
                     f"{d['gain_post']} | {d['gain_transfer']} |")
    L += ["", f"Transfer gain, adaptive minus control (mean over sub-skills): {pp['transfer_gain_diff']} stages "
          f"(standardized {pp['standardized_transfer_diff']}). A real pilot of this size is reported "
          "descriptively as a protocol check, not as an efficacy claim.", "",
          "## Lesson-mode telemetry: baseline proactive-hint trigger", "",
          "Rule under test: idle ≥ 60 s within 3 events of an error, or the same error 3 times in a row; "
          "120 s cooldown. Ground truth = simulated stuck episodes.", "",
          "| Sessions | Stuck episodes | Detected | Episode recall | Trigger precision | "
          "False triggers / session | Median detection delay (s) |", "|---|---|---|---|---|---|---|",
          f"| {tel['sessions']} | {tel['stuck_episodes']} | {tel['episodes_detected']} | {tel['episode_recall']} | "
          f"{tel['trigger_precision']} | {tel['false_triggers_per_session']} | {tel['median_detection_delay_s']} |", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Simulated cohort data for E04, E06, E07, and telemetry.")
    ap.add_argument("--seed", type=int, default=8)
    args = ap.parse_args(argv)
    profiles = json.loads((DATA / "mock_students.json").read_text(encoding="utf-8"))
    run_id = f"sim-seed{args.seed}-n{len(profiles)}"
    t0 = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)

    events, eps = [], []
    for p in profiles:
        for pol in POLICIES:
            eps.append(run_episode(p, pol, run_id, t0, events, args.seed))
    _write_jsonl(DATA / "routing_sim_events.jsonl", events)

    pp_rows = run_prepost(profiles, args.seed, run_id, t0)
    _write_jsonl(DATA / "prepost_synthetic.jsonl", pp_rows)

    sessions = [sim_telemetry(p, args.seed, t0) for p in profiles]
    _write_jsonl(DATA / "telemetry_synthetic.jsonl", [e for s in sessions for e in s])

    pol, pp, tel = policy_table(eps), prepost_table(pp_rows), evaluate_triggers(sessions)
    fun = lesson_funnel(events)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "synthetic_cohort_summary.json").write_text(
        json.dumps({"run_id": run_id, "contract_version": CONTRACT_VERSION, "E06_E07": pol, "E05": fun,
                    "E04": pp, "telemetry": tel}, indent=2), encoding="utf-8")
    write_report(RESULTS / "synthetic_cohort_report.md", run_id, len(profiles), pol, pp, tel, args.seed, fun)
    print(f"{len(events)} routing events, {len(pp_rows)} pre/post rows, "
          f"{sum(len(s) for s in sessions)} telemetry events -> results/synthetic_cohort_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
