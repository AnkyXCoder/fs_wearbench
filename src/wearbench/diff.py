"""Compare two JSON reports and flag regressions."""

from __future__ import annotations

import sys


def _max_wear(data: dict) -> int:
    return max((b["cycles"] for b in data.get("per_block_wear", [])), default=0)


def _amp(data: dict, key: str) -> float:
    user = data.get("metrics", {}).get("user_bytes", 0)
    flash = data.get("metrics", {}).get(key, 0)
    return flash / user if user else 0.0


def _pct(old: float, new: float) -> float:
    if old == 0:
        return 0.0 if new == 0 else float("inf")
    return ((new - old) / old) * 100


def print_diff(a: dict, b: dict, threshold: float = 5.0, file=None) -> int:
    metrics = [
        ("Write amplification", _amp(a, "proged_bytes"), _amp(b, "proged_bytes")),
        ("Erase amplification", _amp(a, "erased_bytes"), _amp(b, "erased_bytes")),
        ("Max block wear", _max_wear(a), _max_wear(b)),
    ]

    print("Wearbench Diff", file=file)
    print("=" * 70, file=file)
    print(f"{'Metric':<26} {'Baseline':>14} {'New':>14} {'Change %':>12}", file=file)
    print("-" * 70, file=file)

    over = 0
    for name, av, bv in metrics:
        change = _pct(av, bv)
        mark = ""
        if change != float("inf") and abs(change) > threshold:
            mark = " <-- REGRESSION"
            over += 1
        elif change == float("inf"):
            mark = " <-- NEW VALUE"
        print(
            f"{name:<26} {av:>14.3f} {bv:>14.3f} {change:>11.2f}%"
            f"{mark}",
            file=file,
        )

    raw_metrics = [
        ("Proged bytes", "proged_bytes"),
        ("Erased bytes", "erased_bytes"),
        ("Readed bytes", "readed_bytes"),
    ]
    for name, key in raw_metrics:
        av = a.get("metrics", {}).get(key, 0)
        bv = b.get("metrics", {}).get(key, 0)
        change = _pct(av, bv)
        mark = ""
        if change != float("inf") and abs(change) > threshold:
            mark = " <-- REGRESSION"
            over += 1
        elif change == float("inf"):
            mark = " <-- NEW VALUE"
        print(
            f"{name:<26} {av:>14,} {bv:>14,} {change:>11.2f}%"
            f"{mark}",
            file=file,
        )

    print("=" * 70, file=file)
    if over:
        print(f"FAIL: {over} metric(s) changed by more than {threshold}%", file=file)
        return 1
    print(f"PASS: all changes within {threshold}%", file=file)
    return 0
