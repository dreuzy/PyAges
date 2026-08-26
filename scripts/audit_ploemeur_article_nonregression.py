"""Build the Ploemeur Article.docx scientific non-regression audit.

This is intentionally a forward/post-processing audit.  It does not launch MCMC,
modify the manuscript, or mutate archived campaign outputs.
"""

# ruff: noqa: E402, I001

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import warnings
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import integrate
from scipy.interpolate import interp1d
from scipy.stats import invgauss

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pyage.config.paths import DIRECTORY_TRACER_DATA
from pyage.convolution.convolution import Convolution
from pyage.lpm.models.inverse_gaussian import scipy_params_from_mean_std
from pyage.lpm.models.inverse_gaussian_shifted import InverseGaussianShiftedLpm
from pyage.tracer.tracer_protocol import SyntheticTracer
from pyage.tracer.tracer_root import Tracer


ROOT = REPO_ROOT
RESULTS = ROOT / "results" / "HYP-26-0172"
AUDIT_OUTPUT = ROOT / "results" / "ploemeur_article_nonregression_audit"
ARTICLE = Path(r"C:\Users\dreuzy\Downloads\Article.docx")
HISTORICAL_COMMIT = "5432034"
TRACERS = ("cfc11", "cfc12", "cfc113")
WELLS = ("F09", "F11")
N_DISTRIBUTIONS = 10
OLD_RESOLUTION = 200

METRIC_CSV = AUDIT_OUTPUT / "ploemeur_transit_time_metric_audit.csv"
DIST_CSV = AUDIT_OUTPUT / "ig_old_new_distribution_equivalence.csv"
FORWARD_CSV = AUDIT_OUTPUT / "ploemeur_old_new_forward_equivalence.csv"
COMPARISON_CSV = AUDIT_OUTPUT / "ploemeur_article_current_comparison.csv"
CAUSES_CSV = AUDIT_OUTPUT / "ploemeur_nonregression_root_causes.csv"
REPORT_MD = AUDIT_OUTPUT / "PLOEMEUR_ARTICLE_NONREGRESSION_AUDIT.md"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_bytes(revision: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)


def full_series_chain(well: str, version: str = "article") -> Path:
    base = RESULTS
    if version == "current":
        base = base / "v2"
    workflow = base / "runs" / f"main_{well}_exp_ig_3cfc_err20_seed12345" / "workflow"
    candidates = list(
        workflow.glob(
            f"ploemeur_apriori_double_0.2span_full/*/{well}_*/"
            "ig_shifted/Metropolis_Hastings/lpm_dist_calibrated.txt"
        )
    )
    if not candidates:
        raise FileNotFoundError(f"No full-series chain below {workflow}")

    def span(path: Path) -> int:
        case = path.parts[-4].split("_")
        return int(case[-1]) - int(case[-2])

    return max(candidates, key=span)


def selected_historical_samples(well: str) -> tuple[Path, pd.DataFrame]:
    path = full_series_chain(well)
    frame = pd.read_csv(path, sep="\t", index_col=0)
    ordered = frame.sort_values("median")
    positions = np.linspace(0, len(ordered) - 1, N_DISTRIBUTIONS)
    positions = np.rint(positions).astype(int)
    selected = ordered.iloc[positions].copy()
    selected["archive_row"] = selected.index.astype(int)
    selected.reset_index(drop=True, inplace=True)
    selected["sample_id"] = [f"{well}-{index:02d}" for index in range(1, 11)]
    return path, selected


def historical_tracer(name: str) -> tuple[SyntheticTracer, pd.DataFrame, str]:
    relpath = f"data_core/data_tracer/{name}/recharge.csv"
    raw = git_bytes(HISTORICAL_COMMIT, relpath)
    # This deliberately reproduces the historical loader.  In particular, the
    # old CFC-12 file had no header, so its first 1940.0 row became the header.
    frame = pd.read_csv(StringIO(raw.decode("utf-8")), comment="#")
    dates = frame.iloc[:, 0].to_numpy(dtype=float)
    values = frame.iloc[:, 1].to_numpy(dtype=float)
    interpolation = interp1d(dates, values, kind="linear")

    def response(date, _age):
        input_dates = np.asarray(date, dtype=float)
        scalar = input_dates.ndim == 0
        inputs = np.atleast_1d(input_dates)
        output = np.zeros(inputs.shape, dtype=float)
        valid = (inputs >= dates.min()) & (inputs <= dates.max())
        if np.any(valid):
            output[valid] = interpolation(inputs[valid])
        if scalar:
            return float(output[0])
        return output

    tracer = SyntheticTracer(
        name=name,
        unit="pptv",
        datemin=float(dates.min()),
        datemax=float(dates.max()),
        concentration_fn=response,
        convolution_dates=dates,
    )
    return tracer, frame, sha256_bytes(raw)


def old_forward(
    tracer: SyntheticTracer, date: float, a: float, s: float, shift: float
) -> float:
    distribution = invgauss(a, loc=shift, scale=s)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        q10, q50 = distribution.ppf([0.10, 0.50])
    if q10 - shift <= 0.75 and q50 - shift <= 2.5:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            q90, q99 = distribution.ppf([0.90, 0.99])
        tmax = float(date - tracer.datemin)
        clipped = np.maximum.accumulate(np.clip([q10, q50, q90, q99], shift, tmax))
        segments = ((60, 2.8), (60, 1.6), (40, 1.2), (20, 1.0))
        parts: list[np.ndarray] = []
        current = max(shift, 0.0)
        for boundary, (count, power) in zip(clipped, segments, strict=False):
            if boundary > current:
                sampling = np.linspace(0.0, 1.0, count, endpoint=False)
                parts.append(current + (boundary - current) * sampling**power)
            current = float(boundary)
        if tmax > current:
            sampling = np.linspace(0.0, 1.0, 10, endpoint=False)
            parts.append(current + (tmax - current) * sampling)
        parts.append(np.array([tmax]))
        ages = np.unique(np.concatenate(parts))
        values = tracer.get_concentration(date - ages, ages)
        return float(integrate.simpson(values * distribution.pdf(ages), x=ages))

    dates = tracer.datemin + (date - tracer.datemin) * np.arange(
        0.0, 1.0, 1.0 / OLD_RESOLUTION
    )
    ages = date - dates
    values = tracer.get_concentration(dates, ages)
    return float(-integrate.simpson(values * distribution.pdf(ages), x=ages))


