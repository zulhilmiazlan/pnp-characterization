"""Quality checks: give each run a status (ok / unstable / invalid) with reasons. DESIGN.md section 8."""

import csv
import json
import os

# Initial thresholds for the pilot (section 8); reviewed after the pilot.
MAX_GAP_S = 0.5
MAX_ENERGY_NA_FRACTION = 0.05
HOT_START_C = 5.0
NOT_QUIET_W = 3.0


def load_telemetry(path):
    """Return the rows of a telemetry CSV as a list of dicts (values are text), or None if the file is missing."""
    try:
        with open(path) as f:
            return list(csv.DictReader(f))
    except OSError:
        return None


def telemetry_problems(rows):
    """Return a list of reasons (strings) why this telemetry can't be trusted; an empty list means no problems.

    Checks: no readings; timestamps not strictly increasing; any gap > MAX_GAP_S;
    more than MAX_ENERGY_NA_FRACTION of energy readings are NA.
    """

    if not rows:
        return ["no telemetry readings"]

    problems = []

    # Check timestamps
    times = [float(r["t_s"]) for r in rows]
    largest_gap = 0.0
    timestamps_invalid = False

    for i in range(1, len(times)):
        gap = times[i] - times[i - 1]

        if gap <= 0:
            timestamps_invalid = True

        if gap > largest_gap:
            largest_gap = gap

    if timestamps_invalid:
        problems.append("timestamps not increasing")

    if largest_gap > MAX_GAP_S:
        problems.append(f"reading gap of {largest_gap:.2f} s")

    # Check missing energy readings
    na_count = sum(1 for r in rows if r["energy_uj"] == "NA")
    fraction = na_count / len(rows)

    if fraction > MAX_ENERGY_NA_FRACTION:
        problems.append(f"{fraction:.0%} of energy readings are NA")

    return problems
