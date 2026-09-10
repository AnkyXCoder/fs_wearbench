# fs-wearbench

A measurement-first flash wear-leveling and endurance estimator for LittleFS,
Zephyr NVS and Zephyr ZMS.

Instead of hand-rolling a mathematical model, `fs-wearbench` compiles and runs the
real storage code on a host simulator, records per-block/per-sector erase cycles,
and reports write amplification and estimated years-in-field. It is meant for
desk-checking customer workloads and for CI regression checks.

## Why not a spreadsheet?

- **LittleFS** already has `lfs_emubd` and web simulators, but they are not a
  CLI or CI tool.
- **Zephyr ZMS** already has interactive doc calculators, but they are
  formula-based and not tied to real code execution.
- **Zephyr NVS** already has a lifetime formula in the docs.

`fs-wearbench` is the missing measurement/orchestration layer: it drives the real
backends with a declarative workload, reports normalised results, and supports
`diff` for CI.

## Install

```bash
pip install -e .
```

## Run a workload

Workloads are YAML files with `backend`, `workload` and `endurance` sections.

```yaml
backend: littlefs_host
flash:
  block_size: 4096
  block_count: 256
  read_size: 16
  prog_size: 16
  cache_size: 64
  lookahead_size: 16
  block_cycles: 512
workload:
  name: "128-byte sensor record every 10 seconds"
  record_size: 128
  record_count: 1000
  record_interval_ms: 10000
endurance:
  p_e_cycles: 100000
  temperature_c: 25
```

Run it and produce JSON:

```bash
fs-wearbench run examples/sensor_log_littlefs.yaml -o report.json
```

Render the report:

```bash
fs-wearbench show-report report.json
```

## Compare two runs

```bash
fs-wearbench run examples/sensor_log_littlefs.yaml -o baseline.json
# ... make a change ...
fs-wearbench run examples/sensor_log_littlefs.yaml -o changed.json
fs-wearbench diff baseline.json changed.json
```

## Supported backends

| Backend           | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| `littlefs_host`   | Host `lfs_emubd` runner; fastest and exact per-block wear.        |
| `nvs`             | Zephyr `native_sim` app using the flash simulator and `nvs_` API. |
| `zms`             | Zephyr `native_sim` app using the flash simulator and `zms_` API. |
| `zephyr_littlefs` | Zephyr `native_sim` app using `fs/fs.h` and `FS_LITTLEFS`.        |

## Repository layout

```
fs-wearbench/
├── backends/
│   ├── littlefs_host/    # Host emubd runner
│   └── zephyr_native/    # Zephyr native_sim app
├── examples/             # Sample workloads
├── src/wearbench/        # Python CLI
├── PLAN.md               # Original development plan
└── README.md
```

## Temperature derating

`fs-wearbench` applies a conservative rule of thumb: effective P/E cycles halve
for every 10 °C above 25 °C. This is a deliberately simple model; the report
always prints the temperature assumption so users can sanity-check the number.

## Web configurator

A static HTML configurator lives in `docs/index.html`. It can be hosted on
GitHub Pages by pointing the Pages source to the `docs` folder on the main
branch. Use the form to select a backend, tune the workload, and download a
ready-to-run YAML file. It also shows a rough estimated build + run time
based on the selected backend and record count.

## License

Apache-2.0
