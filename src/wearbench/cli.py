"""Command-line interface for fs-wearbench."""

from __future__ import annotations
from .diff import print_diff
from .emulation import emulate
from .report import print_report
from . import __version__

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import click
import yaml

_WEST = Path(sys.executable).parent / "west"


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "backends" / "littlefs_host"


def _build_littlefs_host() -> Path:
    backend = _backend_dir()
    exe = backend / "wear_littlefs"
    if exe.exists():
        return exe
    click.echo(f"Building host LittleFS runner in {backend} ...")
    result = subprocess.run(
        ["make"],
        cwd=str(backend),
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("Failed to build wear_littlefs")
    return exe


def _run_littlefs_host(workload: dict, exe: Path) -> dict:
    flash = workload["flash"]
    w = workload["workload"]
    cmd = [
        str(exe),
        "--block-size", str(flash["block_size"]),
        "--block-count", str(flash["block_count"]),
        "--read-size", str(flash["read_size"]),
        "--prog-size", str(flash["prog_size"]),
        "--cache-size", str(flash["cache_size"]),
        "--lookahead-size", str(flash["lookahead_size"]),
        "--block-cycles", str(flash["block_cycles"]),
        "--record-size", str(w["record_size"]),
        "--record-count", str(w["record_count"]),
    ]
    result = subprocess.run(
        cmd,
        cwd=str(exe.parent),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        click.echo(result.stderr, err=True)
        raise RuntimeError(
            f"wear_littlefs failed with exit code {result.returncode}")
    return json.loads(result.stdout)


_ZEPHYR_BACKEND_NAMES = {
    "nvs": "NVS",
    "zms": "ZMS",
    "zephyr_littlefs": "LITTLEFS",
}


def _pristine_if_stale(build_dir: Path, app_dir: Path) -> None:
    cache = build_dir / "CMakeCache.txt"
    if not cache.exists():
        return
    expected = f"CMAKE_HOME_DIRECTORY:STATIC={app_dir}"
    text = cache.read_text(errors="replace")
    if expected not in text:
        shutil.rmtree(build_dir, ignore_errors=True)


def _zephyr_app_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "backends" / "zephyr_native"


def _build_zephyr(workload: dict, backend: str) -> Path:
    if backend not in _ZEPHYR_BACKEND_NAMES:
        raise click.ClickException(f"Unknown Zephyr backend: {backend!r}")
    app_dir = _zephyr_app_dir()
    w = workload["workload"]
    build_dir = app_dir / f"build_{backend}"
    record_size = w["record_size"]
    record_count = w["record_count"]
    cmake_backend = _ZEPHYR_BACKEND_NAMES[backend]

    _pristine_if_stale(build_dir, app_dir)

    click.echo(f"Building Zephyr {cmake_backend} runner in {build_dir} ...")
    build_cmd = [
        str(_WEST),
        "build",
        "-b",
        "native_sim",
        str(app_dir),
        "-d",
        str(build_dir),
        "-p",
        "auto",
        "--",
        f"-DWEAR_RECORD_SIZE={record_size}",
        f"-DWEAR_RECORD_COUNT={record_count}",
        f"-DWEAR_BACKEND={cmake_backend}",
    ]
    result = subprocess.run(
        build_cmd,
        cwd=str(app_dir.parents[2]),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        click.echo(result.stdout, err=True)
        raise RuntimeError(f"west build for {backend} failed")
    exe = build_dir / "zephyr" / "zephyr.exe"
    if not exe.exists():
        raise RuntimeError(f"No binary at {exe}")
    return exe


def _run_zephyr(workload: dict, backend: str) -> dict:
    exe = _build_zephyr(workload, backend)
    click.echo(f"Running {exe} ...")
    result = subprocess.run(
        [str(exe), "--flash_in_ram"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if result.returncode != 0:
        click.echo(result.stdout, err=True)
        raise RuntimeError(f"{exe} failed with exit code {result.returncode}")

    start = result.stdout.find("{")
    end = result.stdout.rfind("}")
    if start == -1 or end == -1:
        click.echo(result.stdout, err=True)
        raise RuntimeError("No JSON output from native runner")
    return json.loads(result.stdout[start:end + 1])


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Flash wear-leveling and endurance estimator."""


@main.command()
@click.argument("workload", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--mode", "mode", type=click.Choice(["real", "emulated"], case_sensitive=False),
              default=None, help="Use real measurement or fast Python emulation (default: emulated).")
def run(workload: Path, output: Path | None, mode: str | None) -> None:
    """Run a workload and emit a JSON report."""
    with workload.open() as f:
        doc = yaml.safe_load(f)

    mode = (mode or doc.get("mode") or "emulated").lower()
    backend = doc.get("backend")

    if mode == "emulated":
        report = emulate(doc)
    elif mode == "real":
        if backend == "littlefs_host":
            exe = _build_littlefs_host()
            report = _run_littlefs_host(doc, exe)
        elif backend in ("nvs", "zms", "zephyr_littlefs"):
            report = _run_zephyr(doc, backend)
        else:
            raise click.ClickException(f"Unsupported backend: {backend!r}")
    else:
        raise click.ClickException(f"Unsupported mode: {mode!r}")

    report["mode"] = mode
    report["workload"] = doc.get("workload", {})
    report["endurance"] = doc.get("endurance", {})

    payload = json.dumps(report, indent=2)
    if output:
        output.write_text(payload)
    else:
        click.echo(payload)


@main.command()
@click.argument("report", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.File("w"), default="-")
def show_report(report: Path, output) -> None:
    """Render a JSON report as a human-readable table."""
    with report.open() as f:
        data = json.load(f)
    print_report(data, file=output)


@main.command("diff")
@click.argument("baseline", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("new", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-t", "--threshold", default=5.0, type=float,
              help="Percent change that counts as a regression.")
@click.pass_context
def diff_command(ctx, baseline: Path, new: Path, threshold: float) -> None:
    """Compare two JSON reports and fail if amplification regresses."""
    with baseline.open() as f:
        a = json.load(f)
    with new.open() as f:
        b = json.load(f)
    rc = print_diff(a, b, threshold=threshold)
    ctx.exit(rc)
