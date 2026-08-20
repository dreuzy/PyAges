"""Reproducible non-Ploemeur article qualification and regeneration.

The launcher deliberately writes only below ``results/article_non_ploemeur_final``.
It provides independently runnable phases so a long campaign can be resumed
without silently mixing numerical settings or code snapshots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
import time
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np
import numpy.typing as npt
import pandas as pd
import scipy
import yaml
from numpy.polynomial.legendre import leggauss
from scipy import integrate, stats

from pyage.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyage.calibration.problem import CalibrationProblem
from pyage.config.paths import DIRECTORY_LPM_DATA, DIRECTORY_TRACER_DATA
from pyage.config.runtime import DisplayOptions
from pyage.convolution.convolution import Convolution
from pyage.convolution.convolution_tracers import ConvolutionTracers
from pyage.convolution.settings import DEFAULT_TRACER_GRID_SETTINGS, TracerGridSettings
from pyage.lpm.lpm_build import lpm_build
from pyage.tracer.tracer_protocol import ConstantTracer, SyntheticTracer
from pyage.tracer.tracer_root import Tracer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "results" / "article_non_ploemeur_final"
TRACERS = ("cfc11", "cfc12", "cfc113", "sf6", "3H", "39Ar", "kr85")
TABLE3_TRACERS = ("cfc11", "cfc12", "cfc113", "sf6")
DATE = 2010.0
TABLE3_PAIRS = tuple(
    (1.0 if mu == 0 else float(mu), 1.0 if shift == 0 else float(shift))
    for mu in range(0, 50, 10)
    for shift in range(0, 50, 10)
    if mu + shift <= 50
)


def _markdown(frame: pd.DataFrame) -> str:
    """Render a compact GFM table without the optional ``tabulate`` package."""
    values = frame.copy().replace({np.nan: ""})
    headers = [str(column).replace("|", "\\|") for column in values.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in values.itertuples(index=False, name=None):
        lines.append(
            "| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |"
        )
    return "\n".join(lines)


def _guard_output(path: Path) -> Path:
    resolved = path.resolve()
    if any(re.match(r"^ploemeur(?:_|$)", part.lower()) for part in resolved.parts):
        raise ValueError(f"Refusing excluded output path: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str, binary: bool = False) -> bytes | str:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True
    )
    return completed.stdout if binary else completed.stdout.decode("utf-8", "replace")


def _excluded_from_run(relative: Path) -> bool:
    parts = [part.lower() for part in relative.parts]
    return any(part.startswith("ploemeur") or part == "hyp-26-0172" for part in parts)


def _workspace_snapshot(excluded_root: Path) -> tuple[str, str, str, int]:
    tracked = _git("diff", "--binary", binary=True)
    tracked_hash = hashlib.sha256(tracked).hexdigest()
    scoped_tracked = _git(
        "diff",
        "--binary",
        "--",
        ".",
        ":(exclude)sites/ploemeur/**",
        ":(exclude)tests/golden/*ploemeur*",
        ":(exclude)results/HYP-26-0172/**",
        binary=True,
    )
    scoped_hash = hashlib.sha256(scoped_tracked).hexdigest()
    digest = hashlib.sha256(b"tracked-diff\0" + scoped_hash.encode("ascii") + b"\0")
    untracked = sorted(
        Path(line)
        for line in str(_git("ls-files", "--others", "--exclude-standard")).splitlines()
        if line
    )
    included = 0
    for relative in untracked:
        if _excluded_from_run(relative):
            continue
        path = ROOT / relative
        try:
            path.resolve().relative_to(excluded_root)
            continue
        except ValueError:
            pass
        if not path.is_file():
            continue
        payload = path.read_bytes()
        digest.update(str(relative).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0" + str(len(payload)).encode("ascii") + b"\0")
        digest.update(hashlib.sha256(payload).digest())
        included += 1
    return tracked_hash, scoped_hash, digest.hexdigest(), included


def write_manifest(output: Path) -> Path:
    output = _guard_output(output)
    tracked_hash, scoped_hash, snapshot_hash, untracked_count = _workspace_snapshot(
        output
    )
    grid = asdict(DEFAULT_TRACER_GRID_SETTINGS)
    tracer_hashes: dict[str, dict[str, str]] = {}
    for tracer in TRACERS:
        directory = DIRECTORY_TRACER_DATA / tracer
        files = sorted(path for path in directory.iterdir() if path.is_file())
        tracer_hashes[tracer] = {
            str(path.relative_to(ROOT)).replace("\\", "/"): _sha256(path)
            for path in files
            if path.suffix.lower() in {".yaml", ".csv", ".txt"}
        }
    status = str(_git("status", "--porcelain"))
    manifest = {
        "run_id": "article_non_ploemeur_final",
        "scope": {
            "included": "article generic, TracerLPM, Holten",
            "excluded": "Ploemeur",
        },
        "created_local": pd.Timestamp.now(tz="Europe/Paris").isoformat(),
        "git": {
            "base_sha": str(_git("rev-parse", "HEAD")).strip(),
            "dirty": bool(status.strip()),
            "tracked_diff_sha256": tracked_hash,
            "run_scoped_tracked_diff_sha256": scoped_hash,
            "workspace_snapshot_sha256": snapshot_hash,
            "workspace_snapshot_untracked_file_count": untracked_count,
            "snapshot_excludes_generated_output": str(output.relative_to(ROOT)).replace(
                "\\", "/"
            ),
            "snapshot_excluded_scopes": [
                "sites/ploemeur",
                "results/HYP-26-0172",
                "Ploemeur goldens",
            ],
        },
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "pandas": pd.__version__,
            "matplotlib": matplotlib.__version__,
            "platform": platform.platform(),
            "system": platform.system(),
        },
        "cdf_partial_first_moment_grid": grid,
        "tracer_files_sha256": tracer_hashes,
        "tracer_aliases": {"85Kr": "kr85"},
        "scientific_engine": "CDF bin masses plus exact partial first moments",
    }
    path = output / "run_manifest.yaml"
    path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )
    return path


MODEL_CASES = (
    ("exp", {"mu": 0.2}, "very_narrow"),
    ("exp", {"mu": 20.0}, "intermediate"),
    ("exp", {"mu": 100.0}, "long_tail"),
    ("exp_shifted", {"mu": 0.2, "shift": 5.0}, "shifted_narrow"),
    ("exp_shifted", {"mu": 30.0, "shift": 40.0}, "shifted_long_tail"),
    ("gamma", {"k": 0.35, "scale": 30.0}, "shape_lt_1"),
    ("gamma", {"k": 8.0, "scale": 2.0}, "shape_gt_1"),
    ("uniform", {"tmin": 5.0, "delta": 0.05}, "very_narrow"),
    ("uniform", {"tmin": 20.0, "delta": 80.0}, "wide"),
    ("weibull", {"k": 0.5, "lambda": 30.0}, "long_tail"),
    ("weibull", {"k": 8.0, "lambda": 15.0}, "narrow"),
    ("ig", {"mu": 20.0, "sigma": 1.0}, "low_dispersion"),
    ("ig", {"mu": 20.0, "sigma": 30.0}, "high_dispersion"),
    ("ig_shifted", {"mu": 10.0, "sigma": 1.0, "shift": 5.0}, "shifted_low_dispersion"),
    (
        "ig_shifted",
        {"mu": 30.0, "sigma": 35.0, "shift": 20.0},
        "shifted_high_dispersion",
    ),
    ("shapefree_n_oldbin", {"z1": -1.0, "z2": 0.5, "z3": 1.0}, "shape_free"),
    ("mix_exp_shifted", {"rate": 0.35, "mu1": 8.0, "mu2": 20.0, "shift": 4.0}, "mixed"),
    ("dirac", {"mu": 20.0}, "discrete"),
    ("dirac_double", {"mu1": 8.0, "mu2": 35.0, "rate": 0.4}, "discrete"),
)


def _model(name: str, parameters: dict[str, float]):
    model = lpm_build(name, directory_lpm=str(DIRECTORY_LPM_DATA))
    model.p.update(parameters)
    return model


def _independent_distribution(name: str, p: dict[str, float]):
    if name == "exp":
        return stats.expon(loc=0.0, scale=p["mu"])
    if name == "exp_shifted":
        return stats.expon(loc=p["shift"], scale=p["mu"])
    if name == "gamma":
        return stats.gamma(a=p["k"], loc=0.0, scale=p["scale"])
    if name == "uniform":
        return stats.uniform(loc=p["tmin"], scale=p["delta"])
    if name == "weibull":
        return stats.weibull_min(c=p["k"], loc=0.0, scale=p["lambda"])
    if name in {"ig", "ig_shifted"}:
        mean, std = p["mu"], p["sigma"]
        shape = (std / mean) ** 2
        scale = mean**3 / std**2
        return stats.invgauss(
            shape,
            loc=p.get("shift", 0.0),
            scale=scale,
        )
    return None


@lru_cache(maxsize=None)
def _legendre_rule(order: int) -> tuple[np.ndarray, np.ndarray]:
    """Cache immutable Gauss-Legendre rules reused across chronology segments."""
    return leggauss(order)


def _gauss_interval(function, left: float, right: float, order: int = 48) -> float:
    if right <= left:
        return 0.0
    nodes, weights = _legendre_rule(order)
    x = 0.5 * (right - left) * nodes + 0.5 * (right + left)
    return float(0.5 * (right - left) * np.dot(weights, function(x)))


def independent_reference(tracer: Tracer, model, date: float) -> float:
    """Independent segmented Gauss-Legendre expectation."""
    name, p = model.name, model.p
    tmax = float(date - tracer.datemin)
    age_breaks = _chronology_age_breaks(tracer, date, tmax)

    def response(age):
        age = np.asarray(age)
        return np.asarray(
            tracer.get_concentration(date - age, age),
            dtype=float,
        )

    if name == "dirac":
        age = p["mu"]
        return float(response(age)) if 0.0 <= age <= tmax else 0.0
    if name == "dirac_double":
        return _double_dirac_reference(response, p, tmax)
    if name == "mix_exp_shifted":
        dirac = p["rate"] * float(response(p["mu1"])) if p["mu1"] <= tmax else 0.0
        distribution = stats.expon(loc=p["mu1"] + p["shift"], scale=p["mu2"])
        continuous = _quantile_reference(response, distribution, tmax, age_breaks)
        return dirac + (1.0 - p["rate"]) * continuous
    if name == "shapefree_n_oldbin":
        return _shapefree_reference(response, model, tmax, age_breaks)
    distribution = _independent_distribution(name, p)
    if distribution is None:
        raise ValueError(f"No independent reference for {name}")
    return _quantile_reference(response, distribution, tmax, age_breaks)


def _chronology_age_breaks(tracer: Tracer, date: float, tmax: float) -> np.ndarray:
    dates = tracer.convolution_dates
    if dates is None:
        return np.array([0.0, tmax], dtype=float)
    ages = date - np.asarray(dates, dtype=float).reshape(-1)
    ages = ages[np.isfinite(ages) & (ages > 0.0) & (ages < tmax)]
    return np.unique(np.concatenate(([0.0, tmax], ages)))


def _double_dirac_reference(response, parameters: dict, tmax: float) -> float:
    ages = (parameters["mu1"], parameters["mu1"] + parameters["mu2"])
    weights = (parameters["rate"], 1.0 - parameters["rate"])
    return sum(
        weight * float(response(age))
        for age, weight in zip(ages, weights)
        if 0.0 <= age <= tmax
    )


def _shapefree_reference(response, model, tmax: float, age_breaks: np.ndarray) -> float:
    total = 0.0
    for left, right, fraction in zip(
        model.bin_edges()[:-1], model.bin_edges()[1:], model.fractions()
    ):
        upper = min(float(right), tmax)
        if upper <= left:
            continue
        local_edges = np.unique(
            np.concatenate(
                (
                    np.array([float(left), upper]),
                    age_breaks[(age_breaks > left) & (age_breaks < upper)],
                )
            )
        )
        for segment_left, segment_right in zip(local_edges[:-1], local_edges[1:]):
            total += (
                fraction
                / (right - left)
                * _gauss_interval(response, float(segment_left), float(segment_right))
            )
    return float(total)


def _quantile_reference(
    response,
    distribution,
    tmax: float,
    age_breaks: npt.ArrayLike | None = None,
) -> float:
    p0 = float(distribution.cdf(0.0))
    p1 = float(distribution.cdf(tmax))
    if p1 <= p0:
        return 0.0
    probability_tolerance = 1e-13 * max(1.0, p1 - p0)
    probability_edges = np.linspace(p0, p1, 33)
    if age_breaks is not None:
        ages = np.asarray(age_breaks, dtype=float)
        ages = ages[np.isfinite(ages) & (ages > 0.0) & (ages < tmax)]
        if ages.size:
            chronology_probabilities = np.asarray(distribution.cdf(ages), dtype=float)
            chronology_probabilities = chronology_probabilities[
                np.isfinite(chronology_probabilities)
                & (chronology_probabilities > p0 + probability_tolerance)
                & (chronology_probabilities < p1 - probability_tolerance)
            ]
            probability_edges = np.unique(
                np.concatenate((probability_edges, chronology_probabilities))
            )
    total = 0.0
    for left, right in zip(probability_edges[:-1], probability_edges[1:]):
        if right - left <= probability_tolerance:
            continue
        total += _gauss_interval(
            lambda probability: response(distribution.ppf(probability)),
            float(left),
            float(right),
        )
    return float(total)


def _support_description(name: str, parameters: dict[str, object]) -> str:
    if name in {"exp", "gamma", "weibull", "ig"}:
        return "[0,+infinity)"
    if name in {"exp_shifted", "ig_shifted"}:
        return f"[{parameters['shift']},+infinity)"
    if name == "uniform":
        return f"[{parameters['tmin']},{float(parameters['tmin']) + float(parameters['delta'])}]"
    if name == "shapefree":
        return f"[{parameters['edges'][0]},{parameters['edges'][-1]}] piecewise uniform"
    if name == "shapefree_n_oldbin":
        return "[0,200] piecewise uniform (0-20, 20-40, 40-60, 60-200 yr)"
    if name == "mix_exp_shifted":
        return "one Dirac atom plus shifted-exponential continuous support"
    if name == "dirac":
        return f"atom at {parameters['mu']}"
    if name == "dirac_double":
        return "two Dirac atoms"
    return "declared by LPM"


def _independent_invariant_values(model) -> dict[str, float | bool]:
    """Return independent finite-CDF, moment, mean, and spread checks."""
    name, p = model.name, model.p
    distribution = _independent_distribution(name, p)
    if distribution is not None:
        probability = 0.6
        probe = float(distribution.ppf(probability))
        cdf_actual, moment_actual = model.cdf_and_partial_first_moment(probe)
        support_lower = float(distribution.support()[0])
        moment_expected = float(
            distribution.expect(
                lambda age: age,
                lb=support_lower,
                ub=probe,
                epsabs=1e-12,
                epsrel=1e-12,
            )
        )
        mean_expected, variance_expected = distribution.stats(moments="mv")
        cdf_below_support = float(model.cdf(np.nextafter(support_lower, -np.inf)))
        return {
            "probe_age": probe,
            "cdf_at_probe": float(cdf_actual),
            "cdf_expected": probability,
            "partial_first_moment_at_probe": float(moment_actual),
            "partial_first_moment_expected": moment_expected,
            "mean_expected": float(mean_expected),
            "std_expected": float(np.sqrt(variance_expected)),
            "support_consistent": abs(cdf_below_support) <= 1e-14,
        }

    if name == "shapefree_n_oldbin":
        edges = np.asarray(model.bin_edges(), dtype=float)
        fractions = np.asarray(model.fractions(), dtype=float)
        probe = float(0.5 * (edges[2] + edges[3]))
        cdf_expected = 0.0
        moment_expected = 0.0
        for left, right, fraction in zip(edges[:-1], edges[1:], fractions):
            upper = min(probe, float(right))
            if upper > left:
                cdf_expected += fraction * (upper - left) / (right - left)
                moment_expected += (
                    fraction * (upper**2 - left**2) / (2.0 * (right - left))
                )
        midpoints = 0.5 * (edges[:-1] + edges[1:])
        mean_expected = float(np.dot(fractions, midpoints))
        second_expected = float(
            np.sum(
                fractions * (edges[1:] ** 3 - edges[:-1] ** 3) / (3.0 * np.diff(edges))
            )
        )
        cdf_actual, moment_actual = model.cdf_and_partial_first_moment(probe)
        return {
            "probe_age": probe,
            "cdf_at_probe": float(cdf_actual),
            "cdf_expected": float(cdf_expected),
            "partial_first_moment_at_probe": float(moment_actual),
            "partial_first_moment_expected": float(moment_expected),
            "mean_expected": mean_expected,
            "std_expected": float(
                np.sqrt(max(0.0, second_expected - mean_expected**2))
            ),
            "support_consistent": abs(float(model.cdf(np.nextafter(edges[0], -np.inf))))
            <= 1e-14,
        }

    if name == "mix_exp_shifted":
        rate = float(p["rate"])
        scale = float(p["mu2"])
        support = float(p["mu1"] + p["shift"])
        probability = 0.6
        probe = float(stats.expon(loc=support, scale=scale).ppf(probability))
        tail_cdf, tail_moment = model.continuous_cdf_and_partial_first_moment(probe)
        cdf_actual = rate + (1.0 - rate) * float(tail_cdf)
        moment_actual = rate * float(p["mu1"]) + (1.0 - rate) * float(tail_moment)
        q = (probe - support) / scale
        tail_moment_expected = support * probability + scale * (
            1.0 - np.exp(-q) * (1.0 + q)
        )
        continuous_mean = support + scale
        mean_expected = rate * float(p["mu1"]) + (1.0 - rate) * continuous_mean
        variance_expected = rate * (float(p["mu1"]) - mean_expected) ** 2 + (
            1.0 - rate
        ) * (scale**2 + (continuous_mean - mean_expected) ** 2)
        return {
            "probe_age": probe,
            "cdf_at_probe": cdf_actual,
            "cdf_expected": rate + (1.0 - rate) * probability,
            "partial_first_moment_at_probe": moment_actual,
            "partial_first_moment_expected": rate * float(p["mu1"])
            + (1.0 - rate) * tail_moment_expected,
            "mean_expected": mean_expected,
            "std_expected": float(np.sqrt(variance_expected)),
            "support_consistent": abs(
                float(model.cdf(np.nextafter(float(p["mu1"]), -np.inf)))
            )
            <= 1e-14,
        }

    if name == "dirac":
        probe = float(p["mu"])
        return {
            "probe_age": probe,
            "cdf_at_probe": float(model.cdf(probe)),
            "cdf_expected": 1.0,
            "partial_first_moment_at_probe": probe,
            "partial_first_moment_expected": probe,
            "mean_expected": probe,
            "std_expected": 0.0,
            "support_consistent": abs(float(model.cdf(np.nextafter(probe, -np.inf))))
            <= 1e-14,
        }

    if name == "dirac_double":
        first, second = map(float, model.get_dirac_double_time())
        rate = float(p["rate"])
        probe = 0.5 * (first + second)
        mean_expected = rate * first + (1.0 - rate) * second
        return {
            "probe_age": probe,
            "cdf_at_probe": float(model.cdf(probe)),
            "cdf_expected": rate,
            "partial_first_moment_at_probe": rate * first,
            "partial_first_moment_expected": rate * first,
            "mean_expected": mean_expected,
            "std_expected": float(np.sqrt(rate * (1.0 - rate)) * abs(second - first)),
            "support_consistent": abs(float(model.cdf(np.nextafter(first, -np.inf))))
            <= 1e-14,
        }
    raise ValueError(f"No independent invariant reference for {name}")


def _analytical_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    affine = SyntheticTracer(
        datemin=1700.0,
        convolution_initial_bins=1,
        concentration_fn=lambda date, age: 2.5 + 0.03 * np.asarray(age),
    )
    constant = ConstantTracer(concentration=3.25, datemin=1700.0)
    for name, parameters, regime in MODEL_CASES:
        model = _model(name, parameters)
        row: dict[str, object] = {
            "LPM": name,
            "regime": regime,
            "parameters": json.dumps(parameters, sort_keys=True),
            "support": _support_description(name, parameters),
            "partial_first_moment": (
                "exact discrete" if name in {"dirac", "dirac_double"} else "analytic"
            ),
            "mean": float(model.mean()),
            "std": float(model.std()),
        }
        row.update(_independent_invariant_values(model))
        row.update(
            mean_abs_error=abs(float(row["mean"]) - float(row["mean_expected"])),
            std_abs_error=abs(float(row["std"]) - float(row["std_expected"])),
            cdf_abs_error=abs(float(row["cdf_at_probe"]) - float(row["cdf_expected"])),
            partial_first_moment_abs_error=abs(
                float(row["partial_first_moment_at_probe"])
                - float(row["partial_first_moment_expected"])
            ),
        )
        if name not in {"dirac", "dirac_double", "mix_exp_shifted"}:
            cdf_inf, moment_inf = model.cdf_and_partial_first_moment(np.inf)
            normalization = float(cdf_inf - model.cdf(-np.inf))
            row.update(
                normalization=normalization,
                cdf_infinity=float(cdf_inf),
                partial_first_moment_infinity=float(moment_inf),
            )
        else:
            moment = float(model.mean())
            row.update(
                normalization=1.0,
                cdf_infinity=float(model.cdf(np.inf)),
                partial_first_moment_infinity=moment,
            )
        constant_value = float(Convolution(constant, 2020.0).convolve(model))
        affine_value = float(Convolution(affine, 2020.0).convolve(model))
        window = float(Convolution(constant, 2020.0).window_mass(model))
        if name == "dirac":
            affine_expected = 2.5 + 0.03 * model.p["mu"]
        elif name == "dirac_double":
            first, second = model.get_dirac_double_time()
            affine_expected = model.p["rate"] * (2.5 + 0.03 * first) + (
                1.0 - model.p["rate"]
            ) * (2.5 + 0.03 * second)
        elif name == "mix_exp_shifted":
            continuous_mass, continuous_moment = (
                model.continuous_cdf_and_partial_first_moment(320.0)
            )
            affine_expected = model.p["rate"] * (
                2.5 + 0.03 * model.get_dirac_time()
            ) + (1.0 - model.p["rate"]) * (
                2.5 * continuous_mass + 0.03 * continuous_moment
            )
        else:
            _, partial = model.cdf_and_partial_first_moment(320.0)
            affine_expected = 2.5 * window + 0.03 * float(partial)
        row.update(
            window_mass=window,
            constant_value=constant_value,
            constant_expected=3.25 * window,
            constant_abs_error=abs(constant_value - 3.25 * window),
            affine_value=affine_value,
            affine_expected=affine_expected,
            affine_abs_error=abs(affine_value - affine_expected),
        )
        rows.append(row)
    return rows


def _validation_matrix(settings: TracerGridSettings) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for tracer_name in TRACERS:
        tracer = Tracer(DIRECTORY_TRACER_DATA, tracer_name)
        conv = Convolution(tracer, DATE, grid_settings=settings)
        for name, parameters, regime in MODEL_CASES:
            model = _model(name, parameters)
            value = float(conv.convolve(model))
            reference = independent_reference(tracer, model, DATE)
            abs_error = abs(value - reference)
            rows.append(
                {
                    "tracer": tracer_name,
                    "LPM": name,
                    "regime": regime,
                    "parameters": json.dumps(parameters, sort_keys=True),
                    "PyAge": value,
                    "reference": reference,
                    "abs_error": abs_error,
                    "rel_error": abs_error / abs(reference)
                    if reference != 0.0
                    else np.nan,
                    "window_mass": conv.window_mass(model),
                    "n_bins": conv.diagnostics.n_bins if conv.diagnostics else 0,
                }
            )
    return pd.DataFrame(rows)


def _error_summary(frame: pd.DataFrame, label: str) -> dict[str, object]:
    relative = frame.loc[np.isfinite(frame["rel_error"]), "rel_error"].to_numpy(
        dtype=float
    )
    worst = frame.iloc[int(np.nanargmax(frame["rel_error"].to_numpy(dtype=float)))]
    return {
        "configuration": label,
        "comparison_count": int(len(frame)),
        "median_rel_error": float(np.nanmedian(relative)),
        "p95_rel_error": float(np.nanpercentile(relative, 95)),
        "p99_rel_error": float(np.nanpercentile(relative, 99)),
        "maximum_rel_error": float(np.nanmax(relative)),
        "median_n_bins": float(frame["n_bins"].median()),
        "maximum_n_bins": int(frame["n_bins"].max()),
        "worst_case": f"{worst['tracer']} | {worst['LPM']} | {worst['regime']}",
    }


def _tolerance_timing(settings: TracerGridSettings) -> dict[str, float]:
    """Time one four-tracer preparation and 1,000 cached convolutions."""
    model = _model("exp_shifted", {"mu": 10.0, "shift": 20.0})
    group = ConvolutionTracers(
        names=list(TABLE3_TRACERS), date=DATE, grid_settings=settings
    )
    start = time.perf_counter()
    group.prepare(model)
    preparation = time.perf_counter() - start
    start = time.perf_counter()
    for _ in range(1000):
        group.convolve(model)
    repeated = time.perf_counter() - start
    return {
        "representative_preparation_seconds": preparation,
        "representative_1000_repeated_seconds": repeated,
        "representative_seconds_per_repeated_convolution": repeated / 1000.0,
    }


def _performance(output: Path) -> pd.DataFrame:
    definitions = (
        ("exp_shifted", {"mu": 10.0, "shift": 20.0}),
        ("gamma", {"k": 2.0, "scale": 10.0}),
        ("uniform", {"tmin": 10.0, "delta": 20.0}),
        ("weibull", {"k": 1.7, "lambda": 20.0}),
        ("ig", {"mu": 20.0, "sigma": 8.0}),
        ("ig_shifted", {"mu": 15.0, "sigma": 5.0, "shift": 10.0}),
    )
    rows = []
    for name, parameters in definitions:
        for tracer_names in (("cfc11",), TABLE3_TRACERS):
            model = _model(name, parameters)
            group = ConvolutionTracers(names=list(tracer_names), date=DATE)
            start = time.perf_counter()
            group.prepare(model)
            prepare_seconds = time.perf_counter() - start
            start = time.perf_counter()
            for _ in range(1000):
                group.convolve(model)
            repeated_seconds = time.perf_counter() - start
            bins = [element.prepared_grid.edges.size - 1 for element in group.elements]
            rows.append(
                {
                    "LPM": name,
                    "n_tracers": len(tracer_names),
                    "tracers": ",".join(tracer_names),
                    "preparation_seconds": prepare_seconds,
                    "seconds_1000_repeated_convolutions": repeated_seconds,
                    "seconds_per_repeated_convolution": repeated_seconds / 1000.0,
                    "median_n_bins": float(np.median(bins)),
                    "maximum_n_bins": int(max(bins)),
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "s1_performance.csv", index=False)
    return frame


def run_s1(output: Path) -> dict[str, object]:
    output = _guard_output(output) / "supplement_s1"
    output.mkdir(parents=True, exist_ok=True)
    analytical = pd.DataFrame(_analytical_rows())
    analytical.to_csv(output / "analytical_invariants.csv", index=False)
    default = DEFAULT_TRACER_GRID_SETTINGS
    configurations = {
        "0.5x": TracerGridSettings(
            absolute_tolerance_factor=default.absolute_tolerance_factor * 0.5,
            relative_tolerance=default.relative_tolerance * 0.5,
            linear_curvature_factor=default.linear_curvature_factor * 0.5,
        ),
        "1x": default,
        "2x": TracerGridSettings(
            absolute_tolerance_factor=default.absolute_tolerance_factor * 2.0,
            relative_tolerance=default.relative_tolerance * 2.0,
            linear_curvature_factor=default.linear_curvature_factor * 2.0,
        ),
    }
    summaries = []
    default_matrix = None
    for label, settings in configurations.items():
        start = time.perf_counter()
        matrix = _validation_matrix(settings)
        elapsed = time.perf_counter() - start
        matrix.to_csv(
            output / f"independent_matrix_{label.replace('.', '_')}.csv", index=False
        )
        summary = _error_summary(matrix, label)
        summary["matrix_seconds"] = elapsed
        summary.update(_tolerance_timing(settings))
        summaries.append(summary)
        if label == "1x":
            default_matrix = matrix
    sensitivity = pd.DataFrame(summaries)
    sensitivity.to_csv(output / "tolerance_sensitivity.csv", index=False)
    performance = _performance(output)
    assert default_matrix is not None
    report = f"""# Supplement S1 — qualification numérique finale

