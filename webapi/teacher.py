"""Teacher view: who is where, who needs help, one student's detail, and a content check.

Read-only. It reads the same progress files the engine writes and never changes them.
This includes things students never see (stages, confidence, the child's own words), so the
routes need a teacher token (see server.py).
"""
from __future__ import annotations

import datetime as dt
import hmac
from pathlib import Path
from typing import Any, Dict, List, Optional

from engine.content import check_content
from engine.progress import ProgressLoadError, ProgressRecord
from engine.project import ProjectLoadError, load_project
from engine.stages import STAGE_NAMES

from .service import STUDENT_ID, ApiError, Service

MAX_STUDENTS = 500
HELP_ATTEMPTS = 4      # the same bar the Course uses for "struggled"
HELP_HINTS = 2


def token_ok(expected: Optional[str], given: Optional[str]) -> None:
    if not expected:
        raise ApiError(403, "teacher_off", "Teacher pages are turned off on this server.")
    if not given or not hmac.compare_digest(given.encode(), expected.encode()):
        raise ApiError(403, "teacher_token", "A valid teacher token is needed.")


def _iso(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


class Teacher:
    def __init__(self, service: Service):
        self.svc = service
        self.course = service.course
        self.store = service.course.store

    # Helpers ------------------------------------------------------------------------------
    def _student_ids(self) -> List[str]:
        root = self.store.root
        if not root.is_dir():
            return []
        ids = [p.name for p in root.iterdir() if p.is_dir() and STUDENT_ID.match(p.name)]
        return sorted(ids)[:MAX_STUDENTS]

    def _records(self, sid: str) -> Dict[str, ProgressRecord]:
        out: Dict[str, ProgressRecord] = {}
        folder = self.store.root / sid
        for path in sorted(folder.glob("*.json")):
            if path.name == "profile.json" or ".corrupt-" in path.name:
                continue
            try:
                rec = self.store.load(sid, path.stem)
            except ProgressLoadError:
                rec = None
            if rec is not None:
                out[path.stem] = rec
        return out

    def _last_active(self, sid: str) -> float:
        files = list((self.store.root / sid).glob("*.json"))
        return max((f.stat().st_mtime for f in files), default=0.0)

    @staticmethod
    def _trouble(rec: ProgressRecord) -> Optional[str]:
        if rec.complete:
            return None
        pid = rec.current_problem
        if rec.on_fallback:
            return "On the fixed path because routing failed"
        if rec.attempts.get(pid, 0) >= HELP_ATTEMPTS:
            return f"{rec.attempts[pid]} tries on the current step"
        if rec.hints_seen.get(pid, 0) >= HELP_HINTS:
            return f"{rec.hints_seen[pid]} hints used on the current step"
        return None

    def _stages(self, profile: dict, recs: Dict[str, ProgressRecord]) -> Dict[str, int]:
        stages = {c: int(s) for c, s in (profile.get("concepts") or {}).items()}
        for rec in recs.values():
            for cid, state in rec.concepts.items():
                stages[cid] = max(stages.get(cid, 0), int(state.stage))
        return stages

    # Views --------------------------------------------------------------------------------
    def overview(self) -> Dict[str, Any]:
        concepts = self.course.catalog.concepts
        rows: List[Dict[str, Any]] = []
        dist = {cid: [0, 0, 0, 0] for cid in concepts}
        for sid in self._student_ids():
            profile = self.store.profile(sid)
            recs = self._records(sid)
            quest = self.course.diagnostic_status(sid)
            try:
                project = self.course.project_for(sid)
            except Exception:
                project = self.course.default_project()
            rec = recs.get(project.id)
            if quest == "in_progress":
                status = "quest"
            elif rec is None:
                status = "new"
            else:
                status = "finished" if rec.complete else "working"
            trouble = self.__class__._trouble(rec) if rec else None
            stages = self._stages(profile, recs)
            for cid in concepts:
                dist[cid][min(3, max(0, stages.get(cid, 0)))] += 1
            current = None
            if rec and not rec.complete:
                try:
                    current = project.problem(rec.current_problem).label
                except Exception:
                    current = rec.current_problem
            rows.append({
                "studentId": sid, "status": status, "quest": quest, "project": project.title,
                "current": current,
                "attempts": sum(rec.attempts.values()) if rec else 0,
                "passed": len(rec.passed_problems) if rec else 0,
                "completedProjects": len(profile.get("completed") or []),
                "onFallback": bool(rec and rec.on_fallback),
                "needsHelp": trouble,
                "stages": {cid: stages.get(cid, 0) for cid in concepts},
                "lastActive": _iso(self._last_active(sid)) if self._last_active(sid) else None,
            })
        rows.sort(key=lambda r: (r["needsHelp"] is None, r["lastActive"] or ""), reverse=False)
        counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("quest", "working", "finished", "new")}
        return {
            "students": rows,
            "summary": {"total": len(rows), **counts, "needHelp": sum(1 for r in rows if r["needsHelp"])},
            "concepts": [{"id": cid, "name": name, "counts": dist[cid]} for cid, name in concepts.items()],
            "stageNames": [STAGE_NAMES[i] for i in range(4)],
            "truncated": len(rows) >= MAX_STUDENTS,
        }

    def student(self, sid: str) -> Dict[str, Any]:
        self.svc._check_id(sid)
        profile = self.store.profile(sid)
        recs = self._records(sid)
        names = self.course.catalog.concepts
        stages = self._stages(profile, recs)
        projects = []
        for pid, rec in recs.items():
            title = pid
            try:
                folder = next((p for p in [self.course.projects_root / pid] if p.is_dir()), None)
                if folder:
                    title = self.course._project(folder).title
            except Exception:
                pass
            projects.append({
                "id": pid, "title": title, "complete": rec.complete, "current": rec.current_problem,
                "onFallback": rec.on_fallback, "attempts": rec.attempts, "hintsSeen": rec.hints_seen,
                "passed": rec.passed_problems, "needsHelp": self._trouble(rec),
                "route": [{"selected": e.get("selected"), "reason": e.get("reason"), "policy": e.get("policy"),
                           "at": e.get("timestamp")} for e in rec.routing_log][-12:],
            })
        report = None
        if self.course.diagnostic_status(sid) != "none":
            try:
                report = self.course.diagnostic().teacher_report(sid)
            except Exception:
                report = None
        diag = profile.get("diagnostic") or {}
        return {
            "studentId": sid,
            "concepts": [{"id": c, "name": n, "stage": stages.get(c, 0), "stageName": STAGE_NAMES[min(3, stages.get(c, 0))]}
                         for c, n in names.items()],
            "projects": projects,
            "completed": [{"project": c.get("project_id"), "topic": c.get("topic"), "at": c.get("at")} for c in profile.get("completed") or []],
            "nextStep": (profile.get("next_step") or {}).get("reason"),
            "seededFromQuest": diag.get("seeded") or {},
            "quest": report,
            # The Strands Decider 2B's choice, with the teacher-only fields (stance, note, evidence, fallback).
            "pathway": profile.get("pathway"),
            "lastActive": _iso(self._last_active(sid)) if self._last_active(sid) else None,
        }

    def content_check(self) -> Dict[str, Any]:
        out = []
        root = self.course.projects_root
        for manifest in sorted(Path(root).glob("*/manifest.yaml")):
            folder = manifest.parent
            try:
                res = check_content(load_project(folder))
                out.append({"project": folder.name, "passed": res.passed, "problems": list(res.problems), "notices": list(res.notices)})
            except ProjectLoadError as exc:
                out.append({"project": folder.name, "passed": False, "problems": list(getattr(exc, "errors", [str(exc)])), "notices": []})
            except Exception as exc:  # a broken project must not hide the rest
                out.append({"project": folder.name, "passed": False, "problems": [f"{type(exc).__name__}: {exc}"], "notices": []})
        quest: Dict[str, Any]
        try:
            from diagnostic.content import check_content as check_quest
            res = check_quest(self.course.default_project().root)
            quest = {"passed": res.passed, "problems": list(res.problems), "notices": list(res.notices)}
        except Exception as exc:
            quest = {"passed": False, "problems": [f"{type(exc).__name__}: {exc}"], "notices": []}
        return {"projects": out, "quest": quest}
