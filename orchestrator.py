"""Orchestrator: run one block of measurement runs (one boot, one BIOS profile). DESIGN.md sections 5, 7 and 8."""

import argparse
import csv
import os
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime

import checks
import results
import sampler
import workload

HERE = os.path.dirname(os.path.abspath(__file__))


def log_event(run_dir, event):
    """Append one line to `run_dir`/events.log: an ISO 8601 timestamp, a space, then `event`."""
    path = os.path.join(run_dir, "events.log")
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

    with open(path, "a") as f:
        f.write(f"{timestamp} {event}\n")
        f.flush()
        os.fsync(f.fileno())


def wait_for_cooldown(temp_path, target_mc, timeout_s, poll_s=2.0):
    """Wait until the temperature in `temp_path` is at or below `target_mc` (millidegrees C), or `timeout_s` passes.

    Return (reached, last_temp_mc, waited_s): reached is True if the target was met before the timeout.
    """
    start = time.monotonic()

    while True:
        temp = sampler.read_int(temp_path)
        waited = time.monotonic() - start

        if temp is not None and temp <= target_mc:
            return (True, temp, waited)

        if waited >= timeout_s:
            return (False, temp, waited)

        time.sleep(poll_s)


def run_one(runs_root, block_id, profile, workload_name, repeat, position, room_temp_c,
            warmup_s, workload_s, rate, gpu_pci=None, quiet_s=10):
    """Do one complete run: folder, run.json, sampler in the background, warm-up, workload, result.json."""
    start = datetime.now().astimezone()
    run_id = results.make_run_id(start, profile, workload_name, repeat)
    run_dir = results.create_run_dir(runs_root, run_id)

    run_info = {
        "run_id": run_id,
        "block_id": block_id,
        "cpu_profile": profile,
        "workload": workload_name,
        "quiet_s": quiet_s,
        "warmup_s": warmup_s,
        "workload_s": workload_s,
        "gpu_cap_w": None,
        "gpu_pci": gpu_pci,
        "repeat": repeat,
        "position_in_block": position,
        "room_temp_c": room_temp_c,
        "sample_rate_hz": rate,
        "framework_commit": results.framework_commit(),
    }
    results.write_json(os.path.join(run_dir, "run.json"), run_info)

    # Sampler runs in the background for a quiet window, the warm-up and the workload, plus a margin for
    # start-up delays. The quiet window gives the "not quiet" check (section 8) telemetry from before warm-up.
    margin_s = 10
    cmd = [sys.executable, os.path.join(HERE, "sampler.py"),
           "--rate", str(rate), "--duration", str(quiet_s + warmup_s + workload_s + margin_s),
           "--out", os.path.join(run_dir, "telemetry.csv")]
    if gpu_pci:
        cmd += ["--gpu-pci", gpu_pci]
    log_event(run_dir, "sampler start")
    sampler_proc = subprocess.Popen(cmd)
    time.sleep(quiet_s)

    log_event(run_dir, "warm-up start")
    workload.run_workload(workload_name, warmup_s, os.path.join(run_dir, "warmup.txt"))
    log_event(run_dir, "workload start")
    res = workload.run_workload(workload_name, workload_s, os.path.join(run_dir, "workload.txt"))
    log_event(run_dir, "workload end")

    sampler_exit = sampler_proc.wait()
    log_event(run_dir, f"sampler end (exit {sampler_exit})")
    end = datetime.now().astimezone()

    result = {
        "score": res["score"],
        "score_unit": res["score_unit"],
        "exit_status": res["exit_status"],
        "sampler_exit_status": sampler_exit,
        "start_time": start.isoformat(timespec="seconds"),
        "end_time": end.isoformat(timespec="seconds"),
        "duration_s": round((end - start).total_seconds(), 1),
    }
    results.write_json(os.path.join(run_dir, "result.json"), result)
    return run_dir


def summarise_idle(csv_path):
    """Return (median CPU temperature in mC, mean CPU power in W) from an idle telemetry CSV, skipping NA values.

    Either value is None if the CSV has no usable readings for it.
    """
    temps = []
    powers = []

    with open(csv_path, "r") as f:
        for row in csv.DictReader(f):
            if row["cpu_temp_mc"] != "NA":
                temps.append(int(row["cpu_temp_mc"]))

            if row["power_w"] != "NA":
                powers.append(float(row["power_w"]))

    median_temp = statistics.median(temps) if temps else None
    mean_power = statistics.mean(powers) if powers else None

    return (median_temp, mean_power)


