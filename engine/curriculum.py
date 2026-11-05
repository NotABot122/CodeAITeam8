"""Load CSTA standards from versioned JSON, with legacy workbook support.

The local JSON is an offline default. Set CODEAI_CURRICULUM and
CODEAI_CURRICULUM_VERSION_ID to read an immutable S3 object version.
"""
from __future__ import annotations

import os
import re
import zipfile
import json
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKBOOK = ROOT / "documentation" / "curriculum" / "CSTA_2026_PK12_Standards_by_Grade.xlsx"
DEFAULT_CURRICULUM = ROOT / "documentation" / "curriculum" / "csta-standards.json"
SHEET = "Standards by Grade"
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}

# Workbook column header -> field name.
_COLUMNS = {
    "Grade Level": "level", "Grades": "grades", "Standard ID": "id", "Competency": "competency",
    "Skill Area": "skill_area", "Skill": "skill", "What the Student Must Be Able to Do": "must_do",
    "Not Expected Yet": "not_yet", "Progression: Builds On": "builds_on", "Progression: Leads To": "leads_to",
}


class CurriculumError(Exception):
    """The workbook is missing or can't be read. Callers carry on without standards."""


@dataclass(frozen=True)
class Standard:
    id: str
    level: str          # "High School", "Middle School", "Grade 3", "PK/K", ...
    grades: str         # "9-12", "6-8", "3", "PK-K"
    competency: str
    skill_area: str
    skill: str
    must_do: str
    not_yet: str = ""
    builds_on: str = ""
    leads_to: str = ""

    def brief(self) -> Dict[str, str]:
        """What a model or a teacher screen needs."""
        return {"id": self.id, "skill": self.skill, "must_do": self.must_do, "skill_area": self.skill_area}

    def builds_on_ids(self) -> List[str]:
        return re.findall(r"\b[A-Z0-9]{2}-[A-Z]{3}-[A-Z]{2}-\d{2}\b", self.builds_on or "")


def level_for_grade(grade: int) -> str:
    """The workbook's level name for a school grade (0 = kindergarten)."""
    if grade >= 9:
        return "High School"
    if grade >= 6:
        return "Middle School"
    if grade >= 1:
        return f"Grade {grade}"
    return "PK/K"


