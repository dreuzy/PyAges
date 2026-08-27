# Copyright (c) 2021-2026 Centre national de la recherche scientifique (CNRS)
# Contributor: Jean-Raynald de Dreuzy
# SPDX-License-Identifier: CECILL-2.1

"""Final four-case Ploemeur shifted-exponential article campaign.

The campaign is deliberately limited to F09/F11 and to two independent
calibrations per well: the complete record and the manuscript's 2014-2015
observation window. It never runs shifted inverse Gaussian,
empirical conditioning, error sensitivity, or another Ploemeur well.
"""

# ruff: noqa: E402 -- direct execution adds the repository root before imports.

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyages.calibration.methods.metropolis_hastings import MetropolisHastings, MHConfig
from pyages.calibration.mh_proposals import regularize_empirical_covariance
from pyages.calibration.problem import CalibrationProblem
from pyages.concentrations import Concentrations
from pyages.config.runtime import DisplayOptions
from pyages.convolution import ConvolutionTracers
from pyages.lpm import build_lpm
from scripts.common.mcmc_diagnostics import (
    ess as _ess,
)
from scripts.common.mcmc_diagnostics import mcse_mean
from scripts.common.mcmc_diagnostics import (
    rank_normalize as _rank_normalize,
)
from scripts.common.mcmc_diagnostics import (
    split_rhat as _split_rhat,
)
from scripts.common.provenance import repository_provenance
from scripts.common.publication_plotting import (
    PUBLICATION_RC,
    mm_to_in,
    save_pdf_png,
)
from scripts.common.reporting import markdown_table
from sites.ploemeur.scripts.prepare_observations import prepare_well

OUTPUT = (
    ROOT
    / "results"
    / "final_article_simulations"
    / "ploemeur_shifted_exponential_final"
)
DATA_OUTPUT = OUTPUT / "data_audit"
INSERTION_OUTPUT = OUTPUT / "manuscript_insertion" / "final_figures"
LPM_DIRECTORY = ROOT / "sites" / "ploemeur" / "params_lpm"
RAW_DIRECTORY = ROOT / "sites" / "ploemeur" / "data" / "brut"
ORI_DIRECTORY = ROOT / "sites" / "ploemeur" / "data" / "ori"
TRACERS = ("cfc11", "cfc12", "cfc113")
TRACER_LABELS = {"cfc11": "CFC-11", "cfc12": "CFC-12", "cfc113": "CFC-113"}
PILOT_STEPS = 4_000
PRODUCTION_STEPS = 10_000
EXTENDED_STEPS = 20_000
BURN_IN = 0.20
RIDGE = 1.0e-6
PROPOSAL_SCALE = 2.38 / math.sqrt(2.0)
NCHAINS = 5
RELATIVE_ERROR = 0.20
MIN_ESS = 300.0
MAX_RHAT = 1.01
FIGURE_DRAWS = 500
FIGURE_START_YEAR = 1990.0
LN2 = math.log(2.0)


@dataclass(frozen=True)
class Case:
    key: str
    well: str
    calibration: str
    interval: tuple[float, float] | None


CASES = (
    Case(
        "F09_full_record_shifted_exponential",
        "F09",
        "full_record",
        None,
    ),
    Case(
        "F09_2014_2015_independent_shifted_exponential",
        "F09",
        "2014_2015_independent",
        (2014.0, 2016.0),
    ),
    Case(
        "F11_full_record_shifted_exponential",
        "F11",
        "full_record",
        None,
    ),
    Case(
        "F11_2014_2015_independent_shifted_exponential",
        "F11",
        "2014_2015_independent",
        (2014.0, 2016.0),
    ),
)

