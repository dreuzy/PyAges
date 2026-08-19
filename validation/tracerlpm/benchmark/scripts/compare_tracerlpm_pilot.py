"""Archive and compare the PFM constant pilot across reference, PyAge and TracerLPM."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

from pyage.convolution.convolution import Convolution
from pyage.lpm.lpm_build import lpm_build

from .compare_pyage import load_tracer
from .generate_inputs import BENCHMARK_ROOT
from .mappings import dm_to_inverse_gaussian, epm_to_shifted_exponential
from .reference import forward


RAW_DIR = BENCHMARK_ROOT / "tracerlpm_exports_raw"
OUTPUT_DIR = BENCHMARK_ROOT / "generated" / "tracerlpm_pilot"


def sample_decimal_year(sample: str) -> float:
    date_text = sample.rsplit("-", 1)[-1]
    date = datetime.strptime(date_text, "%d/%m/%Y")
    start = datetime(date.year, 1, 1)
    end = datetime(date.year + 1, 1, 1)
    return date.year + (date - start).total_seconds() / (end - start).total_seconds()


def compare(run_json: Path) -> dict:
    run = json.loads(run_json.read_text(encoding="utf-8-sig"))
    if run["model1"] != run["model2"] or run["model1"] not in {"PFM", "EMM", "EPM", "DM"}:
        raise ValueError("Le comparateur pilote accepte PFM, EMM, EPM ou DM par paires identiques")
    input_path = Path(run["inputHistoryPath"])
    if not input_path.is_file():
        raise FileNotFoundError(input_path)
    import hashlib
    if hashlib.sha256(input_path.read_bytes()).hexdigest().upper() != run["inputHistorySha256"]:
        raise ValueError("Hash de chronique inattendu")
    if run["model1Points"] != run["model2Points"]:
        raise ValueError("Les deux emplacements PFM ne sont pas répétables")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    archived_json = RAW_DIR / f"{run['runId']}.json"
    shutil.copy2(run_json, archived_json)
    series_source = run_json.with_name(run_json.stem + "-series.csv")
    if series_source.exists():
        shutil.copy2(series_source, RAW_DIR / series_source.name)

    input_data = np.genfromtxt(input_path, delimiter=",", names=True)
    years = np.asarray(input_data["date"])
    values = np.asarray(input_data["concentration"])
    observation_year = float(run.get("observationYear") or sample_decimal_year(run["sample"]))
    effective_year = float(run.get("tracerlpmEffectiveObservationYear") or observation_year)
    tracer = load_tracer(input_path)
    model = run["model1"]
    lpm = lpm_build({"PFM": "dirac", "EMM": "exp", "EPM": "exp_shifted", "DM": "ig"}[model])
    model_parameter = run.get("modelParameter")
    if model == "EPM" and model_parameter is None:
        raise ValueError("Le ratio EPM TracerLPM est absent du rapport EPM")
    if model == "DM" and model_parameter is None:
        raise ValueError("Le paramètre de dispersion DP est absent du rapport DM")
    epm_eta = 1.0 + float(model_parameter) if model == "EPM" else None

    def input_function(year):
        return np.interp(year, years, values, left=0.0, right=values[-1])

    rows = []
    for age, point in zip(run["modelAges"], run["model1Points"]):
        parameters = {"tau": float(age)}
        if model == "EPM":
            parameters["eta"] = epm_eta
        elif model == "DM":
            parameters["DP"] = float(model_parameter)
        reference = forward(
            model, parameters, observation_year, input_function,
            observation_year - years[0], observation_year - years,
        )[0]
        effective_reference = forward(
            model, parameters, effective_year, input_function,
            effective_year - years[0], effective_year - years,
        )[0]
        if model == "EPM":
            mapped = epm_to_shifted_exponential(float(age), epm_eta)
            lpm.p.update({"mu": mapped.mu, "shift": mapped.shift})
        elif model == "DM":
            mapped = dm_to_inverse_gaussian(float(age), float(model_parameter))
            lpm.p.update({"mu": mapped.mu, "sigma": mapped.sigma})
        else:
            lpm.p["mu"] = float(age)
        pyage = float(Convolution(tracer, date=observation_year).convolve(lpm))
        for axis in ("x", "y"):
            tracer_lpm = float(point[axis])
            rows.append({
                "age": float(age), "axis": axis, "reference": reference,
                "effective_date_reference": effective_reference,
                "pyage": pyage, "tracerlpm": tracer_lpm,
                "pyage_minus_reference": pyage - reference,
                "tracerlpm_minus_reference": tracer_lpm - reference,
                "tracerlpm_minus_effective_date_reference": tracer_lpm - effective_reference,
                "tracerlpm_minus_pyage": tracer_lpm - pyage,
            })

    case_output_dir = OUTPUT_DIR / run["caseId"]
    case_output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = case_output_dir / "triple_comparison.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    metrics = {
        "case_id": run["caseId"],
        "run_id": run["runId"],
        "observation_year": observation_year,
        "tracerlpm_effective_observation_year": effective_year,
        "model": model,
        "model_parameter": model_parameter,
        "pyage_eta": epm_eta,
        "age_count": len(run["modelAges"]),
        "comparison_row_count": len(rows),
        "model_slots_identical": True,
        "maximum_absolute_pyage_minus_reference": max(abs(row["pyage_minus_reference"]) for row in rows),
        "maximum_absolute_tracerlpm_minus_reference": max(abs(row["tracerlpm_minus_reference"]) for row in rows),
        "maximum_absolute_tracerlpm_minus_effective_date_reference": max(
            abs(row["tracerlpm_minus_effective_date_reference"]) for row in rows
        ),
        "maximum_absolute_tracerlpm_minus_pyage": max(abs(row["tracerlpm_minus_pyage"]) for row in rows),
        "raw_report": archived_json.relative_to(BENCHMARK_ROOT).as_posix(),
        "input_history": str(input_path),
        "input_history_sha256": run["inputHistorySha256"],
    }
    protocol_taus = {10.0, 40.0} if model in {"EPM", "DM"} else {1.0, 20.0, 80.0}
    protocol_rows = [
        row for row in rows
        if row["axis"] == "x" and row["age"] in protocol_taus
    ]
    metrics["protocol_tau_results"] = [
        {
            "tau": row["age"],
            "reference": row["reference"],
            "effective_date_reference": row["effective_date_reference"],
            "pyage": row["pyage"],
            "tracerlpm": row["tracerlpm"],
            "pyage_minus_reference": row["pyage_minus_reference"],
            "tracerlpm_minus_effective_date_reference": row["tracerlpm_minus_effective_date_reference"],
        }
        for row in protocol_rows
    ]
    if input_path.stem == "ramp":
        slope = (values[-1] - values[0]) / (years[-1] - years[0])
        inferred_years = [
            row["age"] + years[0] + (row["tracerlpm"] - values[0]) / slope
            for row in rows if row["axis"] == "x" and row["tracerlpm"] > values[0]
        ]
        effective_year = float(np.median(inferred_years))
        metrics["inferred_tracerlpm_observation_year"] = effective_year
        metrics["observation_year_discretization"] = effective_year - observation_year
        metrics["interpretation"] = "TracerLPM evaluates the ramp on its internal half-year time grid."
    (case_output_dir / "summary.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8", newline="\n")
    markdown = f"""# Pilote triple {model} — {input_path.stem}