def _cell_text(cell: ET.Element, shared: List[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{{{_NS['m']}}}t"))
    value = cell.find("m:v", _NS)
    if value is None or value.text is None:
        return ""
    if kind == "s":
        return shared[int(value.text)]
    return value.text


def _column(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def _read_rows(path: Path, sheet_name: str) -> List[List[str]]:
    try:
        with zipfile.ZipFile(path) as z:
            shared: List[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                    shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
            book = ET.fromstring(z.read("xl/workbook.xml"))
            rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            targets = {r.get("Id"): r.get("Target") for r in rels.findall("rel:Relationship", _NS)}
            sheet = next((s for s in book.find("m:sheets", _NS) if s.get("name") == sheet_name), None)
            if sheet is None:
                raise CurriculumError(f'the workbook has no sheet named "{sheet_name}"')
            target = targets[sheet.get(f"{{{_NS['r']}}}id")].lstrip("/")
            target = target if target.startswith("xl/") else f"xl/{target}"
            rows: List[List[str]] = []
            for row in ET.fromstring(z.read(target)).iter(f"{{{_NS['m']}}}row"):
                values: Dict[int, str] = {_column(c.get("r")): _cell_text(c, shared) for c in row.findall("m:c", _NS)}
                rows.append([values.get(i, "") for i in range(max(values) + 1)] if values else [])
            return rows
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise CurriculumError(f"couldn't read the curriculum workbook: {exc}") from None


class Curriculum:
    def __init__(self, standards: Iterable[Standard]):
        self.standards: Dict[str, Standard] = {s.id: s for s in standards}

    @classmethod
    def load(cls, path: Optional[Union[Path, str]] = None) -> "Curriculum":
        source = str(path or os.environ.get("CODEAI_CURRICULUM") or DEFAULT_CURRICULUM)
        if source.startswith("s3://"):
            parsed = urlparse(source)
            if not parsed.netloc or not parsed.path.lstrip("/") or parsed.query or parsed.fragment:
                raise CurriculumError("curriculum S3 URI must be s3://bucket/key")
            version = os.environ.get("CODEAI_CURRICULUM_VERSION_ID")
            if not version:
                raise CurriculumError("S3 curriculum requires CODEAI_CURRICULUM_VERSION_ID")
            try:
                from .s3_storage import app_client
                client = app_client("s3")          # the app role (CODEAI_APP_ROLE_ARN) when set
                response = client.get_object(Bucket=parsed.netloc, Key=parsed.path.lstrip("/"), VersionId=version)
                body = response["Body"]
                try:
                    contents = body.read(10 * 1024 * 1024 + 1)
                finally:
                    body.close()
                if len(contents) > 10 * 1024 * 1024:
                    raise CurriculumError("curriculum workbook exceeds 10 MiB")
                if parsed.path.lower().endswith(".json"):
                    return cls.from_json(contents)
                rows = _read_rows(BytesIO(contents), SHEET)
            except CurriculumError:
                raise
            except Exception as exc:
                raise CurriculumError(f"couldn't load S3 curriculum: {type(exc).__name__}") from None
        else:
            if source.lower().endswith(".json"):
                try:
                    return cls.from_json(Path(source).read_bytes())
                except OSError as exc:
                    raise CurriculumError(f"couldn't read curriculum: {type(exc).__name__}") from None
            rows = _read_rows(Path(source), SHEET)
        if not rows:
            raise CurriculumError("the standards sheet is empty")
        header = {name: i for i, name in enumerate(rows[0]) if name in _COLUMNS}
        if "Standard ID" not in header:
            raise CurriculumError('the standards sheet has no "Standard ID" column')
        out = []
        for row in rows[1:]:
            get = lambda col: (row[header[col]].strip() if col in header and header[col] < len(row) else "")
            if get("Standard ID"):
                out.append(Standard(**{_COLUMNS[col]: get(col) for col in _COLUMNS}))
        return cls(out)

    @classmethod
    def from_json(cls, contents: bytes) -> "Curriculum":
        try:
            data = json.loads(contents)
            if not isinstance(data, dict) or data.get("schema_version") != 1 or not isinstance(data.get("standards"), list):
                raise ValueError("invalid schema")
            records = data["standards"]
            required = set(_COLUMNS.values())
            if not records or any(not isinstance(r, dict) or set(r) != required or
                                  any(not isinstance(v, str) for v in r.values()) or not r["id"] for r in records):
                raise ValueError("invalid standards")
            if len({r["id"] for r in records}) != len(records):
                raise ValueError("duplicate standard id")
            return cls(Standard(**r) for r in records)
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            raise CurriculumError(f"invalid curriculum JSON: {type(exc).__name__}") from None

    def get(self, standard_id: str) -> Optional[Standard]:
        return self.standards.get(standard_id)

    def for_level(self, level: str) -> List[Standard]:
        return [s for s in self.standards.values() if s.level == level]

    def lookup(self, ids: Iterable[str]) -> List[Standard]:
        seen, out = set(), []
        for i in ids:
            if i in self.standards and i not in seen:
                seen.add(i)
                out.append(self.standards[i])
        return out


_cache: Dict[Tuple[str, str], Curriculum] = {}


def load_curriculum(path: Optional[Union[Path, str]] = None) -> Curriculum:
    """Cached load. Raises CurriculumError if the workbook can't be read."""
    key = str(path or os.environ.get("CODEAI_CURRICULUM") or DEFAULT_CURRICULUM)
    version = os.environ.get("CODEAI_CURRICULUM_VERSION_ID", "") if key.startswith("s3://") else ""
    cache_key = (key, version)
    if cache_key not in _cache:
        _cache[cache_key] = Curriculum.load(key)
    return _cache[cache_key]
