# pnp-characterization: design (draft)

Drafted 2026-10-28. Work in progress: sections are added as decisions are made.

## 1. Goal

This project investigates how CPU power limits, AMD Curve Optimizer undervolting profiles, and GPU power caps affect performance, power consumption, energy efficiency, and temperature on a Ryzen 7 7800X3D and RX 9070 XT desktop running Linux, across CPU-bound, cache-sensitive, GPU, and AI inference workloads. It also explores whether machine learning can detect abnormal hardware behaviour, such as instability and thermal throttling from telemetry collected during experiments.

### Research questions

- **RQ1:** At what CPU power limit does performance per watt peak, and how does performance at that point compare with stock settings?
- **RQ2:** Does Curve Optimizer undervolting improve sustained performance by reducing temperature, rather than merely reducing power consumption?
- **RQ3:** How differently do CPU-bound, cache-sensitive, GPU, and AI inference workloads respond to the same power limit?
- **RQ4:** Can unsupervised anomaly detection identify telemetry patterns associated with unstable undervolting or thermal throttling before a crash or obvious failure?

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

## 8. Quality checks

After each run, the orchestrator checks it and writes a status, plus the reason for any failed check, to `result.json`. Raw data is never changed or deleted.

### Run status

| Status | Meaning | Use in analysis |
|---|---|---|
| `ok` | The run completed and every check passed | Used everywhere |
| `unstable` | The hardware failed: crash, unexpected reboot or a new hardware error | Kept for RQ4 and counted per configuration. Left out of performance and perf/W averages, which need a completed score |
| `invalid` | The measurement failed: the data or the starting conditions cannot be trusted | Left out everywhere; the number of runs excluded and the reasons are reported |

A crash is a result, not bad data: removing unstable runs would hide the behaviour RQ4 investigates. An `unstable` run at **stock** settings is treated differently, because stock is expected to be stable; it points to a system problem and is investigated separately (casebook).

### Checks that mark a run `invalid`

| Check | Initial threshold | Reason |
|---|---|---|
| Telemetry missing | `telemetry.csv` missing or has no readings | Nothing to analyse |
| Timestamps | Not strictly increasing | The sampler or clock misbehaved |
| Reading gap | Any gap between readings > 0.5 s | At 10 Hz, that is at least five missed readings |
| Missing energy | > 5% of CPU energy readings are `NA` | Allows occasional failures, not runs with substantial missing data |
| Hot start | CPU temperature at start > 5 °C above the session's idle baseline | Cooldown did not finish; thermal history would bias the run |
| Not quiet | Mean CPU package power over the 10 s before warm-up > 3 W above the idle baseline | Background activity would add to the measured power |
| Profile mismatch | Measured behaviour contradicts the declared profile (e.g. package power well above the declared PPT), or BIOS version differs from the batch | The run did not use the configuration it claims |
| GPU cap mismatch | Cap read back from sysfs differs from the configured value | Same as above |
| Missing metadata | `run.json` lacks room temperature or the framework commit | The run cannot be interpreted or traced to its code |

Curve Optimizer offsets cannot be read back from Linux, so the CO profile can only be declared, not verified (section 4).

### Checks that mark a run `unstable`

- The workload crashes or exits with a non-zero status without producing a score.
- The machine reboots during the run. This is detected at the next start: a run whose `events.log` has no "workload end" entry is marked `unstable`, with the time of its last reading.
- rasdaemon records a new hardware error during the run.

### Thresholds are provisional

All thresholds are initial values for the pilot. After the pilot, they are reviewed against the observed distributions and changed if needed, with the change recorded in this document. The "not quiet" threshold comes from laptop measurements (idle about 1.5–3 W); the desktop idles much higher, so it will be reset from the desktop's idle baseline in the first desktop session, possibly as a percentage instead of a fixed number of watts.

## 9. Risks and known issues

| Risk | Effect | How the project handles it |
|---|---|---|
| GPU sensors return "Device or resource busy" while the GPU is runtime-suspended (casebook 001) | Gaps in GPU telemetry | Record the reading as unavailable rather than writing `0`, which would incorrectly imply zero power consumption. Preserve the error or status so the gap can be investigated later. |
| The RAPL energy counter wraps (~48 min at 90 W on the laptop; possibly sooner on AMD) | A single long reading could be off by a whole lap | Sample the counter regularly and use `max_energy_range_uj` to correct deltas across a wrap. Validate the counter range on the desktop before relying on it. |
| An unstable Curve Optimizer undervolt crashes the machine | A run ends early; data may be lost | Treat crashes as experimental data. Write each telemetry row to disk immediately (flushed), so data up to the moment of the crash survives. Record run metadata, and use `rasdaemon` to monitor and preserve relevant hardware error records where available. After reboot, inspect the logs and mark the interrupted run as failed rather than discarding it silently. |
| Room temperature is not controlled at home | Hotter days give higher temperatures and possibly lower boost | Record ambient room temperature alongside each run, using a thermometer if available, and compare results with environmental conditions noted. Run a baseline configuration (stock) at the start of each session to detect drift between sessions. |
| Clock-speed readings are snapshots (DVFS, C-states) | A single reading misrepresents the actual speed | Avoid relying on individual `scaling_cur_freq` readings. Use time-series samples and workload performance measurements; use performance counters such as `perf stat` where appropriate to provide additional aggregate context. |

