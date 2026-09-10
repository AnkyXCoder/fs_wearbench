"""Fast Python-side emulation for the fs-wearbench workloads.

This is *not* a measurement: it is a deterministic approximation used when
``mode: emulated`` is selected. The numbers are rough and should only be used
for a quick sanity check. Use ``mode: real`` (the default) for a real
measurement.
"""

from __future__ import annotations

import math


def _align(n: int, a: int) -> int:
    return ((n + a - 1) // a) * a


def _emulate_littlefs(record_size: int, record_count: int, block_size: int,
                      block_count: int, prog_size: int) -> dict:
    meta = 16  # metadata overhead per record
    per_record = _align(record_size + meta, prog_size)
    proged = record_count * per_record
    erased = _align(proged, block_size)
    readed = proged + block_size  # mount/format reads
    touched = min(block_count, erased // block_size)
    wear = [
        {"block": i, "cycles": 1}
        for i in range(touched)
    ]
    return {
        "user_bytes": record_count * record_size,
        "proged_bytes": proged,
        "erased_bytes": erased,
        "readed_bytes": readed,
        "per_block_wear": wear,
    }


def _emulate_nvs(record_size: int, record_count: int, block_size: int,
                 block_count: int, prog_size: int) -> dict:
    meta = 16  # NVS ATE + data
    per_record = _align(record_size + meta, 16)
    proged = record_count * per_record
    erased = _align(proged, block_size)
    readed = int(proged * 1.5)
    touched = min(block_count, erased // block_size)
    wear = [
        {"block": i, "cycles": 1}
        for i in range(touched)
    ]
    return {
        "user_bytes": record_count * record_size,
        "proged_bytes": proged,
        "erased_bytes": erased,
        "readed_bytes": readed,
        "per_block_wear": wear,
    }


def _emulate_zms(record_size: int, record_count: int, block_size: int,
                 block_count: int, prog_size: int) -> dict:
    meta = 32  # ZMS entry + padding
    per_record = _align(record_size + meta, 16)
    proged = record_count * per_record
    erased = _align(proged, block_size)
    readed = int(proged * 1.2)
    touched = min(block_count, erased // block_size)
    wear = [
        {"block": i, "cycles": 1}
        for i in range(touched)
    ]
    return {
        "user_bytes": record_count * record_size,
        "proged_bytes": proged,
        "erased_bytes": erased,
        "readed_bytes": readed,
        "per_block_wear": wear,
    }


def emulate(workload: dict) -> dict:
    backend = workload.get("backend")
    w = workload.get("workload", {})
    flash = workload.get("flash", {})

    record_size = int(w.get("record_size", 0))
    record_count = int(w.get("record_count", 0))
    block_size = int(flash.get("block_size", 4096))
    block_count = int(flash.get("block_count", 64))
    prog_size = int(flash.get("prog_size", 16))

    if backend in ("littlefs_host", "zephyr_littlefs"):
        full = _emulate_littlefs(record_size, record_count, block_size,
                                 block_count, prog_size)
    elif backend == "nvs":
        full = _emulate_nvs(record_size, record_count, block_size,
                            block_count, prog_size)
    elif backend == "zms":
        full = _emulate_zms(record_size, record_count, block_size,
                            block_count, prog_size)
    else:
        raise ValueError(f"No emulation model for backend {backend!r}")

    metrics = {k: v for k, v in full.items() if k != "per_block_wear"}

    config = {
        "record_size": record_size,
        "record_count": record_count,
        "block_size": block_size,
        "block_count": block_count,
    }
    if backend in ("littlefs_host", "zephyr_littlefs"):
        config["cache_size"] = int(flash.get("cache_size", 64))
        config["block_cycles"] = int(flash.get("block_cycles", 0))
        config["read_size"] = int(flash.get("read_size", 16))
        config["prog_size"] = prog_size
        config["lookahead_size"] = int(flash.get("lookahead_size", 16))

    return {
        "backend": backend,
        "mode": "emulated",
        "config": config,
        "metrics": metrics,
        "per_block_wear": full["per_block_wear"],
        "workload": workload.get("workload", {}),
        "endurance": workload.get("endurance", {}),
    }