def measure_idle(block_dir, seconds, rate):
    """Record `seconds` of idle telemetry to `block_dir`/idle.csv and return summarise_idle() of it."""
    csv_path = os.path.join(block_dir, "idle.csv")
    subprocess.run([sys.executable, os.path.join(HERE, "sampler.py"),
                    "--rate", str(rate), "--duration", str(seconds), "--out", csv_path], check=True)
    return summarise_idle(csv_path)


def main():
    parser = argparse.ArgumentParser(description="Run one block: one boot, one BIOS profile, every workload once.")
    parser.add_argument("--profile", required=True, help="BIOS profile selected for this boot, e.g. stock")
    parser.add_argument("--repeat", type=int, required=True, help="repeat number of this block (1-5 in the pilot)")
    parser.add_argument("--room-temp", type=float, required=True, help="room temperature in degrees C, read by the operator")
    parser.add_argument("--gpu-pci", default=None, help="PCI address of the GPU under test, e.g. 0000:03:00.0")
    parser.add_argument("--warmup", type=int, default=60, help="warm-up seconds per run (default 60)")
    parser.add_argument("--duration", type=int, default=180, help="measured workload seconds per run (default 180)")
    parser.add_argument("--idle", type=int, default=30, help="idle baseline seconds at block start (default 30)")
    parser.add_argument("--cooldown-timeout", type=int, default=180, help="max seconds to wait for cooldown (default 180)")
    parser.add_argument("--rate", type=float, default=10.0, help="sampler readings per second (default 10)")
    parser.add_argument("--runs-root", default=os.path.join(HERE, "runs"), help="where run folders go")
    args = parser.parse_args()

    temp_dev = sampler.find_hwmon("coretemp") or sampler.find_hwmon("k10temp")
    if temp_dev is None:
        raise SystemExit("error: CPU temperature sensor not found")
    temp_path = temp_dev + "/temp1_input"

    # Runs left without a status by a crash or reboot are checked first (section 8).
    for run_dir in checks.unchecked_runs(args.runs_root):
        record = checks.check_and_record(run_dir, args.runs_root)
        print(f"Checked earlier run {os.path.basename(run_dir)}: {record['status']}")

    block_start = datetime.now().astimezone()
    block_id = f"{block_start:%Y%m%dT%H%M%S}_{args.profile}"
    block_dir = results.create_run_dir(os.path.join(args.runs_root, "state"), block_id)

    print(f"Block {block_id}: measuring idle baseline for {args.idle} s ...")
    idle_temp_mc, idle_power_w = measure_idle(block_dir, args.idle, args.rate)
    if idle_temp_mc is None:
        raise SystemExit("error: no CPU temperature readings during the idle baseline")

    order = list(workload.WORKLOADS)
    random.shuffle(order)  # shuffled inside the block (DESIGN.md section 5)
    results.write_json(os.path.join(block_dir, "block.json"), {
        "block_id": block_id,
        "cpu_profile": args.profile,
        "repeat": args.repeat,
        "room_temp_c": args.room_temp,
        "idle_temp_mc": idle_temp_mc,
        "idle_power_w": idle_power_w,
        "workload_order": order,
        "framework_commit": results.framework_commit(),
    })
    print(f"  idle: {idle_temp_mc / 1000:.1f} C, {idle_power_w} W; order: {order}")

    target_mc = idle_temp_mc + 3000  # cooldown target: idle + 3 C (hot-start check is +5 C, section 8)
    for position, name in enumerate(order, start=1):
        reached, temp, waited = wait_for_cooldown(temp_path, target_mc, args.cooldown_timeout)
        print(f"  cooldown: reached={reached}, {temp} mC after {waited:.0f} s")
        run_dir = run_one(args.runs_root, block_id, args.profile, name, args.repeat, position, args.room_temp,
                          args.warmup, args.duration, args.rate, args.gpu_pci)
        record = checks.check_and_record(run_dir, args.runs_root)
        reasons = record["unstable_reasons"] + record["invalid_reasons"]
        print(f"  run {position}/{len(order)} {record['status']}: {run_dir}" + (f" ({'; '.join(reasons)})" if reasons else ""))


if __name__ == "__main__":
    main()
