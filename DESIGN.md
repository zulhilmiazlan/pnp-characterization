# pnp-characterization: design (draft)

Drafted 2026-10-28. Work in progress: sections are added as decisions are made.

## 1. Goal

This project investigates how CPU power limits, AMD Curve Optimizer undervolting profiles, and GPU power caps affect performance, power consumption, energy efficiency, and temperature on a Ryzen 7 7800X3D and RX 9070 XT desktop running Linux, across CPU-bound, cache-sensitive, GPU, and AI inference workloads. It also explores whether machine learning can detect abnormal hardware behaviour, such as instability, thermal throttling, and sensor faults, from telemetry collected during experiments.

### Research questions

- **RQ1:** At what CPU power limit does performance per watt peak, and how does performance at that point compare with stock settings?
- **RQ2:** Does Curve Optimizer undervolting improve sustained performance by reducing temperature, rather than merely reducing power consumption?
- **RQ3:** How differently do CPU-bound, cache-sensitive, GPU, and AI inference workloads respond to the same power limit?
- **RQ4:** Can unsupervised anomaly detection identify telemetry patterns associated with unstable undervolting, thermal throttling, or sensor faults before a crash or obvious failure?

## 3. System under test

| Component | Detail |
|---|---|
| CPU | AMD Ryzen 7 7800X3D (8 cores / 16 threads), integrated Radeon 610M enabled |
| GPU | AMD Radeon RX 9070 XT (discrete) |
| Board | MSI B650M GAMING PLUS WIFI (MS-7E24) |
| RAM | 2 × 16 GB DDR5, rated 6000 MT/s, running at 6000 (EXPO on) |
| OS | CachyOS (Linux); Windows 11 on a separate partition for cross-checks |
| Boot | Limine (CachyOS) and Windows Boot Manager |

Development machine and optional second platform: Lenovo ThinkPad (Intel Core i5-1135G7), CachyOS.

## 4. Architecture

```
   Configuration  →  Orchestrator  →  Workload driver  +  Telemetry sampler
                                              ↓
                                       Result store
                                              ↓
                                          Analysis
                                              ↓
                                   Reports, plots, pass/fail
```

| Part | Takes in | Produces |
|---|---|---|
| **Configuration** | The BIOS profile name declared by the operator, framework-controlled settings such as GPU power cap, repeat count, warm-up/cooldown limits, sampling rate, and workload parameters. | A validated run configuration that distinguishes declared BIOS settings from settings the framework applies, plus checks that flag mismatches between the declared profile and measurable hardware state. |
| **Orchestrator** | The validated configuration, workload driver, telemetry sampler, and `capture_state.sh` script. | A coordinated experiment that captures a machine snapshot before each batch, runs warm-up and measurement phases, starts and stops telemetry, repeats runs, and waits for the CPU to cool below a target temperature or until a timeout is reached. |
| **Workload driver** | The selected workload, its parameters, and the requested run duration. | A workload result containing a measurable performance figure, such as operations per second, frames per second, or images per second, alongside execution time and exit status. |
| **Telemetry sampler** | A list of sensors to read (found by name, not by `hwmon` number), how often to read them, and for how long. | A CSV file with one row per reading: a timestamp and each sensor's value, or a marker that the sensor was unavailable (e.g. the GPU was runtime-suspended), never a fake zero. Energy-counter wraps are handled using `max_energy_range_uj`. |
| **Result store** | The unique run ID, configuration, machine snapshot, raw telemetry CSV, and workload result. | A persistent, immutable run directory containing all artefacts needed to reproduce the analysis and compare experiments later. |
| **Analysis** | The saved run directories, raw telemetry, workload performance results, configuration, and comparison criteria. | Derived metrics such as average power, energy consumption, performance per watt, temperature behaviour, plus run-to-run variance per configuration and whether configurations are distinguishable (spread within a configuration smaller than the difference between configurations), presented as reports and plots, without modifying the original run data. |

## 9. Risks and known issues

| Risk | Effect | How the project handles it |
|---|---|---|
| GPU sensors return "Device or resource busy" while the GPU is runtime-suspended (casebook 001) | Gaps in GPU telemetry | Record the reading as unavailable rather than writing `0`, which would incorrectly imply zero power consumption. Preserve the error or status so the gap can be investigated later. |
| The RAPL energy counter wraps (~48 min at 90 W on the laptop; possibly sooner on AMD) | A single long reading could be off by a whole lap | Sample the counter regularly and use `max_energy_range_uj` to correct deltas across a wrap. Validate the counter range on the desktop before relying on it. |
| An unstable Curve Optimizer undervolt crashes the machine | A run ends early; data may be lost | Treat crashes as experimental data. Write each telemetry row to disk immediately (flushed), so data up to the moment of the crash survives. Record run metadata, and use `rasdaemon` to monitor and preserve relevant hardware error records where available. After reboot, inspect the logs and mark the interrupted run as failed rather than discarding it silently. |
| Room temperature is not controlled at home | Hotter days give higher temperatures and possibly lower boost | Record ambient room temperature alongside each run, using a thermometer if available, and compare results with environmental conditions noted. Run a baseline configuration (stock) at the start of each session to detect drift between sessions. |
| Clock-speed readings are snapshots (DVFS, C-states) | A single reading misrepresents the actual speed | Avoid relying on individual `scaling_cur_freq` readings. Use time-series samples and workload performance measurements; use performance counters such as `perf stat` where appropriate to provide additional aggregate context. |
