"""Telemetry sampler v0: find the CPU sensors by name, then (later) read them at a fixed rate."""

import glob


def read_text(path):
    """Return the contents of a small sysfs file as text, or None if it can't be read."""
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def find_hwmon(name):
    """Return the hwmon folder (e.g. '/sys/class/hwmon/hwmon6') whose 'name' file equals `name`, or None."""
    for folder in glob.glob("/sys/class/hwmon/hwmon*"):
        if read_text(folder + "/name") == name:
            return folder
    return None


def find_rapl_package():
    """Return the RAPL zone folder (e.g. '/sys/class/powercap/intel-rapl:0') named 'package-0', or None."""
    for folder in glob.glob("/sys/class/powercap/intel-rapl:*"):
        if read_text(folder + "/name") == "package-0":
            return folder
    return None

if __name__ == "__main__":
    temp_dev = find_hwmon("coretemp") or find_hwmon("k10temp")
    rapl = find_rapl_package()
    print("CPU temperature device:", temp_dev)
    print("RAPL package zone:     ", rapl)
