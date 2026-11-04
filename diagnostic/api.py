"""A thin HTTP/JSON layer over DiagnosticEngine, for the frontend.

Optional: needs `pip install -r diagnostic/requirements-api.txt` (FastAPI). The rest of the
package runs without it. Run it with:

    uvicorn diagnostic.api:create_default_app --factory

Student routes return only what a child's screen may show. The teacher report is a
separate route that is OFF unless CODEAI_TEACHER_TOKEN is set, and then needs that
token in the X-Teacher-Token header. Do not expose this service to the internet
without authentication, TLS and rate limiting in front of it: student ids are
unguessable pseudonyms, not credentials.

Settings (environment):  CODEAI_PROJECT, CODEAI_DATA_DIR, CODEAI_AI (off|mock|bedrock),
CODEAI_TEACHER_TOKEN, CODEAI_CORS_ORIGINS (comma separated; unset = no cross-origin access).
"""
from __future__ import annotations

import hmac
import os
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from engine.project import ProjectLoadError

from .ai.factory import make_provider
from .content import ContentError
from .engine import DiagnosticEngine, NothingPending, NotFinished, UnknownQuest
from .models import InvalidResponse
from .store import InvalidStudentId

PREFIX = "/api/v1/diagnostic"
TEACHER_HEADER = "X-Teacher-Token"


class StartBody(BaseModel):
    buddy: Optional[str] = Field(default=None, max_length=40)
    goal: Optional[str] = Field(default=None, max_length=40)
    goal_text: Optional[str] = Field(default=None, max_length=200)


class AnswerBody(BaseModel):
    response: Any = None
    elapsed_ms: Optional[int] = Field(default=None, ge=0, le=3_600_000)


def create_app(engine: DiagnosticEngine, teacher_token: Optional[str] = None,
               cors_origins: Optional[list] = None) -> FastAPI:
    app = FastAPI(title="Weather Station readiness quest", version=str(engine.content.config.version))
    if cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "POST"],
                           allow_headers=["Content-Type", TEACHER_HEADER])

    def guarded(call):
        try:
            return call()
        except (UnknownQuest,) as exc:
            raise HTTPException(404, str(exc))
        except (InvalidStudentId, InvalidResponse) as exc:
            raise HTTPException(422, str(exc))
        except (NothingPending, NotFinished) as exc:
            raise HTTPException(409, str(exc))

    def require_teacher(token: Optional[str] = Header(default=None, alias=TEACHER_HEADER)) -> None:
        if not teacher_token:
            raise HTTPException(403, "teacher reports are turned off on this server")
        if token is None or not hmac.compare_digest(token.encode(), teacher_token.encode()):
            raise HTTPException(403, "a valid teacher token is required")

    @app.get(f"{PREFIX}/options")
    def options():
        return engine.options()

    @app.post(f"{PREFIX}/start")
    def start(body: StartBody):
        return engine.start(body.buddy, body.goal, body.goal_text)

    @app.get(f"{PREFIX}/{{student_id}}/next")
    def next_question(student_id: str):
        return guarded(lambda: engine.next(student_id))

    @app.post(f"{PREFIX}/{{student_id}}/answer")
    def answer(student_id: str, body: AnswerBody):
        return guarded(lambda: engine.answer(student_id, body.response, body.elapsed_ms))

    @app.post(f"{PREFIX}/{{student_id}}/finish")
    def finish(student_id: str):
        return guarded(lambda: engine.finish(student_id))

    @app.get(f"{PREFIX}/{{student_id}}/result")
    def result(student_id: str):
        return guarded(lambda: engine.result(student_id))

    @app.get(f"{PREFIX}/{{student_id}}/skill_tree")
    def skill_tree(student_id: str):
        return guarded(lambda: engine.skill_tree(student_id))

    @app.get(f"{PREFIX}/teacher/{{student_id}}/report", dependencies=[Depends(require_teacher)])
    def report(student_id: str):
        return guarded(lambda: engine.teacher_report(student_id))

    return app


def create_default_app() -> FastAPI:
    """Build the app from environment settings (for `uvicorn ... --factory`)."""
    try:
        engine = DiagnosticEngine.from_paths(provider=make_provider())
    except (ProjectLoadError, ContentError) as exc:
        raise RuntimeError("the diagnostic content could not be loaded: " + "; ".join(getattr(exc, "errors", [str(exc)])))
    origins = [o.strip() for o in os.environ.get("CODEAI_CORS_ORIGINS", "").split(",") if o.strip()]
    return create_app(engine, os.environ.get("CODEAI_TEACHER_TOKEN") or None, origins or None)
