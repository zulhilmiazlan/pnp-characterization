"""Result store: run IDs, run folders that are never overwritten, and JSON records (DESIGN.md section 7)."""

import json
import os
import subprocess
from datetime import datetime


def make_run_id(start, profile, workload, repeat):
    """Return a run ID like '20261115T091230_stock_cpu-matrix_r03' from a datetime and the run's settings."""
    return f"{start:%Y%m%dT%H%M%S}_{profile}_{workload}_r{repeat:02d}"

def create_run_dir(root, run_id):
    """Create the folder `root`/`run_id` and return its path. Raise FileExistsError if it already exists."""
    path = os.path.join(root, run_id)
    os.makedirs(path, exist_ok=False)
    return path


def write_json(path, data):
    """Write `data` to a new JSON file at `path`. Raise FileExistsError if the file already exists."""
    # Mode "x" = create a new file only; it never overwrites (section 7: run records are immutable).
    with open(path, "x") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def framework_commit():
    """Return the git commit hash of this repository, with '-dirty' added if there are uncommitted changes."""
    repo = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=repo)
    if proc.returncode != 0:
        return None
    commit = proc.stdout.strip()

    status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=repo)

    if status.stdout.strip():
        commit += "-dirty"

    return commit
