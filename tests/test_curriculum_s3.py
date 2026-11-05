"""Versioned S3 curriculum loading without AWS credentials."""
import io
import os
import sys
import types
import unittest
from unittest.mock import patch

from engine.curriculum import Curriculum, CurriculumError, DEFAULT_CURRICULUM, DEFAULT_WORKBOOK, load_curriculum, _cache


class FakeS3:
    def __init__(self):
        self.calls = []

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"Body": io.BytesIO(DEFAULT_CURRICULUM.read_bytes())}


class CurriculumS3Tests(unittest.TestCase):
    def setUp(self):
        _cache.clear()
        self.client = FakeS3()
        self.boto = types.SimpleNamespace(client=lambda *a, **kw: self.client)

    def tearDown(self):
        _cache.clear()

    def test_loads_and_caches_each_pinned_version(self):
        with patch.dict(sys.modules, {"boto3": self.boto}), patch.dict(os.environ, {
            "CODEAI_CURRICULUM": "s3://private-bucket/standards/csta.json",
            "CODEAI_CURRICULUM_VERSION_ID": "v1",
        }):
            first = load_curriculum()
            self.assertTrue(first.standards)
            self.assertIs(first, load_curriculum())
            os.environ["CODEAI_CURRICULUM_VERSION_ID"] = "v2"
            self.assertIsNot(first, load_curriculum())
        self.assertEqual([c["VersionId"] for c in self.client.calls], ["v1", "v2"])
        self.assertEqual(self.client.calls[0]["Bucket"], "private-bucket")

    def test_unpinned_s3_is_rejected(self):
        with patch.dict(os.environ, {"CODEAI_CURRICULUM_VERSION_ID": ""}):
            with self.assertRaisesRegex(CurriculumError, "VERSION_ID"):
                Curriculum.load("s3://bucket/csta.xlsx")

    def test_remote_failure_does_not_silently_use_local_workbook(self):
        def fail(*args, **kwargs):
            raise RuntimeError("private credentials")
        with patch.dict(sys.modules, {"boto3": types.SimpleNamespace(client=fail)}), patch.dict(os.environ, {"CODEAI_CURRICULUM_VERSION_ID": "v1"}):
            with self.assertRaises(CurriculumError) as error:
                Curriculum.load("s3://bucket/csta.xlsx")
        self.assertNotIn("private credentials", str(error.exception))

    def test_local_workbook_still_loads(self):
        self.assertTrue(Curriculum.load(DEFAULT_WORKBOOK).standards)

    def test_json_preserves_workbook_standards(self):
        self.assertEqual(Curriculum.load(DEFAULT_CURRICULUM).standards, Curriculum.load(DEFAULT_WORKBOOK).standards)

    def test_invalid_json_rejected(self):
        with self.assertRaises(CurriculumError):
            Curriculum.from_json(b'{"schema_version":1,"standards":[{"id":"x"}]}')
