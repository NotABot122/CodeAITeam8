"""DiagnosticEngine: runs one student's quest from start to placement.

Every public method returns a plain, JSON-ready dict and saves the quest, so a thin
API (diagnostic/api.py), the CLI, or a test can drive it the same way:

    options()                     what the start screen shows (buddies, goals)
    start(buddy, goal, goal_text) create a student; returns the first screen
    next(student_id)              the current question (the same one until it is answered)
    answer(student_id, response)  score it; returns kind feedback and game progress
    finish(student_id)            place the student; returns the closing screen
    result / skill_tree           student-safe views of a finished quest
    teacher_report(student_id)    stages, evidence and placement. Teachers only

Failure handling follows the project's "never block the student" rule:
  - if choosing the next question fails, the quest continues in a fixed order;
  - if the model is unavailable or answers badly, the deterministic placement is used;
  - both are logged (fallback_triggered) for the evaluation harness.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.ai import ModelProvider
from engine.events import EventLog
from engine.project import Project, load_project

from . import game, views
from .ai.advisor import AdviceResult, advise
from .ai.reader import ExplainReading, read_explanation
from .content import Content, load_content
from .contract import RUBRIC_ID, output_from_reading
from .eval_log import EvalEventLog
from .models import ROLE_BONUS, InvalidResponse, ItemResult
from .paths import PathLike, data_dir as default_data_dir, project_dir as default_project_dir
from .placement import Placement, build_placement
from .report import teacher_report
from .safety import clean_goal_text
from .scoring import accumulate_points, estimate_all, score_response
from .selector import DONE, Step, fixed_plan, fixed_step, next_step, zone_complete
from .state import (COMPLETE, EXPLAIN_ANSWERED, EXPLAIN_FLAGGED, EXPLAIN_SKIPPED, KIND_BOOSTER, KIND_EXPLAIN,
                    KIND_ITEM, ExplainRecord, DiagnosticState, Pending, now_iso)
from .store import DiagnosticStore, StateLoadError

MAX_ELAPSED_MS = 10 * 60 * 1000

REASON_SELECTOR_ERROR = "selector_error"
REASON_ADAPTIVE_OFF = "adaptive_disabled"
REASON_LOAD_FAILURE = "progress_load_failure"


class UnknownQuest(LookupError):
    """No quest has been started for this student id."""


class NothingPending(ValueError):
    """An answer arrived but no question is waiting. Call next() first."""


class NotFinished(ValueError):
    """The result was asked for before the quest finished."""


class DiagnosticEngine:
    def __init__(self, project: Project, content: Content, store: DiagnosticStore, events: EventLog,
                 eval_log: EvalEventLog, provider: Optional[ModelProvider] = None, adaptive: bool = True):
        self.project = project
        self.manifest = project.manifest
        self.content = content
        self.store = store
        self.events = events
        self.eval_log = eval_log
        self.provider = provider
        self.adaptive = adaptive

    @classmethod
    def from_paths(cls, project: Optional[PathLike] = None, data: Optional[PathLike] = None,
                   provider: Optional[ModelProvider] = None, adaptive: bool = True,
                   run_id: Optional[str] = None) -> "DiagnosticEngine":
        loaded = load_project(default_project_dir(project))
        content = load_content(loaded.root, loaded.manifest.concept_ids())
        root = default_data_dir(data)
        return cls(loaded, content, DiagnosticStore(root), EventLog(root), EvalEventLog(root, run_id), provider, adaptive)

    # Screens ---------------------------------------------------------------------------
    def options(self) -> Dict[str, Any]:
        cfg = self.content.config
        guide = game.guide(self.content)
        return self._student({
            "title": cfg.title, "guide": guide["name"],
            "message": guide["welcome"].replace("{guide}", guide["name"]),
            "buddies": [{"id": b, "label": label} for b, label in cfg.buddies],
            "goals": [{"id": g.id, "label": g.label} for g in self.content.goals.values()],
            "zones": [{"id": z.id, "name": z.name, "story": z.story} for z in self.content.zones],
        })

    def start(self, buddy: Optional[str] = None, goal: Optional[str] = None,
              goal_text: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.content.config
        notices: List[str] = []
        buddy_ids = [b for b, _ in cfg.buddies]
        goal_id = goal if goal in self.content.goals else self.content.default_goal().id
        cleaned, flags = clean_goal_text(goal_text, cfg.text.max_goal_chars)
        if goal_text and cleaned is None:
            notices.append(game.guide(self.content)["goal_flagged"])
        student_id = self.store.new_student()
        state = DiagnosticState(student_id=student_id, quest_id=cfg.id, goal_id=goal_id,
                                buddy=buddy if buddy in buddy_ids else buddy_ids[0], goal_text=cleaned)
        if not self.adaptive:
            self._enter_fallback(state, REASON_ADAPTIVE_OFF)
        self.store.save(state)
        self.events.write("diagnostic_started", student_id=student_id, project_id=self.project.id)
        first = self.next(student_id)
        return self._student({"student_id": student_id, "welcome": views.welcome_view(self.content, state),
                              "notices": notices, "first": first})

    def next(self, student_id: str) -> Dict[str, Any]:
        state, notices = self._load(student_id)
        if state.phase == COMPLETE:
            return self._result_payload(state)
        if state.pending is None:
            step = self._choose_step(state)
            if step.kind == DONE:
                return self._finish(state, notices)
            self._serve(state, step)
            self.store.save(state)
        return self._student({"done": False, "step": self._step_view(state, state.pending), "notices": notices,
                              "zones": game.zone_progress(self.content, state, self._current_concept(state)),
                              "game": game.game_view(self.content, state)})

    def answer(self, student_id: str, response: Any, elapsed_ms: Optional[int] = None) -> Dict[str, Any]:
        state, _ = self._load(student_id)
        if state.pending is None:
            raise NothingPending("no question is waiting; ask for the next one first")
        pending = state.pending
        if pending.kind == KIND_EXPLAIN:
            feedback = self._answer_explain(state, pending, response)
        elif pending.kind == KIND_BOOSTER:
            feedback = self._answer_booster(state, pending, response)
        else:
            feedback = self._answer_item(state, pending, response, elapsed_ms)
        if isinstance(elapsed_ms, int) and not isinstance(elapsed_ms, bool) and 0 <= elapsed_ms <= MAX_ELAPSED_MS:
            state.elapsed_ms_total += elapsed_ms
        state.pending = None
        feedback["zone_cleared"] = self._close_finished_zones(state)
        self.store.save(state)
        return self._student({"feedback": feedback, "game": game.game_view(self.content, state),
                              "zones": game.zone_progress(self.content, state, self._current_concept(state))})

    def finish(self, student_id: str) -> Dict[str, Any]:
        state, notices = self._load(student_id)
        if state.phase == COMPLETE:
            return self._result_payload(state)
        return self._finish(state, notices)

    def result(self, student_id: str) -> Dict[str, Any]:
        state, _ = self._load(student_id)
        if state.phase != COMPLETE:
            raise NotFinished("the quest is not finished yet")
        return self._result_payload(state)

    def skill_tree(self, student_id: str) -> Dict[str, Any]:
        state, _ = self._load(student_id)
        node_states = self._node_states(state)
        start = self._placement(state).concepts if state.placement else {}
        start_nodes = [n for p in start.values() for n in p.start_nodes]
        return self._student({"tree": views.tree_view(self.content, node_states, start_nodes),
                              "finished": state.phase == COMPLETE})

    def teacher_report(self, student_id: str) -> Dict[str, Any]:
        """Teachers only: has stages, confidence and answers' mistakes. An interim report works mid-quest."""
        state, _ = self._load(student_id)
        estimates = estimate_all(self.content.concepts(), state.results, self.content.config.scoring)
        node_states = self._node_states(state)
        if state.placement:
            placement = self._placement(state)
        else:
            placement = build_placement(self.content, self.manifest, state, estimates, node_states, None)
        report = teacher_report(self.content, state, estimates, node_states, placement)
        report["finished"] = state.phase == COMPLETE
        return report

    # Choosing the next step -------------------------------------------------------------
    def _choose_step(self, state: DiagnosticState) -> Step:
        if not state.on_fallback:
            try:
                return next_step(state, self.content)
            except Exception as exc:                       # any selector failure falls back
                self._enter_fallback(state, f"{REASON_SELECTOR_ERROR}: {type(exc).__name__}")
        return fixed_step(state)

    def _enter_fallback(self, state: DiagnosticState, reason: str) -> None:
        state.on_fallback = True
        state.fallback_reason = reason
        state.fixed_queue = fixed_plan(state, self.content)
        self.events.write("fallback", student_id=state.student_id, project_id=self.project.id,
                          reason=reason.split(":")[0])

    def _serve(self, state: DiagnosticState, step: Step) -> None:
        state.pending = Pending(step.kind, step.id, step.role)
        if step.kind == KIND_ITEM:
            state.served.append(step.id)
        elif step.kind == KIND_BOOSTER:
            state.boosters_served.append(step.id)

    def _current_concept(self, state: DiagnosticState) -> Optional[str]:
        pending = state.pending
        if pending is None:
            return None
        if pending.kind == KIND_ITEM:
            return self.content.items[pending.id].concept
        if pending.kind == KIND_EXPLAIN:
            return next((c for c, p in self.content.explain.items() if p.id == pending.id), None)
        return None

    def _step_view(self, state: DiagnosticState, pending: Pending) -> Dict[str, Any]:
        lines = game.guide(self.content)
        if pending.kind == KIND_EXPLAIN:
            concept = self._current_concept(state)
            return views.explain_view(self.content, state, concept)
        if pending.kind == KIND_BOOSTER:
            booster = next(b for b in self.content.boosters if b.id == pending.id)
            view = views.item_view(self.content, state, booster, kind="booster")
            view["intro"] = lines["booster_intro"]
            return view
        item = self.content.items[pending.id]
        view = views.item_view(self.content, state, item)
        if pending.role == ROLE_BONUS:
            view["intro"] = lines["bonus_intro"]
        elif not any(r.concept == item.concept for r in state.results):
            view["intro"] = self.content.zone_for(item.concept).story
        return view

    # Answers -------------------------------------------------------------------------------
    def _answer_item(self, state: DiagnosticState, pending: Pending, response: Any,
                     elapsed_ms: Optional[int]) -> Dict[str, Any]:
        item = self.content.items[pending.id]
        score = score_response(item, response)             # InvalidResponse leaves the state untouched
        clean_elapsed = elapsed_ms if isinstance(elapsed_ms, int) and not isinstance(elapsed_ms, bool) and \
            0 <= elapsed_ms <= MAX_ELAPSED_MS else None
        state.results.append(ItemResult(item.id, item.concept, item.tier, pending.role, score.credit, score.passed,
                                        round(item.guess_chance, 4), score.misconception, clean_elapsed))
        badges = game.record_answer(self.content, state, score.passed)
        return game.answer_feedback(self.content, state, item, score, badges)

    def _answer_booster(self, state: DiagnosticState, pending: Pending, response: Any) -> Dict[str, Any]:
        booster = next(b for b in self.content.boosters if b.id == pending.id)
        score = score_response(booster, response)
        game.record_booster(self.content, state)
        lines = game.guide(self.content)
        return {"correct": score.passed, "message": booster.feedback_right if score.passed else lines["wrong"][0],
                "tip": None, "new_badges": []}

    def _answer_explain(self, state: DiagnosticState, pending: Pending, response: Any) -> Dict[str, Any]:
        concept = self._current_concept(state)
        prompt = self.content.explain[concept]
        lines = game.guide(self.content)
        if not isinstance(response, dict):
            raise InvalidResponse("send the text, or skip")
        if response.get("skip") is True:
            state.explain[concept] = ExplainRecord(concept, EXPLAIN_SKIPPED)
            return {"correct": None, "message": lines["explain_skip"], "tip": None, "new_badges": []}
        text = response.get("text")
        if not isinstance(text, str):
            raise InvalidResponse("send the text, or skip")

        zone = self.content.zone_for(concept)
        reading = read_explanation(prompt, zone.name, text, self.provider, self.content.config)
        self._log_reading(state, prompt.id, text, reading)
        if reading.unscorable and reading.error is None:
            state.explain[concept] = ExplainRecord(concept, EXPLAIN_FLAGGED, None, list(reading.flags), None, 0.0,
                                                   reading.rationale, [], reading.keyword_stage, reading.model_id)
            return {"correct": None, "message": lines["flagged_text"], "tip": None, "new_badges": []}
        state.explain[concept] = ExplainRecord(
            concept, EXPLAIN_ANSWERED, " ".join(text.split())[: self.content.config.text.max_chars],
            list(reading.flags), reading.stage, reading.confidence, reading.rationale, list(reading.quotes),
            reading.keyword_stage, reading.model_id, reading.fallback)
        badges = game.record_explain(self.content, state)
        return {"correct": None, "message": "Thank you! That helps " + lines["name"] + " a lot.", "tip": None,
                "new_badges": [{"id": b, "name": game.badge_name(self.content, b)} for b in badges]}

    def _log_reading(self, state: DiagnosticState, prompt_id: str, text: str, reading: ExplainReading) -> None:
        tool_input = {"student_id": state.student_id, "lesson_id": self.content.config.id, "level_id": prompt_id,
                      "attempt_no": 1, "submission_text": text, "rubric_id": RUBRIC_ID}
        prompt = next(p for p in self.content.explain.values() if p.id == prompt_id)
        self.eval_log.write_validate(state.student_id, self.content.config.id, prompt_id, 1, tool_input,
                                     output_from_reading(prompt, reading), fallback=reading.fallback,
                                     error=reading.error)

    def _close_finished_zones(self, state: DiagnosticState) -> Optional[Dict[str, Any]]:
        cleared = None
        for zone in self.content.zones:
            if zone.concept not in state.zones_done and zone_complete(state, self.content, zone.concept):
                state.zones_done.append(zone.concept)
                badge = game.award_badge(state, "zone_clear")
                cleared = {"zone": zone.name, "message": zone.done_message,
                           "new_badge": {"id": badge, "name": game.badge_name(self.content, badge)} if badge else None}
        return cleared

    # Finishing -----------------------------------------------------------------------------
    def _node_states(self, state: DiagnosticState):
        th = self.content.config.thresholds
        return self.content.tree.evaluate(accumulate_points(state.results, self.content.items), th.unlock, th.master)

    def _placement(self, state: DiagnosticState) -> Placement:
        return Placement.from_dict(state.placement)

    def _finish(self, state: DiagnosticState, notices: List[str]) -> Dict[str, Any]:
        estimates = estimate_all(self.content.concepts(), state.results, self.content.config.scoring)
        node_states = self._node_states(state)
        advice_result = advise(self.content, state, estimates, node_states, self.provider)
        placement = build_placement(self.content, self.manifest, state, estimates, node_states, advice_result.advice,
                                    advice_result.model_id, model_configured=self.provider is not None)
        self._log_route(state, placement, advice_result)
        game.award_badge(state, "quest_done")
        state.placement = placement.to_dict()
        state.phase = COMPLETE
        state.pending = None
        state.finished_at = now_iso()
        self.store.save(state)
        self.events.write("diagnostic_complete", student_id=state.student_id, project_id=self.project.id,
                          selected=placement.route.next_task_id, stages=placement.stages,
                          model_id=advice_result.model_id or "none")
        payload = self._result_payload(state)
        payload["notices"] = notices
        return payload

    def _log_route(self, state: DiagnosticState, placement: Placement, advice: AdviceResult) -> None:
        validation = [{"subskill": c, "stage": p.game_stage} for c, p in placement.concepts.items()]
        tool_input = {"student_id": state.student_id, "lesson_id": self.content.config.id,
                      "validation_results": validation, "policy": placement.route.policy}
        flags = ["parse_error"] if advice.parse_error else []
        self.eval_log.write_route(state.student_id, self.content.config.id, tool_input, placement.route.to_dict(),
                                  model_id=advice.model_id, latency_ms=advice.latency_ms, tokens_in=advice.tokens_in,
                                  tokens_out=advice.tokens_out, filter_result=flags,
                                  fallback=placement.route.fallback, error=advice.error, stages=placement.stages)

    def _result_payload(self, state: DiagnosticState) -> Dict[str, Any]:
        placement = self._placement(state)
        node_states = self._node_states(state)
        start_nodes = [n for p in placement.concepts.values() for n in p.start_nodes]
        activity = self.project.problems.get(placement.route.next_task_id)
        first_zone = self.content.zone_for(placement.focus_order[0]).name if placement.focus_order else None
        return self._student({
            "done": True,
            "message": placement.student_message,
            "goal_connection": placement.goal_connection,
            "next_stop": {"zone": first_zone,
                          "activity": {"id": placement.route.next_task_id,
                                       "title": activity.title if activity else placement.route.next_task_id}},
            "skill_tree": views.tree_view(self.content, node_states, start_nodes),
            "zones": game.zone_progress(self.content, state, None),
            "game": game.game_view(self.content, state),
        })

    # Plumbing --------------------------------------------------------------------------------
    def _load(self, student_id: str):
        notices: List[str] = []
        try:
            state = self.store.load(student_id)
        except StateLoadError:
            self.store.quarantine(student_id)
            state = DiagnosticState(student_id=student_id, quest_id=self.content.config.id,
                                    goal_id=self.content.default_goal().id,
                                    buddy=self.content.config.buddies[0][0])
            self._enter_fallback(state, REASON_LOAD_FAILURE)
            self.store.save(state)
            notices.append("Your saved quest could not be opened, so we are starting again in a fixed order.")
        if state is None:
            raise UnknownQuest(f"no quest found for {student_id}")
        return state, notices

    def _student(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Fail closed: nothing with stages or scores may reach a student's screen."""
        leaks = game.find_leaks(payload, self.content.config.banned_student_words)
        if leaks:
            raise RuntimeError("student payload would leak teacher-only data: " + "; ".join(leaks[:3]))
        return payload
