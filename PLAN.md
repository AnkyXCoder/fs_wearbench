---
agent: devin-local
session: raspy-bottom
created: 2026-09-10T15:35:58Z
---
# Flash Wear Bench — Automated Wear-Leveling & Endurance Estimator

Build a Python CLI (`wearbench`) that drives real storage implementations (LittleFS via `lfs_emubd`, Zephyr NVS/ZMS via `native_sim`/flash-simulator) with declarative workloads, measures per-block erase cycles and write amplification, and produces an endurance report with years-in-field, hotspot sectors, and tuning recommendations; start as a standalone GitHub repo and propose upstream once mature.

## 1. Prior-art check (brutally honest)

### What already exists

| Source | What it does | Why it is not the product we want |
|---|---|---|
| [LittleFS online demo](http://littlefs.geky.net/demo.html) | Visual JavaScript simulator of LittleFS wear | Still on LittleFS v1 (outdated); not v2 dynamic wear-leveling; browser-only, no CLI, no years-in-field or datasheet mapping. |
| LittleFS `lfs_emubd` (`bd/lfs_emubd.h` / `bd/lfs_emubd.c`) | Emulated block device with per-block wear tracking, bad-block and power-loss simulation | It is an internal test/building block, not a user-facing CLI or CI tool. |
| LittleFS `tests/test_exhaustion.toml` and `runners/bench_runner.c` | Run-to-exhaustion and benchmark harnesses for LittleFS | Developer test infrastructure, not a declarative workload tool, not tied to real customer workloads, and no endurance report. |
| [littlefs-benchmarks](https://github.com/littlefs-project/littlefs-benchmarks) | CSV-based LittleFS benchmarks across v1/v2/v3, NOR/NAND/eMMC geometries, with plots | LittleFS-only; no Zephyr NVS/ZMS; no declarative workload DSL; no hotspot/years/CI regression output. |
| [2ck/flash-playground](https://github.com/2ck/flash-playground) | Academic C++ NOR flash FS simulator (LittleFS/SPIFFS/NF2FS/YAFFS2) | Zero maintenance/adoption; not Zephyr; no NVS/ZMS; no CI-friendly report. |
| Zephyr NVS docs | [Hand-written lifetime formula](https://docs.zephyrproject.org/latest/services/storage/nvs/nvs.html) | Formula only; no simulator, no tool, no per-sector hotspots. |
| Zephyr ZMS docs | [Interactive HTML calculators](https://docs.zephyrproject.org/latest/services/storage/zms/zms.html) for available space and device lifetime | Doc-only; formula-based; no CLI, no CI, no real code execution, no LittleFS/NVS, no regression diff. |
| Zephyr flash simulator (`drivers/flash/flash_simulator.c`) | RAM-based flash with per-page erase stats, callbacks, and timing | Used in tests only; stats limited to the first `FLASH_SIMULATOR_STAT_PAGE_COUNT` pages unless you use callbacks. |

### Conclusion on the gap

The *modeling* side of the idea is largely solved: LittleFS has `lfs_emubd`/bench-runners, and Zephyr ZMS even ships interactive lifetime calculators. The remaining, defensible gap is a **measurement-first, CI-friendly CLI** that:

1. Runs the **real** LittleFS/NVS/ZMS code on a declarative customer workload.
2. Collects **per-block / per-sector** erase counts and write amplification.
3. Maps those counts onto real **datasheet P/E cycles** and workload rates to report **years-in-field**.
4. Identifies **hotspot sectors**, recommends cache/partition settings, and supports **regression checks** in CI.

That gap is real and worth building. A pure hand-rolled model would be wrong and would duplicate the existing calculators.

## 2. Reframed product

**`wearbench`** — a flash endurance profiler for Zephyr-flavored embedded storage.

Core principle: *measure first, model second*. We do not re-implement LittleFS/NVS/ZMS behavior in a spreadsheet; we compile and execute the real libraries on a host simulator and report what they actually did.

### v1 scope (in scope)

- Declarative workload description in YAML: flash geometry, FS type, FS parameters, and a sequence of operations (key-value writes, file writes/rewrites, mixed sizes, periodic "reboots").
- Two measurement runners:
  1. **Host LittleFS runner** using `lfs_emubd` for fast, exact per-block wear counts.
  2. **Zephyr `native_sim` runner** for NVS and ZMS (and optionally Zephyr's `FS_LITTLEFS` layer) using the flash simulator with custom callbacks for per-sector erase tracking.
- CLI commands:
  - `wearbench run workload.yaml` → JSON report.
  - `wearbench report report.json` → human-readable Markdown/terminal table.
  - `wearbench diff baseline.json new.json` → amplification/lifetime delta, non-zero exit for CI thresholds.
- Report contents:
  - total read / program / erase bytes
  - write and erase amplification factors
  - per-block/per-sector erase cycle histogram and hotspot list
  - estimated years-to-wear-out under the configured workload rate and P/E cycles
  - simple tuning recommendations (partition size, sector count, cache size, `block_cycles`)
- No hardware required: everything runs on `lfs_emubd` or `native_sim`.

### Explicit non-goals

- Not a hand-rolled mathematical model of LittleFS/NVS/ZMS.
- Not a GUI in v1 (JSON / Markdown / terminal only).
- Not a generic SPIFFS/YAFFS/FAT benchmarking tool in v1.
- Not a replacement for the ZMS doc calculators for quick desk checks.
- Not a hardware probe or flash-programmer tool.

## 3. Language and architecture

**Language: Python 3.11+** for the CLI.

- Zephyr's own tooling (`west`, `twister`, build scripts) is Python.
- YAML/JSON parsing, `cmake`/West orchestration, CI integration, and report generation are natural in Python.
- Contributors can `pip install wearbench`; no Rust toolchain required to use the tool.

**Measurement runners: C**, built from real upstream sources.

- `backends/littlefs_host/`: compiles `lfs.c`, `lfs_emubd.c`, and a small `main.c` from the LittleFS module into a host binary. It consumes an embedded workload table and emits JSON.
- `backends/zephyr_native/app/`: a Zephyr `native_sim` sample app. CMake generates `workload.c` from the YAML; the app uses `flash_simulator_set_callbacks` to count every erase per sector. Backend is selected by Kconfig: `WEAR_BENCH_BACKEND_LITTLEFS`, `WEAR_BENCH_BACKEND_NVS`, or `WEAR_BENCH_BACKEND_ZMS`.

**Packaging:** standalone GitHub repo with `pyproject.toml` and GitHub Actions CI. The Python CLI can optionally register as a `west` extension later (`west wear run ...`).

**Why not pure Rust?** Rust would be a fine CLI language, but it adds friction for Zephyr contributors and for calling `cmake`/West. The performance-critical wear simulation is already in C; Python is the right glue.

## 4. Milestones (each demoable)

| # | Milestone | Exit criterion |
|---|---|---|
| M1 | Host LittleFS harness | `./wearbench run examples/sensor_log_littlefs.yaml` builds the `lfs_emubd` runner and emits a JSON report with per-block wear and read/prog/erase bytes. |
| M2 | Python CLI + report | `wearbench report` prints a Markdown table: years-to-failure, write amplification, hottest blocks, and a simple tuning hint. |
| M3 | Zephyr `native_sim` NVS backend | `wearbench run examples/sensor_log_nvs.yaml` builds a `native_sim` app, runs it, and emits the same JSON schema as the host runner. |
| M4 | ZMS and Zephyr LittleFS backends | `wearbench run` works for `backend: zms` and `backend: zephyr_littlefs`; a matrix command compares all three on one workload. |
| M5 | CI regression (`wearbench diff`) | `wearbench diff baseline.json pr.json` flags >5% write/erase amplification increase and exits non-zero; GitHub Actions job demonstrates it. |
| M6 | Datasheet/temperature model and sweep | Add optional temperature derating, P/E cycle config, and a `wearbench sweep --param sector_count` command that recommends a config for a target lifetime. |
| M7 | Packaging and upstream proposal | `pip install wearbench`; draft a `samples/storage/wear_bench` PR to Zephyr; optional `west` extension registered. |

If schedule slips, **M1–M4 is the public v1.0**; M5–M7 are v1.x.

## 5. Testing and validation strategy

- **Real artifacts only:** tests build `native_sim` with `CONFIG_FLASH_SIMULATOR=y`, `CONFIG_FLASH_SIMULATOR_CALLBACKS=y`, `CONFIG_FLASH_SIMULATOR_STATS=y`, and run the bundled workloads.
- **Expected-output fixtures:** store `expected_report.json` per bundled workload; CI diffs the actual report.
- **Cross-checks:**
  - Host LittleFS runner counts vs. `littlefs-benchmarks` for identical geometry.
  - NVS/ZMS wear results compared to the documented formulas, within a stated tolerance (e.g., ±10%) to catch implementation drift.
- **Synthetic regression workloads:** same-ID repeated writes, many-IDs write bursts, and file rewrites to exercise GC amplification.
- **No hardware required:** all validation runs in QEMU/`native_sim` or host `lfs_emubd`.

## 6. Upstream-contribution strategy

- Start as a standalone repo so the CLI can support multiple Zephyr versions and iterate without blocking on upstream review.
- The `backends/zephyr_native/app` is intentionally shaped like a Zephyr sample; once stable, propose it as `samples/storage/wear_bench`.
- The Python package can later be exposed as a `west` extension (`west-commands` entry point) or as `scripts/utils/flash_wear_estimate.py` in Zephyr.
- Any small upstream improvements discovered (e.g., exposing per-sector cycle counts from ZMS, making flash-simulator stat tracking more scalable) should be filed as separate PRs rather than bundled.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| `lfs_emubd` is test-only and not exposed through Zephyr's `FS_LITTLEFS` layer | Provide two backends; document that the host emubd runner gives exact per-block wear, while the Zephyr FS runner uses the flash simulator. |
| Big flash sizes in `lfs_emubd` use a lot of host RAM | Default to small, representative geometries and extrapolate; support `scale_factor` in the workload. |
| YAML → C workload generation slows iteration | Cache build directories; reuse runner binaries when only workload data changes; support fast host backend for daily use. |
| NVS/ZMS and file-system semantics differ (kv vs paths) | Backend-specific YAML schema; common JSON report schema hides the differences. |
| Flash simulator per-page stats are capped at 256 pages | Use `flash_simulator_set_callbacks` to count all erase cycles ourselves. |
| Temperature/retention model is a simplification | Expose all assumptions; never claim exact field lifetime; use conservative derating factors. |
| Upstream may prefer a doc calculator over a CLI | Start standalone; demonstrate CI value before proposing upstream. |

## 8. Open decisions for you

1. **v1 backend ordering.** Recommendation: M1 host LittleFS for a fast demo, then M2–M4 `native_sim` for NVS/ZMS. If you want all three in the first binary, M1 can be skipped in favor of a `native_sim` LittleFS backend.
2. **CLI language.** Recommendation: Python 3.11+. If you strongly prefer Rust for the CLI, we can keep the C runners and write a Rust driver, but it will be slower to integrate with `west`/CMake.
3. **Output artifacts in v1.** JSON + Markdown/terminal. HTML or web dashboard as v2.
4. **Packaging path.** Standalone `pip install wearbench` first, then a `west` extension and upstream sample.

## 9. References

- LittleFS emubd API (per-block wear): <ref_file file="/home/ankit/Workspaces/fwProjects/iNode/os/modules/fs/littlefs/bd/lfs_emubd.h" />
- Zephyr flash simulator stats/callbacks: <ref_file file="/home/ankit/Workspaces/fwProjects/iNode/os/zephyr/drivers/flash/flash_simulator.c" />
- Zephyr flash simulator Kconfig: <ref_file file="/home/ankit/Workspaces/fwProjects/iNode/os/zephyr/drivers/flash/Kconfig.simulator" />
- Zephyr NVS lifetime docs: https://docs.zephyrproject.org/latest/services/storage/nvs/nvs.html
- Zephyr ZMS interactive calculators: https://docs.zephyrproject.org/latest/services/storage/zms/zms.html
- littlefs-benchmarks: https://github.com/littlefs-project/littlefs-benchmarks
- 2ck/flash-playground: https://github.com/2ck/flash-playground
- LittleFS test exhaustion: https://github.com/littlefs-project/littlefs/blob/master/tests/test_exhaustion.toml
