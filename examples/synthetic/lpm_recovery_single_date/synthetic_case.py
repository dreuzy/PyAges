# -*- coding: utf-8 -*-
"""
Helpers for the synthetic single-date recovery example.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

import pyage.concentrations.concentrations as co
from pyage.convolution.convolution_tracers import ConvolutionTracers
from pyage.lpm.lpm_build import lpm_build


@dataclass(frozen=True)
class SyntheticCasePaths:
    example_dir: Path
    data_dir: Path
    params_path: Path
    settings_path: Path
    dataset_path: Path
    truth_path: Path
    true_concentration_path: Path


@dataclass
class GeneratedSyntheticCase:
    paths: SyntheticCasePaths
    settings: dict
    observed_frame: pd.DataFrame
    true_frame: pd.DataFrame
    truth_payload: dict


def case_paths() -> SyntheticCasePaths:
    """Return all fixed paths used by the example."""
    example_dir = Path(__file__).resolve().parent
    data_dir = example_dir / "data"
    settings_path = example_dir / "generation" / "generation_settings.yaml"
    params_path = example_dir / "lpm_recovery_single_date.yaml"
    dataset_path = data_dir / "synthetic_exp_shifted_2010.txt"
    truth_path = data_dir / "ground_truth.yaml"
    true_concentration_path = data_dir / "true_concentrations.txt"
    return SyntheticCasePaths(
        example_dir=example_dir,
        data_dir=data_dir,
        params_path=params_path,
        settings_path=settings_path,
        dataset_path=dataset_path,
        truth_path=truth_path,
        true_concentration_path=true_concentration_path,
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML structure in {path}")
    return data


def _dump_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)


def generate_synthetic_case(
    settings_path: Path | None = None,
) -> GeneratedSyntheticCase:
    """
    Generate the synthetic observations and the associated truth metadata.
    """
    paths = case_paths()
    settings = _load_yaml(settings_path or paths.settings_path)
    generation_cfg = settings.get("generation", {})
    dataset_cfg = settings.get("dataset", {})
    lpm_cfg = settings.get("lpm", {})
    example_cfg = settings.get("example", {})

    seed = int(generation_cfg.get("seed", 12345))
    add_noise = bool(generation_cfg.get("add_noise", True))
    relative_error = float(generation_cfg.get("relative_error", 0.04))
    date = float(generation_cfg.get("date", 2010.9))
    tracer_names = list(generation_cfg.get("tracers", ["cfc11", "cfc12", "cfc113", "sf6"]))
    lpm_name = str(lpm_cfg.get("model_name", "exp_shifted"))
    parameter_values = {
        str(name): float(value)
        for name, value in (lpm_cfg.get("parameters", {}) or {}).items()
    }
    if not parameter_values:
        raise ValueError("Synthetic example requires explicit lpm.parameters values.")

    lpm = lpm_build(lpm_name, directory_lpm=str(_repo_root() / "data_core" / "data_lpm"))
    for name, value in parameter_values.items():
        lpm.p[name] = value

    tracers = ConvolutionTracers(names=tracer_names, date=date)
    true_concentrations = tracers.convolve(
        lpm,
        return_type="concentrations",
    )
    true_frame = true_concentrations.cv.copy()
    observed_frame = true_frame.copy()
    observed_frame["error"] = relative_error * true_frame["concentration"]

    if add_noise:
        rng = np.random.default_rng(seed)
        noise = rng.normal(
            loc=0.0,
            scale=observed_frame["error"].to_numpy(dtype=float),
        )
        observed_frame["concentration"] = (
            true_frame["concentration"].to_numpy(dtype=float) + noise
        )
    else:
        observed_frame["concentration"] = true_frame["concentration"]

    paths.data_dir.mkdir(parents=True, exist_ok=True)
    observed_frame.to_csv(paths.dataset_path, sep="\t", index=False)
    true_frame.to_csv(paths.true_concentration_path, sep="\t", index=False)

    truth_payload = {
        "example": {
            "label": example_cfg.get("label", "Synthetic recovery example"),
            "description": example_cfg.get("description", ""),
        },
        "generation": {
            "seed": seed,
            "add_noise": add_noise,
            "relative_error": relative_error,
            "date": date,
            "tracers": tracer_names,
        },
        "dataset": {
            "file_name": dataset_cfg.get("file_name", paths.dataset_path.name),
            "truth_file": dataset_cfg.get("truth_file", paths.truth_path.name),
            "true_concentration_file": dataset_cfg.get(
                "true_concentration_file",
                paths.true_concentration_path.name,
            ),
        },
        "lpm": {
            "model_name": lpm_name,
            "parameters": parameter_values,
        },
        "true_concentrations": true_frame.to_dict(orient="records"),
        "observed_concentrations": observed_frame.to_dict(orient="records"),
    }
    _dump_yaml(paths.truth_path, truth_payload)

    return GeneratedSyntheticCase(
        paths=paths,
        settings=settings,
        observed_frame=observed_frame,
        true_frame=true_frame,
        truth_payload=truth_payload,
    )


def load_ground_truth(truth_path: Path | None = None) -> dict:
    """Load the stored ground-truth metadata."""
    paths = case_paths()
    return _load_yaml(truth_path or paths.truth_path)


def true_concentration_frame(truth_payload: dict | None = None) -> pd.DataFrame:
    """Return the true synthetic concentrations as a DataFrame."""
    truth = truth_payload or load_ground_truth()
    frame = pd.DataFrame(truth.get("true_concentrations", []))
    if frame.empty:
        raise ValueError("Ground-truth file does not contain true_concentrations.")
    return frame


def build_recovery_table(
    results_dir: Path,
    truth_payload: dict | None = None,
    method: str = "Metropolis_Hastings",
) -> pd.DataFrame:
    """Compare true parameters with the recovered posterior summary."""
    truth = truth_payload or load_ground_truth()
    stats_path = results_dir / method / "lpm_stats_calibrated.txt"
    stats = pd.read_csv(stats_path, sep="\t", index_col=0)
    rows = []
    for name, true_value in truth["lpm"]["parameters"].items():
        rows.append(
            {
                "parameter": name,
                "true_value": float(true_value),
                "estimated_mean": float(stats.loc["mean", name]),
                "estimated_std": float(stats.loc["std", name]),
                "difference": float(stats.loc["mean", name]) - float(true_value),
            }
        )
    recovery = pd.DataFrame(rows)
    recovery.to_csv(
        results_dir / "parameter_recovery_summary.txt",
        sep="\t",
        index=False,
    )
    return recovery


def build_truth_aware_figures(
    results_dir: Path,
    truth_payload: dict | None = None,
    dataset_path: Path | None = None,
    method: str = "Metropolis_Hastings",
) -> pd.DataFrame:
    """
    Rewrite the summary figures so the synthetic truth is shown explicitly.
    """
    truth = truth_payload or load_ground_truth()
    import matplotlib.pyplot as plt
    from scripts.common.example_summary_plots import (
        plot_objective_summary,
        plot_parameter_summary,
        plot_single_date_model_space,
    )

    paths = case_paths()
    observed_path = dataset_path or paths.dataset_path
    observed = co.Concentrations(file_load=True, file_name=str(observed_path))
    true_frame = true_concentration_frame(truth)
    posterior_frame = pd.read_csv(
        results_dir / method / "lpm_dist_calibrated.txt",
        sep="\t",
        index_col=0,
    )
    reachable_path = results_dir / "reachable_concentrations" / "c_reach.txt"
    reachable_frame = None
    if reachable_path.exists():
        reachable_frame = pd.read_csv(reachable_path, sep="\t", index_col=0)
    objective_path = results_dir / "objective_function_grid.txt"
    objective_frame = None
    if objective_path.exists():
        objective_frame = pd.read_csv(objective_path, sep="\t")

    results_by_method = {method: posterior_frame}
    reference_params = {
        str(name): float(value)
        for name, value in truth["lpm"]["parameters"].items()
    }
    case_label = truth.get("example", {}).get("label", "Synthetic recovery example")

    if reachable_frame is not None:
        fig = plot_single_date_model_space(
            observed,
            reachable_frame=reachable_frame,
            posterior_results=results_by_method,
            reference_concentrations=true_frame,
            reference_label="True synthetic model",
            filename=results_dir / "01_data_model_space.png",
            title=f"{case_label}: observations, prior reachable space and posterior samples",
        )
        plt.close(fig)

    fig = plot_parameter_summary(
        results_by_method,
        param_names=list(reference_params.keys()),
        reference_params=reference_params,
        reference_label="True parameters",
        filename=results_dir / "02_parameter_summary.png",
        title=f"{case_label}: posterior parameter recovery",
    )
    plt.close(fig)

    if objective_frame is not None:
        fig = plot_objective_summary(
            objective_frame=objective_frame,
            posterior_results=results_by_method,
            param_names=list(reference_params.keys()),
            reference_params=reference_params,
            reference_label="True parameters",
            filename=results_dir / "03_objective_summary.png",
            title=f"{case_label}: prior grid, posterior samples and true parameters",
        )
        plt.close(fig)

    return build_recovery_table(results_dir, truth, method=method)
