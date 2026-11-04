"""Builds data.db for this themed project from theme.json and seed.txt."""
import json
from pathlib import Path

from engine.themes.dataset import build

HERE = Path(__file__).resolve().parent


def read_default_seed():
    return int((HERE / "seed.txt").read_text().strip())


def generate(out_path=HERE / "data.db", seed=None):
    theme = json.loads((HERE.parent / "theme.json").read_text())
    return build(out_path, theme, read_default_seed() if seed is None else seed)
