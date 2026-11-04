"""Telemetry sampler: read CPU energy and temperature, and optionally GPU power and temperatures, at a fixed rate into a CSV file."""
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


def na(value):
    """Return `value`, or "NA" if it is None (for CSV output)."""
    return value if value is not None else "NA"


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


def find_hwmon_on_pci(name, pci_addr):
    """Return the hwmon folder named `name` whose device is at PCI address `pci_addr`, or None."""
    for folder in glob.glob("/sys/class/hwmon/hwmon*"):
        if read_text(folder + "/name") != name:
            continue

        device_path = os.path.realpath(folder + "/device")

        if pci_addr in device_path.split("/"):
            return folder

    return None


def find_rapl_package():
    """Return the RAPL zone folder named 'package-0', or None."""
    for folder in glob.glob("/sys/class/powercap/intel-rapl:*"):
        if read_text(folder + "/name") == "package-0":
            return folder
    return None


def sample(rapl, temp_dev, gpu_dev, rate, duration, out_path):
    """Read the sensors `rate` times per second for `duration` seconds."""
    period = 1.0 / rate
    count = int(duration * rate)
    max_range = read_int(rapl + "/max_energy_range_uj")
    prev_energy = None
    prev_t = None

    start = time.monotonic()

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "t_s", "energy_uj", "cpu_temp_mc", "power_w",
            "gpu_power_uw", "gpu_edge_mc", "gpu_junction_mc", "gpu_mem_mc"
        ])

        for i in range(count):
            t = time.monotonic() - start
            energy = read_int(rapl + "/energy_uj")
            temp = read_int(temp_dev + "/temp1_input")

            delta_uj = energy_delta(prev_energy, energy, max_range)

            if delta_uj is None:
                power = None
            else:
                power = (delta_uj / 1e6) / (t - prev_t)

            if gpu_dev is None:
                gpu_power = None
                gpu_edge = None
                gpu_junction = None
                gpu_mem = None
            else:
                gpu_power = read_int(gpu_dev + "/power1_average")
                gpu_edge = read_int(gpu_dev + "/temp1_input")
                gpu_junction = read_int(gpu_dev + "/temp2_input")
                gpu_mem = read_int(gpu_dev + "/temp3_input")

            writer.writerow([
                f"{t:.3f}",
                na(energy),
                na(temp),
                na(f"{power:.2f}" if power is not None else None),
                na(gpu_power),
                na(gpu_edge),
                na(gpu_junction),
                na(gpu_mem),
            ])

            f.flush()
            os.fsync(f.fileno())

            prev_energy = energy
            prev_t = t

            next_time = start + (i + 1) * period
            time.sleep(max(0.0, next_time - time.monotonic()))


def main():
    parser = argparse.ArgumentParser(description="Sample CPU (and optionally GPU) telemetry into a CSV file.")
    parser.add_argument("--gpu-pci", default=None, help="PCI address of the GPU under test, e.g. 0000:03:00.0")
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

    # GPU under test is chosen by PCI address, because the iGPU also reports as "amdgpu" (casebook 001).
    gpu_dev = None
    if args.gpu_pci:
        gpu_dev = find_hwmon_on_pci("amdgpu", args.gpu_pci)
        if gpu_dev is None:
            raise SystemExit(f"error: amdgpu hwmon not found for PCI address {args.gpu_pci}")

    print(f"Sampling {rapl}, {temp_dev}, GPU: {gpu_dev} at {args.rate}/s for {args.duration} s -> {args.out}")
    sample(rapl, temp_dev, gpu_dev, args.rate, args.duration, args.out)


if __name__ == "__main__":
    main()
