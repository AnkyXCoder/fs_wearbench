"""Human-readable report rendering from a JSON measurement."""

from __future__ import annotations

SECONDS_PER_YEAR = 365.25 * 24 * 60 * 60


def _safe_div(a: float, b: float) -> float:
    return a / b if b else float("inf")


def _derate_for_temperature(p_e_cycles: int, temperature_c: float) -> int:
    """Conservative rule of thumb: endurance halves every 10 C above 25 C."""
    if temperature_c <= 25:
        return p_e_cycles
    return max(1, int(p_e_cycles * (0.5 ** ((temperature_c - 25) / 10.0))))


def print_report(data: dict, file=None) -> None:
    config = data.get("config", {})
    metrics = data.get("metrics", {})
    wear = data.get("per_block_wear", [])
    workload = data.get("workload", {})
    endurance = data.get("endurance", {})

    user_bytes = metrics.get("user_bytes", 0)
    proged = metrics.get("proged_bytes", 0)
    erased = metrics.get("erased_bytes", 0)
    write_amp = _safe_div(proged, user_bytes)
    erase_amp = _safe_div(erased, user_bytes)

    max_wear = max((b["cycles"] for b in wear), default=0)
    hottest = sorted(wear, key=lambda b: b["cycles"], reverse=True)[:5]

    p_e_cycles = endurance.get("p_e_cycles", 0)
    temperature_c = endurance.get("temperature_c", 25)
    record_count = config.get("record_count", 0)
    record_interval_ms = workload.get("record_interval_ms", 0)

    # Runtime simulated by this workload, in years
    run_time_years = (record_count * record_interval_ms) / \
        (1000 * SECONDS_PER_YEAR)
    effective_cycles = _derate_for_temperature(p_e_cycles, temperature_c)
    years_to_failure = (
        _safe_div(effective_cycles, max_wear) * run_time_years
        if max_wear and effective_cycles else float("inf")
    )

    print("Flash Wear Report", file=file)
    print("=" * 60, file=file)
    print(f"Backend:          {data.get('backend', 'unknown')}", file=file)
    print(f"Block size:       {config.get('block_size', 0)} bytes", file=file)
    print(f"Block count:      {config.get('block_count', 0)}", file=file)
    if config.get('cache_size'):
        print(f"Cache size:       {config['cache_size']} bytes", file=file)
    if config.get('block_cycles'):
        print(f"LittleFS block_cycles: {config['block_cycles']}", file=file)
    print(file=file)
    print("Metrics", file=file)
    print("-" * 60, file=file)
    print(f"User data written:     {user_bytes:,} bytes", file=file)
    print(
        f"Flash bytes read:      {metrics.get('readed_bytes', 0):,}", file=file)
    print(f"Flash bytes programed: {proged:,}", file=file)
    print(f"Flash bytes erased:    {erased:,}", file=file)
    print(f"Write amplification:   {write_amp:.2f}x", file=file)
    print(f"Erase amplification:   {erase_amp:.2f}x", file=file)
    print(file=file)
    print("Wear", file=file)
    print("-" * 60, file=file)
    print(f"Max erase cycles on any block: {max_wear}", file=file)
    print("Hottest blocks:", file=file)
    for b in hottest:
        print(f"  block {b['block']:>4}: {b['cycles']} cycles", file=file)
    print(file=file)
    print("Endurance", file=file)
    print("-" * 60, file=file)
    print(f"Datasheet P/E cycles: {p_e_cycles:,}", file=file)
    print(f"Effective P/E cycles: {effective_cycles:,}", file=file)
    print(
        f"Temperature:          {temperature_c} C", file=file)
    print(
        f"Simulated runtime:    {run_time_years * 365.25 * 24:,.2f} hours", file=file)
    if years_to_failure == float("inf"):
        print(f"Estimated lifetime:   no measurable wear", file=file)
    else:
        print(f"Estimated lifetime:   {years_to_failure:.2f} years", file=file)
