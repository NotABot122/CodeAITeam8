"""Generate the synthetic Weather_Database (weather.db) from a fixed seed.

All values are synthetic. The stations are invented and are not real places.

Usage:
    python generate.py [--seed N] [--out PATH]
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import random
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DB = HERE / "weather.db"
SEED_FILE = HERE / "seed.txt"

START = dt.date(2026, 1, 1)
DAYS = 365

# Invented climates: mean daily high (C), seasonal swing, day of year of peak
# heat, typical gap between high and low, chance of rain, mean rain on wet days.
STATIONS = {
    "ST-A": dict(mean=29.0, amp=6.0, peak=20, spread=11.0, rain_p=0.18, rain_mean=9.0),
    "ST-B": dict(mean=17.0, amp=12.0, peak=200, spread=9.0, rain_p=0.30, rain_mean=7.0),
    "ST-C": dict(mean=21.0, amp=6.0, peak=210, spread=6.0, rain_p=0.45, rain_mean=11.0),
}

# Forced rows make sure boundary, near-boundary, and overlap cases exist for
# every station. Key: day index (0 = Jan 1). Value: (temp_high_c, rain_mm).
FORCED = {
    "ST-A": {9: (35.0, 0.0), 10: (34.9, 0.0), 13: (24.6, 20.0), 14: (25.1, 19.9), 25: (36.2, 23.4)},
    "ST-B": {180: (35.0, 0.0), 181: (34.9, 0.0), 100: (15.0, 20.0), 101: (16.0, 19.9), 190: (35.5, 21.0)},
    "ST-C": {200: (35.0, 2.0), 201: (34.9, 0.0), 60: (18.2, 20.0), 61: (17.4, 19.9), 215: (35.8, 27.3)},
}

TEMP_MIN, TEMP_MAX = -30.0, 50.0
RAIN_MIN, RAIN_MAX = 0.0, 200.0


def read_default_seed() -> int:
    return int(SEED_FILE.read_text().strip())


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def build_rows(seed: int) -> list[tuple]:
    """Return all rows as (station_id, date, temp_high_c, temp_low_c, rain_mm)."""
    rng = random.Random(seed)
    rows = []
    for station_id, cfg in STATIONS.items():
        forced = FORCED[station_id]
        for day in range(DAYS):
            date = START + dt.timedelta(days=day)
            seasonal = cfg["mean"] + cfg["amp"] * math.cos(2 * math.pi * (day - cfg["peak"]) / 365.0)
            high = seasonal + rng.gauss(0.0, 3.0)
            gap = abs(rng.gauss(cfg["spread"], 2.0))
            rain = rng.expovariate(1.0 / cfg["rain_mean"]) if rng.random() < cfg["rain_p"] else 0.0
            if day in forced:
                high, rain = forced[day]
            high = round(_clamp(high, TEMP_MIN, TEMP_MAX), 1)
            low = round(_clamp(high - gap, TEMP_MIN, high), 1)
            rain = round(_clamp(rain, RAIN_MIN, RAIN_MAX), 1)
            rows.append((station_id, date.isoformat(), high, low, rain))
    return rows


def generate(out_path: Path = DEFAULT_DB, seed: int | None = None) -> Path:
    """Write a fresh database to out_path. Replaces any existing file."""
    out_path = Path(out_path)
    if seed is None:
        seed = read_default_seed()
    rows = build_rows(seed)
    fd, tmp_name = tempfile.mkstemp(prefix=".weather-", suffix=".db", dir=str(out_path.parent))
    os.close(fd)
    try:
        conn = sqlite3.connect(tmp_name)
        try:
            conn.execute(
                "CREATE TABLE daily_readings ("
                " station_id TEXT NOT NULL,"
                " date TEXT NOT NULL,"
                " temp_high_c REAL NOT NULL,"
                " temp_low_c REAL NOT NULL,"
                " rain_mm REAL NOT NULL,"
                " PRIMARY KEY (station_id, date))"
            )
            conn.executemany("INSERT INTO daily_readings VALUES (?, ?, ?, ?, ?)", rows)
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp_name, out_path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=None, help="random seed (default: seed.txt)")
    parser.add_argument("--out", type=Path, default=DEFAULT_DB, help="output database path")
    args = parser.parse_args(argv)
    try:
        path = generate(args.out, args.seed)
    except (OSError, sqlite3.Error) as exc:
        print(f"Could not write the weather database to {args.out}: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