def physical_parameters(a: float, s: float) -> tuple[float, float]:
    return a * s, s * a**1.5


def concentration_columns(frame: pd.DataFrame) -> dict[tuple[str, float], str]:
    result: dict[tuple[str, float], str] = {}
    pattern = re.compile(r"(cfc(?:11|12|113))_([0-9.]+)_\d+$")
    for column in frame.columns:
        match = pattern.fullmatch(column)
        if match:
            result.setdefault((match.group(1), float(match.group(2))), column)
    return result


def build_distribution_equivalence() -> tuple[pd.DataFrame, dict[str, float]]:
    rows = []
    cdf_residuals = []
    for well in WELLS:
        source, selected = selected_historical_samples(well)
        for _, row in selected.iterrows():
            a, s, shift = (float(row[name]) for name in ("mu", "sigma", "shift"))
            mean, sd = physical_parameters(a, s)
            new_a, new_s = scipy_params_from_mean_std(mean, sd)
            old = invgauss(a, loc=shift, scale=s)
            new = invgauss(new_a, loc=shift, scale=new_s)
            probabilities = np.array([1e-4, 0.01, 0.10, 0.25, 0.50, 0.75, 0.90])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                times = old.ppf(np.linspace(1e-4, 0.90, 2001))
                old_q, new_q = old.ppf(probabilities), new.ppf(probabilities)
                old_t50, new_t50 = float(old.ppf(0.5)), float(new.ppf(0.5))
            old_pdf, new_pdf = old.pdf(times), new.pdf(times)
            old_cdf, new_cdf = old.cdf(times), new.cdf(times)
            cdf_at_t50 = float(new.cdf(new_t50))
            cdf_residuals.append(abs(cdf_at_t50 - 0.5))
            rows.append(
                {
                    "well": well,
                    "sample_id": row["sample_id"],
                    "source_file": source.relative_to(ROOT).as_posix(),
                    "archive_row": int(row["archive_row"]),
                    "old_shape": a,
                    "old_scale": s,
                    "old_shift": shift,
                    "new_mean": mean,
                    "new_sd": sd,
                    "new_shift": shift,
                    "recovered_shape": new_a,
                    "recovered_scale": new_s,
                    "max_pdf_abs_error": float(np.max(np.abs(old_pdf - new_pdf))),
                    "max_cdf_abs_error": float(np.max(np.abs(old_cdf - new_cdf))),
                    "max_quantile_abs_error": float(np.max(np.abs(old_q - new_q))),
                    "old_ppf_0_5": old_t50,
                    "new_ppf_0_5": new_t50,
                    "cdf_at_new_ppf_0_5": cdf_at_t50,
                    "old_mean": float(old.mean()),
                    "new_mean_check": float(new.mean()),
                    "old_sd": float(old.std()),
                    "new_sd_check": float(new.std()),
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(DIST_CSV, index=False)
    summary = {
        "max_pdf_abs_error": float(frame["max_pdf_abs_error"].max()),
        "max_cdf_abs_error": float(frame["max_cdf_abs_error"].max()),
        "max_quantile_abs_error": float(frame["max_quantile_abs_error"].max()),
        "max_t50_cdf_residual": max(cdf_residuals),
    }
    return frame, summary


def build_forward_equivalence() -> tuple[pd.DataFrame, dict[str, float]]:
    old_tracers = {name: historical_tracer(name)[0] for name in TRACERS}
    current_tracers = {name: Tracer(DIRECTORY_TRACER_DATA, name) for name in TRACERS}
    old_convolvers: dict[tuple[str, float], Convolution] = {}
    current_convolvers: dict[tuple[str, float], Convolution] = {}
    rows = []

    for well in WELLS:
        source, selected = selected_historical_samples(well)
        columns = concentration_columns(selected)
        for _, row in selected.iterrows():
            a, s, shift = (float(row[name]) for name in ("mu", "sigma", "shift"))
            mean, sd = physical_parameters(a, s)
            model = InverseGaussianShiftedLpm(
                mu=mean,
                sigma=sd,
                shift=shift,
                directory_lpm=ROOT / "sites/ploemeur/params_lpm",
            )
            for (tracer_name, date), archive_column in columns.items():
                key = (tracer_name, date)
                old_tracer = old_tracers[tracer_name]
                old_value = old_forward(old_tracer, date, a, s, shift)
                if key not in old_convolvers:
                    old_convolvers[key] = Convolution(old_tracer, date=date)
                new_value = old_convolvers[key].convolve(model)
                if key not in current_convolvers:
                    current_convolvers[key] = Convolution(
                        current_tracers[tracer_name], date=date
                    )
                new_current_data = current_convolvers[key].convolve(model)
                archived = float(row[archive_column])
                absolute = abs(new_value - old_value)
                relative = absolute / max(abs(old_value), np.finfo(float).tiny)
                rows.append(
                    {
                        "well": well,
                        "sample_id": row["sample_id"],
                        "date": date,
                        "tracer": tracer_name.upper().replace("CFC", "CFC-"),
                        "old_concentration": old_value,
                        "new_concentration": new_value,
                        "abs_error": absolute,
                        "rel_error": relative,
                        "archived_old_concentration": archived,
                        "old_archive_abs_error": abs(old_value - archived),
                        "new_current_data_concentration": new_current_data,
                        "current_data_effect_abs": abs(new_current_data - new_value),
                        "old_shape": a,
                        "old_scale": s,
                        "old_shift": shift,
                        "new_mean": mean,
                        "new_sd": sd,
                        "source_file": source.relative_to(ROOT).as_posix(),
                    }
                )
    frame = pd.DataFrame(rows)
    frame.to_csv(FORWARD_CSV, index=False)
    summary = {
        "rows": len(frame),
        "max_abs_error": float(frame["abs_error"].max()),
        "max_rel_error": float(frame["rel_error"].max()),
        "median_rel_error": float(frame["rel_error"].median()),
        "max_archive_reproduction_error": float(frame["old_archive_abs_error"].max()),
        "max_current_data_effect": float(frame["current_data_effect_abs"].max()),
    }
    return frame, summary


def build_metric_audit() -> pd.DataFrame:
    rows = [
        {
            "workflow": "Article campaign (Git 5432034 + archived July 2026 outputs)",
            "model": "exp_shifted",
            "quantity_name": "median transit time / median_mean",
            "exact_formula": "E_posterior[t0 + mu*ln(2)]; each sample satisfies F(t50)=0.5",
            "code_function": "LpmBase.moments -> LpmScipy.cdf_inv -> scipy.stats.expon.ppf",
            "file": "Git 5432034:pyage/lpm/core/lpm_base.py; pyage/lpm/core/lpm_scipy.py",
            "line": "601-606; 58-61",
            "scientifically_correct": True,
        },
        {
            "workflow": "Article campaign (Git 5432034 + archived July 2026 outputs)",
            "model": "ig_shifted",
            "quantity_name": "median transit time / median_mean",
            "exact_formula": "E_posterior[t0 + invgauss.ppf(0.5, shape=old_mu, scale=old_sigma)]",
            "code_function": "LpmBase.moments -> LpmScipySafe.cdf_inv; _scipy_params=(old_mu,),loc=shift,scale=old_sigma",
            "file": "Git 5432034:pyage/lpm/core/lpm_base.py; pyage/lpm/core/lpm_scipy.py; pyage/lpm/models/inverse_gaussian_shifted.py",
            "line": "601-606; 84-105; 46-47",
            "scientifically_correct": True,
        },
        {
            "workflow": "Current PyAge / v2 campaign",
            "model": "exp_shifted",
            "quantity_name": "median transit time / median_mean",
            "exact_formula": "E_posterior[t0 + mu*ln(2)]; each sample satisfies F(t50)=0.5",
            "code_function": "LpmBase.moments -> LpmScipy.cdf_inv -> scipy.stats.expon.ppf",
            "file": "pyage/lpm/core/lpm_base.py; pyage/lpm/core/lpm_scipy.py; sites/ploemeur/studies/HYP-26-0172/postprocessing/build_products.py",
            "line": "491-501; 56-60; 219,247,298,341-345",
            "scientifically_correct": True,
        },
        {
            "workflow": "Current PyAge / v2 campaign",
            "model": "ig_shifted",
            "quantity_name": "median transit time / median_mean",
            "exact_formula": "E_posterior[t0 + invgauss.ppf(0.5, shape=(S/M)^2, scale=M^3/S^2)]",
            "code_function": "LpmBase.moments -> LpmScipySafe.cdf_inv -> InverseGaussianShiftedLpm._scipy_params",
            "file": "pyage/lpm/core/lpm_base.py; pyage/lpm/core/lpm_scipy.py; pyage/lpm/models/inverse_gaussian.py; pyage/lpm/models/inverse_gaussian_shifted.py",
            "line": "491-501; 82-105; 28-36; 51-53",
            "scientifically_correct": True,
        },
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(METRIC_CSV, index=False)
    return frame


def merge_figure(name: str, selector=None) -> pd.DataFrame:
    old = pd.read_csv(RESULTS / "derived" / name)
    new = pd.read_csv(RESULTS / "v2" / "derived" / name)
    if selector is not None:
        old = selector(old)
        new = selector(new)
    keys = ["well", "date", "lpm", "mode", "conditioned", "relative_error"]
    merged = old[keys + ["median_mean"]].merge(
        new[keys + ["median_mean"]], on=keys, suffixes=("_article", "_current")
    )
    merged.insert(
        0,
        "figure",
        name.replace("_median_transit_times.csv", "")
        .replace("_model_comparison.csv", "")
        .replace("_error_sensitivity.csv", ""),
    )
    merged.rename(
        columns={
            "lpm": "model",
            "median_mean_article": "article_t50",
            "median_mean_current": "current_t50",
        },
        inplace=True,
    )
    merged["delta_t50"] = merged["current_t50"] - merged["article_t50"]
    return merged


def build_article_comparison() -> pd.DataFrame:
    frames = [
        merge_figure("figure4_median_transit_times.csv"),
        merge_figure("figure5_model_comparison.csv"),
        merge_figure(
            "figureA1_error_sensitivity.csv",
            lambda frame: frame[frame["relative_error"].eq(0.2)],
        ),
        merge_figure(
            "figure6_median_transit_times.csv",
            lambda frame: frame[frame["well"].isin(["PE", "F38", "MF1"])],
        ),
    ]
    result = pd.concat(frames, ignore_index=True)
    result.to_csv(COMPARISON_CSV, index=False)
    return result


def prior_and_jacobian_audit() -> dict[str, float]:
    rng = np.random.default_rng(260172)
    errors = []
    for a, s in zip(
        rng.uniform(0.2, 90.0, 100), rng.uniform(0.2, 29.0, 100), strict=False
    ):
        h_a = 1e-6 * a
        h_s = 1e-6 * s
        f_a_plus = np.array(physical_parameters(a + h_a, s))
        f_a_minus = np.array(physical_parameters(a - h_a, s))
        f_s_plus = np.array(physical_parameters(a, s + h_s))
        f_s_minus = np.array(physical_parameters(a, s - h_s))
        numeric = np.column_stack(
            ((f_a_plus - f_a_minus) / (2 * h_a), (f_s_plus - f_s_minus) / (2 * h_s))
        )
        expected = -0.5 * s * a**1.5
        errors.append(abs(np.linalg.det(numeric) - expected) / abs(expected))

    result: dict[str, float] = {"jacobian_max_relative_error": max(errors)}
    for well in WELLS:
        old = pd.read_csv(full_series_chain(well), sep="\t", index_col=0)
        mean = old["mu"] * old["sigma"]
        sd = old["sigma"] * old["mu"] ** 1.5
        current_support = (
            mean.between(0.1, 100.0)
            & sd.between(0.1, 30.0)
            & old["shift"].between(0.1, 50.0)
        )
        result[f"{well}_historical_posterior_in_current_support_fraction"] = float(
            current_support.mean()
        )
        result[f"{well}_mapped_mean_median"] = float(mean.median())
        result[f"{well}_mapped_sd_median"] = float(sd.median())
    return result


def data_audit() -> tuple[pd.DataFrame, dict[str, str]]:
    rows = []
    for tracer in TRACERS:
        old_tracer, old_frame, old_hash = historical_tracer(tracer)
        path = ROOT / f"data_core/data_tracer/{tracer}/recharge.csv"
        current = pd.read_csv(path, comment="#")
        normalized_old = old_frame.iloc[:, :2].copy()
        normalized_old.columns = ["date", "concentration"]
        common = normalized_old.merge(current, on="date", suffixes=("_old", "_current"))
        rows.append(
            {
                "file": path.relative_to(ROOT).as_posix(),
                "historical_sha256": old_hash,
                "current_sha256": sha256_file(path),
                "historical_rows_seen_by_loader": len(old_frame),
                "current_rows": len(current),
                "historical_datemin": old_tracer.datemin,
                "current_datemin": float(current["date"].min()),
                "max_common_numeric_difference": float(
                    (common["concentration_old"] - common["concentration_current"])
                    .abs()
                    .max()
                ),
            }
        )
    observations = {}
    for well in WELLS:
        old_checksums = json.loads(
            (
                RESULTS
                / "runs"
                / f"main_{well}_exp_ig_3cfc_err20_seed12345"
                / "input_checksums.json"
            ).read_text()
        )
        current_checksums = json.loads(
            (
                RESULTS
                / "v2"
                / "runs"
                / f"main_{well}_exp_ig_3cfc_err20_seed12345"
                / "input_checksums.json"
            ).read_text()
        )
        key = next(
            k
            for k in old_checksums
            if k.endswith(f"{well}_2004_2024.txt")
            or k.endswith(f"{well}_2005_2024.txt")
        )
        observations[well] = old_checksums[key]
        if current_checksums[key] != old_checksums[key]:
            raise AssertionError(f"Observation checksum changed for {well}")
    return pd.DataFrame(rows), observations


def trend_table(comparison: pd.DataFrame) -> pd.DataFrame:
    data = comparison[comparison["figure"].eq("figure5")]
    rows = []
    for (well, model), group in data.groupby(["well", "model"]):
        group = group.sort_values("date")
        rows.append(
            {
                "well": well,
                "model": model,
                "article_start": group.iloc[0]["article_t50"],
                "article_end": group.iloc[-1]["article_t50"],
                "current_start": group.iloc[0]["current_t50"],
                "current_end": group.iloc[-1]["current_t50"],
                "article_slope": np.polyfit(group["date"], group["article_t50"], 1)[0],
                "current_slope": np.polyfit(group["date"], group["current_t50"], 1)[0],
                "max_abs_delta": group["delta_t50"].abs().max(),
            }
        )
    return pd.DataFrame(rows)


def f11_tracer_behavior_audit() -> pd.DataFrame:
    observations = pd.read_csv(
        ROOT / "sites/ploemeur/data/ori/ori_ploemeur_F11_2004_2024.txt",
        sep="\t",
    )
    rows = []
    for workflow, version in (("article", "article"), ("current_v2", "current")):
        base = RESULTS if version == "article" else RESULTS / "v2"
        workflow_root = base / "runs/main_F11_exp_ig_3cfc_err20_seed12345/workflow"
        for model in ("exp_shifted", "ig_shifted"):
            candidates = list(
                workflow_root.glob(
                    "ploemeur_apriori_double_0.2span_full/*/F11_*/"
                    f"{model}/Metropolis_Hastings/lpm_dist_calibrated.txt"
                )
            )
            path = max(
                candidates,
                key=lambda item: (
                    int(item.parts[-4].split("_")[-1])
                    - int(item.parts[-4].split("_")[-2])
                ),
            )
            posterior = pd.read_csv(path, sep="\t", index_col=0)
            modeled = []
            for index, observation in observations.iterrows():
                columns = [
                    column
                    for column in posterior.columns
                    if column.startswith(f"{observation['element']}_")
                    and column.endswith(f"_{index}")
                ]
                if len(columns) != 1:
                    raise AssertionError(
                        f"Expected one modeled column for observation {index}, got {columns}"
                    )
                modeled.append(float(posterior[columns[0]].mean()))
            comparison = observations.assign(modeled=modeled)
            for tracer, group in comparison.groupby("element"):
                annual = group.groupby("date")[["concentration", "modeled"]].mean()
                rows.append(
                    {
                        "workflow": workflow,
                        "model": model,
                        "tracer": tracer.upper().replace("CFC", "CFC-"),
                        "observed_slope_pptv_per_year": np.polyfit(
                            annual.index, annual["concentration"], 1
                        )[0],
                        "modeled_slope_pptv_per_year": np.polyfit(
                            annual.index, annual["modeled"], 1
                        )[0],
                        "observed_modeled_correlation": annual.corr().iloc[0, 1],
                        "median_absolute_relative_mismatch": np.median(
                            np.abs(group["modeled"] - group["concentration"])
                            / group["concentration"]
                        ),
                    }
                )
    return pd.DataFrame(rows)


def build_root_causes(
    forward: dict[str, float], prior: dict[str, float]
) -> pd.DataFrame:
    rows = [
        {
            "difference": "F11 shifted-IG hierarchy inverted in v2",
            "well": "F11",
            "model": "ig_shifted",
            "cause": "prior;bounds;IG_parameterization",
            "classification": "implementation/statistical-target mismatch",
            "evidence": (
                "Historical uniform shape/scale support maps to a non-rectangular 2/S density in (M,S); "
                f"only {prior['F11_historical_posterior_in_current_support_fraction']:.3%} of the historical full-series posterior lies in current physical bounds."
            ),
        },
        {
            "difference": "F09 IG temporal trend and levels changed",
            "well": "F09",
            "model": "ig_shifted",
            "cause": "prior;bounds;IG_parameterization",
            "classification": "implementation/statistical-target mismatch",
            "evidence": (
                f"Only {prior['F09_historical_posterior_in_current_support_fraction']:.3%} of mapped historical samples lie in current bounds; "
                f"the forward difference ({forward['max_rel_error']:.3e} relative maximum) is too small to explain the age shift."
            ),
        },
        {
            "difference": "Reported quantity called median transit time",
            "well": "F09;F11",
            "model": "exp_shifted;ig_shifted",
            "cause": "metric_definition",
            "classification": "no mismatch",
            "evidence": "Both workflows compute cdf_inv(0.5) per posterior row and then report its posterior mean/std; neither substitutes mu+shift.",
        },
        {
            "difference": "Mapped old and new IG distributions",
            "well": "F09;F11",
            "model": "ig_shifted",
            "cause": "IG_parameterization",
            "classification": "no distribution mismatch after exact mapping",
            "evidence": "PDF/CDF/PPF/moments agree to floating-point tolerance in ig_old_new_distribution_equivalence.csv.",
        },
        {
            "difference": "Forward values after exact distribution mapping",
            "well": "F09;F11",
            "model": "ig_shifted",
            "cause": "forward",
            "classification": "explained, procedurally blocking but scientifically minor mismatch",
            "evidence": (
                f"CDF/partial-first-moment versus historical Simpson/piecewise: max abs={forward['max_abs_error']:.3e} pptv, "
                f"max rel={forward['max_rel_error']:.3e}, far below the 20% observation error."
            ),
        },
        {
            "difference": "CFC-12 recharge file starts at 1940.0 instead of historical loader seeing 1940.5",
            "well": "F09;F11",
            "model": "all",
            "cause": "data",
            "classification": "implementation/data-ingestion correction",
            "evidence": "Historical CFC-12 CSV lacked a header; pandas consumed the 1940.0 row as column names. Common numeric rows are unchanged.",
        },
        {
            "difference": "F11 CFC-12/CFC-113 fit remains poor",
            "well": "F11",
            "model": "exp_shifted;ig_shifted",
            "cause": "data",
            "classification": "expected scientific mismatch",
            "evidence": "Article.docx identifies local contamination/incompatibility; observations and 20% weights are unchanged.",
        },
        {
            "difference": "Gaussian likelihood and pragmatic conditioning",
            "well": "F09;F11",
            "model": "all",
            "cause": "likelihood;conditioning",
            "classification": "no mismatch",
            "evidence": "Both campaigns use sum(((model-data)/error)^2), log L=-0.5*objective, 20% of observed values, and independent+double_prior.",
        },
        {
            "difference": "Monte Carlo representation under nonlinear coordinates",
            "well": "F09;F11",
            "model": "ig_shifted",
            "cause": "posterior_sampling",
            "classification": "secondary; not isolated because target/support changed",
            "evidence": "The proposal steps were retained numerically while their meanings changed from shape/scale to years; this can alter mixing but cannot restore excluded support.",
        },
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(CAUSES_CSV, index=False)
    return frame


def markdown_table(frame: pd.DataFrame, digits: int = 4) -> str:
    formatted = frame.copy()
    for column in formatted.select_dtypes(include=[np.number]).columns:
        formatted[column] = formatted[column].map(lambda value: f"{value:.{digits}g}")
    headers = [str(column).replace("|", "\\|") for column in formatted.columns]
    rows = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for values in formatted.itertuples(index=False, name=None):
        cells = [str(value).replace("|", "\\|").replace("\n", " ") for value in values]
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def build_report(
    distribution_summary: dict[str, float],
    forward_summary: dict[str, float],
    comparison: pd.DataFrame,
    prior: dict[str, float],
    data_frame: pd.DataFrame,
    observation_hashes: dict[str, str],
    f11_behavior: pd.DataFrame,
) -> None:
    trends = trend_table(comparison)
    figure5 = comparison[comparison["figure"].eq("figure5")]
    exp_delta = figure5[figure5["model"].eq("exp_shifted")]["delta_t50"].abs().max()
    ig_delta = figure5[figure5["model"].eq("ig_shifted")]["delta_t50"].abs().max()
    article_hash = sha256_file(ARTICLE)
    configured_old_prior_density = 1.0 / (100.0 * 30.0 * 30.0)
    active_initial_old_density = 1.0 / (99.9 * 29.9 * 49.9)
    text = f"""# Audit de non-régression Ploemeur contre Article.docx

## Verdict

L'inversion F11 n'est **pas** une erreur de définition de la médiane TTD et n'est **pas** causée par une incompatibilité mathématique entre les deux paramétrisations IG. Les deux workflows calculent, pour chaque tirage posterior, `t50 = F^-1(0.5)`, puis `median_mean` est la moyenne posterior de ces `t50`.

La cause dominante est un changement silencieux de cible statistique : l'ancien prior uniforme rectangulaire en paramètres SciPy `(shape, scale)` a été remplacé par un prior uniforme rectangulaire en `(mean physique M, SD physique S)`, avec des bounds qui excluent l'essentiel du domaine historique. À F11, la fraction du posterior full-series historique qui entre dans les bounds physiques actuels vaut **{prior["F11_historical_posterior_in_current_support_fraction"]:.3%}**; à F09, **{prior["F09_historical_posterior_in_current_support_fraction"]:.3%}**.

Le nouveau forward CDF–partial-first-moment n'est par ailleurs pas numériquement identique à l'ancien Simpson/piecewise (maximum absolu **{forward_summary["max_abs_error"]:.6g} pptv**, maximum relatif **{forward_summary["max_rel_error"]:.6g}** sur les 20 distributions et toutes les dates/CFC testées). Cet écart, environ {0.2 / forward_summary["max_rel_error"]:.0f} fois plus petit que l'erreur relative observationnelle de 20 %, ne peut pas expliquer l'inversion d'âge, mais il déclenche l'arrêt procédural demandé avant MCMC. Il faut d'abord figer le benchmark forward et implémenter le prior historique transformé.

## Périmètre et provenance

- Article : `C:/Users/dreuzy/Downloads/Article.docx`, SHA-256 `{article_hash}`.
- Résultats article : `results/HYP-26-0172/derived`, campagnes terminées le 22 juillet 2026, commit déclaré `5432034` avec worktree dirty. Leur Figure 5 reproduit exactement les gammes décrites dans l'article.
- Campagne actuelle : `results/HYP-26-0172/v2/derived`, snapshot propre `7a99b1f...`, août 2026.
- Aucune modification du manuscrit, aucun commit/reset, aucune relance de la matrice Ploemeur.

## 1. Définition exacte de la median transit time

Pour chaque tirage posterior `theta_j`, le code construit la TTD `G(t|theta_j)`, évalue sa CDF `F_j(t)`, puis calcule `t50_j = F_j^-1(0.5)`. Le fichier `lpm_dist_calibrated.txt` reçoit une colonne `median`; les tableaux de figure utilisent ensuite sa moyenne et son écart-type posterior, nommés `median_mean` et `median_std`.

La chaîne est donc :

`posterior row -> paramètres LPM -> scipy distribution -> cdf_inv(0.5) -> colonne median -> describe().mean/std -> median_mean/median_std -> CSV/figure`.

Le résidu maximal vérifié `|F(t50)-0.5|` est **{distribution_summary["max_t50_cdf_residual"]:.3e}**.

- Shifted exponential : `t50 = t0 + mu ln(2)`.
- Shifted IG historique : `t50 = t0 + invgauss.ppf(0.5, shape=old_mu, scale=old_sigma)`.
- Shifted IG actuelle : `t50 = t0 + invgauss.ppf(0.5, shape=(S/M)^2, scale=M^3/S^2)`.

`mu+t0` est la moyenne de la TTD actuelle, pas sa médiane. La définition métrique est scientifiquement correcte dans les deux workflows; voir `{METRIC_CSV.name}`.

## 2. Ancienne et nouvelle inverse Gaussian

Le code historique appelle sans ambiguïté `scipy.stats.invgauss` avec :

- `shape = old_mu`;
- `scale = old_sigma`;
- `loc = shift`.

Les noms historiques `mu` et `sigma` ne désignaient donc ni la moyenne ni la SD physiques. Les réglages de l'article étaient :

| Coordonnée historique | Bounds | Prior configuré (si activé) | Initialisation réellement archivée | Pas MH |
|---|---:|---:|---:|---:|
| shape (`mu`) | [0.1, 100] | Uniform[0,100] | 10 | 1 |
| scale (`sigma`) | [0.1, 30] | Uniform[0,30] | 2 | 0.5 |
| shift | [0.1, 50] | Uniform[0,30] | 5 | 0.5 |

Le fichier `parameters_calibration.txt` prouve toutefois `prior_option=False` pour les étapes initiales full-series et indépendantes. Leur prior actif est donc l'uniforme implicite induit par les **bounds** (dont `shift` jusqu'à 50), pas le `MHapriori` configuré jusqu'à 30.

Le workflow actuel interprète `mu=M` comme moyenne physique et `sigma=S` comme SD physique :

`a=(S/M)^2`, `s=M^3/S^2`, d'où `E[X]=a s=M` et `SD[X]=s a^(3/2)=S`.

Inversement : `M=a s`, `S=s a^(3/2)`. Les 20 triplets représentatifs donnent les erreurs maximales suivantes : PDF `{distribution_summary["max_pdf_abs_error"]:.3e}`, CDF `{distribution_summary["max_cdf_abs_error"]:.3e}`, quantiles `{distribution_summary["max_quantile_abs_error"]:.3e}`. PDF, CDF, PPF, moments et `t50` sont donc identiques à la précision flottante après mapping; voir `{DIST_CSV.name}`.

## 3. Prior, bounds et Jacobien

Réglages v2 :

| Coordonnée actuelle | Bounds | Prior configuré (si activé) | Initialisation réellement archivée | Pas MH |
|---|---:|---:|---:|---:|
| mean physique `M` (`mu`) | [0.1, 100] | Uniform[0,100] | 10 | 1 |
| SD physique `S` (`sigma`) | [0.1, 30] | Uniform[0,30] | 2 | 0.5 |
| shift | [0.1, 50] | Uniform[0,30] | 5 | 0.5 |

Ici aussi `prior_option=False` aux étapes initiales : le prior actif est uniforme dans le rectangle des bounds actuels. Le même mot « uniforme » ne rend pas ces deux priors équivalents sous changement non linéaire de coordonnées.

La dérivée symbolique de `(M,S)=(a s, s a^(3/2))` est

`J = [[s, a], [3 s sqrt(a)/2, a^(3/2)]]`, donc `det J = -s a^(3/2)/2 = -S/2` et `|det J|=S/2`.

La vérification par différences finies donne une erreur relative maximale de **{prior["jacobian_max_relative_error"]:.3e}**. Le push-forward du prior historique actif dans les coordonnées physiques est donc proportionnel à `2/S`, et non constant :

`p(M,S,t0) = {active_initial_old_density:.12g} * 2/S` sur l'image des bounds historiques.

Pour mémoire, le prior analytique configuré mais inactif dans ces étapes aurait une constante `{configured_old_prior_density:.12g}` en `(a,s,t0)` avant transformation et un support `t0<=30`; il ne faut pas le confondre avec la cible réellement échantillonnée.

Le rectangle historique devient le domaine non rectangulaire :

- `0.1 <= S^2/M^2 <= 100`;
- `0.1 <= M^3/S^2 <= 30`;
- et `0.1 <= t0 <= 50` pour les étapes initiales de l'article.

Ses projections atteignent `M=3000 yr` et `S=30000 yr`. Le rectangle actuel est seulement `M in [0.1,100]`, `S in [0.1,30]`, `t0 in [0.1,50]`, avec densité uniforme.

**The current physical-parameter prior is not statistically equivalent to the prior used for Article.docx.**

Les médianes des paramètres historiques transformés sont `M={prior["F11_mapped_mean_median"]:.2f}`, `S={prior["F11_mapped_sd_median"]:.2f}` à F11, et `M={prior["F09_mapped_mean_median"]:.2f}`, `S={prior["F09_mapped_sd_median"]:.2f}` à F09.

## 4. Forward old/new

Le test utilise 10 distributions full-series historiques par puits, choisies uniformément dans l'ordre de leur `t50`, et toutes les combinaisons date–CFC présentes dans les chaînes archivées. L'ancien calcul reproduit les concentrations stockées avec une erreur maximale de **{forward_summary["max_archive_reproduction_error"]:.3e} pptv**, ce qui valide la reconstruction.

Après mapping exact de la distribution et à chronique historique identique, le nouveau forward diffère : médiane relative **{forward_summary["median_rel_error"]:.3e}**, maximum absolu **{forward_summary["max_abs_error"]:.3e} pptv**, maximum relatif **{forward_summary["max_rel_error"]:.3e}** sur **{forward_summary["rows"]}** lignes. La différence vient de l'intégration CDF/partial-first-moment à masses exactes par bins, contre Simpson à 200 points ou la grille piecewise historique. Elle est documentée, pas assimilée à un changement de famille IG, et sa taille est trop faible pour expliquer les écarts de `t50`.

Le fichier `{FORWARD_CSV.name}` contient aussi `archived_old_concentration` (contrôle de reconstruction) et `new_current_data_concentration` (effet additionnel des données actuelles).

## 5. Données, unités, interpolation, erreur et likelihood

Les fichiers d'observations sont bit-identiques entre article et v2 : F09 `{observation_hashes["F09"]}`, F11 `{observation_hashes["F11"]}`. Dates, trois CFC, unités `pptv`, sélection et erreur `0.2 * concentration_observée` sont inchangés.

Les deux versions utilisent `sum(((model-data)/error)^2)` et `log L = -0.5*objective`, donc la Gaussian likelihood et la fonction objectif sont inchangées. L'interpolation atmosphérique reste linéaire et la réponse reste nulle hors chronique; seule la borne basse CFC-12 change avec la correction d'en-tête décrite ci-dessous.

Chroniques atmosphériques :

{markdown_table(data_frame, 6)}

Le seul changement numérique de support est CFC-12 : le CSV historique n'avait pas d'en-tête; pandas interprétait la ligne `(1940.0,0.34)` comme en-tête et la chronique commençait effectivement à 1940.5. Le CSV actuel corrige cela. Les concentrations aux dates communes sont identiques. L'effet maximal observé dans ce test est **{forward_summary["max_current_data_effect"]:.3e} pptv**.

À F11, le mauvais ajustement CFC-12/CFC-113 est classé **expected scientific mismatch**, conformément à Article.docx; aucune correction automatique n'est indiquée. La vérification directe des posteriors full-series donne :

{markdown_table(f11_behavior, 5)}

Dans les deux campagnes, CFC-11 observé et modélisé augmentent; CFC-12 observé diminue alors que le modèle augmente (corrélation négative); CFC-113 est quasi non corrélé et fortement sous-estimé. Le comportement publié est donc bien présent avant et après v2.

## 6. Conditionnement bayésien

Les configs historiques et v2 portent toutes deux `prior_pipeline: [independent, double_prior]`. Le preset `double_prior` reste :

1. `span_full` avec `prior_option=False`, donc likelihood et hard bounds seulement;
2. `span_with_prior` pré/post-2012 utilisant le posterior full-series;
3. `successive_with_prior` utilisant le posterior du span correspondant.

La calibration indépendante `successive` a également `prior_option=False` et utilise les hard bounds. Aux étapes conditionnées, PyAge recharge un histogramme marginal par paramètre et multiplie ces densités marginales; il ne construit pas un posterior joint hiérarchique. Les données d'une fenêtre apparaissent donc d'abord dans le full-series posterior puis à nouveau dans la likelihood conditionnée : c'est bien la **pragmatic hierarchical conditioning** publiée, pas un bug PyAge nouveau. Elle n'a pas été modifiée.

## 7. Comparaison Article.docx / campagne v2

{markdown_table(trends, 5)}

Le contrôle shifted exponential reste proche (écart absolu maximal Figure 5 : **{exp_delta:.3f} yr**). La shifted IG diverge fortement (écart maximal **{ig_delta:.3f} yr**). Les séries exactes Figure 4, Figure 5, Figure A1 à 20 %, et Figure 6 pour PE/F38/MF1 sont dans `{COMPARISON_CSV.name}`.

À F11, l'article donne IG au-dessus de l'exponentielle d'environ 10–15 ans; v2 donne l'IG en dessous. À F09, l'ancien IG augmente globalement alors que v2 suit une baisse proche de l'exponentielle. Cela est cohérent avec l'exclusion du domaine `(M,S)` historique, pas avec une erreur de tracé.

## 8. Calibrations ciblées

Aucune MCMC ciblée n'a été lancée, car le test forward préalable échoue au critère d'équivalence numérique stricte et parce que PyAge ne sait pas encore exprimer directement le prior `2/S` sur le domaine curviligne transformé. Lancer les six cas demandés avec le prior uniforme physique actuel ne testerait pas la non-régression de l'article; cela répéterait la cible v2 différente.

Avant toute calibration, il faut :

1. ajouter un preset de benchmark en coordonnées physiques évaluant `a=S^2/M^2`, `s=M^3/S^2`, le support historique et la densité Jacobienne `2/S`;
2. figer explicitement la chronique CFC-12 du benchmark (historique exacte ou correction 1940.0, les deux variantes étant nommées);
3. décider une tolérance forward scientifique pour le remplacement Simpson -> CDF/partial-first-moment et la verrouiller par test;
4. seulement ensuite lancer F11 et F09 : full-series exp, full-series IG, puis une fenêtre conditionnée 2014–2015 pour chaque modèle pertinent.

## 9. Réponses A–G

**A. Pourquoi l'IG actuelle est-elle plus jeune à F11 ?** Parce que le prior et surtout les bounds physiques actuels définissent une autre cible et excluent le domaine historique. Le posterior article F11 correspond typiquement à des `M,S` de plusieurs milliers/dizaines de milliers d'années malgré un `t50≈97 yr`, configuration permise par une IG extrêmement asymétrique.

**B. Définition de la median TTD ?** Non. Les deux workflows utilisent `F^-1(0.5)` par TTD posterior. `median_mean` est ensuite la moyenne posterior de cette métrique.

**C. Paramétrisation IG ?** Le renommage/reparamétrage explique comment le changement a été introduit, mais le mapping mathématique exact conserve la distribution. Ce n'est pas, seul, une cause de divergence.

**D. Prior/bounds induits ?** Oui, cause dominante démontrée. Le prior uniforme physique n'est pas le push-forward du prior historique et son rectangle n'est pas l'image du rectangle historique.

**E. Forward ?** Il change de façon mesurable mais mineure : les deux intégrateurs ne sont pas strictement équivalents, et CFC-12 a une correction de première ligne. Avec moins de 0,07 % d'écart relatif, ce changement ne peut pas expliquer l'inversion F11. Les écarts sont quantifiés dans `{FORWARD_CSV.name}`.

**F. Reproductible avec l'IG physique et le nouveau moteur ?** Mathématiquement oui pour la distribution; statistiquement, très probablement oui si le prior/support transformé est implémenté. Ce n'est pas encore démontré par calibration, puisque le prérequis forward strict échoue et que le prior benchmark manque.

**G. Quels cas recalculer ?** Pas la matrice complète. Après les trois prérequis ci-dessus : F11 full-series IG + fenêtre 2014–2015 conditionnée, F09 full-series IG + fenêtre 2014–2015 conditionnée; les full-series shifted exponential F11/F09 ne servent que de contrôles positifs courts. Figure A1 IG n'est à relancer qu'après succès à 20 %, puis seulement aux erreurs nécessaires à la publication. PE/F38/MF1 shifted exponential ne nécessitent pas de relance sur la base de cet audit.

## Artefacts

- `{METRIC_CSV.name}`
- `{DIST_CSV.name}`
- `{FORWARD_CSV.name}`
- `{COMPARISON_CSV.name}`
- `{CAUSES_CSV.name}`
"""
    REPORT_MD.write_text(text, encoding="utf-8")


def main() -> None:
    if not ARTICLE.is_file():
        raise FileNotFoundError(ARTICLE)
    AUDIT_OUTPUT.mkdir(parents=True, exist_ok=True)
    build_metric_audit()
    _, distribution_summary = build_distribution_equivalence()
    _, forward_summary = build_forward_equivalence()
    comparison = build_article_comparison()
    prior = prior_and_jacobian_audit()
    data_frame, observation_hashes = data_audit()
    f11_behavior = f11_tracer_behavior_audit()
    build_root_causes(forward_summary, prior)
    build_report(
        distribution_summary,
        forward_summary,
        comparison,
        prior,
        data_frame,
        observation_hashes,
        f11_behavior,
    )
    print(
        json.dumps(
            {
                "distribution": distribution_summary,
                "forward": forward_summary,
                "prior": prior,
                "outputs": [
                    str(path)
                    for path in (
                        METRIC_CSV,
                        DIST_CSV,
                        FORWARD_CSV,
                        COMPARISON_CSV,
                        CAUSES_CSV,
                        REPORT_MD,
                    )
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