- Exécution TracerLPM : `{run['runId']}`
- Date d’observation décimale : `{observation_year:.12f}`
- Âges comparés : {metrics['age_count']}
- Deux emplacements TracerLPM identiques : oui
- Maximum |PyAge − référence| : `{metrics['maximum_absolute_pyage_minus_reference']:.12g}`
- Maximum |TracerLPM − référence| : `{metrics['maximum_absolute_tracerlpm_minus_reference']:.12g}`
- Maximum |TracerLPM − référence à date effective| : `{metrics['maximum_absolute_tracerlpm_minus_effective_date_reference']:.12g}`
- Maximum |TracerLPM − PyAge| : `{metrics['maximum_absolute_tracerlpm_minus_pyage']:.12g}`

Le passage de 100 à 0 pour les âges très anciens provient explicitement de la
politique `before: 0.0` avant le début de la chronique en 1900.
"""
    if "inferred_tracerlpm_observation_year" in metrics:
        markdown += (
            f"\nPour la rampe, la date effective déduite de tous les points non nuls est "
            f"`{metrics['inferred_tracerlpm_observation_year']:.12f}`. Le décalage "
            f"de `{metrics['observation_year_discretization']:.12f}` an par rapport "
            "à la date demandée provient de la grille semestrielle interne du classeur.\n"
        )
    if metrics["protocol_tau_results"]:
        markdown += "\n## Valeurs du protocole\n\n| Tau | Référence | PyAge | TracerLPM | PyAge − réf. | TracerLPM − réf. date effective |\n|---:|---:|---:|---:|---:|---:|\n"
        for item in metrics["protocol_tau_results"]:
            markdown += (
                f"| {item['tau']:g} | {item['reference']:.9g} | {item['pyage']:.9g} | "
                f"{item['tracerlpm']:.9g} | {item['pyage_minus_reference']:.6g} | "
                f"{item['tracerlpm_minus_effective_date_reference']:.6g} |\n"
            )
    (case_output_dir / "summary.md").write_text(markdown, encoding="utf-8", newline="\n")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-json", type=Path, required=True)
    print(json.dumps(compare(parser.parse_args().run_json), indent=2))
