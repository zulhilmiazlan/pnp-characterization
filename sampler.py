
"""Telemetry sampler v0: read CPU energy and temperature at a fixed rate into a CSV file."""

import argparse
import csv
import glob
import os
import time


def read_text(path):
    """Return the contents of a small sysfs file as text, or None if it can't be read."""
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def read_int(path):
    """Return a sysfs file's value as a whole number, or None if it can't be read."""
    text = read_text(path)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def energy_delta(old, new, max_range):
    """Return the energy used between two counter readings, handling one wrap."""
    if old is None or new is None or max_range is None:
        return None

    if new >= old:
        return new - old
    return (max_range - old) + new


def find_hwmon(name):
    """Return the hwmon folder whose 'name' file matches, or None."""
    for folder in glob.glob("/sys/class/hwmon/hwmon*"):
        if read_text(folder + "/name") == name:
            return folder
    return None


def find_rapl_package():
    """Return the RAPL zone folder named 'package-0', or None."""
    for folder in glob.glob("/sys/class/powercap/intel-rapl:*"):
        if read_text(folder + "/name") == "package-0":
            return folder
    return None


def sample(rapl, temp_dev, rate, duration, out_path):
    """Read the sensors `rate` times per second for `duration` seconds."""
    period = 1.0 / rate
    count = int(duration * rate)
    max_range = read_int(rapl + "/max_energy_range_uj")
    prev_energy = None
    prev_t = None

    start = time.monotonic()

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_s", "energy_uj", "cpu_temp_mc", "power_w"])

        for i in range(count):
            t = time.monotonic() - start
            energy = read_int(rapl + "/energy_uj")
            temp = read_int(temp_dev + "/temp1_input")

            delta_uj = energy_delta(prev_energy, energy, max_range)

            # No power on the first row, or if either energy reading is missing.
            if delta_uj is None:
                power = None
            else:
                power = (delta_uj / 1e6) / (t - prev_t)

            writer.writerow([
                f"{t:.3f}",
                energy if energy is not None else "NA",
                temp if temp is not None else "NA",
                f"{power:.2f}" if power is not None else "NA",
            ])

            f.flush()
            os.fsync(f.fileno())

            prev_energy = energy
            prev_t = t

            # Wait until the next reading is due, counted from the start,
            # so small delays don't add up.
            next_time = start + (i + 1) * period
            time.sleep(max(0.0, next_time - time.monotonic()))


def main():
    parser = argparse.ArgumentParser(description="Sample CPU energy and temperature into a CSV file.")
    parser.add_argument("--rate", type=float, default=10.0, help="readings per second (default 10)")
    parser.add_argument("--duration", type=float, default=5.0, help="seconds to sample (default 5)")
    parser.add_argument("--out", default="telemetry.csv", help="output CSV file")
    args = parser.parse_args()
    if args.rate <= 0 or args.duration <= 0:
        parser.error("--rate and --duration must be greater than zero")

    temp_dev = find_hwmon("coretemp") or find_hwmon("k10temp")
    rapl = find_rapl_package()
    if temp_dev is None or rapl is None:
        raise SystemExit(f"error: sensors not found (temperature: {temp_dev}, RAPL: {rapl})")

    print(f"Sampling {rapl} and {temp_dev} at {args.rate}/s for {args.duration} s -> {args.out}")
    sample(rapl, temp_dev, args.rate, args.duration, args.out)


if __name__ == "__main__":
    main()
