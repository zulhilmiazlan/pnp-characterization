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


def start_problems(rows, idle_temp_mc, idle_power_w, quiet_s):
    """Return reasons why the run's starting conditions can't be trusted (hot start, not quiet).

    rows: telemetry rows (text values). idle_temp_mc / idle_power_w: the block's idle baseline (may be None).
    quiet_s: length of the quiet window at the start of the run, in seconds.
    A check that cannot be evaluated (missing data) is also a reason: missing evidence cannot make a run valid.
    """

    problems = []

    # Check hot start
    temp = rows[0]["cpu_temp_mc"]

    if temp == "NA" or idle_temp_mc is None:
        problems.append("hot start: could not be checked")
    else:
        delta_c = (int(temp) - idle_temp_mc) / 1000

        if delta_c > HOT_START_C:
            problems.append(f"hot start: {delta_c:.1f} C above idle")

    # Check not quiet
    quiet_powers = [
        float(row["power_w"])
        for row in rows
        if float(row["t_s"]) < quiet_s and row["power_w"] != "NA"
    ]

    if not quiet_powers or idle_power_w is None:
        problems.append("not quiet: could not be checked")
    else:
        mean_power = sum(quiet_powers) / len(quiet_powers)
        delta_w = mean_power - idle_power_w

        if delta_w > NOT_QUIET_W:
            problems.append(f"not quiet: {delta_w:.1f} W above idle")

    return problems


def load_json(path):
    """Return the contents of a JSON file, or None if it is missing."""
    try:
        with open(path) as f:
            return json.load(f)
    except OSError:
        return None


def check_run(run_dir, runs_root):
    """Check one run folder and return its status record (section 8). Does not write anything."""
    unstable, invalid, warnings = [], [], []

    run_info = load_json(os.path.join(run_dir, "run.json")) or {}
    block = load_json(os.path.join(runs_root, "state", str(run_info.get("block_id")), "block.json")) or {}
    result = load_json(os.path.join(run_dir, "result.json"))

    # Hardware outcome: a run that never wrote result.json did not finish (crash or reboot).
    if result is None:
        unstable.append("no result.json: run did not finish (crash or reboot)")
    else:
        code = result.get("exit_status")
        if code in (2, 5):
            unstable.append(f"workload exit status {code} (stressor failed or was killed)")
        elif code != 0:
            invalid.append(f"workload exit status {code}")
        elif result.get("score") is None:
            invalid.append("workload finished but no score was found")
        if result.get("sampler_exit_status") != 0:
            invalid.append(f"sampler exit status {result.get('sampler_exit_status')}")

    # Measurement quality.
    rows = load_telemetry(os.path.join(run_dir, "telemetry.csv"))
    if rows is None:
        invalid.append("telemetry.csv missing")
    else:
        invalid += telemetry_problems(rows)
        if rows:
            invalid += start_problems(rows, block.get("idle_temp_mc"), block.get("idle_power_w"),
                                      run_info.get("quiet_s", 0))

    # Metadata.
    if not run_info:
        invalid.append("run.json missing")
    if run_info.get("room_temp_c") is None:
        invalid.append("room temperature missing")
    commit = run_info.get("framework_commit")
    if commit is None:
        invalid.append("framework commit missing")
    elif commit.endswith("-dirty"):
        warnings.append("framework code had uncommitted changes")

    # A crash is the main fact about a run, so unstable takes priority over invalid.
    status = "unstable" if unstable else ("invalid" if invalid else "ok")
    return {"status": status, "unstable_reasons": unstable, "invalid_reasons": invalid, "warnings": warnings}


def check_and_record(run_dir, runs_root):
    """Check a run and write its status.json (write-once). Return the status record."""
    from results import write_json
    record = check_run(run_dir, runs_root)
    write_json(os.path.join(run_dir, "status.json"), record)
    return record


def unchecked_runs(runs_root):
    """Return run folders under `runs_root` that have no status.json yet (e.g. a run cut short by a crash)."""
    found = []
    for name in sorted(os.listdir(runs_root)) if os.path.isdir(runs_root) else []:
        path = os.path.join(runs_root, name)
        if name != "state" and os.path.isdir(path) and not os.path.exists(os.path.join(path, "status.json")):
            found.append(path)
    return found