Run manifest: `../run_manifest.yaml`.

## Méthode

La grille est pilotée par la réponse traceur $K(t)$. Sur chaque bin $[a,b]$,
PyAge emploie la masse exacte $F(b)-F(a)$ et le moment partiel exact
$M(b)-M(a)$, avec $F(t)=\\int_0^t g(u)du$ et
$M(t)=\\int_0^t u g(u)du$. L'interpolation linéaire de $K$ donne donc
exactement $K(a)[F(b)-F(a)] + (K(b)-K(a))/(b-a)\n
\\times (M(b)-M(a)-a[F(b)-F(a)])$. `window_mass` est la masse de la LPM
présente dans la fenêtre de chronique, sans renormalisation.

## LPM et invariants

Les moments partiels $M(t)=E[T\\,1(T\\leq t)]$ utilis\u00e9s par le moteur sont :

| famille | expression de $M(t)$ (sur le support) |
|---|---|
| exponential | $\\mu[1-e^{{-x}}(1+x)]$, $x=t/\\mu$ |
| shifted exponential | $sF(t)+\\mu[1-e^{{-x}}(1+x)]$, $x=(t-s)/\\mu$ |
| gamma | $k\\theta P(k+1,t/\\theta)$ |
| uniform $[a,a+\\Delta]$ | $(u^2-a^2)/(2\\Delta)$, $u=\\mathrm{{clip}}(t,a,a+\\Delta)$ |
| Weibull | $\\lambda\\Gamma(1+1/k)P(1+1/k,(t/\\lambda)^k)$ |
| inverse Gaussian | $\\mu[\\Phi(d_-)-e^{{2\\Lambda/\\mu}}\\Phi(-d_+)]$, $d_\\pm=\\sqrt{{\\Lambda/t}}(t/\\mu\\pm1)$, $\\Lambda=\\mu^3/\\sigma^2$ |
| shifted inverse Gaussian | $sF_X(t-s)+M_X(t-s)$ |
| ShapeFree | somme exacte des intÃ©grales uniformes tronquÃ©es par classe |
| Diracâ€“exponential | somme du moment de l'atome et du moment exponentiel continu pondÃ©rÃ©s |
| Dirac / double Dirac | somme des Ã¢ges des atomes atteints, pondÃ©rÃ©s |