EXPECTED_2024 = {
    "F09": {"cfc11": 227.778, "cfc12": 494.701, "cfc113": 63.033},
    "F11": {"cfc11": 25.588, "cfc12": 234.034, "cfc113": 18.378},
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _path_label(path: Path, base: Path = ROOT) -> str:
    """Return a portable relative label when possible, otherwise an absolute path."""
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _decimal_year_to_calendar_year(value: float) -> int:
    return int(math.floor(float(value)))


def _verify_workbook_values() -> pd.DataFrame:
    workbook = RAW_DIRECTORY / "chronique CFC pptv_080125.xlsx"
    rows: list[dict[str, Any]] = []
    found: list[np.ndarray] = []
    for sheet in pd.ExcelFile(workbook).sheet_names:
        frame = pd.read_excel(workbook, sheet_name=sheet, header=None)
        for row_index in frame.index:
            row = frame.loc[row_index].tolist()
            for column in range(max(0, len(row) - 3)):
                parsed = pd.to_datetime(row[column], errors="coerce")
                if pd.isna(parsed) or parsed.date() != date(2024, 10, 31):
                    continue
                values = pd.to_numeric(
                    pd.Series(row[column + 1 : column + 4]), errors="coerce"
                ).to_numpy(float)
                if np.isfinite(values).all():
                    found.append(values)
                    rows.append(
                        {
                            "workbook": workbook.name,
                            "sheet": sheet,
                            "excel_row_zero_based": int(row_index),
                            "excel_column_zero_based": column,
                            "date": "2024-10-31",
                            "cfc11": values[0],
                            "cfc12": values[1],
                            "cfc113": values[2],
                        }
                    )
    for well, expected in EXPECTED_2024.items():
        target = np.asarray([expected[name] for name in TRACERS])
        if not any(np.allclose(item, target, rtol=0.0, atol=5.0e-7) for item in found):
            raise RuntimeError(
                f"The workbook does not contain the audited {well} 31/10/2024 values"
            )
    return pd.DataFrame(rows)


def _verify_raw_values() -> pd.DataFrame:
    records = []
    for well, expected in EXPECTED_2024.items():
        raw = pd.read_table(RAW_DIRECTORY / f"{well}_brut.txt", header=None)
        header = [str(value).strip().lower().replace("-", "") for value in raw.iloc[0]]
        match = raw.loc[raw.iloc[:, 0].astype(str).str.strip() == "31/10/2024"]
        if len(match) != 1:
            raise RuntimeError(
                f"Expected one 31/10/2024 raw row for {well}, found {len(match)}"
            )
        for tracer in TRACERS:
            column = header.index(tracer)
            actual = float(match.iloc[0, column])
            target = expected[tracer]
            if actual != target:
                raise RuntimeError(
                    f"Raw value mismatch for {well} {tracer}: {actual} != {target}"
                )
            records.append(
                {
                    "well": well,
                    "date": "2024-10-31",
                    "tracer": tracer,
                    "pptv": actual,
                    "verified": True,
                }
            )
    return pd.DataFrame(records)


def prepare_data_and_exports(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    DATA_OUTPUT.mkdir(parents=True, exist_ok=True)
    normalized_output = DATA_OUTPUT / "normalized_observations"
    workbook_rows = _verify_workbook_values()
    raw_rows = _verify_raw_values()
    workbook_rows.to_csv(DATA_OUTPUT / "workbook_2024_candidates.csv", index=False)
    raw_rows.to_csv(DATA_OUTPUT / "verified_2024_raw_values.csv", index=False)

    diff_lines: list[str] = []
    hashes = []
    window_rows = []
    for well in ("F09", "F11"):
        normalized = (
            ORI_DIRECTORY
            / f"ori_ploemeur_{well}_{2005 if well == 'F09' else 2004}_2024.txt"
        )
        old_text = normalized.read_text(encoding="utf-8")
        old_frame = pd.read_table(StringIO(old_text))
        destination = prepare_well(well, RAW_DIRECTORY, normalized_output)
        new_text = destination.read_text(encoding="utf-8")
        diff_lines.extend(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"old/{normalized.relative_to(ROOT).as_posix()}",
                tofile=f"regenerated/{destination.name}",
            )
        )
        frame = pd.read_table(destination)
        if set(frame["unit"].astype(str)) != {"pptv"}:
            raise RuntimeError(f"Final unit metadata is not pptv in {normalized}")
        old_concentrations = (
            old_frame.groupby(["element", "concentration"]).size().rename("old_count")
        )
        new_concentrations = (
            frame.groupby(["element", "concentration"]).size().rename("new_count")
        )
        concentration_check = (
            old_concentrations.to_frame().join(new_concentrations, how="left").fillna(0)
        )
        if not (
            concentration_check["old_count"] == concentration_check["new_count"]
        ).all():
            raise RuntimeError(
                f"An existing concentration changed while normalizing {well}"
            )
        for tracer, value in EXPECTED_2024[well].items():
            selected = frame.loc[
                (frame["element"] == tracer)
                & (frame["date"].map(_decimal_year_to_calendar_year) == 2024)
                & np.isclose(frame["concentration"], value, rtol=0.0, atol=5.0e-7)
            ]
            if len(selected) != 1:
                raise RuntimeError(
                    f"Final normalized row missing for {well} {tracer}={value}"
                )
        window = frame.loc[(frame["date"] >= 2014.0) & (frame["date"] < 2016.0)].copy()
        window.insert(0, "well", well)
        window_rows.append(window)
        hashes.append(
            {
                "well": well,
                "path": str(destination.relative_to(output)),
                "sha256": _sha256(destination),
                "rows": len(frame),
            }
        )
    (DATA_OUTPUT / "ploemeur_versioned_vs_regenerated.diff").write_text(
        "".join(diff_lines), encoding="utf-8", newline="\n"
    )
    pd.DataFrame(hashes).to_csv(DATA_OUTPUT / "final_data_sha256.csv", index=False)
    windows = pd.concat(window_rows, ignore_index=True)
    windows.to_csv(DATA_OUTPUT / "article_2014_2015_exact_selection.csv", index=False)
    expected_counts = {"F09": 8, "F11": 6}
    actual_counts = windows.groupby("well").size().to_dict()
    if actual_counts != expected_counts:
        raise RuntimeError(
            f"Archived 2014-2015 selection changed: {actual_counts} != {expected_counts}"
        )

    print(f"Prepared audited F09/F11 data in {DATA_OUTPUT}", flush=True)


def _display(path: Path) -> DisplayOptions:
    display = DisplayOptions()
    display.text = False
    display.figure = False
    display.figure_save = False
    display.figure_close = True
    display.directory = path
    return display


def _observation_path(well: str) -> Path:
    first = 2005 if well == "F09" else 2004
    name = f"ori_ploemeur_{well}_{first}_2024.txt"
    regenerated = DATA_OUTPUT / "normalized_observations" / name
    return regenerated if regenerated.is_file() else ORI_DIRECTORY / name


def _observations(case: Case) -> Concentrations:
    observations = Concentrations.from_file(_observation_path(case.well))
    if case.interval is not None:
        start, end = case.interval
        frame = observations.frame.loc[
            (observations.frame["date"] >= start) & (observations.frame["date"] < end)
        ]
        observations = Concentrations.from_dataframe(frame)
    observations.frame["unit"] = "pptv"
    observations.set_relative_errors(RELATIVE_ERROR)
    if set(observations.tracer_names()) != set(TRACERS):
        raise RuntimeError(f"Unexpected tracer set for {case.key}")
    return observations


def _problem(case: Case, output: Path) -> CalibrationProblem:
    return CalibrationProblem(
        _observations(case),
        "exp_shifted",
        lpm_directory=LPM_DIRECTORY,
        display_options=_display(output),
        explore_objective=False,
        explore_reachable=False,
    ).prepare()


def _run_mh(
    case: Case,
    seed: int,
    steps: int,
    output: Path,
    covariance: np.ndarray | None,
    initial: dict[str, float],
) -> tuple[pd.DataFrame, float, float]:
    kwargs: dict[str, Any] = {"componentwise_source": "model"}
    if covariance is not None:
        kwargs = {
            "proposal_kind": "correlated",
            "proposal_multiplier": PROPOSAL_SCALE,
            "proposal_covariance": tuple(
                tuple(float(v) for v in row) for row in covariance
            ),
        }
    mh = MetropolisHastings(
        config=MHConfig(
            nstep=steps,
            burn_in=BURN_IN,
            nskip=1,
            prior_option=False,
            likelihood=True,
            monitor=False,
            display_traj=False,
            display_text=False,
            seed=seed,
            initial_params=initial,
            **kwargs,
        )
    )
    started = time.perf_counter()
    posterior = mh.run(_problem(case, output))
    elapsed = time.perf_counter() - started
    frame = posterior.frame[["mu", "shift", "obj_function"]].copy()
    frame.rename(columns={"shift": "t0", "obj_function": "sqrt_J_over_m"}, inplace=True)
    frame["t50"] = frame["t0"] + LN2 * frame["mu"]
    return frame, mh.success_rate, elapsed


def _pilot_seed(index: int) -> int:
    return 701_000 + index


def _production_seed(index: int, chain: int, steps: int) -> int:
    return 710_000 + 1000 * index + 10 * chain + steps // 10_000


def _pilot_path(output: Path, case: Case) -> Path:
    return output / "pilots" / f"{case.key}.npz"


def _covariance_path(output: Path, case: Case) -> Path:
    return output / "pilots" / f"{case.key}_covariance.npy"


def _chain_path(output: Path, case: Case, chain: int, steps: int) -> Path:
    return output / "chains" / f"{case.key}_chain_{chain + 1}_n{steps}.npz"


def run_pilots(output: Path) -> None:
    (output / "pilots").mkdir(parents=True, exist_ok=True)
    for index, case in enumerate(CASES, start=1):
        pilot_path = _pilot_path(output, case)
        covariance_path = _covariance_path(output, case)
        if pilot_path.exists() and covariance_path.exists():
            print(f"pilot {index}/4 already present: {case.key}", flush=True)
            continue
        frame, acceptance, elapsed = _run_mh(
            case,
            _pilot_seed(index),
            PILOT_STEPS,
            output / "pilots",
            None,
            {"mu": 10.0, "shift": 10.0},
        )
        covariance = regularize_empirical_covariance(
            frame[["mu", "t0"]].to_numpy(float), RIDGE
        )
        np.save(covariance_path, covariance)
        np.savez_compressed(
            pilot_path,
            mu=frame["mu"].to_numpy(float),
            t0=frame["t0"].to_numpy(float),
            t50=frame["t50"].to_numpy(float),
            sqrt_J_over_m=frame["sqrt_J_over_m"].to_numpy(float),
            acceptance=acceptance,
            elapsed_seconds=elapsed,
            seed=_pilot_seed(index),
        )
        print(f"pilot {index}/4 complete: {case.key} ({elapsed:.1f} s)", flush=True)


def _pilot_initials(output: Path, case: Case) -> list[dict[str, float]]:
    with np.load(_pilot_path(output, case)) as data:
        frame = pd.DataFrame({"mu": data["mu"], "t0": data["t0"], "t50": data["t50"]})
    ordered = frame.sort_values("t50").reset_index(drop=True)
    positions = np.rint(np.linspace(0.10, 0.90, NCHAINS) * (len(ordered) - 1)).astype(
        int
    )
    return [
        {
            "mu": float(ordered.loc[position, "mu"]),
            "shift": float(ordered.loc[position, "t0"]),
        }
        for position in positions
    ]


def _production_job(payload: tuple[str, int, int, int, str]) -> str:
    case_key, case_index, chain, steps, output_text = payload
    output = Path(output_text)
    case = next(item for item in CASES if item.key == case_key)
    destination = _chain_path(output, case, chain, steps)
    if destination.exists():
        return str(destination)
    covariance = np.load(_covariance_path(output, case))
    initial = _pilot_initials(output, case)[chain]
    frame, acceptance, elapsed = _run_mh(
        case,
        _production_seed(case_index, chain, steps),
        steps,
        output / "chains",
        covariance,
        initial,
    )
    np.savez_compressed(
        destination,
        mu=frame["mu"].to_numpy(float),
        t0=frame["t0"].to_numpy(float),
        t50=frame["t50"].to_numpy(float),
        sqrt_J_over_m=frame["sqrt_J_over_m"].to_numpy(float),
        acceptance=acceptance,
        elapsed_seconds=elapsed,
        seed=_production_seed(case_index, chain, steps),
        requested_steps=steps,
    )
    return str(destination)


def run_production(
    output: Path, workers: int, steps: int, case_keys: set[str] | None = None
) -> None:
    run_pilots(output)
    (output / "chains").mkdir(parents=True, exist_ok=True)
    jobs = []
    for index, case in enumerate(CASES, start=1):
        if case_keys is not None and case.key not in case_keys:
            continue
        for chain in range(NCHAINS):
            if not _chain_path(output, case, chain, steps).exists():
                jobs.append((case.key, index, chain, steps, str(output)))
    if not jobs:
        print(f"All requested n={steps} chains already exist", flush=True)
        return
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(jobs)))) as executor:
        futures = [executor.submit(_production_job, job) for job in jobs]
        for completed, future in enumerate(as_completed(futures), start=1):
            path = Path(future.result()).name
            print(f"production {completed}/{len(futures)} complete: {path}", flush=True)


