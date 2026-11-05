"""The curriculum database: CSTA PK-12 standards from the team's workbook.

Source of truth: "curriculum database/CSTA_2026_PK12_Standards_by_Grade.xlsx", sheet "Standards by Grade"
(one row per standard). Read with the standard library only (an .xlsx file is a zip of XML), so the server
needs no spreadsheet package. Set $CODEAI_CURRICULUM to use another copy of the workbook.
"""
from __future__ import annotations

import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKBOOK = ROOT / "curriculum database" / "CSTA_2026_PK12_Standards_by_Grade.xlsx"
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
    def load(cls, path: Optional[Path] = None) -> "Curriculum":
        path = Path(path or os.environ.get("CODEAI_CURRICULUM") or DEFAULT_WORKBOOK)
        rows = _read_rows(path, SHEET)
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


_cache: Dict[str, Curriculum] = {}


def load_curriculum(path: Optional[Path] = None) -> Curriculum:
    """Cached load. Raises CurriculumError if the workbook can't be read."""
    key = str(path or os.environ.get("CODEAI_CURRICULUM") or DEFAULT_WORKBOOK)
    if key not in _cache:
        _cache[key] = Curriculum.load(Path(key))
    return _cache[key]
