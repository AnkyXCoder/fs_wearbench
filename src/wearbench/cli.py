"""Command-line interface for wearbench."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click
import yaml

from . import __version__
from .report import print_report


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


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Flash wear-leveling and endurance estimator."""


@main.command()
@click.argument("workload", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path))
def run(workload: Path, output: Path | None) -> None:
    """Run a workload and emit a JSON report."""
    with workload.open() as f:
        doc = yaml.safe_load(f)

    backend = doc.get("backend")
    if backend == "littlefs_host":
        exe = _build_littlefs_host()
        report = _run_littlefs_host(doc, exe)
    else:
        raise click.ClickException(f"Unsupported backend: {backend!r}")

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
