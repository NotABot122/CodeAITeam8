"""Helpers for problem checks.py files.

A check fails by raising AssertionError with a plain-language message.
The engine adds the "Level N:" prefix, so messages should start with the
behavior, e.g. "a temperature of 35.0 should count as a heat wave."
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import List

COLUMNS = ("station_id", "date", "temp_high_c", "temp_low_c", "rain_mm")


def expect(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def date_range(start: str, end: str) -> List[str]:
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    days = (last - first).days
    return [(first + dt.timedelta(days=i)).isoformat() for i in range(days + 1)]


def read_rows(db_path: str, station_id=None, start=None, end=None) -> List[dict]:
    """Ground-truth rows, read directly by the engine."""
    sql = f"SELECT {', '.join(COLUMNS)} FROM daily_readings"
    params: tuple = ()
    if station_id is not None:
        sql += " WHERE station_id = ? AND date BETWEEN ? AND ?"
        params = (station_id, start, end)
    sql += " ORDER BY station_id, date"
    conn = sqlite3.connect(db_path)
    try:
        return [dict(zip(COLUMNS, values)) for values in conn.execute(sql, params)]
    finally:
        conn.close()


def make_row(date: str, temp_high_c: float, rain_mm: float, station_id: str = "ST-T") -> dict:
    """A test row in the same shape get_readings returns."""
    return {
        "station_id": station_id,
        "date": date,
        "temp_high_c": temp_high_c,
        "temp_low_c": round(temp_high_c - 8.0, 1),
        "rain_mm": rain_mm,
    }


def describe(value, limit: int = 60) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."
