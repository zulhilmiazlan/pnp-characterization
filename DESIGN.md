# pnp-characterization: design (draft)

Drafted 2026-10-28. Work in progress: sections are added as decisions are made.

## 1. Goal

This project investigates how CPU power limits, AMD Curve Optimizer undervolting profiles, and GPU power caps affect performance, power consumption, energy efficiency, and temperature on a Ryzen 7 7800X3D and RX 9070 XT desktop running Linux, across CPU-bound, cache-sensitive, GPU, and AI inference workloads. It also explores whether machine learning can detect abnormal hardware behaviour, such as instability, thermal throttling, and sensor faults, from telemetry collected during experiments.

### Research questions

- **RQ1:** At what CPU power limit does performance per watt peak, and how does performance at that point compare with stock settings?
- **RQ2:** Does Curve Optimizer undervolting improve sustained performance by reducing temperature, rather than merely reducing power consumption?
- **RQ3:** How differently do CPU-bound, cache-sensitive, GPU, and AI inference workloads respond to the same power limit?
- **RQ4:** Can unsupervised anomaly detection identify telemetry patterns associated with unstable undervolting, thermal throttling, or sensor faults before a crash or obvious failure?

## 2. Scope

### In scope

- One desktop system: the Ryzen 7 7800X3D and Radeon RX 9070 XT described in section 3. Results apply to this tested unit and its recorded configuration.
- CPU settings: package power limit (PPT) and AMD Curve Optimizer undervolting profiles, selected in the BIOS. GPU setting: power cap, set by the framework through sysfs.
- CPU-bound, cache-sensitive, GPU and AI inference workloads, with performance, power, energy efficiency and temperature measured during each run.
- CachyOS Linux, using the CPU and GPU telemetry available through sysfs.
- Unsupervised anomaly detection on the collected telemetry, focused on unstable undervolts and thermal throttling, evaluated against recorded events (crashes, rasdaemon hardware errors, throttling).

### Held fixed

- The same physical desktop, CPU, GPU, motherboard and memory are used throughout.
- Memory stays at its DDR5-6000 EXPO profile. Memory timings and frequency are not experimental variables.
- BIOS version and all other BIOS settings stay unchanged within an experiment batch, apart from the power-limit and Curve Optimizer profile being tested.
- CPU and case fan curves (BIOS) are unchanged across runs, so cooling behaves by the same rules in every run.
- The integrated Radeon 610M's state (enabled or disabled) is decided in the first desktop session, then held fixed and recorded. The discrete RX 9070 XT is the GPU under test.
- Operating system, kernel, graphics driver, workload versions and relevant software settings are kept the same within each comparison and recorded with the run data.

### Out of scope

- Generalising to every Ryzen 7 7800X3D or RX 9070 XT. Because of unit-to-unit variation, other samples may reach different undervolts, temperatures or performance.
- Comparing different CPU or GPU models. This is a controlled characterization of one desktop, not a benchmark across products.
- Windows. Windows 11 is installed on the same machine but is not used for measurements; the framework and all experiments are Linux-only.
- Laboratory-grade external power measurement. The project uses on-chip telemetry and focuses on relative comparisons within the tested system.
- Raising CPU or GPU voltages above stock, or overclocking. Only power limits and undervolting are explored, to avoid voltage-related damage.
- Changing BIOS settings automatically. Power-limit and Curve Optimizer profiles are selected by hand in the BIOS; the framework records and checks the declared profile.

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

## 5. Experiment design

### Factors and levels

| Factor | Levels | How it is changed |
|---|---|---|
| CPU profile | Pilot: stock, Curve Optimizer −30, PPT 65 W | Selected by hand from saved BIOS profiles; one boot per profile |
| Workload | Pilot: two CPU workloads from `stress-ng` (chosen when the workload driver is built). Later: GPU and AI inference workloads | Chosen by the run configuration and launched by the workload driver |
| GPU power cap | Not in the CPU pilot. Levels to be defined downwards from the stock 304 W cap | Set by the framework through sysfs (`power1_cap`) |

