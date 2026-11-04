"""Where things live. Everything is relative to the repository or an env var."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from engine import REPO_ROOT

PathLike = Union[str, "os.PathLike[str]"]

ENV_PROJECT = "CODEAI_PROJECT"
ENV_DATA_DIR = "CODEAI_DATA_DIR"

DEFAULT_PROJECT = REPO_ROOT / "projects" / "weather-station"
DEFAULT_DATA_DIR = REPO_ROOT / ".codeai-data"
CONTENT_FOLDER = "diagnostic"

EVAL_ROOT = REPO_ROOT / "evaluation"


def project_dir(override: Optional[PathLike] = None) -> Path:
    """The project folder: an explicit path, else $CODEAI_PROJECT, else the Weather Station project."""
    chosen = override or os.environ.get(ENV_PROJECT) or DEFAULT_PROJECT
    return Path(chosen).resolve()


def data_dir(override: Optional[PathLike] = None) -> Path:
    """Where progress, logs, and workspaces are saved (the same root the engine CLI uses)."""
    chosen = override or os.environ.get(ENV_DATA_DIR) or DEFAULT_DATA_DIR
    return Path(chosen).resolve()


def content_dir(project_root: PathLike) -> Path:
    """The diagnostic's content folder inside a project."""
    return Path(project_root) / CONTENT_FOLDER
