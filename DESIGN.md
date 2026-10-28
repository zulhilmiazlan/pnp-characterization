# pnp-characterization: design (draft)

Drafted 2026-10-28. Work in progress: sections are added as decisions are made.

## 1. Goal

This project investigates how CPU power limits, AMD Curve Optimizer undervolting profiles, and GPU power caps affect performance, power consumption, energy efficiency, and temperature on a Ryzen 7 7800X3D and RX 9070 XT desktop running Linux, across CPU-bound, cache-sensitive, GPU, and AI inference workloads. It also explores whether machine learning can detect abnormal hardware behaviour, such as instability, thermal throttling, and sensor faults, from telemetry collected during experiments.

### Research questions

- **RQ1:** At what CPU power limit does performance per watt peak, and how does performance at that point compare with stock settings?
- **RQ2:** Does Curve Optimizer undervolting improve sustained performance by reducing temperature, rather than merely reducing power consumption?
- **RQ3:** How differently do CPU-bound, cache-sensitive, GPU, and AI inference workloads respond to the same power limit?
- **RQ4:** Can unsupervised anomaly detection identify telemetry patterns associated with unstable undervolting, thermal throttling, or sensor faults before a crash or obvious failure?

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
