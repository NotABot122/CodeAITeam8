import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from webapi.server import make_handler
from webapi.service import ApiError, Service
from webapi.teacher import Teacher, token_ok


class TeacherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc = Service(Path(self.tmp.name))
        self.teacher = Teacher(self.svc)

    def test_empty_class(self):
        out = self.teacher.overview()
        self.assertEqual(out["summary"]["total"], 0)
        self.assertEqual(len(out["concepts"]), 6)

    def test_overview_flags_a_student_who_is_stuck_and_one_in_the_quest(self):
        stuck = self.svc.new_student()["studentId"]
        for _ in range(4):
            self.svc.submit(stuck, "print(1)")
        fresh = self.svc.new_student()["studentId"]
        quest = self.svc.quest_start("cloud", "build_game")["student_id"]
        out = self.teacher.overview()
        by = {r["studentId"]: r for r in out["students"]}
        self.assertEqual(out["summary"]["total"], 3)
        self.assertIn("4 tries", by[stuck]["needsHelp"])
        self.assertIsNone(by[fresh]["needsHelp"])
        self.assertEqual(by[quest]["status"], "quest")
        self.assertEqual(out["summary"]["needHelp"], 1)
        # the stuck student is listed first
        self.assertEqual(out["students"][0]["studentId"], stuck)

    def test_student_detail_includes_the_quest_report_only_for_quest_students(self):
        plain = self.svc.new_student()["studentId"]
        self.assertIsNone(self.teacher.student(plain)["quest"])
        q = self.svc.quest_start("cloud", "build_game")
        detail = self.teacher.student(q["student_id"])
        self.assertIsNotNone(detail["quest"])
        self.assertEqual(len(detail["concepts"]), 6)

    def test_reading_never_changes_progress(self):
        sid = self.svc.new_student()["studentId"]
        files = lambda: sorted(p.name + str(p.stat().st_mtime_ns) for p in Path(self.tmp.name, "progress").rglob("*.json"))
        before = files()
        self.teacher.overview()
        self.teacher.student(sid)
        self.assertEqual(before, files())

    def test_content_check_runs(self):
        out = self.teacher.content_check()
        self.assertTrue(out["quest"]["passed"])
        self.assertTrue(all(p["passed"] for p in out["projects"]))

    def test_token_rules(self):
        with self.assertRaises(ApiError) as cm:
            token_ok(None, "x")
        self.assertEqual(cm.exception.code, "teacher_off")
        with self.assertRaises(ApiError):
            token_ok("secret", None)
        with self.assertRaises(ApiError):
            token_ok("secret", "wrong")
        token_ok("secret", "secret")


class TeacherHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc = Service(Path(self.tmp.name))
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.svc, "secret"))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.shutdown)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def get(self, path, token=None):
        req = urllib.request.Request(self.base + path, headers={"X-Teacher-Token": token} if token else {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_needs_the_token(self):
        self.assertEqual(self.get("/api/teacher/overview")[0], 403)
        self.assertEqual(self.get("/api/teacher/overview", "nope")[0], 403)
        status, body = self.get("/api/teacher/overview", "secret")
        self.assertEqual(status, 200)
        self.assertEqual(body["summary"]["total"], 0)

    def test_bad_student_id(self):
        self.assertEqual(self.get("/api/teacher/students/..%2Fx", "secret")[0], 404)


if __name__ == "__main__":
    unittest.main()