### Responses

- Workload performance (the workload's own score or execution time) and exit status.
- CPU package energy, average power and temperature.
- GPU power and temperatures, when the workload uses the discrete GPU.
- Derived: performance per watt and temperature behaviour. Room temperature is recorded with every run.

### Repeats

- Each profile × workload combination is repeated five times in the pilot.
- Repeats show run-to-run variation, so a real profile effect can be told apart from noise in a single run. Five is the minimum that gives a usable spread within the time available; Sprint 2 increases it.

### Run order

- A **block** is one boot with one CPU profile. Inside each block, every workload (and later, every GPU cap) runs once, in a shuffled order.
- Profiles are interleaved, never run all-of-one-then-the-next. With three profiles A, B and C, the pilot uses the order ABC CBA ABC CBA ABC (15 blocks), so each profile gets as many early slots as late ones.
- Room temperature is recorded with every run using a thermometer.
- Interleaving and shuffling reduce confounding from time of day, room-temperature drift and workload order.

### Pilot size and time

- 3 CPU profiles × 2 workloads × 5 repeats = 30 runs, in 15 blocks (5 per profile).
- Each run takes up to 7 minutes (1 min warm-up + 3 min workload + up to 3 min cooldown), so a block takes about 14 minutes.
- 14 profile switches × about 2 minutes = 28 minutes.
- Total: 30 × 7 + 14 × 2 = 238 minutes, about 4 hours, not counting setup or problems. The operator must be present for a BIOS switch about every 14 minutes.

## 6. Measurement

### Sources

- CPU package energy is read from RAPL through `energy_uj`. CPU temperature is read from the `coretemp` (laptop) or `k10temp` (desktop) hwmon device.
- Desktop GPU power is read from amdgpu's `power1_average`. GPU temperatures are read from `temp1` (edge), `temp2` (junction) and `temp3` (memory).
- GPU sensor reads fail with "Device or resource busy" (`EBUSY`) while the GPU is runtime-suspended. These readings are recorded as `NA`, not zero (casebook 001).

### Sampling rate

- The sampler takes 10 readings per second (one every 0.1 s). This shows events lasting about 0.1 s or longer, such as a 7 W spike seen during laptop testing. Shorter events are averaged into their 0.1 s interval.
- The laptop RAPL counter has a range of 262,143 J and wraps after about 48 minutes at 90 W. At 10 readings per second there are about 28,800 readings per wrap, so a complete wrap between two readings cannot happen in practice. The desktop counter range is still to be measured.
- At 1 Hz, short power spikes would be averaged away. At 100 Hz or more, Python and `fsync` overhead would grow (a stronger observer effect) and the data would be about 10 times larger.

### Power calculation

- Average power between consecutive readings = energy difference (µJ converted to J) ÷ the actual elapsed time in seconds.
- Counter wraps are handled using `max_energy_range_uj`. Only one wrap between consecutive readings is supported; more than one cannot be detected from two readings.
- If either energy reading is unavailable, power is recorded as `NA`. The current code updates the previous reading on every pass, even when it is unavailable, so one failed energy reading gives two consecutive `NA` power rows.

### Failed readings

- Missing or failed readings are recorded as `NA`, never zero, so that unavailable data cannot be mistaken for a real zero.
- *Planned (v1):* the error type (e.g. `EBUSY`) is also recorded, so missing data can be investigated later.

### Measurement reliability

- **Settling:** the warm-up period before each run is not used in the reported results, so the measurements describe the steady state rather than the settling after a change.
- **Background activity:** other applications are closed during experiment batches. Each configuration is repeated at least five times, and the spread between repeats is reported.
- **Observer effect:** the sampler's own power cost is not yet measured. Planned test: compare idle power sampled at 1 Hz and at 10 Hz. It matters mainly for idle measurements and is small next to a full workload.

## 7. Data format

### Run ID

- Format: `<start time>_<CPU profile>_<workload>_r<repeat>`, e.g. `20261115T091230_stock_cpu-matrix_r03`.
- The start time is local time (UTC+8; Malaysia has no daylight saving), written as `YYYYMMDDTHHMMSS` so that folder names sort in time order.
- The start time makes the ID unique: the orchestrator runs one thing at a time, so no two runs start in the same second. The profile, workload and repeat number make it readable at a glance.
- A run folder is created with `os.makedirs(path, exist_ok=False)`, so an existing folder is never reused or overwritten.

### Run folder layout

```text
runs/
  <run_id>/
    run.json        what was asked for (configuration and conditions)
    telemetry.csv   sampler output (section 6)
    workload.txt    the workload's own output, unedited
    result.json     what happened: score, exit status, start and end times
    events.log      timestamped phases: warm-up, workload start/end, cooldown end, errors
  state/
    <block_id>/     capture_state.sh snapshot, taken once per block (boot)
analysis/           derived results; reads runs/, never writes to it
```

- The machine snapshot is taken once per block rather than once per run, because it is slow and the machine state does not change within one boot. Each `run.json` names its block.

### run.json fields

| Field | Example |
|---|---|
| `run_id` | `20261115T091230_stock_cpu-matrix_r03` |
| `block_id` | `20261115T090500_stock` |
| `cpu_profile` | `stock` (declared by the operator; checked against the snapshot) |
| `workload` | `cpu-matrix`, plus its parameters |
| `gpu_cap_w` | `null` when not set |
| `repeat` | `3` |
| `position_in_block` | `1` |
| `room_temp_c` | `24.5` |
| `sample_rate_hz` | `10` |
| `framework_commit` | git commit hash of this repository when the run started |

### result.json fields

`score`, `score_unit`, `exit_status`, `start_time`, `end_time`, `duration_s` (times in ISO 8601, e.g. `2026-11-15T09:12:30+08:00`).

### Rules

- A run folder is never changed after its run ends.
- Analysis reads `runs/` and writes only to `analysis/`.
- Missing values are `NA` in CSV files and `null` in JSON files, never zero.
- A failed or crashed run keeps its folder. Its exit status and `events.log` record what happened (crash = data, section 9).

## 9. Risks and known issues

| Risk | Effect | How the project handles it |
|---|---|---|
| GPU sensors return "Device or resource busy" while the GPU is runtime-suspended (casebook 001) | Gaps in GPU telemetry | Record the reading as unavailable rather than writing `0`, which would incorrectly imply zero power consumption. Preserve the error or status so the gap can be investigated later. |
| The RAPL energy counter wraps (~48 min at 90 W on the laptop; possibly sooner on AMD) | A single long reading could be off by a whole lap | Sample the counter regularly and use `max_energy_range_uj` to correct deltas across a wrap. Validate the counter range on the desktop before relying on it. |
| An unstable Curve Optimizer undervolt crashes the machine | A run ends early; data may be lost | Treat crashes as experimental data. Write each telemetry row to disk immediately (flushed), so data up to the moment of the crash survives. Record run metadata, and use `rasdaemon` to monitor and preserve relevant hardware error records where available. After reboot, inspect the logs and mark the interrupted run as failed rather than discarding it silently. |
| Room temperature is not controlled at home | Hotter days give higher temperatures and possibly lower boost | Record ambient room temperature alongside each run, using a thermometer if available, and compare results with environmental conditions noted. Run a baseline configuration (stock) at the start of each session to detect drift between sessions. |
| Clock-speed readings are snapshots (DVFS, C-states) | A single reading misrepresents the actual speed | Avoid relying on individual `scaling_cur_freq` readings. Use time-series samples and workload performance measurements; use performance counters such as `perf stat` where appropriate to provide additional aggregate context. |
