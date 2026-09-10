# Changelog

All notable changes to `fs-wearbench` are documented in this file.

## [0.1.0] - WIP

### Added

- Host LittleFS runner using `lfs_emubd` for exact per-block wear counts.
- `fs-wearbench run` to execute a declarative YAML workload and emit a JSON
  report.
- `fs-wearbench show-report` to render a JSON report as a human-readable table.
- `fs-wearbench diff` to compare two JSON reports and exit non-zero on regression.
- Zephyr `native_sim` backend for NVS, with flash-simulator callbacks for
  per-sector erase tracking.
- Zephyr `native_sim` backend for ZMS.
- Zephyr `native_sim` backend for LittleFS via `fs/fs.h` and `FS_LITTLEFS`.
- Conservative temperature derating for lifetime estimates (halves every 10 °C
  above 25 °C).
- Example workloads for littlefs_host, NVS, ZMS and Zephyr LittleFS.
- `pyproject.toml` and editable pip install support.
- Static `docs/index.html` web configurator for GitHub Pages.
- Rough build + run time estimate in the web configurator.
- `mode: emulated` / `--mode emulated` for fast Python-side approximation (default is now emulated).
