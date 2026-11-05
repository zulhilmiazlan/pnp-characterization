"""Orchestrator: run one block of measurement runs (one boot, one BIOS profile). DESIGN.md sections 5, 7 and 8."""

import os
import subprocess
import sys
from datetime import datetime

import results
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


def run_one(runs_root, block_id, profile, workload_name, repeat, position, room_temp_c,
            warmup_s, workload_s, rate, gpu_pci=None):
    """Do one complete run: folder, run.json, sampler in the background, warm-up, workload, result.json."""
    start = datetime.now().astimezone()
    run_id = results.make_run_id(start, profile, workload_name, repeat)
    run_dir = results.create_run_dir(runs_root, run_id)

    run_info = {
        "run_id": run_id,
        "block_id": block_id,
        "cpu_profile": profile,
        "workload": workload_name,
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

    # Sampler runs in the background for the warm-up and the workload, plus a margin for start-up delays.
    margin_s = 10
    cmd = [sys.executable, os.path.join(HERE, "sampler.py"),
           "--rate", str(rate), "--duration", str(warmup_s + workload_s + margin_s),
           "--out", os.path.join(run_dir, "telemetry.csv")]
    if gpu_pci:
        cmd += ["--gpu-pci", gpu_pci]
    log_event(run_dir, "sampler start")
    sampler = subprocess.Popen(cmd)

    log_event(run_dir, "warm-up start")
    workload.run_workload(workload_name, warmup_s, os.path.join(run_dir, "warmup.txt"))
    log_event(run_dir, "workload start")
    res = workload.run_workload(workload_name, workload_s, os.path.join(run_dir, "workload.txt"))
    log_event(run_dir, "workload end")

    sampler_exit = sampler.wait()
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
        "status": "unchecked",  # set by the quality checks (section 8), added later
    }
    results.write_json(os.path.join(run_dir, "result.json"), result)
    return run_dir
