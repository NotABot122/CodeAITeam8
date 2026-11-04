"""The optional HTTP layer. Skipped when FastAPI is not installed."""
from __future__ import annotations

import importlib.util
import unittest

from diagnostic.ai import RuleBasedProvider
from diagnostic.game import find_leaks

from tests.diag_helpers import TempDirCase, content

HAVE_API = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx"))
C = content()


def right(view):
    if view["kind"] == "explain":
        return {"text": "you do it again for each day and keep a total"}
    item = C.items.get(view["id"]) or next(b for b in C.boosters if b.id == view["id"])
    return item.answer


@unittest.skipUnless(HAVE_API, "FastAPI and httpx are not installed (pip install -r diagnostic/requirements-api.txt)")
class HttpApi(TempDirCase):
    def client(self, token="secret"):
        from fastapi.testclient import TestClient

        from diagnostic.api import create_app

        return TestClient(create_app(self.engine(RuleBasedProvider()), teacher_token=token))

    def test_a_quest_over_http_and_the_skill_tree(self):
        c = self.client()
        base = "/api/v1/diagnostic"
        self.assertEqual(c.get(f"{base}/options").status_code, 200)
        started = c.post(f"{base}/start", json={"buddy": "cloud", "goal": "weather_report"}).json()
        sid, step = started["student_id"], started["first"]
        seen = [started]
        while not step.get("done"):
            reply = c.post(f"{base}/{sid}/answer", json={"response": right(step["step"]), "elapsed_ms": 2500})
            self.assertEqual(reply.status_code, 200, reply.text)
            seen.append(reply.json())
            step = c.get(f"{base}/{sid}/next").json()
        seen += [step, c.get(f"{base}/{sid}/result").json(), c.get(f"{base}/{sid}/skill_tree").json()]
        for payload in seen:
            self.assertEqual(find_leaks(payload, C.config.banned_student_words), [])
        self.assertIn("tree", seen[-1])

    def test_error_codes(self):
        c = self.client()
        base = "/api/v1/diagnostic"
        sid = c.post(f"{base}/start", json={}).json()["student_id"]
        self.assertEqual(c.post(f"{base}/{sid}/answer", json={"response": "not-an-option"}).status_code, 422)
        self.assertEqual(c.get(f"{base}/STU-0123456789abcdef/next").status_code, 404)
        self.assertEqual(c.get(f"{base}/not-a-student/next").status_code, 422)
        self.assertEqual(c.get(f"{base}/{sid}/result").status_code, 409)
        self.assertEqual(c.post(f"{base}/start", json={"goal_text": "x" * 500}).status_code, 422)

    def test_the_teacher_report_needs_the_token_and_is_off_without_one(self):
        base = "/api/v1/diagnostic"
        c = self.client("secret")
        sid = c.post(f"{base}/start", json={}).json()["student_id"]
        url = f"{base}/teacher/{sid}/report"
        self.assertEqual(c.get(url).status_code, 403)
        self.assertEqual(c.get(url, headers={"X-Teacher-Token": "wrong"}).status_code, 403)
        ok = c.get(url, headers={"X-Teacher-Token": "secret"})
        self.assertEqual(ok.status_code, 200)
        self.assertIn("concepts", ok.json())
        off = self.client(token=None)
        self.assertEqual(off.get(url, headers={"X-Teacher-Token": "secret"}).status_code, 403)

    def test_no_student_route_serves_teacher_data(self):
        c = self.client()
        base = "/api/v1/diagnostic"
        started = c.post(f"{base}/start", json={}).json()
        text = c.get(f"{base}/{started['student_id']}/skill_tree").text
        for word in ("confidence", "stage", "misconception", "ratio"):
            self.assertNotIn(f'"{word}"', text)


if __name__ == "__main__":
    unittest.main()