{_markdown(analytical)}

## Matrice indépendante

Référence : Gauss–Legendre segmentée d'ordre 48 en espace des quantiles,
32 segments, avec lois SciPy construites directement à partir des paramètres
physiques et sans appel au moteur de convolution PyAge.

{_markdown(pd.DataFrame([_error_summary(default_matrix, "1x")]))}

## Sensibilité numérique

{_markdown(sensitivity)}

## Performance

Les temps muraux ont ete mesures sur un poste partage charge a 100 % par une
campagne Ploemeur preexistante et independante. Ils documentent ce run mais ne
doivent pas etre interpretes comme des benchmarks absolus sur machine isolee.

{_markdown(performance)}
"""
    report = (
        report.replace("\u00c3\u00a9", "\u00e9")
        .replace("\u00c3\u00a2", "\u00e2")
        .replace("\u00e2\u20ac\u201c", "\u2013")
    )
    (output / "supplement_s1.md").write_text(report, encoding="utf-8", newline="\n")
    return {"comparisons": len(default_matrix), "output": str(output)}


def _display(output: Path) -> DisplayOptions:
    display = DisplayOptions()
    display.text = False
    display.figure = False
    display.figure_save = False
    display.figure_close = True
    display.directory = output
    return display


def _run_table3_chain(
    observations,
    output: Path,
    seed: int,
    steps: int,
    skip: int,
):
    problem = CalibrationProblem(
        observations,
        "exp_shifted",
        display_options=_display(output),
        sample_count=10000,
        explore_objective=False,
        explore_reachable=False,
    ).prepare()
    mh = MetropolisHastings(
        config=MHConfig(
            nstep=steps,
            nskip=skip,
            prior_option=False,
            likelihood=True,
            monitor=False,
            display_traj=False,
            display_text=False,
            seed=seed,
            initial_params={"mu": 10.0, "shift": 10.0},
        )
    )
    mh.MH_step.define_by_value()
    return mh, mh.run(problem)


def _historical_tracers(output: Path) -> list[Tracer]:
    """Materialize the four tracer definitions from the Git base snapshot."""
    root = output / "historical_inputs_at_base_sha"
    for name in TABLE3_TRACERS:
        directory = root / name
        directory.mkdir(parents=True, exist_ok=True)
        for filename in (f"{name}.yaml", "recharge.csv"):
            relative = f"data_core/data_tracer/{name}/{filename}"
            try:
                payload = _git("show", f"HEAD:{relative}", binary=True)
            except subprocess.CalledProcessError:
                continue
            (directory / filename).write_bytes(payload)
    return [Tracer(root, name) for name in TABLE3_TRACERS]


def _old_simpson_kernel(tracer: Tracer, resolution: int = 1000):
    dates = tracer.datemin + (DATE - tracer.datemin) * np.arange(
        0.0, 1.0, 1.0 / resolution
    )
    ages = DATE - dates
    response = np.asarray(tracer.get_concentration(dates, ages), dtype=float)
    return ages, response


def _old_simpson_values(kernels, mu: float, shift: float) -> np.ndarray:
    values = []
    for ages, response in kernels:
        density = stats.expon.pdf(ages, loc=shift, scale=mu)
        values.append(-integrate.simpson(response * density, x=ages))
    return np.asarray(values, dtype=float)


def _historical_chain(
    kernels,
    observed: np.ndarray,
    steps: int,
    skip: int,
    seed: int,
) -> tuple[pd.DataFrame, float]:
    """Historical no-prior MH using the PDF+Simpson forward operator."""
    sigma = 0.08 * observed
    rng = np.random.default_rng(seed)
    parameters = np.array([10.0, 10.0], dtype=float)

    def evaluate(candidate: np.ndarray):
        if not (0.1 <= candidate[0] <= 70.0 and 0.0 <= candidate[1] <= 70.0):
            return -math.inf, math.inf, np.full(4, np.nan)
        concentrations = _old_simpson_values(kernels, candidate[0], candidate[1])
        j_value = float(np.sum(np.square((concentrations - observed) / sigma)))
        return -0.5 * j_value, j_value, concentrations

    log_probability, j_value, concentrations = evaluate(parameters)
    records = []
    accepted = 0
    for step in range(steps):
        proposal = parameters + 1.5 * rng.standard_normal(2)
        proposal_log_probability, proposal_j, proposal_concentrations = evaluate(
            proposal
        )
        if proposal_log_probability >= log_probability or (
            np.isfinite(proposal_log_probability)
            and np.log(rng.random()) < proposal_log_probability - log_probability
        ):
            parameters = proposal
            log_probability = proposal_log_probability
            j_value = proposal_j
            concentrations = proposal_concentrations
            accepted += 1
        if step > 0.2 * steps and step % skip == 0:
            record = {
                "mu": parameters[0],
                "shift": parameters[1],
                "obj_function": math.sqrt(j_value / 4.0),
            }
            record.update(
                {
                    f"{name}_{DATE:g}": value
                    for name, value in zip(TABLE3_TRACERS, concentrations)
                }
            )
            records.append(record)
    return pd.DataFrame(records), accepted / steps


def _summary_row(
    index: int,
    mu: float,
    shift: float,
    observations,
    frame: pd.DataFrame,
    steps: int,
) -> dict[str, object]:
    row: dict[str, object] = {
        "case": index,
        "target_mu": mu,
        "target_t0": shift,
        "target_mean_transit_time": mu + shift,
        "relative_error": 0.08,
        "seed": 12345,
        "steps": steps,
        "stored_samples": len(frame),
    }
    observed_values = (
        observations.cv["concentration"].to_numpy(dtype=float)
        if hasattr(observations, "cv")
        else np.asarray(observations, dtype=float)
    )
    for tracer_name, concentration in zip(TABLE3_TRACERS, observed_values):
        row[f"C_{tracer_name}"] = float(concentration)
    for parameter in ("mu", "shift"):
        values = frame[parameter].to_numpy(dtype=float)
        row[f"posterior_{parameter}_mean"] = float(np.mean(values))
        row[f"posterior_{parameter}_median"] = float(np.median(values))
        row[f"posterior_{parameter}_std"] = float(np.std(values, ddof=1))
        row[f"posterior_{parameter}_q025"] = float(np.quantile(values, 0.025))
        row[f"posterior_{parameter}_q25"] = float(np.quantile(values, 0.25))
        row[f"posterior_{parameter}_q75"] = float(np.quantile(values, 0.75))
        row[f"posterior_{parameter}_q975"] = float(np.quantile(values, 0.975))
    row["posterior_mean_transit_time_mean"] = float(
        np.mean(frame["mu"] + frame["shift"])
    )
    row["posterior_mean_transit_time_median"] = float(
        np.median(frame["mu"] + frame["shift"])
    )
    row["sqrt_J_data_over_m_best"] = float(frame["obj_function"].min())
    return row


def run_table3(output: Path, steps: int = 10_000, skip: int = 5) -> dict[str, object]:
    output = _guard_output(output) / "table3"
    chains = output / "chains"
    chains.mkdir(parents=True, exist_ok=True)
    tracers = ConvolutionTracers(names=list(TABLE3_TRACERS), date=DATE)
    rows: list[dict[str, object]] = []
    old_rows: list[dict[str, object]] = []
    old_tracers = _historical_tracers(output)
    old_kernels = [_old_simpson_kernel(tracer) for tracer in old_tracers]
    for index, (mu, shift) in enumerate(TABLE3_PAIRS, start=1):
        target = _model("exp_shifted", {"mu": mu, "shift": shift})
        observations = tracers.convolve(target, return_type="concentrations")
        observations.error_affect_from_value(0.08)
        final_chain_path = chains / f"case_{index:02d}_mu{mu:g}_t0{shift:g}.csv"
        if final_chain_path.exists():
            frame = pd.read_csv(final_chain_path)
        else:
            _, posterior = _run_table3_chain(observations, output, 12345, steps, skip)
            frame = posterior.frame.copy()
            frame.to_csv(final_chain_path, index=False)
        rows.append(
            _summary_row(
                index,
                mu,
                shift,
                observations,
                frame,
                steps,
            )
        )
        old_observed = _old_simpson_values(old_kernels, mu, shift)
        old_chain_path = (
            chains / f"historical_case_{index:02d}_mu{mu:g}_t0{shift:g}.csv"
        )
        if old_chain_path.exists():
            old_frame = pd.read_csv(old_chain_path)
        else:
            old_frame, _ = _historical_chain(
                old_kernels, old_observed, steps, skip, 12345
            )
            old_frame.to_csv(old_chain_path, index=False)
        old_rows.append(
            _summary_row(
                index,
                mu,
                shift,
                old_observed,
                old_frame,
                steps,
            )
        )
    table = pd.DataFrame(rows)
    old_table = pd.DataFrame(old_rows)
    table.to_csv(output / "table3_final.csv", index=False)
    old_table.to_csv(output / "table3_historical_pdf_simpson.csv", index=False)
    comparison_rows = []
    for column in table.select_dtypes(include=[np.number]).columns:
        for case, old_value, new_value in zip(
            table["case"], old_table[column], table[column]
        ):
            absolute = abs(float(new_value - old_value))
            comparison_rows.append(
                {
                    "case": int(case),
                    "column": column,
                    "old_value": float(old_value),
                    "new_value": float(new_value),
                    "absolute_difference": absolute,
                    "relative_difference": absolute / abs(float(old_value))
                    if old_value != 0
                    else np.nan,
                }
            )
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(output / "table3_old_new_all_numeric_columns.csv", index=False)
    (output / "table3_final.md").write_text(
        "# Table 3 — shifted exponential\n\n"
        "`mu` is the exponential timescale, `t0` is the shift, and mean transit time is `mu+t0`.\n\n"
        + _markdown(table),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "cases": len(table),
        "comparison_rows": len(comparison),
        "output": str(output),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("manifest", "s1", "table3", "all"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mh-steps", type=int, default=10_000)
    parser.add_argument("--mh-skip", type=int, default=5)
    args = parser.parse_args(argv)
    output = _guard_output(args.output)
    results: dict[str, object] = {}
    if args.phase in {"manifest", "all"}:
        results["manifest"] = str(write_manifest(output))
    if args.phase in {"s1", "all"}:
        results["s1"] = run_s1(output)
    if args.phase in {"table3", "all"}:
        results["table3"] = run_table3(output, args.mh_steps, args.mh_skip)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
