# Project A: component design (draft)

Drafted 2026-10-28. Moves into the Project A repo's `DESIGN.md` once the repo exists.

```
   Configuration  →  Orchestrator  →  Workload driver  +  Telemetry sampler
                                              ↓
                                       Result store
                                              ↓
                                   Analysis  →  Reports / plots
```

| Part | Takes in | Produces |
|---|---|---|
| **Configuration** | The BIOS profile name you declare, framework-controlled settings such as GPU power cap, repeat count, warm-up/cooldown limits, sampling rate, and workload parameters. | A validated run configuration that distinguishes declared BIOS settings from settings the framework applies, plus checks that flag mismatches between the declared profile and measurable hardware state. |
| **Orchestrator** | The validated configuration, workload driver, telemetry sampler, and `capture_state.sh` script. | A coordinated experiment that captures a machine snapshot before each batch, runs warm-up and measurement phases, starts and stops telemetry, repeats runs, and waits for the CPU to cool below a target temperature or until a timeout is reached. |
| **Workload driver** | The selected workload, its parameters, and the requested run duration. | A workload result containing a measurable performance figure, such as operations per second, frames per second, or images per second, alongside execution time and exit status. |
| **Telemetry sampler** | A list of sensors to read (found by name, not by `hwmon` number), how often to read them, and for how long. | A CSV file with one row per reading: a timestamp and each sensor's value, or a marker that the sensor was unavailable (e.g. the GPU was runtime-suspended), never a fake zero. Energy-counter wraps are handled using `max_energy_range_uj`. |
| **Result store** | The unique run ID, configuration, machine snapshot, raw telemetry CSV, and workload result. | A persistent, immutable run directory containing all artefacts needed to reproduce the analysis and compare experiments later. |
| **Analysis** | The saved run directories, raw telemetry, workload performance results, configuration, and comparison criteria. | Derived metrics such as average power, energy consumption, performance per watt, temperature behaviour, plus run-to-run variance per configuration and whether configurations are distinguishable (spread within a configuration smaller than the difference between configurations), presented as reports and plots, without modifying the original run data. |
