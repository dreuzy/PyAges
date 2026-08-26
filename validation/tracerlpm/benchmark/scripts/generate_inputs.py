"""Generate deterministic monthly input histories and a SHA-256 manifest."""

from __future__ import annotations

import csv
import hashlib
import os
import platform
from pathlib import Path

import numpy as np
import yaml

BENCHMARK_ROOT = Path(
    os.environ.get(
        "PYAGE_TRACERLPM_BENCHMARK_ROOT", Path(__file__).resolve().parents[1]
    )
).resolve()
SOURCE_REPOSITORY_ROOT = Path(
    os.environ.get(
        "PYAGE_TRACERLPM_SOURCE_ROOT", Path(__file__).resolve().parents[4]
    )
).resolve()
DEFAULT_CONFIG = BENCHMARK_ROOT / "configs" / "campaign.yaml"
DEFAULT_OUTPUT = BENCHMARK_ROOT / "inputs" / "synthetic"
DEFAULT_MANIFEST = BENCHMARK_ROOT / "inputs" / "manifest.yaml"


def decimal_years(start_year: int, end_year: int) -> np.ndarray:
    """Return mid-month decimal years for an inclusive range of years."""
    return np.array(
        [
            year + (month - 0.5) / 12
            for year in range(start_year, end_year + 1)
            for month in range(1, 13)
        ],
        dtype=float,
    )


def build_series(config: dict) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    grid = config["time_grid"]
    if (
        grid["frequency"] != "monthly"
        or grid["timestamp_convention"] != "middle_of_month"
    ):
        raise ValueError("Phase 1 requires a monthly, middle_of_month time grid")
    years = decimal_years(int(grid["start_year"]), int(grid["end_year"]))
    specs = config["synthetic_inputs"]

    constant = np.full_like(years, float(specs["constant"]["value"]))
    ramp_spec = specs["ramp"]
    ramp = np.linspace(
        float(ramp_spec["start_value"]), float(ramp_spec["end_value"]), years.size
    )
    step_spec = specs["step"]
    step = np.where(
        years < float(step_spec["transition_year"]),
        float(step_spec["low_value"]),
        float(step_spec["high_value"]),
    )
    pulse_spec = specs["rectangular_pulse"]
    pulse = np.full_like(years, float(pulse_spec["baseline"]))
    inside = (years >= float(pulse_spec["start_year"])) & (
        years < float(pulse_spec["end_year"])
    )
    pulse[inside] += float(pulse_spec["amplitude"])
    peak_spec = specs["multi_peak"]
    multi_peak = np.full_like(years, float(peak_spec["baseline"]))
    for peak in peak_spec["peaks"]:
        center = float(peak["center_year"])
        width = float(peak["width_years"])
        amplitude = float(peak["amplitude"])
        if width <= 0:
            raise ValueError("multi_peak widths must be positive")
        multi_peak += amplitude * np.exp(-0.5 * ((years - center) / width) ** 2)
    return years, {
        "constant": constant,
        "ramp": ramp,
        "step": step,
        "rectangular_pulse": pulse,
        "multi_peak": multi_peak,
    }


def _write_csv(path: Path, years: np.ndarray, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["date", "concentration"])
        for year, value in zip(years, values, strict=False):
            writer.writerow([f"{year:.12f}", f"{value:.12f}"])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _manifest_path(path: Path, output_dir: Path) -> str:
    """Use benchmark-relative paths in production and portable paths in tests."""
    try:
        return path.relative_to(BENCHMARK_ROOT).as_posix()
    except ValueError:
        return (Path(output_dir.name) / path.name).as_posix()


def generate(
    config_path: Path = DEFAULT_CONFIG,
    output_dir: Path = DEFAULT_OUTPUT,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict:
    config_bytes = config_path.read_bytes()
    config = yaml.safe_load(config_bytes)
    years, series = build_series(config)
    files = []
    for name, values in series.items():
        path = output_dir / f"{name}.csv"
        _write_csv(path, years, values)
        files.append(
            {
                "name": name,
                "path": _manifest_path(path, output_dir),
                "rows": int(years.size),
                "sha256": _sha256(path),
            }
        )
    manifest = {
        "campaign_id": config["campaign_id"],
        "generator": "validation.tracerlpm.benchmark.scripts.generate_inputs",
        "campaign_config_sha256": hashlib.sha256(config_bytes).hexdigest().upper(),
        "time_unit": config["time_unit"],
        "concentration_unit": config["concentration_unit"],
        "timestamp_convention": config["time_grid"]["timestamp_convention"],
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pyyaml": yaml.__version__,
        },
        "files": files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8", newline="\n"
    )
    return manifest


if __name__ == "__main__":
    generated = generate()
    print(yaml.safe_dump(generated, sort_keys=False), end="")