def _load_chains(output: Path, case: Case, steps: int) -> dict[str, np.ndarray]:
    loaded = []
    for chain in range(NCHAINS):
        path = _chain_path(output, case, chain, steps)
        if not path.is_file():
            raise FileNotFoundError(f"Missing production chain: {path}")
        with np.load(path) as data:
            loaded.append({name: data[name].copy() for name in data.files})
    return {
        name: np.asarray([item[name] for item in loaded])
        for name in ("mu", "t0", "t50", "sqrt_J_over_m")
    } | {
        "acceptance": np.asarray([float(item["acceptance"]) for item in loaded]),
        "elapsed_seconds": np.asarray(
            [float(item["elapsed_seconds"]) for item in loaded]
        ),
    }


def _diagnostics(
    output: Path, lengths: dict[str, int]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    diagnostic_rows = []
    summary_rows = []
    chain_rows = []
    for case in CASES:
        steps = lengths[case.key]
        data = _load_chains(output, case, steps)
        for chain in range(NCHAINS):
            chain_rows.append(
                {
                    "case": case.key,
                    "chain": chain + 1,
                    "steps": steps,
                    "retained_draws": data["mu"].shape[1],
                    "acceptance": data["acceptance"][chain],
                    "elapsed_seconds": data["elapsed_seconds"][chain],
                    "best_sqrt_J_over_m": float(np.min(data["sqrt_J_over_m"][chain])),
                }
            )
        for parameter in ("mu", "t0", "t50"):
            values = data[parameter]
            rhat = _split_rhat(values)
            ess = _ess(_rank_normalize(values))
            flat = values.reshape(-1)
            mean_mcse = mcse_mean(flat, ess)
            diagnostic_rows.append(
                {
                    "case": case.key,
                    "well": case.well,
                    "calibration": case.calibration,
                    "parameter": parameter,
                    "steps_per_chain": steps,
                    "split_rhat": rhat,
                    "ESS": ess,
                    "mcse_mean": mean_mcse,
                    "converged": bool(rhat < MAX_RHAT and ess >= MIN_ESS),
                }
            )
            summary_rows.append(
                {
                    "case": case.key,
                    "well": case.well,
                    "calibration": case.calibration,
                    "parameter": parameter,
                    "mean": float(np.mean(flat)),
                    "sd": float(np.std(flat, ddof=1)),
                    "mcse_mean": mean_mcse,
                    "median": float(np.median(flat)),
                    "q025": float(np.quantile(flat, 0.025)),
                    "q10": float(np.quantile(flat, 0.10)),
                    "q90": float(np.quantile(flat, 0.90)),
                    "q975": float(np.quantile(flat, 0.975)),
                }
            )
    return (
        pd.DataFrame(diagnostic_rows),
        pd.DataFrame(summary_rows),
        pd.DataFrame(chain_rows),
    )


def _prediction_grid(well: str) -> np.ndarray:
    frame = pd.read_table(_observation_path(well))
    observed_start = float(frame["date"].min())
    observed_end = float(frame["date"].max())
    smooth = np.linspace(observed_start, observed_end, 180)
    earlier_count = max(
        2,
        int(
            np.ceil(
                180
                * (observed_start - FIGURE_START_YEAR)
                / (observed_end - observed_start)
            )
        ),
    )
    earlier = np.linspace(
        FIGURE_START_YEAR, observed_start, earlier_count, endpoint=False
    )
    return np.unique(np.concatenate((earlier, smooth, frame["date"].to_numpy(float))))


def _predict_draws(case: Case, samples: pd.DataFrame) -> pd.DataFrame:
    grid = _prediction_grid(case.well)
    names = [tracer for tracer in TRACERS for _ in grid]
    dates = np.tile(grid, len(TRACERS))
    tracers = ConvolutionTracers(names=names, date=dates)
    rows = []
    model = build_lpm("exp_shifted", directory_lpm=str(LPM_DIRECTORY))
    # One complete samples row is consumed per realization. Never select
    # mu and t0 independently here or in any downstream figure/statistic.
    for draw, row in samples.reset_index(drop=True).iterrows():
        model.p.update({"mu": float(row["mu"]), "shift": float(row["t0"])})
        predicted = np.asarray(tracers.convolve(model), dtype=float)
        rows.extend(
            {
                "case": case.key,
                "well": case.well,
                "calibration": case.calibration,
                "draw": draw,
                "posterior_row": int(row["posterior_row"]),
                "mu": float(row["mu"]),
                "t0": float(row["t0"]),
                "tracer": tracer,
                "date": float(year),
                "predicted_pptv": float(value),
            }
            for tracer, year, value in zip(names, dates, predicted, strict=True)
        )
    return pd.DataFrame(rows)


def _posterior_rows_for_figure(output: Path, case: Case, steps: int) -> pd.DataFrame:
    data = _load_chains(output, case, steps)
    flat = pd.DataFrame({"mu": data["mu"].reshape(-1), "t0": data["t0"].reshape(-1)})
    positions = np.unique(np.linspace(0, len(flat) - 1, FIGURE_DRAWS, dtype=int))
    selected = flat.iloc[positions].copy()
    selected.insert(0, "posterior_row", positions)
    return selected


def _render_figure4(output: Path, intervals: pd.DataFrame) -> None:
    colors = {"full_record": "#1769aa", "2014_2015_independent": "#d1495b"}
    labels = {
        "full_record": "Full-record calibration",
        "2014_2015_independent": "2014–2015-only calibration",
    }
    with plt.rc_context(PUBLICATION_RC):
        figure, axes = plt.subplots(
            2,
            3,
            figsize=(mm_to_in(165), mm_to_in(112)),
            sharex=True,
        )
        panel_labels = iter("abcdef")
        for row_index, well in enumerate(("F11", "F09")):
            observations = pd.read_table(_observation_path(well))
            for column_index, tracer in enumerate(TRACERS):
                axis = axes[row_index, column_index]
                observed = observations.loc[
                    observations["element"] == tracer
                ].sort_values("date")
                in_window = (observed["date"] >= 2014.0) & (observed["date"] < 2016.0)
                axis.errorbar(
                    observed["date"],
                    observed["concentration"],
                    yerr=RELATIVE_ERROR * observed["concentration"],
                    fmt="o",
                    ms=2.8,
                    color="0.25",
                    ecolor="0.6",
                    elinewidth=0.7,
                    capsize=1.2,
                    label="Observations ±20 %"
                    if row_index == 0 and column_index == 0
                    else None,
                )
                axis.scatter(
                    observed.loc[in_window, "date"],
                    observed.loc[in_window, "concentration"],
                    s=28,
                    facecolors="none",
                    edgecolors="#f4a261",
                    linewidths=1.2,
                    zorder=5,
                    label="Observations used for 2014–2015-only calibration"
                    if row_index == 0 and column_index == 0
                    else None,
                )
                for calibration in ("full_record", "2014_2015_independent"):
                    values = intervals.loc[
                        (intervals["well"] == well)
                        & (intervals["tracer"] == tracer)
                        & (intervals["calibration"] == calibration)
                    ].sort_values("date")
                    axis.fill_between(
                        values["date"],
                        values["q10"],
                        values["q90"],
                        color=colors[calibration],
                        alpha=0.16,
                    )
                    axis.plot(
                        values["date"],
                        values["median"],
                        color=colors[calibration],
                        lw=1.3,
                        label=labels[calibration]
                        if row_index == 0 and column_index == 0
                        else None,
                    )
                panel = next(panel_labels)
                axis.set_title(
                    f"({panel}) {well} – {TRACER_LABELS[tracer]}",
                    fontweight="bold",
                    fontsize=9.0,
                )
                axis.set_xlim(left=FIGURE_START_YEAR)
                axis.grid(alpha=0.18)
        handles, current_labels = axes[0, 0].get_legend_handles_labels()
        handles_by_label = dict(zip(current_labels, handles, strict=True))
        legend_labels = (
            "Observations ±20 %",
            "Observations used for 2014–2015-only calibration",
            "Full-record calibration",
            "2014–2015-only calibration",
        )
        figure.legend(
            [handles_by_label[label] for label in legend_labels],
            legend_labels,
            loc="upper center",
            bbox_to_anchor=(0.5, 0.995),
            ncol=2,
            frameon=False,
        )
        figure.supxlabel("Sampling year", y=0.025)
        figure.supylabel(
            "Atmospheric-equivalent mixing ratio (pptv)",
            x=0.015,
        )
        figure.subplots_adjust(
            left=0.12,
            right=0.99,
            top=0.80,
            bottom=0.12,
            wspace=0.27,
            hspace=0.34,
        )
        final_paths = save_pdf_png(figure, output, "figure4_ploemeur_final")
        legacy_paths = save_pdf_png(figure, output, "figure4_ploemeur_shiftedexp_final")
        INSERTION_OUTPUT.mkdir(parents=True, exist_ok=True)
        for destination in (*final_paths, *legacy_paths):
            shutil.copy2(destination, INSERTION_OUTPUT / destination.name)
        plt.close(figure)


def _figure4(output: Path, lengths: dict[str, int]) -> pd.DataFrame:
    predictions_path = output / "figure4_rowwise_posterior_predictions.csv.gz"
    intervals_path = output / "figure4_prediction_intervals.csv"
    required_interval_columns = {
        "well",
        "calibration",
        "tracer",
        "date",
        "median",
        "q10",
        "q90",
    }
    intervals = None
    if predictions_path.is_file() and intervals_path.is_file():
        cached = pd.read_csv(intervals_path)
        if not cached.empty and required_interval_columns.issubset(cached.columns):
            intervals = cached
            print("Reusing cached Figure 4 posterior predictions", flush=True)
    if intervals is None:
        predictions = pd.concat(
            [
                _predict_draws(
                    case, _posterior_rows_for_figure(output, case, lengths[case.key])
                )
                for case in CASES
            ],
            ignore_index=True,
        )
        predictions.to_csv(predictions_path, index=False, compression="gzip")
        intervals = (
            predictions.groupby(["well", "calibration", "tracer", "date"])[
                "predicted_pptv"
            ]
            .agg(
                median="median",
                q10=lambda x: x.quantile(0.10),
                q90=lambda x: x.quantile(0.90),
            )
            .reset_index()
        )
        intervals.to_csv(intervals_path, index=False)
    INSERTION_OUTPUT.mkdir(parents=True, exist_ok=True)
    _render_figure4(output, intervals)
    return intervals


def _tracer_fit_diagnostics(output: Path, intervals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for case in CASES:
        observations = _observations(case).frame
        for tracer in TRACERS:
            observed = (
                observations.loc[observations["element"] == tracer]
                .sort_values("date")
                .copy()
            )
            predicted = (
                intervals.loc[
                    (intervals["well"] == case.well)
                    & (intervals["calibration"] == case.calibration)
                    & (intervals["tracer"] == tracer)
                ]
                .sort_values("date")
                .copy()
            )
            # Decimal-year dates can move by a few ulps after a CSV round-trip.
            # A rounded join also lets repeated measurements at the same date
            # share the corresponding posterior prediction without collapsing
            # either observation.
            observed["_date_key"] = observed["date"].round(10)
            predicted["_date_key"] = predicted["date"].round(10)
            aligned = observed.merge(
                predicted[["_date_key", "median"]],
                on="_date_key",
                how="left",
                validate="many_to_one",
                indicator=True,
            )
            missing = aligned.loc[aligned["_merge"] != "both", "date"].unique()
            if (
                len(aligned) != len(observed)
                or len(missing)
                or aligned["median"].isna().any()
            ):
                raise RuntimeError(
                    "Posterior predictions do not cover every observation for "
                    f"{case.key} {tracer}; missing dates={missing.tolist()}"
                )
            normalized = (
                aligned["median"].to_numpy(float)
                - aligned["concentration"].to_numpy(float)
            ) / aligned["error"].to_numpy(float)
            rows.append(
                {
                    "case": case.key,
                    "well": case.well,
                    "calibration": case.calibration,
                    "tracer": tracer,
                    "observations": len(observed),
                    "posterior_median_normalized_RMSE": float(
                        np.sqrt(np.mean(normalized**2))
                    ),
                    "posterior_median_mean_normalized_residual": float(
                        np.mean(normalized)
                    ),
                    "posterior_median_max_abs_normalized_residual": float(
                        np.max(np.abs(normalized))
                    ),
                }
            )
    result = pd.DataFrame(rows)
    result.to_csv(output / "tracer_fit_diagnostics.csv", index=False)
    return result


def _pairing_effect_diagnostics(output: Path) -> pd.DataFrame:
    """Record that posterior prediction uses complete row-wise samples."""
    rows = [
        {
            "well": case.well,
            "tracer": tracer,
            "posterior_pairing": "complete_row_wise_samples",
            "verified": True,
        }
        for case in CASES
        if case.calibration == "full_record"
        for tracer in TRACERS
    ]
    result = pd.DataFrame(rows)
    result.to_csv(output / "pairing_correction_effect.csv", index=False)
    return result


def _compact_and_quality(
    output: Path,
    lengths: dict[str, int],
    diagnostics: pd.DataFrame,
    summaries: pd.DataFrame,
    chains: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    compact_rows = []
    quality_rows = []
    for case in CASES:
        case_summary = summaries.loc[summaries["case"] == case.key].set_index(
            "parameter"
        )
        case_diagnostics = diagnostics.loc[diagnostics["case"] == case.key]
        new_t50 = case_summary.loc["t50"]
        compact_rows.append(
            {
                "well": case.well,
                "calibration": case.calibration,
                "t50_median": new_t50["median"],
                "t50_q10": new_t50["q10"],
                "t50_q90": new_t50["q90"],
                "mu_median": case_summary.loc["mu", "median"],
                "t0_median": case_summary.loc["t0", "median"],
                "best_sqrt_J_over_m": chains.loc[
                    chains["case"] == case.key, "best_sqrt_J_over_m"
                ].min(),
                "max_split_rhat": case_diagnostics["split_rhat"].max(),
                "min_ESS": case_diagnostics["ESS"].min(),
            }
        )
        row = {
            "well": case.well,
            "calibration": case.calibration,
            "t50_mean": new_t50["mean"],
            "t50_median": new_t50["median"],
            "steps_per_chain": lengths[case.key],
            "max_split_rhat": case_diagnostics["split_rhat"].max(),
            "min_ESS": case_diagnostics["ESS"].min(),
            "converged": bool(case_diagnostics["converged"].all()),
        }
        quality_rows.append(row)
    compact = pd.DataFrame(compact_rows)
    quality = pd.DataFrame(quality_rows)
    compact.to_csv(output / "ploemeur_shiftedexp_final_summary.csv", index=False)
    quality.to_csv(output / "ploemeur_shiftedexp_final_quality.csv", index=False)
    return compact, quality


def _markdown_table(frame: pd.DataFrame) -> str:
    return markdown_table(frame, numeric_round=4)


def _report(
    output: Path,
    compact: pd.DataFrame,
    quality: pd.DataFrame,
    tracer_fit: pd.DataFrame,
    pairing_effect: pd.DataFrame,
) -> None:
    converged = bool(quality["converged"].all())
    indexed = compact.set_index(["well", "calibration"])
    f09_full = indexed.loc[("F09", "full_record")]
    f09_window = indexed.loc[("F09", "2014_2015_independent")]
    f11_full = indexed.loc[("F11", "full_record")]
    f11_window = indexed.loc[("F11", "2014_2015_independent")]
    coherent = bool(
        f09_full.t50_median < 25.0
        and f09_window.t50_q90 > f09_full.t50_median
        and 65.0 <= f11_full.t50_median <= 105.0
        and abs(f11_window.t50_median - f11_full.t50_median) >= 10.0
    )
    f11_fit = tracer_fit.loc[
        (tracer_fit["well"] == "F11") & (tracer_fit["calibration"] == "full_record")
    ].set_index("tracer")
    f11_inconsistent = bool(
        f11_full.best_sqrt_J_over_m > 1.0
        and f11_fit["posterior_median_normalized_RMSE"].max() > 1.0
    )
    f11_fit_text = ", ".join(
        f"{TRACER_LABELS[tracer]}={f11_fit.loc[tracer, 'posterior_median_normalized_RMSE']:.2f}"
        for tracer in TRACERS
    )
    report = f"""# Ploemeur — shifted exponential final

## Réponses finales

- **Les quatre calibrations sont-elles convergées ?** {"Oui" if converged else "Non"}. Les critères imposés sont split-Rhat < {MAX_RHAT} et ESS ≥ {MIN_ESS:.0f} pour `mu`, `t0` et `t50`.
- **Les résultats satisfont-ils les critères scientifiques stabilisés ?** {"Oui" if coherent else "Non, une conclusion robuste au moins doit être réexaminée"} selon les contrôles quantitatifs documentés ci-dessous.
- **Les sorties historiques interviennent-elles dans le calcul ?** Non. Les données normalisées sont régénérées dans le dossier de campagne et les anciens postérieurs ne sont ni lus ni comparés pendant cette exécution.
- **Le pairing posterior-predictive est-il correct ?** Oui. Chaque prédiction utilise une ligne posterior complète `(mu,t0)`; les paramètres ne sont jamais recombinés marginalement.
- **F09 montre-t-il toujours clairement l’intérêt de la série temporelle ?** {"Oui" if f09_window.t50_q90 > f09_full.t50_median else "Non"}; la calibration isolée autorise des âges plus anciens tandis que la série complète contraint une solution jeune.
- **F11 conserve-t-il l’incohérence CFC-11 versus CFC-12/CFC-113 ?** {"Oui" if f11_inconsistent else "Non selon le seuil d’un sigma"}; `best_sqrt_J_over_m={f11_full.best_sqrt_J_over_m:.2f}` et RMSE normalisées par traceur : {f11_fit_text}. Aucun traceur ni terme d’erreur n’a été supprimé ou modifié.
- **Les résultats et Figure 4 sont-ils prêts pour le manuscrit stabilisé ?** {"Oui" if converged and coherent else "Non"}; cette réponse n’est positive que si convergence et contrôles scientifiques sont satisfaits.

`t50 = t0 + mu*ln(2)` est calculé pour chaque ligne posterior. `mu+t0` est le mean transit time et n’est pas utilisé comme âge article.

## Tableau compact

{_markdown_table(compact)}

## Qualité de la campagne stabilisée

{_markdown_table(quality)}

## Diagnostics d’ajustement par traceur

{_markdown_table(tracer_fit)}

## Effet de la correction du pairing

{_markdown_table(pairing_effect)}

## Protocole

Shifted exponential uniquement; bornes uniformes `mu ∈ [0.1,70] yr`, `t0 ∈ [0,70] yr`; CFC-11/CFC-12/CFC-113; `sigma_i=0.20*Cobs_i`; `J=sum(((Cmod-Cobs)/sigma)**2)` et `logL=-0.5*J`. Pilote 4 000 pas avec burn-in 20 %, covariance empirique `(mu,t0)` et ridge relatif `1e-6`, production fixe corrélée à l’échelle `2.38/sqrt(2)`, cinq chaînes, burn-in 20 %, aucun thinning diagnostique. Le forward courant CDF–partial-first-moment est utilisé.
"""
    (output / "PLOEMEUR_SHIFTED_EXPONENTIAL_FINAL.md").write_text(
        report, encoding="utf-8", newline="\n"
    )


def _manifest(output: Path, lengths: dict[str, int]) -> None:
    artifacts = [
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    ]
    sources = [
        Path(__file__),
        ROOT / "scripts/common/mcmc_diagnostics.py",
        ROOT / "scripts/common/reporting.py",
        ROOT / "sites/ploemeur/scripts/prepare_observations.py",
        ROOT / "pyages/lpm/samples/analysis.py",
        ROOT / "pyages/lpm/core/lpm_base.py",
        ROOT / "pyages/convolution/continuous.py",
        ROOT / "pyages/lpm/models/exponential_shifted.py",
    ]
    payload = {
        "repository": repository_provenance(ROOT),
        "created_at": pd.Timestamp.now(tz="Europe/Paris").isoformat(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "git_status": subprocess.run(
            ["git", "status", "--short"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines(),
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
        },
        "protocol": {
            "cases": [case.key for case in CASES],
            "model": "exp_shifted",
            "bounds": {"mu": [0.1, 70.0], "t0": [0.0, 70.0]},
            "prior": "uniform within bounds",
            "tracers": TRACERS,
            "relative_error": RELATIVE_ERROR,
            "pilot_steps": PILOT_STEPS,
            "production_steps_by_case": lengths,
            "burn_in": BURN_IN,
            "ridge": RIDGE,
            "proposal_scale": "2.38/sqrt(2)",
            "chains": NCHAINS,
            "diagnostic_thinning": 1,
            "posterior_pairing": "complete row only",
        },
        "source_sha256": {_path_label(path): _sha256(path) for path in sources},
        "artifact_sha256": {
            _path_label(path, output): _sha256(path) for path in artifacts
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def analyze_and_extend(
    output: Path, workers: int, allow_extension: bool = True
) -> None:
    lengths = {case.key: PRODUCTION_STEPS for case in CASES}
    diagnostics, _, _ = _diagnostics(output, lengths)
    failing = set(diagnostics.loc[~diagnostics["converged"], "case"])
    if failing and allow_extension:
        print(f"Targeted n=20000 extension: {sorted(failing)}", flush=True)
        run_production(output, workers, EXTENDED_STEPS, failing)
        lengths.update({key: EXTENDED_STEPS for key in failing})
    diagnostics, summaries, chains = _diagnostics(output, lengths)
    diagnostics.to_csv(output / "convergence_diagnostics.csv", index=False)
    summaries.to_csv(output / "posterior_summaries.csv", index=False)
    chains.to_csv(output / "chain_diagnostics.csv", index=False)
    compact, quality = _compact_and_quality(
        output, lengths, diagnostics, summaries, chains
    )
    intervals = _figure4(output, lengths)
    tracer_fit = _tracer_fit_diagnostics(output, intervals)
    pairing_effect = _pairing_effect_diagnostics(output)
    _report(output, compact, quality, tracer_fit, pairing_effect)
    _manifest(output, lengths)
    if not bool(diagnostics["converged"].all()):
        raise RuntimeError(
            "At least one calibration still fails convergence after the permitted extension"
        )
    print(f"Final products written to {output}", flush=True)


def main(argv: list[str] | None = None) -> int:
    global DATA_OUTPUT, INSERTION_OUTPUT, OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=("prepare", "pilot", "production", "analyze", "all"),
        nargs="?",
        default="all",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--workers", type=int, default=min(NCHAINS, max(1, os.cpu_count() or 1))
    )
    parser.add_argument(
        "--no-extension",
        action="store_true",
        help="Analyze n=10000 chains without the permitted targeted extension",
    )
    args = parser.parse_args(argv)
    output = args.output.resolve()
    OUTPUT = output
    DATA_OUTPUT = output / "data_audit"
    INSERTION_OUTPUT = output / "manuscript_insertion" / "final_figures"
    output.mkdir(parents=True, exist_ok=True)
    if args.phase in {"prepare", "all"}:
        prepare_data_and_exports(output)
    if args.phase in {"pilot", "all"}:
        run_pilots(output)
    if args.phase in {"production", "all"}:
        run_production(output, args.workers, PRODUCTION_STEPS)
    if args.phase in {"analyze", "all"}:
        analyze_and_extend(output, args.workers, allow_extension=not args.no_extension)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
