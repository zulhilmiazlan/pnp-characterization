"""Tests for checks.py. Run from the repo folder: python tests/test_checks.py"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import checks  # noqa: E402


def rows(n, energy="1000"):
    """n good telemetry rows, 0.1 s apart."""
    return [{"t_s": f"{i / 10:.3f}", "energy_uj": energy} for i in range(n)]


def test_telemetry_problems():
    good = rows(20)
    assert checks.telemetry_problems(good) == [], "good telemetry should have no problems"
    assert len(checks.telemetry_problems([])) == 1, "empty telemetry: one problem"

    gap = good[:5] + good[12:]                       # 0.4 s -> 1.2 s
    assert len(checks.telemetry_problems(gap)) == 1, "one gap > 0.5 s"

    backwards = good[:5] + [good[3]] + good[6:]      # 0.4 s -> 0.3 s
    assert len(checks.telemetry_problems(backwards)) == 1, "timestamps go backwards"

    some_na = [dict(r, energy_uj="NA") if i < 3 else r for i, r in enumerate(good)]  # 3/20 = 15 %
    assert len(checks.telemetry_problems(some_na)) == 1, "too many NA energy readings"

    one_na = [dict(r, energy_uj="NA") if i == 0 else r for i, r in enumerate(good)]  # 1/20 = 5 %
    assert checks.telemetry_problems(one_na) == [], "5 % NA is still allowed (limit is 'more than')"

    # Several problems in one CSV: a gap first, then a backwards timestamp. All must be reported.
    both = good[:5] + good[12:15] + [good[13]] + good[16:]
    assert len(checks.telemetry_problems(both)) == 2, "gap AND backwards timestamp must both be reported"


def start_rows(first_temp, quiet_power, n=20):
    """n rows 0.1 s apart: first CPU temperature `first_temp`, power `quiet_power` throughout (text or "NA")."""
    out = []
    for i in range(n):
        out.append({"t_s": f"{i / 10:.3f}", "cpu_temp_mc": first_temp if i == 0 else "50000",
                    "power_w": "NA" if i == 0 else quiet_power})
    return out


def test_start_problems():
    idle_t, idle_p, quiet = 40000, 2.0, 1   # idle 40 C and 2 W; 1 s quiet window (rows with t_s < 1)
    assert checks.start_problems(start_rows("43000", "4.0"), idle_t, idle_p, quiet) == [], "+3 C, +2 W: fine"
    assert len(checks.start_problems(start_rows("46000", "4.0"), idle_t, idle_p, quiet)) == 1, "+6 C: hot start"
    assert len(checks.start_problems(start_rows("43000", "6.0"), idle_t, idle_p, quiet)) == 1, "+4 W: not quiet"
    assert len(checks.start_problems(start_rows("46000", "6.0"), idle_t, idle_p, quiet)) == 2, "both problems"
    assert len(checks.start_problems(start_rows("NA", "4.0"), idle_t, idle_p, quiet)) == 1, "no start temp: can't check"
    assert len(checks.start_problems(start_rows("43000", "NA"), idle_t, idle_p, quiet)) == 1, "no power: can't check"
    assert len(checks.start_problems(start_rows("43000", "4.0"), idle_t, None, quiet)) == 1, "no idle power baseline"


if __name__ == "__main__":
    test_telemetry_problems()
    test_start_problems()
    print("all checks tests passed")