## 10. Open decisions

| Decision | Options | Decided when |
|---|---|---|
| `stress-ng` workloads | **Decided 4 Nov:** `cpu --cpu-method matrixprod` (compute-bound) and `stream` (memory-sensitive; buffers sized from the last-level cache). Both verify their results (`stress-ng --verifiable`). `cache` and `memrate` rejected: no verification, so they report "passed" without checking | Done (`workload.py`) |
| Cooldown target and timeout | Cool until CPU temperature is within a few °C of idle; give up after a fixed timeout | Fri 6 Nov, when the orchestrator is built; checked in the first desktop batch |
| iGPU configuration | Enabled (recorded) or disabled in the BIOS | Sat 7 Nov, first desktop session; then held fixed (section 2) |
| Desktop RAPL counter range | Read from `max_energy_range_uj`; work out the wrap time at full load | Sat 7 Nov, first desktop session |
| Desktop idle baseline | Measure idle package power and temperature; set the "not quiet" threshold in watts or as a percentage | Sat 7 Nov, before any pilot run is judged (section 8) |
| Room temperature measurement | Cheap digital thermometer now; a BME280 sensor on the Project B board later | Thermometer bought before Sun 8 Nov (first batch) |
| GPU power cap levels | Stock 304 W plus lower steps | Block B (14–29 Nov), before the GPU batch |

## 11. Anomaly detection (RQ4)

### Approach

- An unsupervised detector learns what normal telemetry looks like from runs at stable settings, then flags readings that do not fit. It is never trained on examples labelled as failures.
- The model itself is chosen in Semester 2. This section fixes how it will be **evaluated**, so that the data collected from Block B onwards can support that evaluation.

### Ground truth events

Recorded events are used to evaluate the detector, never to train it. Each event needs an exact time.

| Event | Source | Time taken from |
|---|---|---|
| Crash or unexpected reboot | Run without a "workload end" entry in `events.log` (section 8) | Time of the last telemetry reading |
| Hardware error | rasdaemon (corrected and uncorrected errors) | rasdaemon's own timestamp |
| Wrong result | Workload's built-in result check (e.g. `stress-ng --verify`) reports a mismatch | Time in `workload.txt` / `events.log` |
| Thermal throttling | Clock speed falls while temperature is at its limit (exact definition fixed with the desktop data) | Telemetry timestamp |

- Telemetry times are seconds since the run started (`t_s`). Adding the run's start time from `result.json` converts them to clock time, so they can be matched with rasdaemon's timestamps.
- A wrong result without a crash is the closest this project gets to silent data corruption, so these events are reported separately.

### Creating marginal behaviour

- After the pilot, Curve Optimizer is stepped further negative from the last stable level in steps of 5 (e.g. −30, −35, −40, …), running the workloads several times at each step.
- Stepping, rather than jumping to an extreme value, records the transition from stable to marginal behaviour. An extreme value may crash at once, leaving no telemetry from before the failure.
- Stepping stops at the first level that crashes repeatedly. That level and the one before it are the marginal region of most interest.
- Safety: only undervolting (lower voltage than stock) is used; telemetry is flushed to disk row by row (section 6); the BIOS can be reset by clearing CMOS if a setting does not boot.

### Matching alerts to events

- An alert is a **correct warning** if it comes up to 60 s before an event (initial window; reviewed after the first unstable runs).
- An event with no alert in its window is a **missed event**. An alert with no event in the following 60 s is a **false alarm**. Alerts after an event in the same run are ignored.
- **No look-ahead:** when the detector judges time *t*, it may only use readings from time *t* or earlier, even though analysis runs after the batch on saved files.

### Evaluation

- For each detector, report together: events caught (out of the total), false alarms per hour of telemetry, and lead time (how long before each event the warning came).
- The ML detector is compared with simple baseline rules on the same data and the same matching window, e.g. "alert if CPU temperature > 85 °C". Comparisons are made at a similar false-alarm rate, because any detector can catch more events by alerting more often.
- If a simple rule does as well as the ML detector, that is reported as the finding: the project measures whether ML adds value, not that it does.
- Crashes are rare, so event counts will be small. Results are reported as counts (e.g. "4 of 5"), not only as percentages, and are not generalised beyond this machine (section 2).
