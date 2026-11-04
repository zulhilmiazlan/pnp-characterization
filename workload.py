"""Workload driver: run one stress-ng workload and return its score and exit status."""

import argparse
import subprocess

# Pilot workloads (DESIGN.md section 5). Both support --verify (checked with `stress-ng --verifiable`).
# "0" means one worker per logical CPU.
WORKLOADS = {
    "cpu-matrix": ["--cpu", "0", "--cpu-method", "matrixprod"],
    "stream": ["--stream", "0"],
}


def parse_score(text):
    """Return the 'bogo ops/s (real time)' value from stress-ng --metrics-brief output, or None."""
    for line in text.splitlines():
        if "metrc:" in line:
            fields = line.split()
            try:
                return float(fields[-2])
            except ValueError:
                continue

    return None


def run_workload(name, duration_s, out_path):
    """Run workload `name` for `duration_s` seconds, save its output to `out_path`, return a result dict."""
    cmd = ["stress-ng", *WORKLOADS[name], "--timeout", f"{duration_s}s", "--metrics-brief", "--verify"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    with open(out_path, "w") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.write(proc.stdout)
        f.write(proc.stderr)

    return {
        "workload": name,
        "exit_status": proc.returncode,
        "score": parse_score(proc.stdout),
        "score_unit": "bogo ops/s",
    }


def main():
    parser = argparse.ArgumentParser(description="Run one stress-ng workload and print its result.")
    parser.add_argument("workload", choices=sorted(WORKLOADS))
    parser.add_argument("--duration", type=int, default=10, help="seconds (default 10)")
    parser.add_argument("--out", default="workload.txt", help="file for the workload's own output")
    args = parser.parse_args()
    print(run_workload(args.workload, args.duration, args.out))


if __name__ == "__main__":
    main()
