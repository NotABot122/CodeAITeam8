"""Build the direct-code deployment package for AgentCore Runtime.

The zip holds the engine and diagnostic packages, the Weather Station project content,
`app.py` as `main.py` at the root, and PyYAML vendored for Linux arm64 (the only
architecture AgentCore Runtime runs). A requirements file inside the zip would be
ignored: the archive is the whole environment.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterator, Tuple

from engine import REPO_ROOT

from .settings import RUNTIME_PYTHON

HERE = Path(__file__).resolve().parent
REQUIREMENTS = HERE / "requirements.txt"
BUILD_DIR = REPO_ROOT / ".codeai-data" / "agentcore"
SOURCES = ("engine", "diagnostic", "projects/weather-station")
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".db"}                   # the weather database is rebuilt from its seed when needed
FILE_MODE, DIR_MODE = 0o644, 0o755                # AgentCore needs read access to every file


def _python_version() -> str:
    return RUNTIME_PYTHON.replace("PYTHON_", "").replace("_", ".")   # PYTHON_3_12 -> 3.12


def _vendor_dependencies(target: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "--platform", "manylinux2014_aarch64", "--implementation", "cp",
         "--python-version", _python_version(), "--only-binary=:all:",
         "--target", str(target), "-r", str(REQUIREMENTS)],
        check=True,
    )


def _walk(root: Path, arc_prefix: str) -> Iterator[Tuple[Path, str]]:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_dir() or SKIP_DIRS & set(relative.parts) or path.suffix in SKIP_SUFFIXES:
            continue
        yield path, f"{arc_prefix}{relative.as_posix()}"


def _add(archive: zipfile.ZipFile, path: Path, arcname: str) -> None:
    info = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))   # fixed time: same input, same zip
    info.external_attr = FILE_MODE << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, path.read_bytes())


def build(output: Path = BUILD_DIR / "deployment_package.zip") -> Path:
    """Write the deployment zip and return its path."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as vendor_dir, zipfile.ZipFile(output, "w") as archive:
        vendor = Path(vendor_dir)
        _vendor_dependencies(vendor)
        for path, arcname in _walk(vendor, ""):
            _add(archive, path, arcname)
        for source in SOURCES:
            for path, arcname in _walk(REPO_ROOT / source, f"{source}/"):
                _add(archive, path, arcname)
        _add(archive, HERE / "app.py", "main.py")
    return output
